from datetime import datetime
from typing import Dict, Any
from fastapi import HTTPException

from ..models import User
from ..security import verify_pin
from ..kafka_producer import send_transaction


class PINValidationService:
    @staticmethod
    def validate_pin(user: User, pin: str) -> bool:
        """Validate user PIN."""
        return verify_pin(pin, user.hashed_pin)
    
    @staticmethod
    async def handle_pin_validation_failure(
        user: User,
        transaction_type: str,
        amount: float = None,
        additional_data: Dict[str, Any] = None
    ) -> None:
        """Send PIN validation failure event to Kafka."""
        failure_event = {
            "timestamp": datetime.utcnow().isoformat(),
            "log_type": "security_alert",
            "alert_type": "pin_validation_failure",
            "customer_id": user.customer_id,
            "transaction_type": transaction_type,
            "amount": amount,
            "alert_severity": "medium",
            "failure_reason": "invalid_pin",
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
        if not PINValidationService.validate_pin(user, pin):
            # Send failure event to Kafka
            await PINValidationService.handle_pin_validation_failure(
                user, transaction_type, amount, additional_data
            )
            # Raise HTTP exception
            raise HTTPException(status_code=401, detail="Invalid PIN")


# Global instance
pin_validation_service = PINValidationService()