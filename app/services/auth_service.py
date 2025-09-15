from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from ..kafka_producer import send_transaction
from ..models import User
from ..schemas import (
    StandardKafkaEvent, LocationInfo, SuspiciousActivity
)
from .location_service import location_service
from .crash_simulator import crash_simulator


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

        # Send alert for every failed attempt (1, 2, 3+)
        attempt_count = len(window)

        # Determine alert severity based on attempt count
        if attempt_count == 1:
            severity = "low"
            alert_type = "failed_login"
        elif attempt_count == 2:
            severity = "medium"
            alert_type = "repeated_failed_login"
        else:  # 3+
            severity = "high"
            alert_type = "multiple_failed_login"

        alert = {
            "timestamp": timestamp_str,
            "log_type": "security_alert",
            "alert_type": alert_type,
            "customer_id": user.customer_id if user else "UNKNOWN",
            "alert_severity": severity,
            "failed_attempts": attempt_count,
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
        user_agent: str,
        selected_location: Optional[str] = None
    ) -> None:
        """Handle successful login."""
        # Clear failed attempts
        self.failed_logins[username] = []

        # Get location data based on selected_location or default to Jakarta
        from .location_service import location_service
        if selected_location:
            location_info = location_service.get_location_info(selected_location)
            if location_info:
                city = location_info.city
                province = f"Prov. {location_info.city}"
                latitude = location_info.latitude
                longitude = location_info.longitude
            else:
                # Fallback to Jakarta if invalid location
                city = "Jakarta"
                province = "DKI Jakarta"
                latitude = -6.2088
                longitude = 106.8456
        else:
            # Default to Jakarta
            city = "Jakarta"
            province = "DKI Jakarta"
            latitude = -6.2088
            longitude = 106.8456

        # Send success event using standard schema
        now = datetime.utcnow()
        success_event = StandardKafkaEvent(
            timestamp=now,
            log_type="login",
            login_status="success",
            customer_id=user.customer_id,
            auth_method="password",
            auth_success=True,
            auth_timestamp=now,
            attempted_channel="web_api",
            ip_address=ip_address,
            user_agent=user_agent,
            device_type="web",
            device_is_trusted=True,  # Successful login assumes trusted for now
            session_id=f"session_{datetime.utcnow().timestamp()}",
            city=city,
            province=province,
            latitude=latitude,
            longitude=longitude,
            processing_time_ms=int(datetime.utcnow().timestamp() * 1000) % 1000,
            business_date=datetime.utcnow().strftime("%Y-%m-%d"),
            status="success",
            validation_stage="authentication_complete"
        )
        # Convert to dict and serialize datetime objects
        event_data = success_event.model_dump(exclude_none=True)
        event_data['timestamp'] = success_event.timestamp.isoformat() + 'Z'
        event_data['auth_timestamp'] = success_event.auth_timestamp.isoformat() + 'Z'
        await send_transaction(event_data)

    async def send_login_error_event(
        self,
        error_type: str,
        username: str,
        customer_id: Optional[str],
        ip_address: str,
        user_agent: str,
        error_message: str,
        error_details: Optional[dict] = None,
        request_payload: Optional[dict] = None
    ) -> None:
        """Send login error event to Kafka using standard schema."""
        error_event = StandardKafkaEvent(
            timestamp=datetime.utcnow(),
            log_type="login_error",
            login_status="failed",
            customer_id=customer_id,
            auth_method="password",
            auth_success=False,
            auth_timestamp=datetime.utcnow(),
            error_type=error_type,
            error_detail=error_message,
            failure_reason=error_type,
            failure_message=error_message,
            validation_stage="authentication",
            attempted_channel="web_api",
            ip_address=ip_address,
            user_agent=user_agent,
            device_type="web",
            device_is_trusted=False,
            session_id=f"session_{datetime.utcnow().timestamp()}",
            city="Jakarta",
            province="DKI Jakarta",
            latitude=-6.2088,
            longitude=106.8456,
            processing_time_ms=int(datetime.utcnow().timestamp() * 1000) % 1000,
            business_date=datetime.utcnow().strftime("%Y-%m-%d"),
            status="failed"
        )
        # Convert to dict and serialize datetime objects
        event_data = error_event.model_dump(exclude_none=True)
        event_data['timestamp'] = error_event.timestamp.isoformat() + 'Z'
        event_data['auth_timestamp'] = error_event.auth_timestamp.isoformat() + 'Z'
        await send_transaction(event_data)

    async def send_location_suspicious_event(
        self,
        username: str,
        customer_id: str,
        ip_address: str,
        user_agent: str,
        current_location: LocationInfo,
        previous_location: Optional[LocationInfo],
        suspicious_activity: SuspiciousActivity
    ) -> None:
        """Send location suspicious activity event to Kafka using standard schema."""
        alert_types = {
            "high": "impossible_travel_detected",
            "medium": "rapid_location_change" if suspicious_activity.reason == "Rapid location change detected" else "multiple_location_pattern",
            "low": "suspicious_login_pattern"
        }

        event = StandardKafkaEvent(
            timestamp=datetime.utcnow(),
            log_type="security_alert",
            login_status="suspicious",
            customer_id=customer_id,
            alert_type=alert_types.get(suspicious_activity.suspicionLevel, "suspicious_login_pattern"),
            alert_severity=suspicious_activity.suspicionLevel,
            auth_method="password",
            auth_success=True,  # Credentials were valid but location suspicious
            auth_timestamp=datetime.utcnow(),
            risk_assessment_score=float(suspicious_activity.score) if suspicious_activity.score else 0.0,
            fraud_indicator=suspicious_activity.reason,
            ip_address=ip_address,
            user_agent=user_agent,
            device_type="web",
            device_is_trusted=False,
            session_id=f"session_{datetime.utcnow().timestamp()}",
            city=current_location.city,
            province=current_location.city,  # Using city as province for simplicity
            latitude=current_location.latitude,
            longitude=current_location.longitude,
            processing_time_ms=int(datetime.utcnow().timestamp() * 1000) % 1000,
            business_date=datetime.utcnow().strftime("%Y-%m-%d"),
            status="alert",
            attempted_channel="web_api",
            validation_stage="location_verification"
        )
        # Convert to dict and serialize datetime objects
        event_data = event.model_dump(exclude_none=True)
        event_data['timestamp'] = event.timestamp.isoformat() + 'Z'
        event_data['auth_timestamp'] = event.auth_timestamp.isoformat() + 'Z'
        await send_transaction(event_data)

    async def send_crash_simulator_event(
        self,
        crash_type: str,
        username: str,
        customer_id: Optional[str],
        ip_address: str,
        user_agent: str,
        error_message: str,
        selected_location: Optional[str] = None,
        stack_trace: Optional[str] = None
    ) -> None:
        """Send crash simulator event to Kafka using standard schema."""
        # Get location data based on selected_location or default to Jakarta
        from .location_service import location_service
        if selected_location:
            location_info = location_service.get_location_info(selected_location)
            if location_info:
                city = location_info.city
                province = f"Prov. {location_info.city}"
                latitude = location_info.latitude
                longitude = location_info.longitude
            else:
                # Fallback to Jakarta if invalid location
                city = "Jakarta"
                province = "DKI Jakarta"
                latitude = -6.2088
                longitude = 106.8456
        else:
            # Default to Jakarta
            city = "Jakarta"
            province = "DKI Jakarta"
            latitude = -6.2088
            longitude = 106.8456

        crash_event = StandardKafkaEvent(
            timestamp=datetime.utcnow(),
            log_type="system_error",
            login_status="error",
            customer_id=customer_id,
            auth_method="password",
            auth_success=False,
            auth_timestamp=datetime.utcnow(),
            error_type="crash_simulation",
            error_detail=error_message,
            failure_reason=f"crash_simulation_{crash_type}",
            failure_message=error_message,
            validation_stage="post_authentication",
            attempted_channel="web_api",
            ip_address=ip_address,
            user_agent=user_agent,
            device_type="web",
            device_is_trusted=False,
            session_id=f"session_{datetime.utcnow().timestamp()}",
            city=city,
            province=province,
            latitude=latitude,
            longitude=longitude,
            processing_time_ms=int(datetime.utcnow().timestamp() * 1000) % 1000,
            business_date=datetime.utcnow().strftime("%Y-%m-%d"),
            status="error",
            alert_type="system_failure",
            alert_severity="high"
        )
        # Convert to dict and serialize datetime objects
        event_data = crash_event.model_dump(exclude_none=True)
        event_data['timestamp'] = crash_event.timestamp.isoformat() + 'Z'
        event_data['auth_timestamp'] = crash_event.auth_timestamp.isoformat() + 'Z'
        await send_transaction(event_data)

    async def handle_enhanced_login_attempt(
        self,
        username: str,
        password: str,
        ip_address: str,
        user_agent: str,
        location_detection_enabled: bool = False,
        selected_location: str = "",
        crash_simulator_enabled: bool = False,
        crash_type: str = "",
        request_payload: Optional[dict] = None
    ) -> dict:
        """Handle enhanced login attempt with location checks (crash simulation moved to post-auth)."""
        try:
            # Handle location validation if enabled
            suspicious_activity = None
            if location_detection_enabled and selected_location:
                suspicious_activity, previous_location = location_service.check_suspicious_location(
                    username, selected_location
                )

                if suspicious_activity and suspicious_activity.isSuspicious:
                    current_location = location_service.get_location_info(selected_location)
                    # We'll send this after user validation to get customer_id
                    pass

            return {
                "suspicious_activity": suspicious_activity,
                "location": selected_location if location_detection_enabled else None,
                "crash_enabled": crash_simulator_enabled and crash_type
            }

        except Exception as e:
            # Send error event for any unexpected errors
            await self.send_login_error_event(
                error_type="unexpected_error",
                username=username,
                customer_id=None,
                ip_address=ip_address,
                user_agent=user_agent,
                error_message=str(e),
                error_details={"exception_type": type(e).__name__},
                request_payload=request_payload
            )
            raise


# Global instance
auth_service = AuthService()