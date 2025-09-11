import uuid
from pydantic import BaseModel, validator
from zoneinfo import ZoneInfo
from typing import List, Optional, Literal
from datetime import datetime


class UserBase(BaseModel):
    username: str


class UserCreate(UserBase):
    password: str
    pin: Optional[str] = "123456"


class UserResponse(UserBase):
    id: uuid.UUID
    customer_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


class PINValidationRequest(BaseModel):
    pin: str


class PINValidationResponse(BaseModel):
    valid: bool
    message: str


class TransactionCorporateInput(BaseModel):
    account_number: str
    transaction_type: Literal["pos_purchase", "withdrawal", "transfer", "salary_credit", "bill_payment"]
    amount: float
    currency: str
    channel: Literal["mobile_app", "web", "atm"]
    branch_code: str
    province: str
    city: str
    merchant_name: str
    merchant_category: str
    merchant_id: str
    terminal_id: str
    pin: str
    
    # Enhanced fields for real case simulation
    recipient_account_number: Optional[str] = None
    recipient_account_name: Optional[str] = None
    recipient_bank_code: Optional[str] = None
    transaction_description: Optional[str] = None
    reference_number: Optional[str] = None


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

class GenerateQRISRequest(BaseModel):
    account_number: str
    amount: float
    currency: str = "IDR"
    merchant_name: str
    merchant_category: str
    pin: str


class GenerateQRISResponse(BaseModel):
    qris_id: str
    qris_code: str
    expired_at: datetime


class ConsumeQRISRequest(BaseModel):
    qris_code: str
    customer_id: str
    account_number: str
    pin: str


class ConsumeQRISResponse(BaseModel):
    qris_id: str
    status: str
    message: str
