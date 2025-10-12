"""
Enhanced Validation Utilities for User Management

This module provides comprehensive validation functions with detailed error messages
and business rule validation for user management operations.
"""

import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import or_
from email_validator import validate_email, EmailNotValidError

import models
from user_schemas import ValidationError
from error_handlers import (
    DataValidationError,
    BusinessRuleViolationError,
    UserAlreadyExistsError,
    InsufficientPermissionsError
)


class UserValidationRules:
    """Centralized validation rules for user management"""
    
    # Username validation
    MIN_USERNAME_LENGTH = 3
    MAX_USERNAME_LENGTH = 50
    USERNAME_PATTERN = r'^[a-zA-Z0-9_]+$'
    
    # Password validation
    MIN_PASSWORD_LENGTH = 8
    MAX_PASSWORD_LENGTH = 128
    PASSWORD_UPPERCASE_PATTERN = r'[A-Z]'
    PASSWORD_LOWERCASE_PATTERN = r'[a-z]'
    PASSWORD_DIGIT_PATTERN = r'\d'
    PASSWORD_SPECIAL_PATTERN = r'[!@#$%^&*(),.?":{}|<>]'
    
    # Email validation
    MAX_EMAIL_LENGTH = 254
    
    # Business rules
    MAX_USERS_PER_ADMIN = 1000
    MAX_USERS_PER_SUPER_USER = 10000
    MIN_POINTS_FOR_TRANSFER = 10
    MAX_POINTS_PER_TRANSACTION = 10000000


class ValidationResult:
    """Container for validation results"""
    
    def __init__(self):
        self.is_valid = True
        self.field_errors: Dict[str, List[str]] = {}
        self.business_errors: List[str] = []
        self.warnings: List[str] = []
    
    def add_field_error(self, field: str, error: str):
        """Add a field-specific validation error"""
        if field not in self.field_errors:
            self.field_errors[field] = []
        self.field_errors[field].append(error)
        self.is_valid = False
    
    def add_business_error(self, error: str):
        """Add a business rule validation error"""
        self.business_errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str):
        """Add a validation warning (doesn't affect validity)"""
        self.warnings.append(warning)
    
    def get_all_errors(self) -> Dict[str, Any]:
        """Get all errors in a structured format"""
        return {
            "field_errors": self.field_errors,
            "business_errors": self.business_errors,
            "warnings": self.warnings
        }


