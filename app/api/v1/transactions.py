from fastapi import APIRouter, Depends, Request, Body, HTTPException
from sqlalchemy.orm import Session

from ...api.deps import get_db
from ...auth import get_current_user
from ...models import User, Account, TransactionHistory
from ...schemas import (
    GenerateQRISRequest, GenerateQRISResponse,
    ConsumeQRISRequest, ConsumeQRISResponse,
    TransactionCorporateInput, FraudDataLegitimate
)
from ...services.qris_service import QRISService
from ...services.transaction_service import TransactionService
from ...services.enhanced_transaction_service import EnhancedTransactionService
from ...services.pin_validation_service import pin_validation_service
from ...services.transaction_validation_service import transaction_validation_service

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
    data: ConsumeQRISRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Consume QRIS code for retail transaction."""
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
            print(f"QRIS Consume - Account details: {user_account.account_number}, Status: {user_account.status}, Balance: {user_account.balance}")
        
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
        qris_data, qris_id = QRISService.validate_and_consume_qris(data, current_user.customer_id, db)
        print(f"QRIS Consume - QRIS validated, ID: {qris_id}")
        
        # Validate transaction (balance, limits, etc.)
        print(f"QRIS Consume - Validating transaction amount: {qris_data['amount']}")
        await transaction_validation_service.validate_transaction(
            user=current_user,
            account=user_account,
            amount=qris_data["amount"],
            transaction_type="qris_consume",
            db=db,
            additional_data={
                "qris_id": qris_id,
                "merchant_name": qris_data["merchant_name"],
                "merchant_category": qris_data["merchant_category"]
            }
        )
        print("QRIS Consume - Transaction validation passed")
        
        # Validate PIN after transaction validation
        await pin_validation_service.validate_pin_or_fail(
            current_user, 
            data.pin, 
            "qris_consume",
            qris_data["amount"],
            {"account_number": user_account.account_number, "qris_id": qris_id, "merchant_name": qris_data["merchant_name"]}
        )
        
        # Update account balance and create transaction history
        balance_before = user_account.balance
        user_account.balance -= qris_data["amount"]
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
        
        await EnhancedTransactionService.send_transaction_to_kafka(transaction_data)
        
        return ConsumeQRISResponse(
            qris_id=qris_id,
            status="SUCCESS",
            message=f"Payment of {qris_data['amount']} {qris_data['currency']} to {qris_data['merchant_name']} completed from account {user_account.account_number}."
        )
    
    except HTTPException as e:
        # Re-raise HTTPExceptions as they are already properly formatted
        raise e
    except Exception as e:
        # Catch any other unexpected errors and provide detailed info
        raise HTTPException(
            status_code=500, 
            detail={
                "error": "Failed to consume QRIS", 
                "message": str(e),
                "error_type": type(e).__name__
            }
        )


@router.post("/corporate")
async def create_corporate_transaction(
    request: Request,
    tx: TransactionCorporateInput = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Process corporate transaction."""
    try:
        # Get user's account for the specified account number
        user_account = db.query(Account).filter(
            Account.user_id == current_user.id,
            Account.account_number == tx.account_number,
            Account.status == "active"
        ).first()
        
        if not user_account:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Account not found",
                    "message": f"Active account {tx.account_number} not found for current user"
                }
            )
        
        # Validate transaction (balance, limits, etc.)
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
        
        # Validate PIN after transaction validation
        await pin_validation_service.validate_pin_or_fail(
            current_user, 
            tx.pin, 
            "corporate_transaction",
            tx.amount,
            {
                "account_number": tx.account_number, 
                "transaction_type": tx.transaction_type,
                "merchant_name": tx.merchant_name
            }
        )
        
        tx_dict = tx.model_dump()
        
        transaction_data = await EnhancedTransactionService.create_enhanced_corporate_transaction_data(
            tx_dict, current_user.customer_id, dict(request.headers), request.client.host
        )
        
        await EnhancedTransactionService.send_transaction_to_kafka(transaction_data)
        
        return {"status": "success", "transaction": transaction_data}
    
    except HTTPException as e:
        # Re-raise HTTPExceptions as they are already properly formatted
        raise e
    except Exception as e:
        # Catch any other unexpected errors and provide detailed info
        raise HTTPException(
            status_code=500, 
            detail={
                "error": "Failed to process corporate transaction", 
                "message": str(e),
                "error_type": type(e).__name__
            }
        )


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