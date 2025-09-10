from pydantic import BaseModel

from typing import List, Optional
from datetime import datetime
from sqlalchemy import Column, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID, unique=True, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)


class UserCreate(BaseModel):
    username: str
    password: str
    createdAt: datetime
    updatedAt: datetime


class UserResponse(BaseModel):
    id: int
    username: str

    class Config:
        orm_mode = True


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


class TransactionRetail(BaseModel):
    timestamp: datetime
    log_type: str
    transaction_id: str
    customer_id: str
    account_number: str
    customer_segment: str
    transaction_type: str
    amount: float
    currency: str
    channel: str
    status: str
    branch_code: str
    province: str
    city: str
    latitude: float
    longitude: float
    processing_time_ms: int
    business_date: datetime
    customer_age: int
    customer_gender: str
    customer_occupation: str
    customer_income_bracket: str
    customer_education: str
    customer_marital_status: str
    customer_monthly_income: float
    customer_credit_limit: float
    customer_savings_balance: float
    customer_risk_score: float
    customer_kyc_level: str
    customer_pep_status: bool
    customer_previous_fraud_incidents: int
    device_id: str
    device_type: str
    device_os: str
    device_browser: str
    device_is_trusted: bool
    ip_address: str
    user_agent: str
    session_id: str
    merchant_name: str
    merchant_category: str
    merchant_id: str
    terminal_id: str


class TransactionFraud(BaseModel):
    transaction_id: str
    from_account: str
    to_account: str
    amount: float
    timestamp: str


class RealisticTransactionRetail(BaseModel):
    timestamp: datetime
    log_type: str
    transaction_id: str
    customer_id: str
    account_number: str
    customer_segment: str
    transaction_type: str
    amount: float
    currency: str
    channel: str
    status: str
    branch_code: str
    province: str
    city: str
    latitude: float
    longitude: float
    processing_time_ms: int
    business_date: str
    customer_age: int
    customer_gender: str
    customer_occupation: str
    customer_income_bracket: str
    customer_education: str
    customer_marital_status: str
    customer_monthly_income: float
    customer_credit_limit: float
    customer_savings_balance: float
    customer_risk_score: float
    customer_kyc_level: str
    customer_pep_status: bool
    customer_previous_fraud_incidents: int
    device_id: str
    device_type: str
    device_os: str
    device_browser: str
    device_is_trusted: bool
    ip_address: str
    user_agent: str
    session_id: str
    merchant_name: str
    merchant_category: str
    merchant_id: str
    terminal_id: str

class FraudDataLegitimate(BaseModel):
    timestamp: datetime
    log_type: str
    transaction_id: str
    customer_id: str
    account_number: str
    customer_segment: str
    transaction_type: str
    amount: float
    currency: str
    channel: str
    status: str
    branch_code: str
    province: str
    city: str
    latitude: float
    longitude: float
    processing_time_ms: int
    business_date: str
    customer_age: int
    customer_gender: str
    customer_occupation: str
    customer_income_bracket: str
    customer_education: str
    customer_marital_status: str
    customer_monthly_income: float
    customer_credit_limit: float
    customer_savings_balance: float
    customer_risk_score: float
    customer_kyc_level: str
    customer_pep_status: bool
    customer_previous_fraud_incidents: int
    is_fraud: bool
    fraud_type: Optional[str]
    fraud_indicators: List[str]
    legitimate_indicators: List[str]
    fraud_confidence: float
    investigation_priority: str
    ml_model_score: float
    rule_based_score: float
    final_fraud_score: float

class LoginAttempt(BaseModel):
    attempt_number: int
    timestamp: datetime
    ip_address: str
    user_agent: str
    failure_reason: str
    geolocation: dict

class AlertScenarioMultipleFailedLogin(BaseModel):
    timestamp: datetime
    log_type: str
    alert_type: str
    customer_id: str
    alert_severity: str
    failed_attempts: int
    time_window_minutes: int
    login_attempts: List[LoginAttempt]