class UserValidator:
    """Comprehensive user validation class"""
    
    def __init__(self, db: Session):
        self.db = db
        self.rules = UserValidationRules()
    
    def validate_username(self, username: str, user_id: Optional[str] = None) -> ValidationResult:
        """Validate username with detailed error messages"""
        result = ValidationResult()
        
        if not username:
            result.add_field_error("username", "Username is required")
            return result
        
        # Length validation
        if len(username) < self.rules.MIN_USERNAME_LENGTH:
            result.add_field_error(
                "username", 
                f"Username must be at least {self.rules.MIN_USERNAME_LENGTH} characters long"
            )
        
        if len(username) > self.rules.MAX_USERNAME_LENGTH:
            result.add_field_error(
                "username", 
                f"Username must not exceed {self.rules.MAX_USERNAME_LENGTH} characters"
            )
        
        # Pattern validation
        if not re.match(self.rules.USERNAME_PATTERN, username):
            result.add_field_error(
                "username", 
                "Username can only contain letters, numbers, and underscores"
            )
        
        # Reserved usernames
        reserved_usernames = ['admin', 'root', 'system', 'api', 'test', 'guest']
        if username.lower() in reserved_usernames:
            result.add_field_error(
                "username", 
                f"Username '{username}' is reserved and cannot be used"
            )
        
        # Uniqueness validation
        existing_user = self.db.query(models.User).filter(
            models.User.username == username
        )
        if user_id:
            existing_user = existing_user.filter(models.User.id != user_id)
        
        if existing_user.first():
            result.add_field_error(
                "username", 
                f"Username '{username}' is already taken"
            )
        
        return result
    
    def validate_email(self, email: str, user_id: Optional[str] = None) -> ValidationResult:
        """Validate email with detailed error messages"""
        result = ValidationResult()
        
        if not email:
            result.add_field_error("email", "Email address is required")
            return result
        
        # Length validation
        if len(email) > self.rules.MAX_EMAIL_LENGTH:
            result.add_field_error(
                "email", 
                f"Email address must not exceed {self.rules.MAX_EMAIL_LENGTH} characters"
            )
        
        # Format validation using email-validator
        try:
            validated_email = validate_email(email)
            email = validated_email.email
        except EmailNotValidError as e:
            result.add_field_error("email", f"Invalid email format: {str(e)}")
            return result
        
        # Domain validation (optional business rule)
        blocked_domains = ['tempmail.com', '10minutemail.com', 'guerrillamail.com']
        domain = email.split('@')[1].lower()
        if domain in blocked_domains:
            result.add_field_error(
                "email", 
                f"Email addresses from domain '{domain}' are not allowed"
            )
        
        # Uniqueness validation
        existing_user = self.db.query(models.User).filter(
            models.User.email == email
        )
        if user_id:
            existing_user = existing_user.filter(models.User.id != user_id)
        
        if existing_user.first():
            result.add_field_error(
                "email", 
                f"Email address '{email}' is already registered"
            )
        
        return result
    
    def validate_password(self, password: str) -> ValidationResult:
        """Validate password with detailed strength requirements"""
        result = ValidationResult()
        
        if not password:
            result.add_field_error("password", "Password is required")
            return result
        
        # Length validation
        if len(password) < self.rules.MIN_PASSWORD_LENGTH:
            result.add_field_error(
                "password", 
                f"Password must be at least {self.rules.MIN_PASSWORD_LENGTH} characters long"
            )
        
        if len(password) > self.rules.MAX_PASSWORD_LENGTH:
            result.add_field_error(
                "password", 
                f"Password must not exceed {self.rules.MAX_PASSWORD_LENGTH} characters"
            )
        
        # Strength validation
        strength_errors = []
        
        if not re.search(self.rules.PASSWORD_UPPERCASE_PATTERN, password):
            strength_errors.append("at least one uppercase letter")
        
        if not re.search(self.rules.PASSWORD_LOWERCASE_PATTERN, password):
            strength_errors.append("at least one lowercase letter")
        
        if not re.search(self.rules.PASSWORD_DIGIT_PATTERN, password):
            strength_errors.append("at least one digit")
        
        if not re.search(self.rules.PASSWORD_SPECIAL_PATTERN, password):
            strength_errors.append("at least one special character (!@#$%^&*(),.?\":{}|<>)")
        
        if strength_errors:
            result.add_field_error(
                "password", 
                f"Password must contain {', '.join(strength_errors)}"
            )
        
        # Common password validation
        common_passwords = [
            'password', '123456', '123456789', 'qwerty', 'abc123', 
            'password123', 'admin', 'letmein', 'welcome', 'monkey'
        ]
        if password.lower() in common_passwords:
            result.add_field_error(
                "password", 
                "Password is too common. Please choose a more secure password"
            )
        
        # Sequential characters check
        if self._has_sequential_chars(password):
            result.add_warning(
                "Password contains sequential characters which may be less secure"
            )
        
        return result
    
    def validate_role_assignment(self, role: models.UserRole, current_user: models.User, target_user: Optional[models.User] = None) -> ValidationResult:
        """Validate role assignment based on business rules"""
        result = ValidationResult()
        
        # Super user can assign any role
        if current_user.role == models.UserRole.SUPER_USER:
            return result
        
        # Admin user can only assign general user role
        if current_user.role == models.UserRole.ADMIN_USER:
            if role != models.UserRole.GENERAL_USER:
                result.add_business_error(
                    "Admin users can only assign the 'general_user' role"
                )
        
        # General users cannot assign roles
        if current_user.role == models.UserRole.GENERAL_USER:
            result.add_business_error(
                "General users cannot assign roles to other users"
            )
        
        # Role downgrade validation
        if target_user and target_user.role.value > role.value:
            if current_user.role != models.UserRole.SUPER_USER:
                result.add_business_error(
                    "Only super users can downgrade user roles"
                )
        
        return result
    
    def validate_user_creation_limits(self, current_user: models.User) -> ValidationResult:
        """Validate user creation limits based on business rules"""
        result = ValidationResult()
        
        # Count users created by current user
        created_by_str = f"{current_user.role.lower()}: {current_user.email}"
        user_count = self.db.query(models.User).filter(
            models.User.created_by == created_by_str
        ).count()
        
        # Check limits based on role
        if current_user.role == models.UserRole.ADMIN_USER:
            if user_count >= self.rules.MAX_USERS_PER_ADMIN:
                result.add_business_error(
                    f"Admin users can create a maximum of {self.rules.MAX_USERS_PER_ADMIN} users. "
                    f"You have already created {user_count} users."
                )
        elif current_user.role == models.UserRole.SUPER_USER:
            if user_count >= self.rules.MAX_USERS_PER_SUPER_USER:
                result.add_business_error(
                    f"Super users can create a maximum of {self.rules.MAX_USERS_PER_SUPER_USER} users. "
                    f"You have already created {user_count} users."
                )
        
        return result
    
    def validate_point_transaction(self, giver: models.User, receiver: models.User, points: int) -> ValidationResult:
        """Validate point transaction business rules"""
        result = ValidationResult()
        
        # Minimum points validation
        if points < self.rules.MIN_POINTS_FOR_TRANSFER:
            result.add_business_error(
                f"Minimum points for transfer is {self.rules.MIN_POINTS_FOR_TRANSFER}"
            )
        
        # Maximum points validation
        if points > self.rules.MAX_POINTS_PER_TRANSACTION:
            result.add_business_error(
                f"Maximum points per transaction is {self.rules.MAX_POINTS_PER_TRANSACTION}"
            )
        
        # Self-transfer validation
        if giver.id == receiver.id:
            result.add_business_error("Cannot transfer points to yourself")
        
        # Role-based transfer validation
        if giver.role == models.UserRole.ADMIN_USER and receiver.role != models.UserRole.GENERAL_USER:
            result.add_business_error(
                "Admin users can only transfer points to general users"
            )
        
        # Insufficient points validation (skip for super users)
        if giver.role != models.UserRole.SUPER_USER:
            giver_points = self.db.query(models.UserPoint).filter(
                models.UserPoint.user_id == giver.id
            ).first()
            
            available_points = giver_points.current_points if giver_points else 0
            if available_points < points:
                result.add_business_error(
                    f"Insufficient points. Available: {available_points}, Required: {points}"
                )
        
        # Receiver account status validation
        if not receiver.is_active:
            result.add_business_error(
                f"Cannot transfer points to inactive user '{receiver.username}'"
            )
        
        return result
    
    def validate_user_deletion(self, user_to_delete: models.User, current_user: models.User) -> ValidationResult:
        """Validate user deletion business rules"""
        result = ValidationResult()
        
        # Self-deletion validation
        if user_to_delete.id == current_user.id:
            result.add_business_error("Cannot delete your own account")
        
        # Permission validation
        if current_user.role == models.UserRole.GENERAL_USER:
            result.add_business_error("General users cannot delete other users")
        
        # Admin user restrictions
        if current_user.role == models.UserRole.ADMIN_USER:
            if user_to_delete.role != models.UserRole.GENERAL_USER:
                result.add_business_error(
                    "Admin users can only delete general users"
                )
            
            # Check if user was created by this admin
            created_by_str = f"{current_user.role.lower()}: {current_user.email}"
            if user_to_delete.created_by != created_by_str:
                result.add_business_error(
                    "Admin users can only delete users they created"
                )
        
        # Check for active transactions
        active_transactions = self.db.query(models.PointTransaction).filter(
            or_(
                models.PointTransaction.giver_id == user_to_delete.id,
                models.PointTransaction.receiver_id == user_to_delete.id
            ),
            models.PointTransaction.created_at >= datetime.utcnow() - timedelta(days=30)
        ).count()
        
        if active_transactions > 0:
            result.add_warning(
                f"User has {active_transactions} transactions in the last 30 days. "
                "Consider deactivating instead of deleting."
            )
        
        return result
    
    def _has_sequential_chars(self, password: str) -> bool:
        """Check if password contains sequential characters"""
        sequences = ['123', '234', '345', '456', '567', '678', '789', 'abc', 'bcd', 'cde']
        password_lower = password.lower()
        return any(seq in password_lower for seq in sequences)


