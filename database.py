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
    pool_size=10,  # Increased pool size for better concurrency
    max_overflow=20,  # Increased overflow for burst traffic
    pool_timeout=15,  # Reduced timeout for faster failover
    pool_recycle=1800,  # Recycle connections more frequently (30 min)
    pool_pre_ping=True,  # Validate connections before use
    pool_use_lifo=True,  # Use LIFO for better connection reuse
    echo=False,  # Set to True for SQL debugging
)


@event.listens_for(engine, "connect")
def enable_sqlite_fk_constraints(dbapi_connection, connection_record):
    # Check if the database dialect is SQLite
    if isinstance(engine.dialect, sqlalchemy.dialects.sqlite.dialect):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        # Enable WAL mode for better concurrency (allows reads during writes)
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")  # Faster writes, still safe
        cursor.execute("PRAGMA busy_timeout=30000")  # 30 second timeout for locks
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
        "invalid": pool.invalid(),
    }
