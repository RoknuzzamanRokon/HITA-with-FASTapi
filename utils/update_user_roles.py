# Add the project directory to the Python path
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from sqlalchemy import update
from models import User
from database import get_db

def update_user_roles():
    db: Session = next(get_db())
    try:
        # Update roles to match new enum values
        db.execute(update(User).where(User.role == 'SUPER_USER').values(role='super_user'))
        db.execute(update(User).where(User.role == 'ADMIN_USER').values(role='admin_user'))
        db.execute(update(User).where(User.role == 'GENERAL_USER').values(role='general_user'))
        db.commit()
        print("User roles updated successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error updating user roles: {e}")

if __name__ == "__main__":
    update_user_roles()
