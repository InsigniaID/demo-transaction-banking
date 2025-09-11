import uuid
from datetime import datetime, timedelta
from typing import Dict
from fastapi import HTTPException

from ..utils.qris import encode_qris_payload, decode_qris_payload
from ..schemas import GenerateQRISRequest, GenerateQRISResponse, ConsumeQRISRequest, ConsumeQRISResponse


# In-memory storage for QRIS data (consider using Redis for production)
QRIS_STORAGE: Dict[str, dict] = {}


class QRISService:
    @staticmethod
    def generate_qris(data: GenerateQRISRequest, customer_id: str) -> GenerateQRISResponse:
        """Generate QRIS code for payment."""
        qris_id = str(uuid.uuid4())
        expired_at = datetime.utcnow() + timedelta(minutes=15)

        payload = {
            "qris_id": qris_id,
            "merchant_name": data.merchant_name,
            "merchant_category": data.merchant_category,
            "amount": data.amount,
            "currency": data.currency,
            "expired_at": expired_at.isoformat()
        }

        qris_code = encode_qris_payload(payload)

        QRIS_STORAGE[qris_id] = {
            "qris_code": qris_code,
            "customer_id": customer_id,
            "account_number": data.account_number,
            "amount": data.amount,
            "currency": data.currency,
            "merchant_name": data.merchant_name,
            "merchant_category": data.merchant_category,
            "expired_at": expired_at,
            "status": "ACTIVE",
        }

        return GenerateQRISResponse(
            qris_id=qris_id,
            qris_code=qris_code,
            expired_at=expired_at
        )

    @staticmethod
    def validate_and_consume_qris(data: ConsumeQRISRequest, customer_id: str) -> tuple[dict, str]:
        """Validate and consume QRIS code."""
        decoded = decode_qris_payload(data.qris_code)
        qris_id = decoded.get("qris_id")
        qris_data = QRIS_STORAGE.get(qris_id)

        if not qris_data:
            raise HTTPException(status_code=404, detail="QRIS not found")

        if qris_data["status"] != "ACTIVE":
            raise HTTPException(status_code=400, detail="Invalid QRIS code")

        if datetime.utcnow() > qris_data["expired_at"]:
            qris_data["status"] = "EXPIRED"
            raise HTTPException(status_code=400, detail="QRIS expired")

        if data.customer_id == qris_data["customer_id"]:
            raise HTTPException(status_code=400, detail="Player cannot be the same as payee")

        qris_data["status"] = "CONSUMED"
        
        return qris_data, qris_id