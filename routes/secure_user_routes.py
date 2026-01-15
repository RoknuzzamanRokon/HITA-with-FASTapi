"""
Enhanced Secure User Routes

This module demonstrates how to integrate the new security features
into user management endpoints with comprehensive validation,
rate limiting, and audit logging.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from typing import Annotated, Optional, Dict, Any
from datetime import datetime

from database import get_db
from routes.auth import get_current_user
import models
from user_schemas import (
    UserCreateRequest,
    UserUpdateRequest,
    UserListResponse,
    APIError,
    ValidationError,
)

# Import security components
from security import (
    SecurityValidator,
    InputSanitizer,
    AuditLogger,
    ActivityType,
    SecurityLevel,
    rate_limit,
    validate_user_permissions,
    log_user_action,
    check_rate_limit_manual,
)

router = APIRouter(
    prefix="/v1.0/user/secure",
    tags=["Secure User Management"],
    responses={404: {"description": "Not found"}},
)


@router.post("/create", response_model=UserListResponse)
@rate_limit("user_creation", use_user_id=True)
async def create_user_secure(
    request: Request,
    user_data: UserCreateRequest,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Create a new user with enhanced security validation and audit logging

    This endpoint demonstrates the integration of:
    - Advanced input validation and sanitization
    - Rate limiting (5 requests per 5 minutes)
    - Comprehensive audit logging
    - Role-based access control
    """

    # Initialize security components
    security_validator = SecurityValidator()
    audit_logger = AuditLogger(db)

    try:
        # Log the attempt
        audit_logger.log_activity(
            activity_type=ActivityType.USER_CREATED,
            user_id=current_user.id,
            details={
                "attempted_username": user_data.username,
                "attempted_email": user_data.email,
                "attempted_role": user_data.role.value if user_data.role else None,
                "status": "attempt",
            },
            request=request,
            security_level=SecurityLevel.MEDIUM,
        )

        # Validate user permissions
        allowed_roles = [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER]
        validate_user_permissions(current_user, allowed_roles)

        # Additional role-specific validation
        if current_user.role == models.UserRole.ADMIN_USER:
            if user_data.role != models.UserRole.GENERAL_USER:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": True,
                        "message": "Admin users can only create general users",
                        "error_code": "INSUFFICIENT_PERMISSIONS",
                    },
                )

        # Comprehensive input validation
        validation_data = {
            "username": user_data.username,
            "email": user_data.email,
            "password": user_data.password,
            "role": user_data.role.value if user_data.role else None,
        }

        validation_result = security_validator.validate_user_creation_data(
            validation_data
        )

        if not validation_result["is_valid"]:
            # Log validation failure
            audit_logger.log_activity(
                activity_type=ActivityType.USER_CREATED,
                user_id=current_user.id,
                details={
                    "status": "validation_failed",
                    "validation_errors": validation_result["errors"],
                    "attempted_data": {
                        "username": user_data.username,
                        "email": user_data.email,
                        "role": user_data.role.value if user_data.role else None,
                    },
                },
                request=request,
                security_level=SecurityLevel.MEDIUM,
                success=False,
            )

            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=ValidationError(
                    message="User creation validation failed",
                    error_code="VALIDATION_ERROR",
                    field_errors=validation_result["errors"],
                ).dict(),
            )

        # Check for existing users
        existing_user = (
            db.query(models.User)
            .filter(
                (models.User.email == validation_result["sanitized_data"]["email"])
                | (
                    models.User.username
                    == validation_result["sanitized_data"]["username"]
                )
            )
            .first()
        )

        if existing_user:
            # Log duplicate attempt
            audit_logger.log_security_event(
                activity_type=ActivityType.SUSPICIOUS_ACTIVITY,
                user_id=current_user.id,
                request=request,
                details={
                    "reason": "duplicate_user_creation_attempt",
                    "existing_user_id": existing_user.id,
                    "attempted_username": user_data.username,
                    "attempted_email": user_data.email,
                },
                security_level=SecurityLevel.MEDIUM,
            )

            conflict_field = (
                "email" if existing_user.email == user_data.email else "username"
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": True,
                    "message": f"User with this {conflict_field} already exists",
                    "error_code": "DUPLICATE_USER",
                    "conflicting_field": conflict_field,
                },
            )

        # Create the user (simplified - in practice, use your existing user creation logic)
        import secrets
        from passlib.context import CryptContext

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        new_user = models.User(
            id=secrets.token_hex(5),
            username=validation_result["sanitized_data"]["username"],
            email=validation_result["sanitized_data"]["email"],
            hashed_password=pwd_context.hash(user_data.password),
            role=user_data.role or models.UserRole.GENERAL_USER,
            is_active=True,
            created_by=f"{current_user.role.lower()}: {current_user.email}",
            created_at=datetime.utcnow(),
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        # Log successful creation
        audit_logger.log_activity(
            activity_type=ActivityType.USER_CREATED,
            user_id=current_user.id,
            target_user_id=new_user.id,
            details={
                "status": "success",
                "created_user": {
                    "id": new_user.id,
                    "username": new_user.username,
                    "email": new_user.email,
                    "role": new_user.role.value,
                },
            },
            request=request,
            security_level=SecurityLevel.MEDIUM,
        )

        # Return user response (simplified)
        return UserListResponse(
            id=new_user.id,
            username=new_user.username,
            email=new_user.email,
            role=new_user.role,
            is_active=new_user.is_active,
            created_at=new_user.created_at,
            updated_at=new_user.updated_at,
            created_by=new_user.created_by,
        )

    except HTTPException:
        raise
    except Exception as e:
        # Log unexpected error
        audit_logger.log_activity(
            activity_type=ActivityType.USER_CREATED,
            user_id=current_user.id,
            details={
                "status": "error",
                "error": str(e),
                "attempted_data": {
                    "username": user_data.username,
                    "email": user_data.email,
                },
            },
            request=request,
            security_level=SecurityLevel.HIGH,
            success=False,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": True,
                "message": "An error occurred while creating the user",
                "error_code": "INTERNAL_ERROR",
            },
        )


