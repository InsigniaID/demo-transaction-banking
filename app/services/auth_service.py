from datetime import datetime, timedelta
import random
import uuid
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from ..utils.cities_data import cities
# from ..kafka_producer import send_transaction
from ..elk_kafka import send_transaction
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

        geo_info = random.choice(cities)

        # Add failed attempt
        self.failed_logins[username].append({
            "timestamp": timestamp_str,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "failure_reason": "invalid_password" if user else "user_not_found",
            "geolocation": geo_info
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
            "log_type": "login_error",
            "login_status": "failed",
            "customer_id": user.customer_id if user else "UNKNOWN",
            "alert_type": alert_type,
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
            ],
            "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
            "customer_segment": "retail",
            "status": "failed",
            "processing_time_ms": random.randint(100, 500),
            "business_date": now.date().isoformat(),
            "transaction_fee": 0,
            "total_amount": 0,
            "account_balance_before": 0,
            "account_balance_after": 0,
            "attempted_amount": 0,
            "currency": "IDR",
            "attempted_transaction_type": "login",
            "attempted_channel": "web_app",
            "attempted_account_number": "",
            "attempted_recipient_account": "",
            "attempted_merchant_name": "",
            "attempted_merchant_category": "",
            "auth_method": "password",
            "auth_success": False,
            "auth_timestamp": timestamp_str,
            "error_type": "authentication_failed",
            "error_code": 401,
            "error_detail": "Invalid username or password",
            "validation_stage": "login_validation",
            "transaction_description": "",
            "recipient_account_number": "",
            "recipient_account_name": "",
            "recipient_bank_code": "",
            "reference_number": "",
            "risk_assessment_score": round(random.uniform(0.5, 0.9), 3),
            "fraud_indicator": "true" if attempt_count >= 3 else "false",
            "aml_screening_result": "pending",
            "sanction_screening_result": "pending",
            "compliance_status": "failed",
            "settlement_date": "",
            "settlement_status": "",
            "clearing_code": "",
            "transaction_type": "login",
            "requested_amount": 0,
            "failure_reason": "invalid_credentials",
            "failure_message": "Username or password is incorrect",
            "limits": "",
            "account_number": "",
            "amount": 0,
            "channel": "web_app",
            "branch_code": "BR-0001",
            "province": "DKI Jakarta",
            "city": "Jakarta Selatan",
            "merchant_name": "",
            "merchant_category": "",
            "merchant_id": "",
            "terminal_id": "",
            "latitude": -6.261493,
            "longitude": 106.810600,
            "device_id": f"dev_web_{uuid.uuid4().hex[:10]}",
            "device_type": "web",
            "device_os": random.choice(["Windows 11", "macOS 14", "Ubuntu 22.04"]),
            "device_browser": random.choice(["Chrome 120", "Safari 17", "Firefox 121"]),
            "device_is_trusted": False,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "session_id": f"sess_{uuid.uuid4().hex[:8]}",
            "customer_age": random.randint(18, 65) if user else 0,
            "customer_gender": random.choice(["M", "F"]) if user else "",
            "customer_occupation": random.choice(["karyawan", "wiraswasta", "pns"]) if user else "",
            "customer_income_bracket": random.choice(["<3jt", "3-5jt", "5-10jt"]) if user else "",
            "customer_education": random.choice(["SMA", "D3", "S1"]) if user else "",
            "customer_marital_status": random.choice(["single", "married"]) if user else "",
            "customer_monthly_income": random.uniform(3000000, 15000000) if user else 0,
            "customer_credit_limit": random.uniform(10000000, 50000000) if user else 0,
            "customer_risk_score": round(random.uniform(0.5, 0.9), 3) if user else 0,
            "customer_kyc_level": random.choice(["basic", "enhanced"]) if user else "",
            "customer_pep_status": random.choice([True, False]) if user else False,
            "customer_previous_fraud_incidents": random.randint(0, 1) if user else 0,
            "device_fingerprint": f"fp_{uuid.uuid4().hex[:16]}",
            "qris_id": "",
            "transaction_reference": f"REF{now.strftime('%Y%m%d')}{random.randint(100000, 999999)}",
            "interchange_fee": 0,
            "db_transaction_id": f"db_{uuid.uuid4().hex[:12]}",
            "balance_after": 0,
            "qris_status": ""
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
            failed_attempts=0,
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

    @staticmethod
    async def handle_otp_error(request, otp, current_user):
        if otp == "123456":
            geo_info = random.choice(cities)
            ip_address = request.client.host
            user_agent = request.headers.get("user-agent", "unknown")
            otp_error = StandardKafkaEvent(timestamp=datetime.utcnow(),
                                           log_type="otp_success",
                                           login_status="success",
                                           customer_id=current_user.customer_id,
                                           auth_method="password",
                                           auth_success=True,
                                           auth_timestamp=datetime.utcnow(),
                                           error_type="",
                                           error_detail="",
                                           failure_reason="",
                                           failure_message="",
                                           validation_stage="",
                                           attempted_channel="web_api",
                                           ip_address=ip_address,
                                           user_agent=user_agent,
                                           device_type="web",
                                           device_is_trusted=True,
                                           session_id=f"session_{datetime.utcnow().timestamp()}",
                                           city=geo_info["city"],
                                           province="",
                                           latitude=geo_info["lat"],
                                           longitude=geo_info["lon"],
                                           processing_time_ms=int(datetime.utcnow().timestamp() * 1000) % 1000,
                                           business_date=datetime.utcnow().strftime("%Y-%m-%d"),
                                           status="",
                                           alert_type="",
                                           alert_severity="")

            event_data = otp_error.model_dump(exclude_none=True)
            event_data['timestamp'] = otp_error.timestamp.isoformat() + 'Z'
            event_data['auth_timestamp'] = otp_error.auth_timestamp.isoformat() + 'Z'

            print(event_data)
            await send_transaction(event_data)

            return {"status": "success", "message": "otp_success"}

        else:
            geo_info = random.choice(cities)
            ip_address = request.client.host
            user_agent = request.headers.get("user-agent", "unknown")
            otp_error = StandardKafkaEvent(timestamp=datetime.utcnow(),
                                           log_type="otp_error",
                                           login_status="error",
                                           customer_id=current_user.customer_id,
                                           auth_method="password",
                                           auth_success=False,
                                           auth_timestamp=datetime.utcnow(),
                                           error_type="otp_validation",
                                           error_detail="",
                                           failure_reason="otp_error",
                                           failure_message="",
                                           validation_stage="",
                                           attempted_channel="web_api",
                                           ip_address=ip_address,
                                           user_agent=user_agent,
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
                                           alert_type="otp_failure",
                                           alert_severity="medium")

            event_data = otp_error.model_dump(exclude_none=True)
            event_data['timestamp'] = otp_error.timestamp.isoformat() + 'Z'
            event_data['auth_timestamp'] = otp_error.auth_timestamp.isoformat() + 'Z'

            print(event_data)
            await send_transaction(event_data)

            return {"status": "error", "message": "otp_error"}

    @staticmethod
    async def handle_otp_advanced_error(request, current_user, reason):
        geo_info = random.choice(cities)
        ip_address = request.client.host
        user_agent = request.headers.get("user-agent", "unknown")
        otp_error = StandardKafkaEvent(timestamp=datetime.utcnow(),
                                       log_type="otp_advanced_error",
                                       login_status="error",
                                       customer_id=current_user.customer_id,
                                       auth_method="password",
                                       auth_success=False,
                                       auth_timestamp=datetime.utcnow(),
                                       error_type="otp_advanced_validation",
                                       error_detail="",
                                       failure_reason=reason,
                                       failure_message="",
                                       validation_stage="",
                                       attempted_channel="web_api",
                                       ip_address=ip_address,
                                       user_agent=user_agent,
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
                                       alert_type="otp_advanced_failure",
                                       alert_severity="high")

        event_data = otp_error.model_dump(exclude_none=True)
        event_data['timestamp'] = otp_error.timestamp.isoformat() + 'Z'
        event_data['auth_timestamp'] = otp_error.auth_timestamp.isoformat() + 'Z'

        print(event_data)
        await send_transaction(event_data)


# Global instance
auth_service = AuthService()