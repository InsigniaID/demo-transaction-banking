import base64
import json
import uuid
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, security, Request, Body
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
from . import schemas, database, models, security
from .auth import get_current_user
from .kafka_producer import init_kafka, shutdown_kafka, send_transaction
from .models import User
from .schemas import TransactionCorporateInput, ConsumeQRISRequest, ConsumeQRISResponse, GenerateQRISRequest, \
    GenerateQRISResponse

database.Base.metadata.create_all(bind=database.engine)
app = FastAPI()
FAILED_LOGINS = {}
QRIS_STORAGE = {}


def get_db():
    db = database.SessionLocal()

    try:
        yield db

    finally:
        db.close()

def encode_qris_payload(payload: dict) -> str:
    raw = json.dumps(payload).encode("utf-8")

    return base64.urlsafe_b64encode(raw).decode("utf-8")

def decode_qris_payload(qris_code: str) -> dict:
    try:
        raw = base64.urlsafe_b64decode(qris_code.encode("utf-8"))
        return json.loads(raw.decode("utf-8"))

    except Exception:
        raise HTTPException(status_code=400, detail="Invalid QRIS code")


@app.on_event("startup")
async def startup_event():
    await init_kafka()


@app.on_event("shutdown")
async def shutdown_event():
    await shutdown_kafka()


@app.on_event("startup")
async def debug_openapi():
    import json
    openapi_schema = app.openapi()

    for path, methods in openapi_schema.get("paths", {}).items():
        for method, details in methods.items():
            if "parameters" in details:
                print(f"Path: {path}, Method: {method}")
                print(f"Parameters: {json.dumps(details['parameters'], indent=2)}")


@app.get("/")
def root():
    return {"message": "API is running"}


@app.post("/transaction/retail/qris-generate")
async def create_retail_transaction_gen(data: GenerateQRISRequest = Body(...),
                                        current_user: User = Depends(get_current_user)):
    # customer_id, account_number, transaction_type, amount, currency, channel, branch_code, province, city
    # merchant_name, merchant_category
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
        "customer_id": current_user.customer_id,
        "account_number": data.account_number,
        "amount": data.amount,
        "currency": data.currency,
        "merchant_name": data.merchant_name,
        "merchant_category": data.merchant_category,
        "expired_at": expired_at,
        "status": "ACTIVE",
    }

    return  GenerateQRISResponse(qris_id=qris_id,
                                 qris_code=qris_code,
                                 expired_at=expired_at)

    print(current_user.customer_id)
    tx_dict = tx.model_dump(mode="json")
    await send_transaction(tx_dict)

    return {"status": "success", "transaction": tx_dict}


