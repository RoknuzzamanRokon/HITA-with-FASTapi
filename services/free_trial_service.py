from sqlalchemy.orm import Session
from repositories.free_trial_repository import FreeTrialRepository
from schemas import (
    FreeTrialRequestCreate,
    FreeTrialRequestUpdate,
    FreeTrialRequestResponse,
    FreeTrialRequestListResponse,
)
from fastapi import HTTPException, status
from typing import Optional


class FreeTrialService:
    """Service layer for Free Trial Request business logic"""

    @staticmethod
    def create_request(
        db: Session, request_data: FreeTrialRequestCreate
    ) -> FreeTrialRequestResponse:
        """Create a new free trial request"""
        # Check if email already exists
        existing = FreeTrialRepository.get_by_email(db, request_data.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A free trial request with this email already exists",
            )

        # Create the request
        db_request = FreeTrialRepository.create(
            db=db,
            username=request_data.username,
            business_name=request_data.business_name,
            email=request_data.email,
            phone_number=request_data.phone_number,
            message=request_data.message,
        )

        return FreeTrialRequestResponse.from_orm(db_request)

    @staticmethod
    def get_request_by_id(db: Session, request_id: str) -> FreeTrialRequestResponse:
        """Get a free trial request by ID"""
        db_request = FreeTrialRepository.get_by_id(db, request_id)
        if not db_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Free trial request not found",
            )

        return FreeTrialRequestResponse.from_orm(db_request)

    @staticmethod
    def get_all_requests(
        db: Session,
        skip: int = 0,
        limit: int = 50,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> FreeTrialRequestListResponse:
        """Get all free trial requests with filtering"""
        # Validate limit
        if limit > 100:
            limit = 100

        requests, total = FreeTrialRepository.get_all(
            db=db, skip=skip, limit=limit, status=status, search=search
        )

        return FreeTrialRequestListResponse(
            total=total,
            skip=skip,
            limit=limit,
            data=[FreeTrialRequestResponse.from_orm(req) for req in requests],
        )

    @staticmethod
    def update_request(
        db: Session,
        request_id: str,
        update_data: FreeTrialRequestUpdate,
        updated_by: str,
    ) -> FreeTrialRequestResponse:
        """Update a free trial request"""
        # Check if request exists
        db_request = FreeTrialRepository.get_by_id(db, request_id)
        if not db_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Free trial request not found",
            )

        # Update the request
        updated_request = FreeTrialRepository.update(
            db=db,
            request_id=request_id,
            status=update_data.status,
            notes=update_data.notes,
            updated_by=updated_by,
        )

        return FreeTrialRequestResponse.from_orm(updated_request)

    @staticmethod
    def delete_request(db: Session, request_id: str) -> dict:
        """Delete a free trial request"""
        success = FreeTrialRepository.delete(db, request_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Free trial request not found",
            )

        return {"message": "Free trial request deleted successfully"}

    @staticmethod
    def get_statistics(db: Session) -> dict:
        """Get statistics about free trial requests"""
        return {
            "pending": FreeTrialRepository.count_by_status(db, "pending"),
            "approved": FreeTrialRepository.count_by_status(db, "approved"),
            "rejected": FreeTrialRepository.count_by_status(db, "rejected"),
            "contacted": FreeTrialRepository.count_by_status(db, "contacted"),
        }
