from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from dotenv import load_dotenv
import os
from sqlalchemy.engine import Engine
import sqlalchemy.dialects.sqlite  # Import the SQLite dialect directly

# Load environment variables
load_dotenv()

# Database Configuration
DATABASE_URL = os.getenv("DB_CONNECTION")
# DATABASE_URL = "sqlite:///./hita.db"

engine = create_engine(
    DATABASE_URL,
    pool_size=5,          # Number of connections to maintain in the pool
    max_overflow=10,      # Additional connections beyond pool_size
    pool_timeout=30,      # Timeout for getting connection from pool
    pool_recycle=3600,    # Recycle connections after 1 hour
    pool_pre_ping=True,   # Validate connections before use
    echo=False            # Set to True for SQL debugging
)

@event.listens_for(engine, "connect")
def enable_sqlite_fk_constraints(dbapi_connection, connection_record):
    # Check if the database dialect is SQLite
    if isinstance(engine.dialect, sqlalchemy.dialects.sqlite.dialect):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency to get DB session
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Connection pool health check
def get_pool_status():
    """Get current connection pool status"""
    pool = engine.pool
    return {
        "pool_size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "invalid": pool.invalid()
    }
