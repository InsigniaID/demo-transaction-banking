"""
Transaction validation service for checking balance, limits, and business rules.
"""
import random
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from fastapi import HTTPException

from ..models import Account, TransactionHistory, User
# from ..kafka_producer import send_transaction
from ..elk_kafka import send_transaction
from ..schemas import StandardKafkaEvent
from ..utils.cities_data import cities


class TransactionLimits:
    """Transaction limits configuration."""
    MIN_TRANSACTION_AMOUNT = Decimal("0.00")  # Rp 1,000
    MAX_TRANSACTION_AMOUNT = Decimal("1000000000000.00")  # Rp 10 juta
    DAILY_TRANSACTION_LIMIT = Decimal("2000000000000.00")  # Rp 20 juta/hari


class TransactionValidationService:
    
    @staticmethod
    async def validate_transaction(
        user: User,
        account: Account,
        amount: Decimal,
        transaction_type: str,
        db: Session,
        additional_data: Dict[str, Any] = None
    ) -> None:
        """
        Comprehensive transaction validation including:
        - Balance check
        - Amount limits (min/max per transaction)
        - Daily limit check
        - Business rules validation
        
        Raises HTTPException if validation fails and sends alerts to Kafka.
        """
        amount = Decimal(str(amount))
        additional_data = additional_data or {}
        
        # 1. Balance validation
        if amount > account.balance:
            await TransactionValidationService._send_validation_failure(
                user, account, amount, transaction_type, 
                "insufficient_balance",
                f"Insufficient balance. Available: {account.balance}, Required: {amount}",
                additional_data
            )

            geo_info = random.choice(cities)
            event_data = StandardKafkaEvent(timestamp=datetime.utcnow(),
                                            log_type=f"{transaction_type}_error",
                                            login_status="success",
                                            customer_id=user.customer_id,
                                            auth_method="password",
                                            auth_success=False,
                                            auth_timestamp=datetime.utcnow(),
                                            error_type="insufficient_balance",
                                            error_detail="",
                                            failure_reason="",
                                            failure_message="",
                                            validation_stage="",
                                            attempted_channel="web_api",
                                            ip_address="",
                                            user_agent="",
                                            device_type="web",
                                            device_is_trusted=False,
                                            session_id=f"session_{datetime.utcnow().timestamp()}",
                                            city=geo_info["city"],
                                            province="",
                                            latitude=geo_info["lat"],
                                            longitude=geo_info["lon"],
                                            processing_time_ms=int(datetime.utcnow().timestamp() * 1000) % 1000,
                                            business_date=datetime.utcnow().strftime("%Y-%m-%d"),
                                            status="error",
                                            alert_type="",
                                            alert_severity="high")
            event_data = event_data.model_dump(exclude_none=True)
            event_data['timestamp'] = event_data.timestamp.isoformat() + 'Z'
            event_data['auth_timestamp'] = event_data.auth_timestamp.isoformat() + 'Z'

            await send_transaction(event_data)


            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Insufficient balance",
                    "message": f"Your account balance (Rp {account.balance:,.2f}) is insufficient for this transaction (Rp {amount:,.2f})",
                    "available_balance": float(account.balance),
                    "requested_amount": float(amount)
                }
            )
        
        # 2. Minimum transaction amount
        if amount < TransactionLimits.MIN_TRANSACTION_AMOUNT:
            await TransactionValidationService._send_validation_failure(
                user, account, amount, transaction_type,
                "amount_below_minimum",
                f"Transaction amount {amount} below minimum {TransactionLimits.MIN_TRANSACTION_AMOUNT}",
                additional_data
            )
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Amount below minimum",
                    "message": f"Minimum transaction amount is Rp {TransactionLimits.MIN_TRANSACTION_AMOUNT:,.2f}",
                    "minimum_amount": float(TransactionLimits.MIN_TRANSACTION_AMOUNT),
                    "requested_amount": float(amount)
                }
            )
        
        # 3. Maximum transaction amount
        if amount > TransactionLimits.MAX_TRANSACTION_AMOUNT:
            await TransactionValidationService._send_validation_failure(
                user, account, amount, transaction_type,
                "amount_exceeds_limit",
                f"Transaction amount {amount} exceeds maximum {TransactionLimits.MAX_TRANSACTION_AMOUNT}",
                additional_data
            )
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Amount exceeds transaction limit",
                    "message": f"Maximum transaction amount is Rp {TransactionLimits.MAX_TRANSACTION_AMOUNT:,.2f}",
                    "maximum_amount": float(TransactionLimits.MAX_TRANSACTION_AMOUNT),
                    "requested_amount": float(amount)
                }
            )
        
        # 4. Daily transaction limit
        daily_total = await TransactionValidationService._get_daily_transaction_total(
            user, db
        )
        
        if (daily_total + amount) > TransactionLimits.DAILY_TRANSACTION_LIMIT:
            await TransactionValidationService._send_validation_failure(
                user, account, amount, transaction_type,
                "daily_limit_exceeded",
                f"Daily limit exceeded. Current: {daily_total}, Requested: {amount}, Limit: {TransactionLimits.DAILY_TRANSACTION_LIMIT}",
                additional_data
            )
            remaining_limit = TransactionLimits.DAILY_TRANSACTION_LIMIT - daily_total
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Daily transaction limit exceeded",
                    "message": f"Daily transaction limit (Rp {TransactionLimits.DAILY_TRANSACTION_LIMIT:,.2f}) would be exceeded",
                    "daily_limit": float(TransactionLimits.DAILY_TRANSACTION_LIMIT),
                    "daily_used": float(daily_total),
                    "remaining_limit": float(remaining_limit),
                    "requested_amount": float(amount)
                }
            )
        
        # 5. Account status validation
        if account.status != "active":
            await TransactionValidationService._send_validation_failure(
                user, account, amount, transaction_type,
                "account_inactive",
                f"Account {account.account_number} status is {account.status}",
                additional_data
            )
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Account not active",
                    "message": f"Account {account.account_number} is {account.status} and cannot process transactions",
                    "account_status": account.status
                }
            )
        
        # All validations passed
        await TransactionValidationService._send_validation_success(
            user, account, amount, transaction_type, additional_data
        )
    
    @staticmethod
    async def _get_daily_transaction_total(user: User, db: Session) -> Decimal:
        """Get total transaction amount for current day."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        result = db.query(
            func.coalesce(func.sum(TransactionHistory.amount), 0)
        ).filter(
            and_(
                TransactionHistory.user_id == user.id,
                TransactionHistory.status == "success",
                TransactionHistory.created_at >= today_start,
                TransactionHistory.created_at < today_end
            )
        ).scalar()
        
        return Decimal(str(result or 0))
    
    @staticmethod
    async def _send_validation_failure(
        user: User,
        account: Account,
        amount: Decimal,
        transaction_type: str,
        failure_reason: str,
        failure_message: str,
        additional_data: Dict[str, Any]
    ) -> None:
        """Send transaction validation failure alert to Kafka."""
        alert_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "log_type": "transaction_failure",
            "login_status": "",
            "customer_id": user.customer_id,
            "alert_type": "transaction_validation_failure",
            "alert_severity": "medium",
            "failed_attempts": "",
            "time_window_minutes": "",
            "login_attempts": "",
            "transaction_id": "",
            "customer_segment": "",
            "status": "",
            "processing_time_ms": "",
            "business_date": "",
            "transaction_fee": "",
            "total_amount": "",
            "currency": "",
            "account_balance_before": "",
            "account_balance_after": "",
            "attempted_amount": "",
            "attempted_transaction_type": "",
            "attempted_channel": "",
            "attempted_account_number": account.account_number,
            "attempted_recipient_account": additional_data.get("recipient_account"),
            "attempted_merchant_name": additional_data.get("merchant_name"),
            "attempted_merchant_category": additional_data.get("merchant_category"),
            "auth_method": "",
            "auth_success": "",
            "auth_timestamp": "",
            "error_type": "",
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
            "settlement_date": "",
            "settlement_status": "",
            "clearing_code": "",
            "transaction_type": transaction_type,
            "requested_amount": float(amount),
            "failure_reason": failure_reason,
            "failure_message": failure_message,
            "limits": {
                "min_amount": float(TransactionLimits.MIN_TRANSACTION_AMOUNT),
                "max_amount": float(TransactionLimits.MAX_TRANSACTION_AMOUNT),
                "daily_limit": float(TransactionLimits.DAILY_TRANSACTION_LIMIT)
            },
        }

        print("====_send_validation_failure", alert_data)
        await send_transaction(alert_data)

    @staticmethod
    async def _send_validation_success(
            user: User,
            account: Account,
            amount: Decimal,
            transaction_type: str,
            additional_data: Dict[str, Any]
    ) -> None:
        """Send transaction validation success event to Kafka."""
        try:
            geo_info = random.choice(cities)
            now = datetime.utcnow()

            event_data = {
                "timestamp": now.isoformat(),
                "log_type": "transaction_event",
                "login_status": "success",
                "customer_id": user.customer_id,
                "alert_type": "transaction_validation_success",
                "alert_severity": "low",
                "failed_attempts": 0,
                "time_window_minutes": 5,
                "login_attempts": 1,
                "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
                "customer_segment": "retail",
                "status": "validated",
                "processing_time_ms": random.randint(100, 500),
                "business_date": now.date().isoformat(),
                "transaction_fee": 2500.0,
                "total_amount": float(amount) + 2500.0,
                "account_balance_before": float(account.balance),
                "account_balance_after": float(account.balance) - float(amount),
                "attempted_amount": float(amount),
                "currency": "IDR",
                "attempted_transaction_type": transaction_type,
                "attempted_channel": "web_app",
                "attempted_account_number": account.account_number,
                "attempted_recipient_account": additional_data.get("recipient_account"),
                "attempted_merchant_name": additional_data.get("merchant_name"),
                "attempted_merchant_category": additional_data.get("merchant_category"),
                "auth_method": "pin",
                "auth_success": True,
                "auth_timestamp": now.isoformat(),
                "error_type": "",
                "error_code": "",
                "error_detail": "",
                "validation_stage": "completed",
                "transaction_description": "",
                "recipient_account_number": "",
                "recipient_account_name": "",
                "recipient_bank_code": "",
                "reference_number": "",
                "risk_assessment_score": round(random.uniform(0.1, 0.3), 3),
                "fraud_indicator": "false",
                "aml_screening_result": "pass",
                "sanction_screening_result": "pass",
                "compliance_status": "approved",
                "settlement_date": now.date().isoformat(),
                "settlement_status": "pending",
                "clearing_code": f"CLR{random.randint(100000, 999999)}",
                "transaction_type": transaction_type,
                "requested_amount": float(amount),
                "failure_reason": "",
                "failure_message": "",
                "limits": {
                    "min_amount": float(TransactionLimits.MIN_TRANSACTION_AMOUNT),
                    "max_amount": float(TransactionLimits.MAX_TRANSACTION_AMOUNT),
                    "daily_limit": float(TransactionLimits.DAILY_TRANSACTION_LIMIT)
                },
                "account_number": account.account_number,
                "amount": float(amount),
                "channel": "web_app",
                "branch_code": "BR-0001",
                "province": geo_info["province"],
                "city": geo_info["city"],
                "merchant_name": additional_data.get("merchant_name", ""),
                "merchant_category": additional_data.get("merchant_category", ""),
                "merchant_id": f"MID{random.randint(10000000, 99999999)}",
                "terminal_id": f"TID{random.randint(100000, 999999)}",
                "latitude": geo_info["lat"],
                "longitude": geo_info["lon"],
                "device_id": f"dev_web_{uuid.uuid4().hex[:10]}",
                "device_type": "web",
                "device_os": random.choice(["Windows 11", "macOS 14", "Ubuntu 22.04"]),
                "device_browser": random.choice(["Chrome 120", "Safari 17", "Firefox 121"]),
                "device_is_trusted": random.choice([True, False]),
                "ip_address": f"192.168.{random.randint(1,255)}.{random.randint(1,255)}",
                "user_agent": "Mozilla/5.0 (Web Banking App)",
                "session_id": f"sess_{uuid.uuid4().hex[:8]}",
                "customer_age": random.randint(18, 65),
                "customer_gender": random.choice(["M", "F"]),
                "customer_occupation": random.choice(["karyawan", "wiraswasta", "pns", "pensiunan", "mahasiswa"]),
                "customer_income_bracket": random.choice(["<3jt", "3-5jt", "5-10jt", "10-25jt", ">25jt"]),
                "customer_education": random.choice(["SMA", "D3", "S1", "S2", "S3"]),
                "customer_marital_status": random.choice(["single", "married", "divorced"]),
                "customer_monthly_income": random.uniform(3000000, 25000000),
                "customer_credit_limit": random.uniform(10000000, 100000000),
                "customer_risk_score": round(random.uniform(0.1, 0.8), 3),
                "customer_kyc_level": random.choice(["basic", "enhanced", "premium"]),
                "customer_pep_status": random.choice([True, False]),
                "customer_previous_fraud_incidents": random.randint(0, 2),
                "device_fingerprint": f"fp_{uuid.uuid4().hex[:16]}",
                "qris_id": additional_data.get("qris_id", ""),
                "transaction_reference": f"REF{now.strftime('%Y%m%d')}{random.randint(100000, 999999)}",
                "interchange_fee": round(float(amount) * 0.007, 2),
                "db_transaction_id": f"db_{uuid.uuid4().hex[:12]}",
                "balance_after": float(account.balance) - float(amount),
                "qris_status": additional_data.get("qris_status", "")
            }

            await send_transaction(event_data)

        except Exception as e:
            print(f"Failed to send validation success event: {str(e)}")

    @staticmethod
    def get_transaction_limits() -> Dict[str, float]:
        """Get current transaction limits."""
        return {
            "min_transaction_amount": float(TransactionLimits.MIN_TRANSACTION_AMOUNT),
            "max_transaction_amount": float(TransactionLimits.MAX_TRANSACTION_AMOUNT),
            "daily_transaction_limit": float(TransactionLimits.DAILY_TRANSACTION_LIMIT)
        }


# Global instance
transaction_validation_service = TransactionValidationService()
