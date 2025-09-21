import uuid
from pydantic import BaseModel, validator
from zoneinfo import ZoneInfo
from typing import List, Optional, Literal, Dict, Any
from datetime import datetime
from decimal import Decimal


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


class UserWithAccountsResponse(UserBase):
    id: uuid.UUID
    customer_id: str
    created_at: datetime
    updated_at: datetime
    accounts: List['AccountResponse']

    class Config:
        from_attributes = True


class RegisterResponse(BaseModel):
    user: UserResponse
    message: str
    default_account_number: str


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
    crash_type: Optional[str] = None


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
    pin: Optional[str] = None  # PIN not required for generate QRIS


class GenerateQRISResponse(BaseModel):
    qris_id: str
    qris_code: str
    expired_at: datetime


class ConsumeQRISRequest(BaseModel):
    qris_code: str
    pin: str
    crash_type: Optional[str] = None


class ConsumeQRISResponse(BaseModel):
    qris_id: str
    status: str
    message: str


# Account and Transaction History Schemas
class AccountResponse(BaseModel):
    id: uuid.UUID
    account_number: str
    account_type: str
    balance: Decimal
    currency: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TransactionHistoryResponse(BaseModel):
    id: uuid.UUID
    transaction_id: str
    transaction_type: str
    amount: Decimal
    currency: str
    balance_before: Decimal
    balance_after: Decimal
    status: str
    description: Optional[str] = None
    reference_number: Optional[str] = None
    recipient_account: Optional[str] = None
    recipient_name: Optional[str] = None
    channel: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AccountBalanceResponse(BaseModel):
    account_number: str
    balance: Decimal
    currency: str
    account_type: str
    status: str


class CreateAccountRequest(BaseModel):
    account_type: Literal["savings", "checking", "corporate"] = "savings"
    initial_balance: Optional[Decimal] = Decimal("0.00")


class EnhancedLoginRequest(BaseModel):
    username: str
    password: str
    locationDetectionEnabled: Optional[bool] = False
    selectedLocation: Optional[str] = ""
    crashSimulatorEnabled: Optional[bool] = False
    crashType: Optional[str] = ""
    databaseErrorSimulationEnabled: Optional[bool] = False


class LocationInfo(BaseModel):
    city: str
    country: str = "Indonesia"
    latitude: float
    longitude: float
    travel_time_minutes: Optional[int] = None
    distance_km: Optional[float] = None


class SuspiciousActivity(BaseModel):
    isSuspicious: bool
    suspicionLevel: Optional[str] = None  # "low", "medium", "high"
    reason: Optional[str] = None
    details: Optional[List[str]] = []
    score: Optional[int] = 0


class StandardKafkaEvent(BaseModel):
    # Core timestamp and logging
    timestamp: datetime
    log_type: str

    # Login specific fields
    login_status: Optional[str] = None  # "success", "failed", "error"
    customer_id: Optional[str] = None

    # Alert fields
    alert_type: Optional[str] = None
    alert_severity: Optional[str] = None
    failed_attempts: Optional[int] = None
    time_window_minutes: Optional[int] = None
    login_attempts: Optional[List[dict]] = None

    # Transaction fields
    transaction_id: Optional[str] = None
    customer_segment: Optional[str] = None
    status: Optional[str] = None
    processing_time_ms: Optional[int] = None
    business_date: Optional[str] = None
    transaction_fee: Optional[float] = None
    total_amount: Optional[float] = None
    account_balance_before: Optional[float] = None
    account_balance_after: Optional[float] = None
    attempted_amount: Optional[float] = None
    currency: Optional[str] = None
    attempted_transaction_type: Optional[str] = None
    attempted_channel: Optional[str] = None
    attempted_account_number: Optional[str] = None
    attempted_recipient_account: Optional[str] = None
    attempted_merchant_name: Optional[str] = None
    attempted_merchant_category: Optional[str] = None

    # Authentication fields
    auth_method: Optional[str] = None
    auth_success: Optional[bool] = None
    auth_timestamp: Optional[datetime] = None

    # Error fields
    error_type: Optional[str] = None
    error_code: Optional[str] = None
    error_detail: Optional[str] = None
    validation_stage: Optional[str] = None

    # Transaction details
    transaction_description: Optional[str] = None
    recipient_account_number: Optional[str] = None
    recipient_account_name: Optional[str] = None
    recipient_bank_code: Optional[str] = None
    reference_number: Optional[str] = None

    # Risk and compliance
    risk_assessment_score: Optional[float] = None
    fraud_indicator: Optional[str] = None
    aml_screening_result: Optional[str] = None
    sanction_screening_result: Optional[str] = None
    compliance_status: Optional[str] = None

    # Settlement
    settlement_date: Optional[str] = None
    settlement_status: Optional[str] = None
    clearing_code: Optional[str] = None

    # Request details
    transaction_type: Optional[str] = None
    requested_amount: Optional[float] = None
    failure_reason: Optional[str] = None
    failure_message: Optional[str] = None
    limits: Optional[dict] = None
    account_number: Optional[str] = None
    amount: Optional[float] = None
    channel: Optional[str] = None
    branch_code: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    merchant_name: Optional[str] = None
    merchant_category: Optional[str] = None
    merchant_id: Optional[str] = None
    terminal_id: Optional[str] = None

    # Location and device
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    device_id: Optional[str] = None
    device_type: Optional[str] = None
    device_os: Optional[str] = None
    device_browser: Optional[str] = None
    device_is_trusted: Optional[bool] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None

    # Customer demographics
    customer_age: Optional[int] = None
    customer_gender: Optional[str] = None
    customer_occupation: Optional[str] = None
    customer_income_bracket: Optional[str] = None
    customer_education: Optional[str] = None
    customer_marital_status: Optional[str] = None
    customer_monthly_income: Optional[float] = None
    customer_credit_limit: Optional[float] = None
    customer_risk_score: Optional[float] = None
    customer_kyc_level: Optional[str] = None
    customer_pep_status: Optional[bool] = None
    customer_previous_fraud_incidents: Optional[int] = None

    # Additional fields
    device_fingerprint: Optional[str] = None
    qris_id: Optional[str] = None
    transaction_reference: Optional[str] = None
    interchange_fee: Optional[float] = None
    db_transaction_id: Optional[str] = None
    balance_after: Optional[float] = None
    qris_status: Optional[str] = None


class EnhancedLoginResponse(BaseModel):
    access_token: Optional[str] = None
    token_type: str = "bearer"
    success: bool = False
    error: Optional[str] = None
    suspiciousActivity: Optional[SuspiciousActivity] = None


class DetectionResult(BaseModel):
    total: int
    normal: int
    anomaly: int
    details: List[Dict[str, Any]]