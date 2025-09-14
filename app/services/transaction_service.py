import uuid
from datetime import datetime
from typing import Dict, Any

from ..kafka_producer import send_transaction


class TransactionService:
    @staticmethod
    async def create_retail_transaction_data(
        qris_data: dict,
        customer_id: str,
        account_number: str
    ) -> Dict[str, Any]:
        """Create retail transaction data for QRIS consumption."""
        now = datetime.utcnow()
        
        return {
            "timestamp": now.isoformat(),
            "log_type": "transaction",
            "login_status": "",
            "customer_id": customer_id,
            "alert_type": "pin_validation_failure",
            "alert_severity": "medium",
            "failed_attempts": "",
            "time_window_minutes": "",
            "login_attempts": "",
            "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
            "customer_segment": "retail",
            "status": "success",
            "processing_time_ms": 1250,
            "business_date": now.date().isoformat(),
            "transaction_fee": "",
            "total_amount": qris_data["amount"],
            "currency": qris_data["currency"],
            "account_balance_before": "",
            "account_balance_after": "",
            "attempted_amount": "",
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
            "requested_amount": qris_data["amount"],
            "failure_reason": "",
            "failure_message": "",
            "limits": ""
        }

    @staticmethod
    async def create_corporate_transaction_data(
        transaction_data: dict,
        customer_id: str,
        request_headers: dict,
        client_host: str
    ) -> Dict[str, Any]:
        """Create corporate transaction data."""
        start_time = datetime.utcnow()
        end_time = datetime.utcnow()
        processing_time_ms = int((end_time - start_time).total_seconds() * 1000)

        transaction_data.update({
            "timestamp": datetime.utcnow().isoformat(),
            "log_type": "transaction",
            "transaction_id": str(uuid.uuid4()),
            "customer_id": customer_id,
            "customer_segment": "corporate",
            "status": "success",
            "latitude": request_headers.get("X-Device-Lat"),
            "longitude": request_headers.get("X-Device-Lon"),
            "processing_time_ms": processing_time_ms,
            "business_date": datetime.utcnow().date().isoformat(),
            "device_id": request_headers.get("X-Device-ID"),
            "device_type": request_headers.get("X-Device-Type"),
            "device_os": request_headers.get("X-Device-OS"),
            "device_browser": request_headers.get("X-Device-Browser"),
            "device_is_trusted": request_headers.get("X-Device-Trusted") == "true",
            "ip_address": client_host,
            "user_agent": request_headers.get("user-agent"),
            "session_id": request_headers.get("X-Session-ID"),
        })

        return transaction_data

    @staticmethod
    async def send_transaction_to_kafka(transaction_data: Dict[str, Any]) -> None:
        """Send transaction data to Kafka."""
        await send_transaction(transaction_data)
