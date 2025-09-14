from datetime import datetime
from typing import Dict, Any
from fastapi import HTTPException

from ..models import User
from ..security import verify_pin
from ..kafka_producer import send_transaction


class PINValidationService:
    _failed_attempts: Dict[str, int] = {}

    @staticmethod
    def validate_pin(user: User, pin: str) -> bool:
        """Validate user PIN."""
        if not user.hashed_pin:
            # User doesn't have a PIN set
            return False
        return verify_pin(pin, user.hashed_pin)
    
    @staticmethod
    async def handle_pin_validation_failure(
        user: User,
        transaction_type: str,
        amount: float = None,
        additional_data: Dict[str, Any] = None
    ) -> None:
        """Send PIN validation failure event to Kafka."""
        key = f"{user.customer_id}:{transaction_type}"
        PINValidationService._failed_attempts[key] = PINValidationService._failed_attempts.get(key, 0) + 1
        failed_attempts = PINValidationService._failed_attempts[key]

        failure_event = {
            "timestamp": datetime.utcnow().isoformat(),
            "log_type": "transaction_pin_validation",
            "login_status": "",
            "customer_id": user.customer_id,
            "alert_type": "pin_validation_failure",
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
            "total_amount": amount,
            "currency": "",
            "account_balance_before": "",
            "account_balance_after": "",
            "attempted_amount": "",
            "attempted_transaction_type": "",
            "attempted_channel": "",
            "attempted_account_number": "",
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
            "failure_reason": f"invalid_pin {failed_attempts}" if failed_attempts > 1 else "invalid_pin",
            "failure_message": "",
            "limits": ""
        }

        print("====handle_pin_validation_failure\n", failure_event)
        # await send_transaction(failure_event)
    
    @staticmethod
    async def validate_pin_or_fail(
            user: User,
            pin: str,
            transaction_type: str,
            amount: float = None,
            additional_data: Dict[str, Any] = None
    ) -> None:
        """Validate PIN or raise HTTPException and send to Kafka."""
        if not user.hashed_pin:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "PIN not set",
                    "message": "User does not have a PIN configured. Please set up a PIN first."
                }
            )

        if not PINValidationService.validate_pin(user, pin):
            # Calc failed attempts
            key = f"{user.customer_id}:{transaction_type}"
            PINValidationService._failed_attempts[key] = (PINValidationService._failed_attempts.get(key, 0) % 3) + 1
            failed_attempts = PINValidationService._failed_attempts[key]

            # Raise exception with message ada attempt
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "Invalid PIN",
                    "message": f"The provided PIN is incorrect. Attempt {failed_attempts}"
                }
            )


# Global instance
pin_validation_service = PINValidationService()