@router.put("/{user_id}", response_model=UserListResponse)
@rate_limit("user_update", use_user_id=True)
async def update_user_secure(
    request: Request,
    user_id: str,
    update_data: UserUpdateRequest,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Update a user with enhanced security validation and audit logging
    """

    audit_logger = AuditLogger(db)
    security_validator = SecurityValidator()

    try:
        # Find the target user
        target_user = db.query(models.User).filter(models.User.id == user_id).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": True,
                    "message": f"User with ID '{user_id}' not found",
                    "error_code": "USER_NOT_FOUND",
                },
            )

        # Log the attempt
        audit_logger.log_activity(
            activity_type=ActivityType.USER_UPDATED,
            user_id=current_user.id,
            target_user_id=user_id,
            details={
                "status": "attempt",
                "target_user": {
                    "id": target_user.id,
                    "username": target_user.username,
                    "email": target_user.email,
                    "role": target_user.role.value,
                },
            },
            request=request,
            security_level=SecurityLevel.MEDIUM,
        )

        # Validate permissions
        validate_user_permissions(
            current_user,
            [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER],
            target_user,
        )

        # Prepare update data for validation
        update_dict = update_data.dict(exclude_unset=True)
        if update_dict:
            validation_result = security_validator.validate_user_creation_data(
                update_dict
            )

            if not validation_result["is_valid"]:
                audit_logger.log_activity(
                    activity_type=ActivityType.USER_UPDATED,
                    user_id=current_user.id,
                    target_user_id=user_id,
                    details={
                        "status": "validation_failed",
                        "validation_errors": validation_result["errors"],
                    },
                    request=request,
                    security_level=SecurityLevel.MEDIUM,
                    success=False,
                )

                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=ValidationError(
                        message="User update validation failed",
                        error_code="VALIDATION_ERROR",
                        field_errors=validation_result["errors"],
                    ).dict(),
                )

        # Track changes for audit log
        changes = {}
        sanitized_data = validation_result.get("sanitized_data", {})

        # Apply updates
        if "username" in sanitized_data:
            changes["username"] = {
                "old": target_user.username,
                "new": sanitized_data["username"],
            }
            target_user.username = sanitized_data["username"]

        if "email" in sanitized_data:
            changes["email"] = {
                "old": target_user.email,
                "new": sanitized_data["email"],
            }
            target_user.email = sanitized_data["email"]

        if "password" in update_dict:
            from passlib.context import CryptContext

            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            changes["password"] = {"old": "[REDACTED]", "new": "[REDACTED]"}
            target_user.hashed_password = pwd_context.hash(update_data.password)

        if update_data.role and update_data.role != target_user.role:
            changes["role"] = {
                "old": target_user.role.value,
                "new": update_data.role.value,
            }
            target_user.role = update_data.role

        if (
            update_data.is_active is not None
            and update_data.is_active != target_user.is_active
        ):
            changes["is_active"] = {
                "old": target_user.is_active,
                "new": update_data.is_active,
            }
            target_user.is_active = update_data.is_active

        target_user.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(target_user)

        # Log successful update
        audit_logger.log_activity(
            activity_type=ActivityType.USER_UPDATED,
            user_id=current_user.id,
            target_user_id=user_id,
            details={"status": "success", "changes": changes},
            request=request,
            security_level=SecurityLevel.MEDIUM,
        )

        return UserListResponse(
            id=target_user.id,
            username=target_user.username,
            email=target_user.email,
            role=target_user.role,
            is_active=target_user.is_active,
            created_at=target_user.created_at,
            updated_at=target_user.updated_at,
            created_by=target_user.created_by,
        )

    except HTTPException:
        raise
    except Exception as e:
        audit_logger.log_activity(
            activity_type=ActivityType.USER_UPDATED,
            user_id=current_user.id,
            target_user_id=user_id,
            details={"status": "error", "error": str(e)},
            request=request,
            security_level=SecurityLevel.HIGH,
            success=False,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": True,
                "message": "An error occurred while updating the user",
                "error_code": "INTERNAL_ERROR",
            },
        )


@router.delete("/{user_id}")
@rate_limit("user_deletion", use_user_id=True)
async def delete_user_secure(
    request: Request,
    user_id: str,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Delete a user with enhanced security validation and audit logging
    """

    audit_logger = AuditLogger(db)

    try:
        # Find the target user
        target_user = db.query(models.User).filter(models.User.id == user_id).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": True,
                    "message": f"User with ID '{user_id}' not found",
                    "error_code": "USER_NOT_FOUND",
                },
            )

        # Log the attempt
        audit_logger.log_activity(
            activity_type=ActivityType.USER_DELETED,
            user_id=current_user.id,
            target_user_id=user_id,
            details={
                "status": "attempt",
                "target_user": {
                    "id": target_user.id,
                    "username": target_user.username,
                    "email": target_user.email,
                    "role": target_user.role.value,
                },
            },
            request=request,
            security_level=SecurityLevel.HIGH,
        )

        # Validate permissions
        validate_user_permissions(
            current_user,
            [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER],
            target_user,
        )

        # Additional business rule validation
        if target_user.id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": True,
                    "message": "Cannot delete your own account",
                    "error_code": "SELF_DELETION_NOT_ALLOWED",
                },
            )

        # Check for active transactions or dependencies
        active_transactions = (
            db.query(models.PointTransaction)
            .filter(
                (models.PointTransaction.giver_id == user_id)
                | (models.PointTransaction.receiver_id == user_id)
            )
            .count()
        )

        if active_transactions > 0:
            audit_logger.log_activity(
                activity_type=ActivityType.USER_DELETED,
                user_id=current_user.id,
                target_user_id=user_id,
                details={
                    "status": "blocked",
                    "reason": "active_transactions",
                    "transaction_count": active_transactions,
                },
                request=request,
                security_level=SecurityLevel.HIGH,
                success=False,
            )

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": True,
                    "message": f"Cannot delete user with {active_transactions} active transactions. Consider deactivating instead.",
                    "error_code": "ACTIVE_DEPENDENCIES",
                    "suggestion": "deactivate_user",
                },
            )

        # Store user info for audit log before deletion
        deleted_user_info = {
            "id": target_user.id,
            "username": target_user.username,
            "email": target_user.email,
            "role": target_user.role.value,
            "created_at": target_user.created_at.isoformat(),
            "created_by": target_user.created_by,
        }

        # Delete the user
        db.delete(target_user)
        db.commit()

        # Log successful deletion
        audit_logger.log_activity(
            activity_type=ActivityType.USER_DELETED,
            user_id=current_user.id,
            target_user_id=user_id,
            details={"status": "success", "deleted_user": deleted_user_info},
            request=request,
            security_level=SecurityLevel.HIGH,
        )

        return {
            "success": True,
            "message": f"User '{deleted_user_info['username']}' has been successfully deleted",
            "deleted_user_id": user_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        audit_logger.log_activity(
            activity_type=ActivityType.USER_DELETED,
            user_id=current_user.id,
            target_user_id=user_id,
            details={"status": "error", "error": str(e)},
            request=request,
            security_level=SecurityLevel.HIGH,
            success=False,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": True,
                "message": "An error occurred while deleting the user",
                "error_code": "INTERNAL_ERROR",
            },
        )


@router.get("/audit/{user_id}")
async def get_user_audit_log(
    request: Request,
    user_id: str,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    days: int = Query(30, ge=1, le=365, description="Number of days to retrieve"),
):
    """
    Get audit log for a specific user (admin/super_user only)
    """

    # Validate permissions
    validate_user_permissions(
        current_user, [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER]
    )

    audit_logger = AuditLogger(db)

    # Get user activity history
    activity_history = audit_logger.get_user_activity_history(user_id, days)

    # Log the audit access
    audit_logger.log_activity(
        activity_type=ActivityType.DATA_EXPORT,
        user_id=current_user.id,
        details={
            "action": "audit_log_access",
            "target_user_id": user_id,
            "days_requested": days,
            "records_returned": len(activity_history),
        },
        request=request,
        security_level=SecurityLevel.MEDIUM,
    )

    return {
        "user_id": user_id,
        "period_days": days,
        "total_activities": len(activity_history),
        "activities": [
            {
                "id": log.id,
                "action": log.action,
                "details": log.details,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat(),
            }
            for log in activity_history
        ],
    }
