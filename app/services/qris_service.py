import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..utils.cities_data import cities
from ..utils.qris import encode_qris_payload, decode_qris_payload
from ..schemas import GenerateQRISRequest, GenerateQRISResponse, ConsumeQRISRequest, ConsumeQRISResponse, \
    StandardKafkaEvent
from ..models import QRISTransaction
from ..database import SessionLocal


# In-memory storage for QRIS data (fallback, but now using database)
QRIS_STORAGE: Dict[str, dict] = {}


class QRISService:
    @staticmethod
    def generate_qris(data: GenerateQRISRequest, customer_id: str, db: Optional[Session] = None) -> GenerateQRISResponse:
        """Generate QRIS code for payment."""
        if db is None:
            db = SessionLocal()
            close_db = True
        else:
            close_db = False

        try:
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

            # Store in database
            qris_transaction = QRISTransaction(
                qris_id=qris_id,
                customer_id=customer_id,
                account_number=data.account_number,
                amount=data.amount,
                currency=data.currency,
                merchant_name=data.merchant_name,
                merchant_category=data.merchant_category,
                qris_code=qris_code,
                status="ACTIVE",
                expired_at=expired_at
            )

            db.add(qris_transaction)
            db.commit()
            db.refresh(qris_transaction)

            # Also store in memory for faster access
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

        finally:
            if close_db:
                db.close()

    @staticmethod
    def validate_and_consume_qris(data: ConsumeQRISRequest, customer_id: str, db: Optional[Session] = None) -> tuple[dict, str]:
        """Validate and consume QRIS code."""
        if db is None:
            db = SessionLocal()
            close_db = True
        else:
            close_db = False

        try:
            print(f"QRIS Service - Decoding QRIS code: {data.qris_code[:20]}...")
            decoded = decode_qris_payload(data.qris_code)
            qris_id = decoded.get("qris_id")
            print(f"QRIS Service - Decoded QRIS ID: {qris_id}")

            # Query database for QRIS transaction
            qris_transaction = db.query(QRISTransaction).filter(QRISTransaction.qris_id == qris_id).first()
            print(f"QRIS Service - QRIS data found in DB: {qris_transaction is not None}")

            if not qris_transaction:
                print(f"QRIS Service - QRIS not found for ID: {qris_id}")
                raise HTTPException(status_code=404, detail="QRIS not found")

            print(f"QRIS Service - QRIS status: {qris_transaction.status}")
            if qris_transaction.status != "ACTIVE":
                raise HTTPException(status_code=400, detail="Invalid QRIS code")

            print(f"QRIS Service - Current time: {datetime.utcnow()}, Expires: {qris_transaction.expired_at}")
            if datetime.utcnow() > qris_transaction.expired_at:
                qris_transaction.status = "EXPIRED"
                db.commit()
                print("QRIS Service - QRIS expired")
                raise HTTPException(status_code=400, detail="QRIS expired")

            print(f"QRIS Service - Customer check: {customer_id} vs {qris_transaction.customer_id}")
            # Temporarily disabled same customer validation for testing
            # if customer_id == qris_transaction.customer_id:
            #     print("QRIS Service - Same customer error")
            #     raise HTTPException(status_code=400, detail="Player cannot be the same as payee")

            # Mark as consumed

            # TEMPORARY
            # qris_transaction.status = "CONSUMED"
            db.commit()
            print("QRIS Service - QRIS validated successfully")
            
            # Convert to dict format for backward compatibility
            qris_data = {
                "qris_code": qris_transaction.qris_code,
                "customer_id": qris_transaction.customer_id,
                "account_number": qris_transaction.account_number,
                "amount": float(qris_transaction.amount),
                "currency": qris_transaction.currency,
                "merchant_name": qris_transaction.merchant_name,
                "merchant_category": qris_transaction.merchant_category,
                "expired_at": qris_transaction.expired_at,
                "status": qris_transaction.status,
            }
            
            # Also update in-memory storage for consistency (optional)
            QRIS_STORAGE[qris_id] = qris_data
            
            return qris_data, qris_id

        finally:
            if close_db:
                db.close()