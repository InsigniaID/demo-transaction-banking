from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, security, Request
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
from . import schemas, database, models, auth, security
from .kafka_producer import init_kafka, shutdown_kafka, send_transaction

models.Base.metadata.create_all(bind=database.engine)
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


@app.post("/transaction/retail")
async def create_retail_transaction(tx: schemas.TransactionRetail):
    tx_dict = tx.model_dump(mode="json")
    await send_transaction(tx_dict)

    return {"status": "success", "transaction": tx_dict}


@app.post("/transfer/retail")
async def create_transfer_transaction(tx: schemas.FraudDataLegitimate):
    tx_dict = tx.model_dump(mode="json")
    await send_transaction(tx_dict)

    return {"status": "success", "transaction": tx_dict}


@app.post("/users/", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(models.User.username == user.username).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    hashed_pw = security.get_password_hash(user.password)
    db_user = models.User(username=user.username, hashed_password=hashed_pw)

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user

@app.post("/auth/login")
def login(request: Request, form_data: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    now = datetime.utcnow()
    ip_address = request.client.host
    user_agent = request.headers.get("user-agent", "unknown")

    if form_data.username not in FAILED_LOGINS:
        FAILED_LOGINS[form_data.username] = []

    if not user or not security.verify_password(form_data.password, user.hashed_password):
        FAILED_LOGINS[form_data.username].append({
            "timestamp": now.isoformat(),
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

        attempts = FAILED_LOGINS[form_data.username]
        # filter hanya 30 menit terakhir
        window = [a for a in attempts if datetime.fromisoformat(a["timestamp"]) > now - timedelta(minutes=30)]

        if len(window) >= 3:
            return {
                "timestamp": now.isoformat(),
                "log_type": "security_alert",
                "alert_type": "multiple_failed_login",
                "customer_id": f"CUST-{user.id:06d}" if user else "UNKNOWN",
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

        raise HTTPException(status_code=401, detail="Invalid credentials")

    FAILED_LOGINS[form_data.username] = []
    token = security.create_access_token({"sub": user.username})

    return {"access_token": token, "token_type": "bearer"}