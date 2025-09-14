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
            "log_type": "login_event",
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
            "attempted_account_number": "",
            "attempted_recipient_account": "",
            "attempted_merchant_name": "",
            "attempted_merchant_category": "",
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
            "transaction_type": "",
            "requested_amount": "",
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
            "ip_address": ip_address,
            "user_agent": user_agent,
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
            "log_type": "login_event",
            "login_status": "success",
            "customer_id": user.customer_id,
            "alert_type": "",
            "alert_severity": "",
            "failed_attempts": 0,
            "time_window_minutes": 30,
            "login_attempts": {
                "attempt_number": 1,
                "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f"),
                "ip_address": ip_address,
                "user_agent": user_agent,
                "failure_reason": "",
                "geolocation": [{
                    "country": "Indonesia",
                    "city": "Jakarta",
                    "lat": -6.2088,
                    "lon": 106.8456
                }]
            },
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
            "attempted_account_number": "",
            "attempted_recipient_account": "",
            "attempted_merchant_name": "",
            "attempted_merchant_category": "",
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
            "transaction_type": "",
            "requested_amount": "",
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
            "ip_address": ip_address,
            "user_agent": user_agent,
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

        await send_transaction(success_event)


# Global instance
auth_service = AuthService()