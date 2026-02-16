from sqlalchemy.orm import Session
from sqlalchemy import or_
from models import FreeTrialRequest, FreeTrialStatus
from typing import Optional, List
import uuid


class FreeTrialRepository:
    """Repository for Free Trial Request database operations"""

    @staticmethod
    def create(
        db: Session,
        username: str,
        business_name: str,
        email: str,
        phone_number: str,
        message: Optional[str] = None,
    ) -> FreeTrialRequest:
        """Create a new free trial request"""
        request_id = str(uuid.uuid4())
        db_request = FreeTrialRequest(
            id=request_id,
            username=username,
            business_name=business_name,
            email=email,
            phone_number=phone_number,
            message=message,
            status=FreeTrialStatus.PENDING.value,
        )
        db.add(db_request)
        db.commit()
        db.refresh(db_request)
        return db_request

    @staticmethod
    def get_by_id(db: Session, request_id: str) -> Optional[FreeTrialRequest]:
        """Get a free trial request by ID"""
        return (
            db.query(FreeTrialRequest).filter(FreeTrialRequest.id == request_id).first()
        )

    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[FreeTrialRequest]:
        """Get a free trial request by email"""
        return (
            db.query(FreeTrialRequest).filter(FreeTrialRequest.email == email).first()
        )

    @staticmethod
    def get_all(
        db: Session,
        skip: int = 0,
        limit: int = 50,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[List[FreeTrialRequest], int]:
        """Get all free trial requests with optional filtering"""
        query = db.query(FreeTrialRequest)

        # Filter by status
        if status:
            query = query.filter(FreeTrialRequest.status == status)

        # Search filter
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    FreeTrialRequest.username.ilike(search_pattern),
                    FreeTrialRequest.business_name.ilike(search_pattern),
                    FreeTrialRequest.email.ilike(search_pattern),
                )
            )

        # Get total count
        total = query.count()

        # Apply pagination and ordering
        requests = (
            query.order_by(FreeTrialRequest.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return requests, total

    @staticmethod
    def update(
        db: Session,
        request_id: str,
        status: Optional[str] = None,
        notes: Optional[str] = None,
        updated_by: Optional[str] = None,
    ) -> Optional[FreeTrialRequest]:
        """Update a free trial request"""
        db_request = FreeTrialRepository.get_by_id(db, request_id)
        if not db_request:
            return None

        if status is not None:
            db_request.status = status
        if notes is not None:
            db_request.notes = notes
        if updated_by is not None:
            db_request.updated_by = updated_by

        db.commit()
        db.refresh(db_request)
        return db_request

    @staticmethod
    def delete(db: Session, request_id: str) -> bool:
        """Delete a free trial request"""
        db_request = FreeTrialRepository.get_by_id(db, request_id)
        if not db_request:
            return False

        db.delete(db_request)
        db.commit()
        return True

    @staticmethod
    def count_by_status(db: Session, status: str) -> int:
        """Count requests by status"""
        return (
            db.query(FreeTrialRequest).filter(FreeTrialRequest.status == status).count()
        )
