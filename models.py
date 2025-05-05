from sqlalchemy import create_engine, Column, Integer, String, DateTime, Enum as SQLEnum, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import MetaData
from enum import Enum
from datetime import datetime
from database import Base # Import Base from database.py

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
