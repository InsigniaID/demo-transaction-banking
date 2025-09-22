from decimal import Decimal
import random
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request, Body, HTTPException
from sqlalchemy.orm import Session

from ...api.deps import get_db
from ...auth import get_current_user
from ...kafka_producer import send_transaction
from ...models import User, Account, TransactionHistory
from ...schemas import (
    GenerateQRISRequest, GenerateQRISResponse,
    ConsumeQRISRequest, ConsumeQRISResponse,
    TransactionCorporateInput, FraudDataLegitimate, DetectionResult, StandardKafkaEvent
)
from ...services import transaction_recording_service
from ...services.qris_service import QRISService
from ...services.transaction_recording_service import TransactionRecordingService
from ...services.transaction_service import TransactionService
from ...services.enhanced_transaction_service import EnhancedTransactionService
from ...services.pin_validation_service import pin_validation_service
from ...services.transaction_validation_service import transaction_validation_service, TransactionValidationService


router = APIRouter()


@router.get("/limits")
def get_transaction_limits():
    """Get current transaction limits and rules."""
    return {
        "limits": transaction_validation_service.get_transaction_limits(),
        "rules": {
            "balance_check": "Transaction amount must not exceed account balance",
            "minimum_amount": "Minimum transaction amount is Rp 1,000",
            "maximum_amount": "Maximum transaction amount per transaction is Rp 10,000,000", 
            "daily_limit": "Maximum total transactions per day is Rp 20,000,000",
            "account_status": "Account must be active to process transactions"
        },
        "validation_order": [
            "account_status",
            "minimum_amount", 
            "maximum_amount",
            "balance_check",
            "daily_limit_check"
        ]
    }


@router.post("/retail/qris-generate", response_model=GenerateQRISResponse)
async def create_retail_transaction_gen(
    data: GenerateQRISRequest = Body(...),
    current_user: User = Depends(get_current_user)
):
    """Generate QRIS code for retail transaction."""
    try:
        # Generate QRIS without PIN validation (per user request)
        return QRISService.generate_qris(data, current_user.customer_id)
    
    except HTTPException as e:
        # Re-raise HTTPExceptions as they are already properly formatted
        raise e
    except Exception as e:
        # Catch any other unexpected errors and provide detailed info
        raise HTTPException(
            status_code=500, 
            detail={
                "error": "Failed to generate QRIS",
                "message": str(e),
                "error_type": type(e).__name__
            }
        )


