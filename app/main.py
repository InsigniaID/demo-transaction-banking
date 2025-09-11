import uuid
from datetime import datetime, timedelta

from fastapi import FastAPI, Depends, HTTPException, security, Request, Body
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
from . import schemas, database, models, security
from .auth import get_current_user
from .kafka_producer import init_kafka, shutdown_kafka, send_transaction
from .models import User
from .schemas import TransactionCorporateInput

database.Base.metadata.create_all(bind=database.engine)
app = FastAPI()
FAILED_LOGINS = {}


def get_db():
    db = database.SessionLocal()

    try:
        yield db

    finally:
        db.close()


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


@app.post("/transaction/retail")
async def create_retail_transaction(tx: schemas.TransactionRetail = Body(...),
                                    current_user: User = Depends(get_current_user)):
    # customer_id, account_number, transaction_type, amount, currency, channel, branch_code, province, city
    # merchant_name, merchant_category
    print(current_user.customer_id)
    tx_dict = tx.model_dump(mode="json")
    await send_transaction(tx_dict)

    return {"status": "success", "transaction": tx_dict}


@app.post("/transaction/corporate")
async def create_corporate_transaction(request: Request,
                                       tx: TransactionCorporateInput = Body(...),
                                       current_user: User = Depends(get_current_user)):
    tx_dict = tx.model_dump()
    latitude = request.headers.get("X-Device-Lat")
    longitude = request.headers.get("X-Device-Lon")
    start_time = datetime.utcnow()
    # ... logic send_transaction ...
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

        if len(window) >= 3:
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

    return {"access_token": token, "token_type": "bearer"}
