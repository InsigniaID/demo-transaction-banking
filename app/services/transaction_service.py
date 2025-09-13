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
            "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
            "customer_id": customer_id,
            "account_number": account_number,
            "customer_segment": "retail",
            "transaction_type": "pos_purchase",
            "amount": qris_data["amount"],
            "currency": qris_data["currency"],
            "channel": "mobile_app",
            "status": "success",
            "branch_code": "BR-0001",
            "province": "DKI Jakarta",
            "city": "Jakarta Selatan",
            "latitude": -6.261493,
            "longitude": 106.810600,
            "processing_time_ms": 1250,
            "business_date": now.date().isoformat(),
            "customer_age": 28,
            "customer_gender": "F",
            "customer_occupation": "karyawan",
            "customer_income_bracket": "5-10jt",
            "customer_education": "S1",
            "customer_marital_status": "married",
            "customer_monthly_income": 7500000.0,
            "customer_credit_limit": 22500000.0,
            "customer_savings_balance": 45000000.0,
            "customer_risk_score": 0.25,
            "customer_kyc_level": "basic",
            "customer_pep_status": False,
            "customer_previous_fraud_incidents": 0,
            "device_id": "dev_mobile_abc123",
            "device_type": "mobile",
            "device_os": "Android 14",
            "device_browser": "Chrome 120",
            "device_is_trusted": True,
            "ip_address": "192.168.1.100",
            "user_agent": "Mozilla/5.0 (Android 14; Mobile)",
            "session_id": f"sess_{uuid.uuid4().hex[:8]}",
            "merchant_name": qris_data["merchant_name"],
            "merchant_category": qris_data["merchant_category"],
            "merchant_id": "MID12345678",
            "terminal_id": "TID123456",
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
