import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, Integer, String, DateTime, func, ForeignKey, Numeric, Text
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    hashed_pin = Column(String, nullable=False)
    customer_id = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(), default=datetime.now(), nullable=False)
    updated_at = Column(DateTime(), default=datetime.now(),
                        onupdate=datetime.now(), nullable=False)
    
    # Relationships
    accounts = relationship("Account", back_populates="user")
    transaction_histories = relationship("TransactionHistory", back_populates="user")


class FailedLogin(Base):
    __tablename__ = "failed_logins"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    ip_address = Column(String)
    user_agent = Column(String)
    failure_reason = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)


class Account(Base):
    __tablename__ = "accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    account_number = Column(String, unique=True, index=True, nullable=False)
    account_type = Column(String, nullable=False)  # savings, checking, corporate
    balance = Column(Numeric(15, 2), default=0.00, nullable=False)
    currency = Column(String, default="IDR", nullable=False)
    status = Column(String, default="active", nullable=False)  # active, suspended, closed
    created_at = Column(DateTime(), default=datetime.now(), nullable=False)
    updated_at = Column(DateTime(), default=datetime.now(),
                        onupdate=datetime.now(), nullable=False)
    
    # Relationship
    user = relationship("User", back_populates="accounts")


class TransactionHistory(Base):
    __tablename__ = "transaction_histories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    transaction_id = Column(String, unique=True, index=True, nullable=False)
    transaction_type = Column(String, nullable=False)  # transfer, withdrawal, pos_purchase, etc.
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String, default="IDR", nullable=False)
    balance_before = Column(Numeric(15, 2), nullable=False)
    balance_after = Column(Numeric(15, 2), nullable=False)
    status = Column(String, nullable=False)  # success, failed, pending
    description = Column(Text)
    reference_number = Column(String)
    recipient_account = Column(String)
    recipient_name = Column(String)
    channel = Column(String)  # mobile_app, web, atm
    created_at = Column(DateTime(timezone=True), default=datetime.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="transaction_histories")
    account = relationship("Account")


class QRISTransaction(Base):
    __tablename__ = "qris_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    qris_id = Column(String, unique=True, index=True, nullable=False)
    customer_id = Column(String, nullable=False)
    account_number = Column(String, nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String, default="IDR", nullable=False)
    merchant_name = Column(String, nullable=False)
    merchant_category = Column(String, nullable=False)
    qris_code = Column(Text, nullable=False)
    status = Column(String, default="ACTIVE", nullable=False)  # ACTIVE, CONSUMED, EXPIRED
    expired_at = Column(DateTime(), nullable=False)
    created_at = Column(DateTime(), default=datetime.now(), nullable=False)