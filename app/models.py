import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, Integer, String, DateTime, func
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    customer_id = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(), default=datetime.now(), nullable=False)
    updated_at = Column(DateTime(), default=datetime.now(),
                        onupdate=datetime.now(), nullable=False)


class FailedLogin(Base):
    __tablename__ = "failed_logins"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    ip_address = Column(String)
    user_agent = Column(String)
    failure_reason = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)