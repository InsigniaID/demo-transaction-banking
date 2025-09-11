from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from ..kafka_producer import send_transaction
from ..models import User


class AuthService:
    def __init__(self):
        self.failed_logins: Dict[str, List[dict]] = {}

    async def handle_failed_login(
        self,
        username: str,
        user: Optional[User],
        ip_address: str,
        user_agent: str
    ) -> None:
        """Handle failed login attempt and send alerts if needed."""
        now = datetime.utcnow()
        timestamp_str = now.strftime("%Y-%m-%dT%H:%M:%S.%f")

        if username not in self.failed_logins:
            self.failed_logins[username] = []

        # Add failed attempt
        self.failed_logins[username].append({
            "timestamp": timestamp_str,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "failure_reason": "invalid_password" if user else "user_not_found",
            "geolocation": {
                "country": "Indonesia",
                "city": "Jakarta",
                "lat": -6.2088,
                "lon": 106.8456
            }
        })

        # Get attempts in time window
        window = [
            attempt for attempt in self.failed_logins[username]
            if datetime.fromisoformat(attempt["timestamp"]) > now - timedelta(minutes=30)
        ]

        # Send alert if threshold reached
        if len(window) >= 2:
            alert = {
                "timestamp": timestamp_str,
                "log_type": "security_alert",
                "alert_type": "multiple_failed_login",
                "customer_id": user.customer_id if user else "UNKNOWN",
                "alert_severity": "high",
                "failed_attempts": len(window),
                "time_window_minutes": 30,
                "login_attempts": [
                    {
                        "attempt_number": i + 1,
                        "timestamp": attempt["timestamp"],
                        "ip_address": attempt["ip_address"],
                        "user_agent": attempt["user_agent"],
                        "failure_reason": attempt["failure_reason"],
                        "geolocation": attempt["geolocation"]
                    } for i, attempt in enumerate(window)
                ]
            }
            await send_transaction(alert)

    async def handle_successful_login(
        self,
        username: str,
        user: User,
        ip_address: str,
        user_agent: str
    ) -> None:
        """Handle successful login."""
        # Clear failed attempts
        self.failed_logins[username] = []

        # Send success event
        success_event = {
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f"),
            "log_type": "login",
            "login_status": "success",
            "customer_id": user.customer_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "geolocation": {
                "country": "Indonesia",
                "city": "Jakarta",
                "lat": -6.2088,
                "lon": 106.8456
            }
        }
        await send_transaction(success_event)


# Global instance
auth_service = AuthService()