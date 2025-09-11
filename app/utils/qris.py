import base64
import json
from fastapi import HTTPException


def encode_qris_payload(payload: dict) -> str:
    """Encode QRIS payload to base64 string."""
    raw = json.dumps(payload).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def decode_qris_payload(qris_code: str) -> dict:
    """Decode QRIS code from base64 string to dict."""
    try:
        raw = base64.urlsafe_b64decode(qris_code.encode("utf-8"))
        return json.loads(raw.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid QRIS code")