class ConflictResolver:
    """Handle data conflicts and provide resolution suggestions"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def resolve_username_conflict(self, desired_username: str) -> Dict[str, Any]:
        """Provide suggestions for username conflicts"""
        suggestions = []
        base_username = desired_username
        
        # Try adding numbers
        for i in range(1, 10):
            candidate = f"{base_username}{i}"
            if not self.db.query(models.User).filter(models.User.username == candidate).first():
                suggestions.append(candidate)
                if len(suggestions) >= 3:
                    break
        
        # Try adding underscores
        for suffix in ['_user', '_new', '_2024']:
            candidate = f"{base_username}{suffix}"
            if not self.db.query(models.User).filter(models.User.username == candidate).first():
                suggestions.append(candidate)
                if len(suggestions) >= 5:
                    break
        
        return {
            "conflict_type": "username_taken",
            "original_value": desired_username,
            "suggestions": suggestions[:5],
            "resolution_message": f"Username '{desired_username}' is already taken. Here are some available alternatives."
        }
    
    def resolve_email_conflict(self, desired_email: str) -> Dict[str, Any]:
        """Provide information about email conflicts"""
        existing_user = self.db.query(models.User).filter(
            models.User.email == desired_email
        ).first()
        
        return {
            "conflict_type": "email_taken",
            "original_value": desired_email,
            "existing_user_id": existing_user.id if existing_user else None,
            "resolution_message": f"Email address '{desired_email}' is already registered. Please use a different email address or contact support if this is your email.",
            "suggestions": [
                "Use a different email address",
                "Contact support if you believe this is an error",
                "Try recovering your existing account"
            ]
        }


def validate_user_data_comprehensive(
    db: Session,
    username: Optional[str] = None,
    email: Optional[str] = None,
    password: Optional[str] = None,
    role: Optional[models.UserRole] = None,
    current_user: Optional[models.User] = None,
    target_user_id: Optional[str] = None
) -> ValidationResult:
    """
    Comprehensive validation function for user data
    
    Args:
        db: Database session
        username: Username to validate
        email: Email to validate
        password: Password to validate
        role: Role to validate
        current_user: User performing the operation
        target_user_id: ID of user being updated (for uniqueness checks)
    
    Returns:
        ValidationResult with all validation errors and warnings
    """
    validator = UserValidator(db)
    combined_result = ValidationResult()
    
    # Validate individual fields
    if username is not None:
        username_result = validator.validate_username(username, target_user_id)
        combined_result.field_errors.update(username_result.field_errors)
        combined_result.business_errors.extend(username_result.business_errors)
        combined_result.warnings.extend(username_result.warnings)
        if not username_result.is_valid:
            combined_result.is_valid = False
    
    if email is not None:
        email_result = validator.validate_email(email, target_user_id)
        combined_result.field_errors.update(email_result.field_errors)
        combined_result.business_errors.extend(email_result.business_errors)
        combined_result.warnings.extend(email_result.warnings)
        if not email_result.is_valid:
            combined_result.is_valid = False
    
    if password is not None:
        password_result = validator.validate_password(password)
        combined_result.field_errors.update(password_result.field_errors)
        combined_result.business_errors.extend(password_result.business_errors)
        combined_result.warnings.extend(password_result.warnings)
        if not password_result.is_valid:
            combined_result.is_valid = False
    
    # Validate role assignment if current_user is provided
    if role is not None and current_user is not None:
        target_user = None
        if target_user_id:
            target_user = db.query(models.User).filter(models.User.id == target_user_id).first()
        
        role_result = validator.validate_role_assignment(role, current_user, target_user)
        combined_result.field_errors.update(role_result.field_errors)
        combined_result.business_errors.extend(role_result.business_errors)
        combined_result.warnings.extend(role_result.warnings)
        if not role_result.is_valid:
            combined_result.is_valid = False
    
    # Validate user creation limits for new users
    if current_user is not None and target_user_id is None:
        limits_result = validator.validate_user_creation_limits(current_user)
        combined_result.field_errors.update(limits_result.field_errors)
        combined_result.business_errors.extend(limits_result.business_errors)
        combined_result.warnings.extend(limits_result.warnings)
        if not limits_result.is_valid:
            combined_result.is_valid = False
    
    return combined_result


def handle_validation_errors(validation_result: ValidationResult) -> None:
    """
    Convert validation result to appropriate exceptions
    
    Args:
        validation_result: Result from validation
        
    Raises:
        ValidationError: For field validation errors
        BusinessRuleViolationError: For business rule violations
    """
    if not validation_result.is_valid:
        if validation_result.field_errors:
            # Create detailed field error messages
            error_details = {}
            for field, errors in validation_result.field_errors.items():
                error_details[field] = errors
            
            raise DataValidationError(
                field=list(validation_result.field_errors.keys())[0],
                value="",
                reason="; ".join(validation_result.field_errors[list(validation_result.field_errors.keys())[0]])
            )
        
        if validation_result.business_errors:
            raise BusinessRuleViolationError(
                rule=validation_result.business_errors[0],
                details={"all_errors": validation_result.business_errors}
            )