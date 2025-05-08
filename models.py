from sqlalchemy import create_engine, Column, Integer, String, DateTime, Enum as SQLEnum, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy import MetaData
from enum import Enum
from datetime import datetime
from database import Base

# User Roles
class UserRole(str, Enum):
    SUPER_USER = "super_user"
    ADMIN_USER = "admin_user"
    GENERAL_USER = "general_user"

# User Model
class User(Base):
    __tablename__ = "users"

    id = Column(String(10), primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    email = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(255))
    role = Column(SQLEnum(UserRole), default=UserRole.GENERAL_USER)
    api_key = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sent_transactions = relationship("PointTransaction", foreign_keys="[PointTransaction.giver_id]", back_populates="giver")
    received_transactions = relationship("PointTransaction", foreign_keys="[PointTransaction.receiver_id]", back_populates="receiver")
    user_points = relationship("UserPoint", back_populates="user", foreign_keys="[UserPoint.user_id]")  # Explicitly specify foreign_keys


# Blacklisted Token Model
class BlacklistedToken(Base):
    __tablename__ = "blacklisted_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(255), unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# Point Transaction Model
class PointTransaction(Base):
    __tablename__ = "point_transactions"

    id = Column(Integer, primary_key=True, index=True)
    giver_id = Column(String(10), ForeignKey("users.id"))
    giver_email = Column(String(100), ForeignKey("users.email"))
    receiver_id = Column(String(10), ForeignKey("users.id"))
    receiver_email = Column(String(100), ForeignKey("users.email"))
    points = Column(Integer, nullable=False)
    transaction_type = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    giver = relationship("User", foreign_keys=[giver_id], back_populates="sent_transactions")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_transactions")

# User Point Model
class UserPoint(Base):
    __tablename__ = "user_points"

    user_id = Column(String(10), ForeignKey("users.id"), primary_key=True)
    user_email = Column(String(100), ForeignKey("users.email"))
    total_points = Column(Integer, default=0)
    current_points = Column(Integer, default=0)
    total_used_points = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="user_points", foreign_keys=[user_id])  # Explicitly specify foreign_keys