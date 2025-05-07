from sqlalchemy.orm import Session
from database import SessionLocal
import models
from passlib.context import CryptContext
import secrets

# Use bcrypt for password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

def create_super_admin():
    db: Session = SessionLocal()
    try:
        # Check if a super_user already exists
        existing_super_user = db.query(models.User).filter(models.User.role == models.UserRole.SUPER_USER).first()
        if existing_super_user:
            print("A super_user already exists.")
            return

        # Generate a fixed or random password and hash it
        plain_password = "ursamroko123"  
        hashed_password = get_password_hash(plain_password)

        # Generate a unique ID
        unique_id = secrets.token_hex(5)

        # Create the super_user
        super_user = models.User(
            id=unique_id,
            username="ursamroko",
            email="ursamroko@romel.com",
            hashed_password=hashed_password,
            role=models.UserRole.SUPER_USER,
            is_active=True
        )
        db.add(super_user)
        db.commit()
        print(f"Super user created successfully! Login password: {plain_password}")
    finally:
        db.close()

if __name__ == "__main__":
    create_super_admin()
