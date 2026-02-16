from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from database import get_db
from schemas import (
    FreeTrialRequestCreate,
    FreeTrialRequestUpdate,
    FreeTrialRequestResponse,
    FreeTrialRequestListResponse,
)
from services.free_trial_service import FreeTrialService
from routes.auth import get_current_user
from models import User, UserRole
from typing import Optional

router = APIRouter(prefix="/v1.0/free-trial", tags=["Free Trial"])


def get_current_superuser(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to verify user is a superuser"""
    if current_user.role != UserRole.SUPER_USER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can access this resource",
        )
    return current_user


@router.post(
    "/submit",
    response_model=FreeTrialRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Free Trial Request",
    description="Submit a new free trial registration request. No authentication required.",
)
async def submit_free_trial_request(
    request_data: FreeTrialRequestCreate,
    db: Session = Depends(get_db),
):
    """
    Submit a free trial request with the following information:
    - username: User's full name
    - business_name: Company or business name
    - email: Valid email address (must be unique)
    - phone_number: Contact phone number
    - message: Optional message or inquiry from the user
    """
    result = FreeTrialService.create_request(db, request_data)
    return result


@router.get(
    "/requests",
    response_model=FreeTrialRequestListResponse,
    summary="Get All Free Trial Requests",
    description="Retrieve all free trial requests with optional filtering. Superuser only.",
)
async def get_all_requests(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        50, ge=1, le=100, description="Maximum number of records to return"
    ),
    status: Optional[str] = Query(
        None, description="Filter by status: pending, approved, rejected, contacted"
    ),
    search: Optional[str] = Query(
        None, description="Search by username, business name, or email"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """
    Get all free trial requests with pagination and filtering options.
    Only accessible by superusers.
    """
    return FreeTrialService.get_all_requests(
        db=db, skip=skip, limit=limit, status=status, search=search
    )


@router.get(
    "/requests/{request_id}",
    response_model=FreeTrialRequestResponse,
    summary="Get Free Trial Request by ID",
    description="Retrieve a specific free trial request. Superuser only.",
)
async def get_request_by_id(
    request_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """
    Get a specific free trial request by its ID.
    Only accessible by superusers.
    """
    return FreeTrialService.get_request_by_id(db, request_id)


@router.put(
    "/requests/{request_id}",
    response_model=FreeTrialRequestResponse,
    summary="Update Free Trial Request",
    description="Update the status and notes of a free trial request. Superuser only.",
)
async def update_request(
    request_id: str,
    update_data: FreeTrialRequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """
    Update a free trial request's status and/or notes.
    Only accessible by superusers.

    Status options: pending, approved, rejected, contacted
    """
    return FreeTrialService.update_request(
        db=db,
        request_id=request_id,
        update_data=update_data,
        updated_by=current_user.email,
    )


@router.delete(
    "/requests/{request_id}",
    summary="Delete Free Trial Request",
    description="Delete a free trial request. Superuser only.",
)
async def delete_request(
    request_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """
    Delete a free trial request by its ID.
    Only accessible by superusers.
    """
    return FreeTrialService.delete_request(db, request_id)


@router.get(
    "/statistics",
    summary="Get Free Trial Statistics",
    description="Get statistics about free trial requests. Superuser only.",
)
async def get_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """
    Get statistics showing count of requests by status.
    Only accessible by superusers.
    """
    return FreeTrialService.get_statistics(db)
