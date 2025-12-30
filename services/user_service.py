from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func, case, or_, and_, desc, asc
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timedelta
import secrets
from passlib.context import CryptContext

import models
from user_schemas import (
    UserListResponse,
    PaginatedUserResponse,
    UserDetailResponse,
    UserStatistics,
    PaginationMetadata,
    UserSearchParams,
    UserCreateRequest,
    UserUpdateRequest,
    UserActivityResponse,
)
from validation_utils import (
    validate_user_data_comprehensive,
    handle_validation_errors,
    UserValidator,
    ConflictResolver,
)
from error_handlers import (
    UserNotFoundError,
    UserAlreadyExistsError,
    InsufficientPermissionsError,
    BusinessRuleViolationError,
    DataValidationError,
)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def get_users_paginated(
        self, params: UserSearchParams, current_user: models.User
    ) -> PaginatedUserResponse:
        """Get paginated list of users with filtering and sorting"""

        # Build base query with optimized joins
        query = self.db.query(models.User).options(
            selectinload(models.User.user_points),
            selectinload(models.User.provider_permissions),
            selectinload(models.User.sessions),
        )

        # Apply role-based filtering - users can only see users they created
        if current_user.role in [
            models.UserRole.SUPER_USER,
            models.UserRole.ADMIN_USER,
        ]:
            created_by_str = f"{current_user.role.lower()}: {current_user.email}"
            query = query.filter(models.User.created_by == created_by_str)
        else:
            # General users can only see themselves
            query = query.filter(models.User.id == current_user.id)

        # Apply search filter
        if params.search:
            search_term = f"%{params.search}%"
            query = query.filter(
                or_(
                    models.User.username.ilike(search_term),
                    models.User.email.ilike(search_term),
                )
            )

        # Apply role filter
        if params.role:
            query = query.filter(models.User.role == params.role)

        # Apply active status filter
        if params.is_active is not None:
            query = query.filter(models.User.is_active == params.is_active)

        # Apply sorting
        sort_column = getattr(models.User, params.sort_by, models.User.created_at)
        if params.sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        # Get total count for pagination
        total = query.count()

        # Apply pagination
        offset = (params.page - 1) * params.limit
        users = query.offset(offset).limit(params.limit).all()

        # Convert to response format
        user_responses = []
        for user in users:
            user_response = self._build_user_list_response(user)
            user_responses.append(user_response)

        # Build pagination metadata
        total_pages = (total + params.limit - 1) // params.limit
        pagination = PaginationMetadata(
            page=params.page,
            limit=params.limit,
            total=total,
            total_pages=total_pages,
            has_next=params.page < total_pages,
            has_prev=params.page > 1,
        )

        # Get statistics
        statistics = self.get_user_statistics(current_user)

        return PaginatedUserResponse(
            users=user_responses, pagination=pagination, statistics=statistics
        )

    def get_user_statistics(self, current_user: models.User) -> UserStatistics:
        """Get user statistics for the current user's scope"""

        created_by_str = None

        # Build base query for users in current user's scope
        if current_user.role in [
            models.UserRole.SUPER_USER,
            models.UserRole.ADMIN_USER,
        ]:
            created_by_str = f"{current_user.role.lower()}: {current_user.email}"
            base_query = self.db.query(models.User).filter(
                models.User.created_by == created_by_str
            )
        else:
            # General users can only see themselves
            base_query = self.db.query(models.User).filter(
                models.User.id == current_user.id
            )

        # Get role counts
        role_stats = base_query.with_entities(
            func.count(models.User.id).label("total_users"),
            func.sum(
                case((models.User.role == models.UserRole.SUPER_USER, 1), else_=0)
            ).label("super_users"),
            func.sum(
                case((models.User.role == models.UserRole.ADMIN_USER, 1), else_=0)
            ).label("admin_users"),
            func.sum(
                case((models.User.role == models.UserRole.GENERAL_USER, 1), else_=0)
            ).label("general_users"),
            func.sum(case((models.User.is_active == True, 1), else_=0)).label(
                "active_users"
            ),
        ).first()

        # Get total points distributed
        total_points = (
            self.db.query(func.sum(models.UserPoint.total_points))
            .join(models.User, models.UserPoint.user_id == models.User.id)
            .filter(models.User.created_by == created_by_str)
            .scalar()
            or 0
        )

        # Get recent signups (last 7 days)
        recent_date = datetime.utcnow() - timedelta(days=7)
        recent_signups = base_query.filter(
            models.User.created_at >= recent_date
        ).count()

        return UserStatistics(
            total_users=role_stats.total_users or 0,
            super_users=role_stats.super_users or 0,
            admin_users=role_stats.admin_users or 0,
            general_users=role_stats.general_users or 0,
            active_users=role_stats.active_users or 0,
            inactive_users=(role_stats.total_users or 0)
            - (role_stats.active_users or 0),
            total_points_distributed=total_points,
            recent_signups=recent_signups,
        )

    def get_user_with_details(
        self, user_id: str, current_user: models.User
    ) -> Optional[UserDetailResponse]:
        """Get detailed user information"""

        # Check permissions
        user = (
            self.db.query(models.User)
            .options(
                selectinload(models.User.user_points),
                selectinload(models.User.provider_permissions),
                selectinload(models.User.sessions),
                selectinload(models.User.sent_transactions),
                selectinload(models.User.received_transactions),
            )
            .filter(models.User.id == user_id)
            .first()
        )

        if not user:
            return None

        # Check if current user has permission to view this user
        if current_user.role in [
            models.UserRole.SUPER_USER,
            models.UserRole.ADMIN_USER,
        ]:
            created_by_str = f"{current_user.role.lower()}: {current_user.email}"
            if user.created_by != created_by_str and user.id != current_user.id:
                return None
        elif user.id != current_user.id:
            return None

        # Get recent transactions (last 10)
        recent_transactions = []
        all_transactions = sorted(
            user.sent_transactions + user.received_transactions,
            key=lambda t: t.created_at,
            reverse=True,
        )[:10]

        for transaction in all_transactions:
            transaction_data = {
                "id": transaction.id,
                "type": "sent" if transaction.giver_id == user.id else "received",
                "points": transaction.points,
                "transaction_type": transaction.transaction_type,
                "other_user_email": (
                    transaction.receiver_email
                    if transaction.giver_id == user.id
                    else transaction.giver_email
                ),
                "created_at": transaction.created_at,
            }
            recent_transactions.append(transaction_data)

        return self._build_user_detail_response(user, recent_transactions)

    def create_user_with_validation(
        self, user_data: UserCreateRequest, current_user: models.User
    ) -> UserListResponse:
        """Create a new user with comprehensive validation"""

        # Check basic permissions first
        if current_user.role not in [
            models.UserRole.SUPER_USER,
            models.UserRole.ADMIN_USER,
        ]:
            raise InsufficientPermissionsError(
                required_role="super_user or admin_user",
                current_role=current_user.role.value,
                operation="create_user",
            )

        # Comprehensive validation
        validation_result = validate_user_data_comprehensive(
            db=self.db,
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            role=user_data.role,
            current_user=current_user,
        )

        # Handle validation errors
        if not validation_result.is_valid:
            handle_validation_errors(validation_result)

        # Check for conflicts and provide detailed error messages
        conflict_resolver = ConflictResolver(self.db)

        # Check email conflict with detailed resolution
        existing_email_user = (
            self.db.query(models.User)
            .filter(models.User.email == user_data.email)
            .first()
        )
        if existing_email_user:
            conflict_info = conflict_resolver.resolve_email_conflict(user_data.email)
            raise UserAlreadyExistsError("email", user_data.email)

        # Check username conflict with suggestions
        existing_username_user = (
            self.db.query(models.User)
            .filter(models.User.username == user_data.username)
            .first()
        )
        if existing_username_user:
            conflict_info = conflict_resolver.resolve_username_conflict(
                user_data.username
            )
            raise UserAlreadyExistsError("username", user_data.username)

        try:
            # Generate unique ID and hash password
            unique_id = secrets.token_hex(5)
            hashed_password = pwd_context.hash(user_data.password)

            # Set created_by
            created_by = f"{current_user.role.lower()}: {current_user.email}"

            # Create user
            new_user = models.User(
                id=unique_id,
                username=user_data.username,
                email=user_data.email,
                hashed_password=hashed_password,
                role=user_data.role,
                is_active=True,
                created_by=created_by,
            )

            self.db.add(new_user)
            self.db.commit()
            self.db.refresh(new_user)

            return self._build_user_list_response(new_user)

        except Exception as e:
            self.db.rollback()
            raise BusinessRuleViolationError(
                rule="User creation failed due to database error",
                details={"error": str(e)},
            )

    def update_user_with_validation(
        self, user_id: str, updates: UserUpdateRequest, current_user: models.User
    ) -> Optional[UserListResponse]:
        """Update user with comprehensive validation"""

        # Get user
        user = self.db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise UserNotFoundError(user_id=user_id)

        # Check permissions with detailed error messages
        if current_user.role in [
            models.UserRole.SUPER_USER,
            models.UserRole.ADMIN_USER,
        ]:
            created_by_str = f"{current_user.role.lower()}: {current_user.email}"
            if user.created_by != created_by_str and user.id != current_user.id:
                raise InsufficientPermissionsError(
                    required_role=current_user.role.value,
                    current_role=current_user.role.value,
                    operation=f"update user {user.username}",
                )
        elif user.id != current_user.id:
            raise InsufficientPermissionsError(
                required_role="owner",
                current_role=current_user.role.value,
                operation="update user profile",
            )

        # Validate updates with comprehensive validation
        validation_result = validate_user_data_comprehensive(
            db=self.db,
            username=updates.username,
            email=updates.email,
            password=updates.password,
            role=updates.role,
            current_user=current_user,
            target_user_id=user_id,
        )

        # Handle validation errors
        if not validation_result.is_valid:
            handle_validation_errors(validation_result)

        try:
            # Apply updates with conflict resolution
            conflict_resolver = ConflictResolver(self.db)

            if updates.username is not None:
                # Check username conflict with suggestions
                existing_username = (
                    self.db.query(models.User)
                    .filter(
                        models.User.username == updates.username,
                        models.User.id != user_id,
                    )
                    .first()
                )
                if existing_username:
                    conflict_info = conflict_resolver.resolve_username_conflict(
                        updates.username
                    )
                    raise UserAlreadyExistsError("username", updates.username)
                user.username = updates.username

            if updates.email is not None:
                # Check email conflict with detailed resolution
                existing_email = (
                    self.db.query(models.User)
                    .filter(
                        models.User.email == updates.email, models.User.id != user_id
                    )
                    .first()
                )
                if existing_email:
                    conflict_info = conflict_resolver.resolve_email_conflict(
                        updates.email
                    )
                    raise UserAlreadyExistsError("email", updates.email)
                user.email = updates.email

            if updates.password is not None:
                user.hashed_password = pwd_context.hash(updates.password)

            # Role updates with permission validation
            if updates.role is not None:
                if current_user.role != models.UserRole.SUPER_USER:
                    raise InsufficientPermissionsError(
                        required_role="super_user",
                        current_role=current_user.role.value,
                        operation="change user role",
                    )
                user.role = updates.role

            # Active status updates with permission validation
            if updates.is_active is not None:
                if current_user.role not in [
                    models.UserRole.SUPER_USER,
                    models.UserRole.ADMIN_USER,
                ]:
                    raise InsufficientPermissionsError(
                        required_role="super_user or admin_user",
                        current_role=current_user.role.value,
                        operation="change user active status",
                    )
                user.is_active = updates.is_active

            user.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(user)

            return self._build_user_list_response(user)

        except Exception as e:
            self.db.rollback()
            if isinstance(
                e,
                (
                    UserAlreadyExistsError,
                    InsufficientPermissionsError,
                    DataValidationError,
                ),
            ):
                raise
            raise BusinessRuleViolationError(
                rule="User update failed due to database error",
                details={"error": str(e), "user_id": user_id},
            )

    def delete_user_with_cleanup(self, user_id: str, current_user: models.User) -> bool:
        """Delete user with proper cleanup and validation"""

        # Get user
        user = self.db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise UserNotFoundError(user_id=user_id)

        # Validate deletion with business rules
        validator = UserValidator(self.db)
        deletion_result = validator.validate_user_deletion(user, current_user)

        if not deletion_result.is_valid:
            handle_validation_errors(deletion_result)

        # Check permissions with detailed error messages
        if current_user.role in [
            models.UserRole.SUPER_USER,
            models.UserRole.ADMIN_USER,
        ]:
            created_by_str = f"{current_user.role.lower()}: {current_user.email}"
            if user.created_by != created_by_str:
                raise InsufficientPermissionsError(
                    required_role=current_user.role.value,
                    current_role=current_user.role.value,
                    operation=f"delete user {user.username} (not created by you)",
                )
        else:
            raise InsufficientPermissionsError(
                required_role="super_user or admin_user",
                current_role=current_user.role.value,
                operation="delete users",
            )

        try:
            # Cleanup related data with proper error handling
            # Delete user points
            deleted_points = (
                self.db.query(models.UserPoint)
                .filter(models.UserPoint.user_id == user_id)
                .delete()
            )

            # Delete provider permissions
            deleted_permissions = (
                self.db.query(models.UserProviderPermission)
                .filter(models.UserProviderPermission.user_id == user_id)
                .delete()
            )

            # Delete activity logs (if the model exists)
            try:
                deleted_logs = (
                    self.db.query(models.UserActivityLog)
                    .filter(models.UserActivityLog.user_id == user_id)
                    .delete()
                )
            except AttributeError:
                # UserActivityLog model doesn't exist yet
                deleted_logs = 0

            # Delete sessions (if the model exists)
            try:
                deleted_sessions = (
                    self.db.query(models.UserSession)
                    .filter(models.UserSession.user_id == user_id)
                    .delete()
                )
            except AttributeError:
                # UserSession model doesn't exist yet
                deleted_sessions = 0

            # Note: We don't delete point transactions as they are historical records
            # Instead, we could mark them as "deleted_user" or similar

            # Delete the user
            self.db.delete(user)
            self.db.commit()

            return True

        except Exception as e:
            self.db.rollback()
            raise BusinessRuleViolationError(
                rule="User deletion failed due to database error",
                details={
                    "error": str(e),
                    "user_id": user_id,
                    "username": user.username,
                },
            )

    def get_user_activity(
        self, user_id: str, days: int, current_user: models.User
    ) -> Optional[UserActivityResponse]:
        """Get comprehensive user activity for specified number of days"""

        # Get user and check permissions
        user = self.db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            return None

        # Check permissions
        if current_user.role in [
            models.UserRole.SUPER_USER,
            models.UserRole.ADMIN_USER,
        ]:
            created_by_str = f"{current_user.role.lower()}: {current_user.email}"
            if user.created_by != created_by_str and user.id != current_user.id:
                return None
        elif user.id != current_user.id:
            return None

        # Get activity logs
        start_date = datetime.utcnow() - timedelta(days=days)
        activities = (
            self.db.query(models.UserActivityLog)
            .filter(
                models.UserActivityLog.user_id == user_id,
                models.UserActivityLog.created_at >= start_date,
            )
            .order_by(desc(models.UserActivityLog.created_at))
            .all()
        )

        activity_list = []
        endpoint_usage = {}

        for activity in activities:
            # Extract endpoint information from details
            endpoint = "Unknown"
            method = "Unknown"
            status_code = None

            if activity.details:
                endpoint = activity.details.get("endpoint", "Unknown")
                method = activity.details.get("method", "Unknown")
                status_code = activity.details.get("status_code")

                # Track endpoint usage statistics
                endpoint_key = f"{method} {endpoint}"
                if endpoint_key not in endpoint_usage:
                    endpoint_usage[endpoint_key] = {
                        "count": 0,
                        "success_count": 0,
                        "error_count": 0,
                        "last_used": activity.created_at,
                    }

                endpoint_usage[endpoint_key]["count"] += 1
                if status_code and 200 <= status_code < 300:
                    endpoint_usage[endpoint_key]["success_count"] += 1
                elif status_code and status_code >= 400:
                    endpoint_usage[endpoint_key]["error_count"] += 1

                if activity.created_at > endpoint_usage[endpoint_key]["last_used"]:
                    endpoint_usage[endpoint_key]["last_used"] = activity.created_at

            activity_data = {
                "id": activity.id,
                "action": activity.action,
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
                "details": activity.details,
                "ip_address": activity.ip_address,
                "user_agent": activity.user_agent,
                "created_at": activity.created_at,
            }
            activity_list.append(activity_data)

        # Calculate comprehensive statistics
        total_api_calls = len([a for a in activities if a.action == "api_access"])
        successful_calls = len(
            [
                a
                for a in activities
                if a.action == "api_access"
                and a.details
                and a.details.get("status_code", 0) < 400
            ]
        )
        failed_calls = total_api_calls - successful_calls

        # Get most used endpoints
        most_used_endpoints = sorted(
            endpoint_usage.items(), key=lambda x: x[1]["count"], reverse=True
        )[:10]

        # Build comprehensive summary
        summary = {
            "total_activities": len(activity_list),
            "total_api_calls": total_api_calls,
            "successful_calls": successful_calls,
            "failed_calls": failed_calls,
            "unique_actions": len(set(a.action for a in activities)),
            "unique_endpoints": len(endpoint_usage),
            "most_used_endpoints": [
                {
                    "endpoint": endpoint,
                    "count": stats["count"],
                    "success_rate": (
                        round((stats["success_count"] / stats["count"]) * 100, 2)
                        if stats["count"] > 0
                        else 0
                    ),
                    "last_used": stats["last_used"],
                }
                for endpoint, stats in most_used_endpoints
            ],
            "date_range": {"start": start_date, "end": datetime.utcnow()},
        }

        return UserActivityResponse(
            user_id=user_id, activities=activity_list, summary=summary
        )

    def validate_point_transaction(
        self, giver_id: str, receiver_id: str, points: int, current_user: models.User
    ) -> bool:
        """Validate point transaction with comprehensive business rules"""

        # Get users
        giver = self.db.query(models.User).filter(models.User.id == giver_id).first()
        receiver = (
            self.db.query(models.User).filter(models.User.id == receiver_id).first()
        )

        if not giver:
            raise UserNotFoundError(user_id=giver_id)
        if not receiver:
            raise UserNotFoundError(user_id=receiver_id)

        # Validate transaction with business rules
        validator = UserValidator(self.db)
        transaction_result = validator.validate_point_transaction(
            giver, receiver, points
        )

        if not transaction_result.is_valid:
            handle_validation_errors(transaction_result)

        # Check if current user has permission to perform this transaction
        if current_user.role not in [
            models.UserRole.SUPER_USER,
            models.UserRole.ADMIN_USER,
        ]:
            raise InsufficientPermissionsError(
                required_role="super_user or admin_user",
                current_role=current_user.role.value,
                operation="transfer points",
            )

        # Additional permission checks for admin users
        if current_user.role == models.UserRole.ADMIN_USER:
            # Admin can only give points, not transfer between other users
            if giver.id != current_user.id:
                raise InsufficientPermissionsError(
                    required_role="super_user",
                    current_role=current_user.role.value,
                    operation="transfer points between other users",
                )

        return True

    def _build_user_list_response(self, user: models.User) -> UserListResponse:
        """Build UserListResponse from User model"""

        # Get point information
        user_points = user.user_points[0] if user.user_points else None
        point_balance = user_points.current_points if user_points else 0
        total_points = user_points.total_points if user_points else 0

        # Determine paid status
        if user.role == models.UserRole.SUPER_USER:
            paid_status = "Unlimited"
        elif point_balance > 0:
            paid_status = "Paid"
        elif total_points > 0:
            paid_status = "Used"
        else:
            paid_status = "Unpaid"

        # Get activity status
        last_7_days = datetime.utcnow() - timedelta(days=7)
        recent_activity = (
            self.db.query(models.PointTransaction)
            .filter(
                or_(
                    models.PointTransaction.giver_id == user.id,
                    models.PointTransaction.receiver_id == user.id,
                ),
                models.PointTransaction.created_at >= last_7_days,
            )
            .first()
        )
        activity_status = "Active" if recent_activity else "Inactive"

        # Get total requests
        total_requests = (
            self.db.query(models.PointTransaction)
            .filter(
                or_(
                    models.PointTransaction.giver_id == user.id,
                    models.PointTransaction.receiver_id == user.id,
                )
            )
            .count()
        )

        # Get active suppliers
        active_suppliers = [perm.provider_name for perm in user.provider_permissions]

        # Get last login
        last_login = None
        if user.sessions:
            latest_session = max(user.sessions, key=lambda s: s.last_activity)
            last_login = latest_session.last_activity

        return UserListResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
            created_by=user.created_by,
            point_balance=point_balance,
            total_points=total_points,
            paid_status=paid_status,
            total_requests=total_requests,
            activity_status=activity_status,
            active_suppliers=active_suppliers,
            last_login=last_login,
        )

    def _build_user_detail_response(
        self, user: models.User, recent_transactions: List[Dict[str, Any]]
    ) -> UserDetailResponse:
        """Build UserDetailResponse from User model"""

        # Get point information
        user_points = user.user_points[0] if user.user_points else None
        point_balance = user_points.current_points if user_points else 0
        total_points = user_points.total_points if user_points else 0
        total_used_points = user_points.total_used_points if user_points else 0

        # Determine paid status
        if user.role == models.UserRole.SUPER_USER:
            paid_status = "Unlimited"
        elif point_balance > 0:
            paid_status = "Paid"
        elif total_points > 0:
            paid_status = "Used"
        else:
            paid_status = "Unpaid"

        # Get activity status
        last_7_days = datetime.utcnow() - timedelta(days=7)
        recent_activity = (
            self.db.query(models.PointTransaction)
            .filter(
                or_(
                    models.PointTransaction.giver_id == user.id,
                    models.PointTransaction.receiver_id == user.id,
                ),
                models.PointTransaction.created_at >= last_7_days,
            )
            .first()
        )
        activity_status = "Active" if recent_activity else "Inactive"

        # Get total requests
        total_requests = (
            self.db.query(models.PointTransaction)
            .filter(
                or_(
                    models.PointTransaction.giver_id == user.id,
                    models.PointTransaction.receiver_id == user.id,
                )
            )
            .count()
        )

        # Get active suppliers
        active_suppliers = [perm.provider_name for perm in user.provider_permissions]

        # Get last login
        last_login = None
        if user.sessions:
            latest_session = max(user.sessions, key=lambda s: s.last_activity)
            last_login = latest_session.last_activity

        return UserDetailResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
            created_by=user.created_by,
            point_balance=point_balance,
            total_points=total_points,
            total_used_points=total_used_points,
            paid_status=paid_status,
            activity_status=activity_status,
            total_requests=total_requests,
            last_login=last_login,
            active_suppliers=active_suppliers,
            recent_transactions=recent_transactions,
        )
