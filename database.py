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

engine = create_engine(DATABASE_URL)

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
