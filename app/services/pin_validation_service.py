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
            "log_type": "security_alert",
            "alert_type": "pin_validation_failure",
            "customer_id": user.customer_id,
            "transaction_type": transaction_type,
            "amount": amount,
            "alert_severity": "medium",
            "failure_reason": f"invalid_pin {failed_attempts}" if failed_attempts > 1 else "invalid_pin",
            "additional_data": additional_data or {}
        }

        await send_transaction(failure_event)
    
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