@router.post("/retail/qris-consume", response_model=ConsumeQRISResponse)
async def create_retail_transaction_consume(
        request: Request,
        data: ConsumeQRISRequest = Body(...),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Consume QRIS code for retail transaction with proper transaction recording."""
    try:
        print(f"QRIS Consume - User: {current_user.username}, Customer ID: {current_user.customer_id}")
        print(f"QRIS Consume - Request data: qris_code={data.qris_code[:20]}..., pin=***")

        # Get user's default account (first active account)
        print(f"QRIS Consume - Looking for accounts for user ID: {current_user.id}")

        all_user_accounts = db.query(Account).filter(Account.user_id == current_user.id).all()
        print(f"QRIS Consume - All user accounts: {[acc.account_number for acc in all_user_accounts]}")

        user_account = db.query(Account).filter(
            Account.user_id == current_user.id,
            Account.status == "active"
        ).first()

        print(f"QRIS Consume - Active account found: {user_account.account_number if user_account else 'None'}")
        if user_account:
            print(
                f"QRIS Consume - Account details: {user_account.account_number}, Status: {user_account.status}, Balance: {user_account.balance}")

        if not user_account:
            print("QRIS Consume - No active account found")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "No active account found",
                    "message": "User does not have any active accounts to process payment."
                }
            )

        print(f"QRIS Consume - Validating QRIS...")
        qris_data, qris_id = await QRISService.validate_and_consume_qris(
            data,
            current_user.customer_id,
            db,
            request_headers=dict(request.headers),
            client_host=request.client.host if request.client else "unknown"
        )
        print("========", qris_data, qris_id)
        print(f"QRIS Consume - QRIS validated, ID: {qris_id}")

        # Prepare additional data for validation and recording
        additional_data = {
            "qris_id": qris_id,
            "merchant_name": qris_data["merchant_name"],
            "merchant_category": qris_data["merchant_category"],
            "reference_number": qris_id,
            "recipient_name": qris_data["merchant_name"]
        }

        # Validate transaction (balance, limits, etc.)
        print(f"QRIS Consume - Validating transaction amount: {qris_data['amount']}")
        await transaction_validation_service.validate_transaction(
            user=current_user,
            account=user_account,
            amount=qris_data["amount"],
            transaction_type="qris_consume",
            db=db,
            additional_data=additional_data
        )
        print("QRIS Consume - Transaction validation passed")

        # Validate PIN after transaction validation
        await pin_validation_service.validate_pin_or_fail(
            current_user,
            data.pin,
            data.crash_type,
            "qris_consume",
            qris_data["amount"],
            {"account_number": user_account.account_number, "qris_id": qris_id,
             "merchant_name": qris_data["merchant_name"]}
        )

        # Update account balance and create transaction history
        balance_before = user_account.balance
        amount_decimal = Decimal(str(qris_data["amount"]))
        user_account.balance -= amount_decimal
        balance_after = user_account.balance

        # Create transaction history record
        transaction_history = TransactionHistory(
            user_id=current_user.id,
            account_id=user_account.id,
            transaction_id=qris_id,
            transaction_type="qris_consume",
            amount=qris_data["amount"],
            currency=qris_data["currency"],
            balance_before=balance_before,
            balance_after=balance_after,
            status="success",
            description=f"QRIS payment to {qris_data['merchant_name']}",
            reference_number=qris_id,
            recipient_account=None,
            recipient_name=qris_data["merchant_name"],
            channel="mobile_app"
        )

        db.add(transaction_history)
        db.commit()
        db.refresh(user_account)
        db.refresh(transaction_history)

        transaction_data = await EnhancedTransactionService.create_enhanced_retail_transaction_data(
            qris_data, current_user.customer_id, user_account.account_number
        )

        # Add transaction_id from our database record
        transaction_data["db_transaction_id"] = qris_id
        transaction_data["balance_after"] = balance_after
        transaction_data["qris_status"] = "CONSUMED"

        extra_fields = {
            "login_status": "success",
            "alert_type": "",
            "alert_severity": "",
            "failed_attempts": "",
            "time_window_minutes": "",
            "login_attempts": "",
            "attempted_amount": "",
            "attempted_transaction_type": "",
            "attempted_channel": "",
            "attempted_account_number": "",
            "attempted_recipient_account": "",
            "attempted_merchant_name": "",
            "attempted_merchant_category": "",
            "auth_timestamp": "",
            "error_type": data.crash_type,
            "error_code": "",
            "error_detail": "",
            "validation_stage": "",
            "transaction_description": "",
            "recipient_account_number": "",
            "recipient_account_name": "",
            "recipient_bank_code": "",
            "reference_number": "",
            "risk_assessment_score": "",
            "fraud_indicator": "",
            "aml_screening_result": "",
            "sanction_screening_result": "",
            "compliance_status": "",
            "settlement_status": "",
            "clearing_code": "",
            "requested_amount": "",
            "failure_reason": "",
            "failure_message": "",
            "limits": ""
        }

        for k, v in extra_fields.items():
            transaction_data.setdefault(k, v)

        # Send to Kafka for additional processing (notifications, analytics, etc.)
        await EnhancedTransactionService.send_transaction_to_kafka(transaction_data)
        print("QRIS Consume - Transaction sent to Kafka")

        return ConsumeQRISResponse(
            qris_id=qris_id,
            status="SUCCESS",
            message=f"Payment of {qris_data['amount']} {qris_data['currency']} to {qris_data['merchant_name']} completed from account {user_account.account_number}.",
            transaction_id=qris_id,  # Return our transaction ID
            balance_after=balance_after
        )

    except HTTPException as e:
        # Record failed transaction for audit (don't raise if this fails)
        try:
            if 'user_account' in locals() and 'qris_data' in locals():
                await TransactionRecordingService.record_failed_transaction(
                    user=current_user,
                    account=user_account,
                    amount=qris_data["amount"],
                    transaction_type="qris_consume",
                    failure_reason=str(e.detail),
                    db=db,
                    additional_data=additional_data if 'additional_data' in locals() else {}
                )
                db.commit()  # Commit the failed transaction record
        except Exception as record_error:
            print(f"Failed to record failed transaction: {record_error}")

        # Re-raise the original HTTPException
        raise e
    except Exception as e:
        # Record failed transaction for unexpected errors
        try:
            if 'user_account' in locals():
                amount = qris_data["amount"] if 'qris_data' in locals() else Decimal("0")
                await TransactionRecordingService.record_failed_transaction(
                    user=current_user,
                    account=user_account,
                    amount=amount,
                    transaction_type="qris_consume",
                    failure_reason=f"System error: {str(e)}",
                    db=db,
                    additional_data=additional_data if 'additional_data' in locals() else {}
                )
                db.commit()
        except Exception as record_error:
            print(f"Failed to record failed transaction: {record_error}")

        # Catch any other unexpected errors and provide detailed info
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to consume QRIS",
                "message": str(e),
                "error_type": type(e).__name__
            }
        )


@router.post("/qris/scan")
async def scan_qris(request: Request,
                    current_user: User = Depends(get_current_user)):
    await TransactionService.error_qris_scan(request, current_user)

    return {"status": "error", "message": "error_scan_qris"}


@router.post("/corporate")
async def create_corporate_transaction(
        request: Request,
        tx: TransactionCorporateInput = Body(...),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Process corporate transaction."""
    validation_stage = None

    try:
        # Stage 1: Account validation
        validation_stage = "account_validation"
        user_account = db.query(Account).filter(Account.user_id == current_user.id,
                                                Account.account_number == tx.account_number,
                                                Account.status == "active").first()

        if not user_account:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Account not found",
                    "message": f"Active account {tx.account_number} not found for current user"
                }
            )

        # Stage 1.5: Recipient account validation
        validation_stage = "recipient_account_validation"
        recipient_account = db.query(Account).filter(Account.account_number == tx.recipient_account_number,
                                                     Account.status == "active").first()

        if not recipient_account:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Recipient account not found",
                    "message": f"Active recipient account {tx.recipient_account_number} not found"
                }
            )

        # Prevent self-transfer
        if user_account.account_number == recipient_account.account_number:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Invalid transfer",
                    "message": "Cannot transfer to the same account"
                }
            )

        # Stage 2: Transaction validation
        validation_stage = "transaction_validation"
        await transaction_validation_service.validate_transaction(
            user=current_user,
            account=user_account,
            amount=tx.amount,
            transaction_type=tx.transaction_type,
            db=db,
            additional_data={
                "merchant_name": tx.merchant_name,
                "merchant_category": tx.merchant_category,
                "channel": tx.channel,
                "recipient_account": tx.recipient_account_number
            }
        )

        # Stage 2.5: Fraud detection for large transfers
        if tx.transaction_type == "transfer" and tx.amount >= 100000000:
            # Check for recent large transfers in the last 10 minutes
            ten_minutes_ago = datetime.utcnow() - timedelta(minutes=10)
            recent_large_transfers = db.query(TransactionHistory).filter(
                TransactionHistory.user_id == current_user.id,
                TransactionHistory.transaction_type == "transfer_out",
                TransactionHistory.amount >= 100000000,
                TransactionHistory.created_at >= ten_minutes_ago,
                TransactionHistory.status == "success"
            ).all()

            # If more than 3 large transfers in 10 minutes, send fraud alert to Kafka
            if len(recent_large_transfers) >= 3:
                print(f"FRAUD ALERT: User {current_user.customer_id} has made {len(recent_large_transfers) + 1} large transfers (>100M) within 10 minutes")

                # Create fraud detection log data
                fraud_data = await EnhancedTransactionService.create_error_transaction_data(
                    error_type="fraud_alert_large_transfers",
                    error_code=200,  # Not an error, just an alert
                    error_detail={
                        "message": f"User has made {len(recent_large_transfers) + 1} transfers greater than 100,000,000 within 10 minutes",
                        "current_transfer_amount": tx.amount,
                        "recent_transfers_count": len(recent_large_transfers),
                        "recent_transfer_amounts": [float(t.amount) for t in recent_large_transfers],
                        "time_window_minutes": 10,
                        "threshold_amount": 100000000,
                        "recipient_account": tx.recipient_account_number,
                        "alert_severity": "HIGH"
                    },
                    transaction_input=tx.model_dump(),
                    customer_id=current_user.customer_id,
                    request_headers=dict(request.headers),
                    client_host=request.client.host if request.client else "unknown",
                    validation_stage="fraud_detection"
                )

                # Override some fields for fraud alert
                fraud_data["log_type"] = "fraud_alert"
                fraud_data["alert_type"] = "multiple_large_transfers"
                fraud_data["alert_severity"] = "HIGH"
                fraud_data["risk_assessment_score"] = 0.95
                fraud_data["fraud_indicator"] = True

                # Send fraud alert to Kafka
                await EnhancedTransactionService.send_error_to_kafka(fraud_data)

        # Stage 3: PIN validation
        validation_stage = "pin_validation"
        await pin_validation_service.validate_pin_or_fail(
            current_user,
            tx.pin,
            tx.crash_type,
            "corporate_transaction",
            tx.amount,
            {
                "account_number": tx.account_number,
                "transaction_type": tx.transaction_type,
                "merchant_name": tx.merchant_name
            }
        )

        client_host = request.client.host
        amount_decimal = Decimal(str(tx.amount))

        # Store balances before transaction
        sender_balance_before = user_account.balance

        # Stage 4: Balance updates
        validation_stage = "balance_update"

        # Update sender balance (debit)
        user_account.balance -= amount_decimal
        sender_balance_after = user_account.balance

        # Update recipient balance (credit)
        recipient_account.balance += amount_decimal

        # Stage 5: Transaction processing
        validation_stage = "transaction_processing"
        error_type = tx.crash_type
        tx_dict = tx.model_dump()

        transaction_data = await EnhancedTransactionService.create_enhanced_corporate_transaction_data(
            tx_dict, current_user.customer_id, dict(request.headers), request.client.host
        )
        transaction_service_data = await TransactionService.create_corporate_transaction_data(
            transaction_data=transaction_data,
            customer_id=str(current_user.customer_id),
            request_headers=dict(request.headers),
            client_host=client_host
        )

        # Create transaction history record for SENDER
        transaction_history = TransactionHistory(
            user_id=current_user.id,
            account_id=user_account.id,
            transaction_id=transaction_service_data["transaction_id"],
            transaction_type="transfer_out",
            amount=amount_decimal,
            currency=tx.currency,
            balance_before=Decimal(str(sender_balance_before)),
            balance_after=Decimal(str(sender_balance_after)),
            status="success",
            description=tx.transaction_description,
            reference_number=tx.reference_number,
            recipient_account=tx.recipient_account_number,
            recipient_name=tx.recipient_account_name,
            channel="mobile_app"
        )

        # Add both transaction histories
        db.add(transaction_history)

        # Commit all changes together
        db.commit()

        # Refresh all objects
        db.refresh(user_account)
        db.refresh(recipient_account)
        db.refresh(transaction_history)

        extra_fields = {
            "customer_age": "",
            "customer_gender": "",
            "customer_occupation": "",
            "customer_income_bracket": "",
            "customer_education": "",
            "customer_marital_status": "",
            "customer_monthly_income": "",
            "customer_credit_limit": "",
            "customer_risk_score": "",
            "customer_kyc_level": "",
            "customer_pep_status": "",
            "customer_previous_fraud_incidents": "",
            "device_fingerprint": "",
            "qris_id": "",
            "transaction_reference": "",
            "interchange_fee": "",
            "db_transaction_id": "",
            "balance_after": "",
            "qris_status": ""
        }

        for k, v in extra_fields.items():
            transaction_data.setdefault(k, v)

        print("====create_corporate_transaction\n", transaction_data)
        await EnhancedTransactionService.send_transaction_to_kafka(transaction_data)

        return {"status": "success", "transaction": transaction_data}

    except HTTPException as http_exc:
        # Rollback any database changes
        db.rollback()

        # Send HTTP error to Kafka
        error_data = await EnhancedTransactionService.create_error_transaction_data(
            error_type="http_error",
            error_code=http_exc.status_code,
            error_detail=http_exc.detail,
            transaction_input=tx.model_dump(),
            customer_id=current_user.customer_id,
            request_headers=dict(request.headers),
            client_host=request.client.host,
            validation_stage=validation_stage
        )

        cities = [
            {"country": "Indonesia", "city": "Jakarta", "lat": -6.2088, "lon": 106.8456},
            {"country": "Indonesia", "city": "Bandung", "lat": -6.9175, "lon": 107.6191},
            {"country": "Indonesia", "city": "Surabaya", "lat": -7.2575, "lon": 112.7521},
            {"country": "Indonesia", "city": "Medan", "lat": 3.5952, "lon": 98.6722},
            {"country": "Indonesia", "city": "Denpasar", "lat": -8.65, "lon": 115.2167},
            {"country": "Indonesia", "city": "Makassar", "lat": -5.1477, "lon": 119.4327},
        ]

        geo_info = random.choice(cities)

        extra_fields = {
            "account_number": "",
            "amount": "",
            "channel": "",
            "branch_code": "string",
            "province": "string",
            "city": "string",
            "merchant_name": "string",
            "merchant_category": "string",
            "merchant_id": "string",
            "terminal_id": "string",
            "latitude": geo_info["lat"],
            "longitude": geo_info["lon"],
            "device_id": "",
            "device_type": "",
            "device_os": "",
            "device_browser": "",
            "device_is_trusted": "",
            "ip_address": "",
            "user_agent": "",
            "session_id": "",
            "customer_age": "",
            "customer_gender": "",
            "customer_occupation": "",
            "customer_income_bracket": "",
            "customer_education": "",
            "customer_marital_status": "",
            "customer_monthly_income": "",
            "customer_credit_limit": "",
            "customer_risk_score": "",
            "customer_kyc_level": "",
            "customer_pep_status": "",
            "customer_previous_fraud_incidents": "",
            "device_fingerprint": "",
            "qris_id": "",
            "transaction_reference": "",
            "interchange_fee": "",
            "db_transaction_id": "",
            "balance_after": "",
            "qris_status": ""
        }

        for k, v in extra_fields.items():
            error_data.setdefault(k, v)

        print("====create_corporate_transaction==EXCEPTION==1==\n", error_data)
        await EnhancedTransactionService.send_error_to_kafka(error_data)

        # Re-raise the original exception
        raise http_exc

    except Exception as exc:
        # Rollback any database changes
        db.rollback()

        # Send system error to Kafka
        error_data = await EnhancedTransactionService.create_error_transaction_data(
            error_type="system_error",
            error_code=500,
            error_detail={
                "error": "Failed to process corporate transaction",
                "message": str(exc),
                "error_type": type(exc).__name__
            },
            transaction_input=tx.model_dump(),
            customer_id=current_user.customer_id,
            request_headers=dict(request.headers),
            client_host=request.client.host,
            validation_stage=validation_stage
        )
        print("====create_corporate_transaction==EXCEPTION==2==\n", error_data)
        await EnhancedTransactionService.send_error_to_kafka(error_data)

        # Raise HTTP exception for client
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to process corporate transaction",
                "message": str(exc),
                "error_type": type(exc).__name__
            }
        )