@app.post("/transaction/retail/qris-consume")
async def create_retail_transaction_consume(data: ConsumeQRISRequest = Body(...),
                                            current_user: User = Depends(get_current_user)):
    # customer_id, account_number, transaction_type, amount, currency, channel, branch_code, province, city
    # merchant_name, merchant_category
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

    now = datetime.utcnow()

    tx_dict = {
        "timestamp": now.isoformat(),
        "log_type": "transaction",
        "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
        "customer_id": current_user.customer_id,
        "account_number": data.account_number,
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

    await send_transaction(tx_dict)

    return ConsumeQRISResponse(qris_id=qris_id,
                              status="SUCCESS",
                               message=f"Payment of {qris_data['amount']} {qris_data['currency']} to {qris_data['merchant_name']} completed.")
    # print(current_user.customer_id)
    # tx_dict = tx.model_dump(mode="json")
    # await send_transaction(tx_dict)
    #
    # return {"status": "success", "transaction": tx_dict}


@app.post("/transaction/corporate")
async def create_corporate_transaction(request: Request,
                                       tx: TransactionCorporateInput = Body(...),
                                       current_user: User = Depends(get_current_user)):
    tx_dict = tx.model_dump()
    latitude = request.headers.get("X-Device-Lat")
    longitude = request.headers.get("X-Device-Lon")
    start_time = datetime.utcnow()
    end_time = datetime.utcnow()
    processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
    device_id = request.headers.get("X-Device-ID")
    device_type = request.headers.get("X-Device-Type")
    device_os = request.headers.get("X-Device-OS")
    device_browser = request.headers.get("X-Device-Browser")
    device_is_trusted = request.headers.get("X-Device-Trusted") == "true"
    ip_address = request.client.host
    user_agent = request.headers.get("user-agent")
    session_id = request.headers.get("X-Session-ID")

    tx_dict.update({
        "customer_id": current_user.customer_id,
        "timestamp": datetime.utcnow().isoformat(),
        "transaction_id": str(uuid.uuid4()),
        "log_type": "transaction",
        "customer_segment": "corporate",
        "status": "success",
        "latitude": latitude,
        "longitude": longitude,
        "processing_time_ms": processing_time_ms,
        "business_date": datetime.utcnow().date().isoformat(),
        "device_id": device_id,
        "device_type": device_type,
        "device_os": device_os,
        "device_browser": device_browser,
        "device_is_trusted": device_is_trusted,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "session_id": session_id,
    })

    await send_transaction(tx_dict)

    return {"status": "success", "transaction": tx_dict}


@app.post("/velocity-violation")
async def create_velocity_violation(tx: schemas.FraudDataLegitimate = Body(...),
                                 current_user: User = Depends(get_current_user)):
    # customer_id, time_window_hours, transaction_count, total_amount,
    # transaction (transaction_id, timestamp, amount, recipient, channel(dropdown: mobile_app, web, atm))
    print(current_user.customer_id)
    tx_dict = tx.model_dump(mode="json")
    await send_transaction(tx_dict)
    return {"status": "success", "transaction": tx_dict}


@app.post("/compliance-violation/aml-reporting")
async def create_velocity_violation(tx: schemas.FraudDataLegitimate = Body(...),
                                 current_user: User = Depends(get_current_user)):

    print(current_user.customer_id)
    tx_dict = tx.model_dump(mode="json")
    await send_transaction(tx_dict)
    return {"status": "success", "transaction": tx_dict}


@app.post("/compliance-violation/kyc-gap")
async def create_velocity_violation(tx: schemas.FraudDataLegitimate = Body(...),
                                 current_user: User = Depends(get_current_user)):

    print(current_user.customer_id)
    tx_dict = tx.model_dump(mode="json")
    await send_transaction(tx_dict)
    return {"status": "success", "transaction": tx_dict}


@app.post("/users/", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(models.User.username == user.username).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    last_user = db.query(models.User).order_by(models.User.created_at.desc()).first()

    if last_user and last_user.customer_id:
        last_number = int(last_user.customer_id.split("-")[1])

    else:
        last_number = 0

    new_customer_id = f"CUST-{last_number+1:06d}"
    hashed_pw = security.get_password_hash(user.password)
    db_user = models.User(username=user.username,
                          hashed_password=hashed_pw,
                          customer_id=new_customer_id)

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


@app.post("/auth/login")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    now = datetime.utcnow()
    timestamp_str = now.strftime("%Y-%m-%dT%H:%M:%S.%f")
    ip_address = request.client.host
    user_agent = request.headers.get("user-agent", "unknown")

    if form_data.username not in FAILED_LOGINS:
        FAILED_LOGINS[form_data.username] = []

    window = [a for a in FAILED_LOGINS[form_data.username]
              if datetime.fromisoformat(a["timestamp"]) > now - timedelta(minutes=30)]

    if not user or not security.verify_password(form_data.password, user.hashed_password):
        FAILED_LOGINS[form_data.username].append({
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

        window = [
            a for a in FAILED_LOGINS[form_data.username]
            if datetime.fromisoformat(a["timestamp"]) > now - timedelta(minutes=30)
        ]

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
                        "timestamp": a["timestamp"],
                        "ip_address": a["ip_address"],
                        "user_agent": a["user_agent"],
                        "failure_reason": a["failure_reason"],
                        "geolocation": a["geolocation"]
                    } for i, a in enumerate(window)
                ]
            }
            await send_transaction(alert)

        raise HTTPException(status_code=401, detail="Invalid credentials")

    FAILED_LOGINS[form_data.username] = []
    token = security.create_access_token({"sub": user.username})

    success_event = {
        "timestamp": timestamp_str,
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

    return {"access_token": token, "token_type": "bearer"}
