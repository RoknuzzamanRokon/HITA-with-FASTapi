"""
Script to create the free_trial_requests table
Run this script to add the table to your database
"""

from database import engine, Base
from models import FreeTrialRequest
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_free_trial_table():
    """Create the free_trial_requests table"""
    try:
        # Create only the FreeTrialRequest table
        FreeTrialRequest.__table__.create(bind=engine, checkfirst=True)
        logger.info("✓ Successfully created free_trial_requests table")
        return True
    except Exception as e:
        logger.error(f"✗ Error creating table: {e}")
        return False


if __name__ == "__main__":
    logger.info("Creating free_trial_requests table...")
    success = create_free_trial_table()

    if success:
        logger.info("\n✓ Table creation completed successfully!")
        logger.info("\nYou can now:")
        logger.info("1. Start your FastAPI server")
        logger.info("2. Access the API at /api/free-trial/submit")
        logger.info("3. View API docs at /docs")
    else:
        logger.error(
            "\n✗ Table creation failed. Please check the error messages above."
        )
