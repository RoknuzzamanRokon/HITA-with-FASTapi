from sqlalchemy.orm import Session
from database import SessionLocal
import models
import secrets

def create_super_user():
    db: Session = SessionLocal()
    try:
        # Check if a super_user already exists
        existing_super_user = db.query(models.User).filter(models.User.role == models.UserRole.SUPER_USER).first()
        if existing_super_user:
            print("A super_user already exists.")
            return

        # Generate a unique ID and hashed password
        unique_id = secrets.token_hex(5)
        hashed_password = secrets.token_hex(8)  # Replace with a proper password hashing function

        # Create the super_user
        super_user = models.User(
            id=unique_id,
            username="superuser",
            email="superuser@example.com",
            hashed_password=hashed_password,
            role=models.UserRole.SUPER_USER,
            is_active=True
        )
        db.add(super_user)
        db.commit()
        print("Super user created successfully!")
    finally:
        db.close()

if __name__ == "__main__":
    create_super_user()