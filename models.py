from sqlalchemy import create_engine, Column, Integer, String, DateTime, Enum as SQLEnum, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
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
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(SQLEnum(UserRole), default=UserRole.GENERAL_USER)
    api_key = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Blacklisted Token Model
class BlacklistedToken(Base):
    __tablename__ = "blacklisted_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# Point Transaction Model
class PointTransaction(Base):
    __tablename__ = "point_transactions"

    id = Column(Integer, primary_key=True, index=True)
    giver_id = Column(String(64), ForeignKey("users.id"))  
    giver_email = Column(String(255), ForeignKey("users.email")) 
    receiver_id = Column(String(64), ForeignKey("users.id"))
    receiver_email = Column(String(255), ForeignKey("users.email"))
    points = Column(Integer, nullable=False)
    transaction_type = Column(String(20), nullable=False) 
    created_at = Column(DateTime, default=datetime.utcnow)

# User Point Model
class UserPoint(Base):
    __tablename__ = "user_points"

    user_id = Column(String(10), ForeignKey("users.id"), primary_key=True)
    user_email = Column(String(255), ForeignKey("users.email")) 
    total_points = Column(Integer, default=0) 
    current_points = Column(Integer, default=0)
    total_used_points = Column(Integer, default=0) 
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