@router.post("/anomaly-detection")
async def anomaly_detection(result: DetectionResult):
    def remove_empty_fields(obj):
        if isinstance(obj, dict):
            return {k: remove_empty_fields(v) for k, v in obj.items() if v not in [None, ""]}

        elif isinstance(obj, list):
            return [remove_empty_fields(v) for v in obj if v not in [None, ""]]

        else:
            return obj

    clean_result = remove_empty_fields(result.model_dump())

    try:
        now = datetime.utcnow()
        success_event = StandardKafkaEvent(timestamp=now,
                                           log_type="anomaly_detection",
                                           processing_time_ms=int(datetime.utcnow().timestamp() * 1000) % 1000,
                                           aml_screening_result=json.dumps(clean_result))
        event_data = success_event.model_dump(exclude_none=True)
        event_data['timestamp'] = success_event.timestamp.isoformat() + 'Z'

        await send_transaction(event_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {e}")


@router.post("/velocity-violation")
async def create_velocity_violation(
    tx: FraudDataLegitimate = Body(...),
    current_user: User = Depends(get_current_user)
):
    """Report velocity violation."""
    tx_dict = tx.model_dump(mode="json")
    await TransactionService.send_transaction_to_kafka(tx_dict)
    return {"status": "success", "transaction": tx_dict}


@router.post("/compliance-violation/aml-reporting")
async def create_aml_reporting(
    tx: FraudDataLegitimate = Body(...),
    current_user: User = Depends(get_current_user)
):
    """Report AML compliance violation."""
    tx_dict = tx.model_dump(mode="json")
    await TransactionService.send_transaction_to_kafka(tx_dict)
    return {"status": "success", "transaction": tx_dict}


@router.post("/compliance-violation/kyc-gap")
async def create_kyc_gap(
    tx: FraudDataLegitimate = Body(...),
    current_user: User = Depends(get_current_user)
):
    """Report KYC gap violation."""
    tx_dict = tx.model_dump(mode="json")
    await TransactionService.send_transaction_to_kafka(tx_dict)
    return {"status": "success", "transaction": tx_dict}
