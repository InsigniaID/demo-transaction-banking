"""
Transaction validation service for checking balance, limits, and business rules.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from fastapi import HTTPException

from ..models import Account, TransactionHistory, User
from ..kafka_producer import send_transaction


class TransactionLimits:
    """Transaction limits configuration."""
    MIN_TRANSACTION_AMOUNT = Decimal("1000.00")  # Rp 1,000
    MAX_TRANSACTION_AMOUNT = Decimal("10000000.00")  # Rp 10 juta
    DAILY_TRANSACTION_LIMIT = Decimal("20000000.00")  # Rp 20 juta/hari


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
        # await send_transaction(alert_data)

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
            event_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "log_type": "transaction_event",
                "login_status": "",
                "customer_id": user.customer_id,
                "alert_type": "transaction_validation_success",
                "alert_severity": "",
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
                "account_balance_before": "",
                "account_balance_after": "",
                "attempted_amount": "",
                "currency": "",
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
                "failure_reason": "",
                "failure_message": "",
                "limits": "",
                "account_number": "",
                "amount": "",
                "channel": "",
                "branch_code": "",
                "province": "",
                "city": "",
                "merchant_name": "",
                "merchant_category": "",
                "merchant_id": "",
                "terminal_id": "",
                "latitude": "",
                "longitude": "",
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
