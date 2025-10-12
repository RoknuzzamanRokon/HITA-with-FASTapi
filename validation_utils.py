"""
Validation and Sanitization Utilities

This module provides additional validation functions and input sanitization
utilities that complement the Pydantic models for enhanced security and data integrity.
"""

import re
import html
import unicodedata
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timedelta
from email_validator import validate_email, EmailNotValidError
import secrets
import string


class ValidationError(Exception):
    """Custom validation error with field-specific details."""
    
    def __init__(self, message: str, field: str = None, code: str = None):
        self.message = message
        self.field = field
        self.code = code
        super().__init__(self.message)


class InputSanitizer:
    """Utility class for input sanitization and validation."""
    
    # Common dangerous patterns to remove or escape
    DANGEROUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'javascript:',               # JavaScript URLs
        r'on\w+\s*=',                # Event handlers
        r'<iframe[^>]*>.*?</iframe>', # Iframe tags
        r'<object[^>]*>.*?</object>', # Object tags
        r'<embed[^>]*>.*?</embed>',   # Embed tags
    ]
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)',
        r'(--|#|/\*|\*/)',
        r'(\b(OR|AND)\s+\d+\s*=\s*\d+)',
        r'(\'\s*(OR|AND)\s*\')',
    ]
    
    @classmethod
    def sanitize_string(cls, value: str, max_length: int = None, allow_html: bool = False) -> str:
        """
        Sanitize string input by removing dangerous content and normalizing.
        
        Args:
            value: Input string to sanitize
            max_length: Maximum allowed length
            allow_html: Whether to allow HTML content (will be escaped)
            
        Returns:
            Sanitized string
        """
        if not isinstance(value, str):
            return str(value)
        
        # Normalize unicode characters
        value = unicodedata.normalize('NFKC', value)
        
        # Remove null bytes and control characters
        value = ''.join(char for char in value if ord(char) >= 32 or char in '\t\n\r')
        
        # Remove dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            value = re.sub(pattern, '', value, flags=re.IGNORECASE | re.DOTALL)
        
        # Check for SQL injection patterns
        for pattern in cls.SQL_INJECTION_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                raise ValidationError(
                    "Input contains potentially dangerous SQL patterns",
                    code="SQL_INJECTION_DETECTED"
                )
        
        # Escape HTML if not allowing HTML content
        if not allow_html:
            value = html.escape(value)
        
        # Trim whitespace
        value = value.strip()
        
        # Check length
        if max_length and len(value) > max_length:
            value = value[:max_length]
        
        return value
    
    @classmethod
    def sanitize_search_query(cls, query: str) -> str:
        """
        Sanitize search query input with special handling for search operators.
        
        Args:
            query: Search query string
            
        Returns:
            Sanitized search query
        """
        if not query:
            return ""
        
        # Remove dangerous characters but preserve search operators
        query = re.sub(r'[<>"\';\\]', '', query.strip())
        
        # Remove excessive whitespace
        query = re.sub(r'\s+', ' ', query)
        
        # Limit length
        if len(query) > 100:
            query = query[:100]
        
        return query
    
    @classmethod
    def validate_user_id(cls, user_id: str) -> bool:
        """
        Validate user ID format.
        
        Args:
            user_id: User ID to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(user_id, str):
            return False
        
        # User IDs should be 10-character alphanumeric strings
        return bool(re.match(r'^[a-zA-Z0-9]{10}$', user_id))
    
    @classmethod
    def validate_email_format(cls, email: str) -> tuple[bool, str]:
        """
        Validate email format using comprehensive validation.
        
        Args:
            email: Email address to validate
            
        Returns:
            Tuple of (is_valid, normalized_email)
        """
        try:
            # Use email-validator library for comprehensive validation
            validated_email = validate_email(email)
            return True, validated_email.email
        except EmailNotValidError:
            return False, email


class PasswordValidator:
    """Utility class for password validation and strength checking."""
    
    MIN_LENGTH = 8
    MAX_LENGTH = 128
    
    # Common weak passwords to reject
    WEAK_PASSWORDS = {
        'password', '12345678', 'qwerty123', 'admin123', 'password123',
        'letmein', 'welcome', 'monkey', '123456789', 'password1'
    }
    
    @classmethod
    def validate_password_strength(cls, password: str) -> Dict[str, Any]:
        """
        Comprehensive password strength validation.
        
        Args:
            password: Password to validate
            
        Returns:
            Dictionary with validation results and suggestions
        """
        result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'strength_score': 0,
            'suggestions': []
        }
        
        if not password:
            result['is_valid'] = False
            result['errors'].append('Password is required')
            return result
        
        # Length checks
        if len(password) < cls.MIN_LENGTH:
            result['is_valid'] = False
            result['errors'].append(f'Password must be at least {cls.MIN_LENGTH} characters long')
        elif len(password) > cls.MAX_LENGTH:
            result['is_valid'] = False
            result['errors'].append(f'Password must not exceed {cls.MAX_LENGTH} characters')
        
        # Character type checks
        has_upper = bool(re.search(r'[A-Z]', password))
        has_lower = bool(re.search(r'[a-z]', password))
        has_digit = bool(re.search(r'\d', password))
        has_special = bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password))
        
        if not has_upper:
            result['is_valid'] = False
            result['errors'].append('Password must contain at least one uppercase letter')
        else:
            result['strength_score'] += 1
        
        if not has_lower:
            result['is_valid'] = False
            result['errors'].append('Password must contain at least one lowercase letter')
        else:
            result['strength_score'] += 1
        
        if not has_digit:
            result['is_valid'] = False
            result['errors'].append('Password must contain at least one digit')
        else:
            result['strength_score'] += 1
        
        if not has_special:
            result['is_valid'] = False
            result['errors'].append('Password must contain at least one special character')
        else:
            result['strength_score'] += 1
        
        # Additional strength checks
        if len(password) >= 12:
            result['strength_score'] += 1
        
        # Check for common weak passwords
        if password.lower() in cls.WEAK_PASSWORDS:
            result['is_valid'] = False
            result['errors'].append('Password is too common and easily guessable')
        
        # Check for repeated characters
        if re.search(r'(.)\1{2,}', password):
            result['warnings'].append('Avoid repeating the same character multiple times')
        
        # Check for sequential characters
        if cls._has_sequential_chars(password):
            result['warnings'].append('Avoid sequential characters (e.g., 123, abc)')
        
        # Provide suggestions based on strength score
        if result['strength_score'] < 3:
            result['suggestions'].append('Consider using a longer password with mixed character types')
        elif result['strength_score'] < 4:
            result['suggestions'].append('Consider adding special characters for better security')
        
        return result
    
    @classmethod
    def _has_sequential_chars(cls, password: str) -> bool:
        """Check if password contains sequential characters."""
        sequences = [
            'abcdefghijklmnopqrstuvwxyz',
            '0123456789',
            'qwertyuiop',
            'asdfghjkl',
            'zxcvbnm'
        ]
        
        password_lower = password.lower()
        for sequence in sequences:
            for i in range(len(sequence) - 2):
                if sequence[i:i+3] in password_lower:
                    return True
        
        return False
    
    @classmethod
    def generate_secure_password(cls, length: int = 12) -> str:
        """
        Generate a secure random password.
        
        Args:
            length: Desired password length
            
        Returns:
            Secure random password
        """
        if length < cls.MIN_LENGTH:
            length = cls.MIN_LENGTH
        
        # Ensure we have at least one character from each required type
        password_chars = [
            secrets.choice(string.ascii_uppercase),  # At least one uppercase
            secrets.choice(string.ascii_lowercase),  # At least one lowercase
            secrets.choice(string.digits),           # At least one digit
            secrets.choice('!@#$%^&*(),.?":{}|<>')  # At least one special char
        ]
        
        # Fill the rest with random characters from all types
        all_chars = string.ascii_letters + string.digits + '!@#$%^&*(),.?":{}|<>'
        for _ in range(length - 4):
            password_chars.append(secrets.choice(all_chars))
        
        # Shuffle the characters
        secrets.SystemRandom().shuffle(password_chars)
        
        return ''.join(password_chars)


class RateLimiter:
    """Simple in-memory rate limiter for validation operations."""
    
    def __init__(self):
        self._attempts = {}
        self._cleanup_interval = timedelta(minutes=15)
        self._last_cleanup = datetime.utcnow()
    
    def is_rate_limited(self, identifier: str, max_attempts: int = 5, window_minutes: int = 15) -> bool:
        """
        Check if an identifier is rate limited.
        
        Args:
            identifier: Unique identifier (e.g., IP address, user ID)
            max_attempts: Maximum attempts allowed in the window
            window_minutes: Time window in minutes
            
        Returns:
            True if rate limited, False otherwise
        """
        now = datetime.utcnow()
        
        # Cleanup old entries periodically
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup_old_entries(now, timedelta(minutes=window_minutes))
        
        # Get attempts for this identifier
        attempts = self._attempts.get(identifier, [])
        
        # Remove attempts outside the window
        window_start = now - timedelta(minutes=window_minutes)
        attempts = [attempt for attempt in attempts if attempt > window_start]
        
        # Update attempts list
        self._attempts[identifier] = attempts
        
        return len(attempts) >= max_attempts
    
    def record_attempt(self, identifier: str):
        """Record an attempt for the given identifier."""
        now = datetime.utcnow()
        if identifier not in self._attempts:
            self._attempts[identifier] = []
        self._attempts[identifier].append(now)
    
    def _cleanup_old_entries(self, now: datetime, window: timedelta):
        """Clean up old entries to prevent memory leaks."""
        cutoff = now - window
        for identifier in list(self._attempts.keys()):
            self._attempts[identifier] = [
                attempt for attempt in self._attempts[identifier] 
                if attempt > cutoff
            ]
            if not self._attempts[identifier]:
                del self._attempts[identifier]
        
        self._last_cleanup = now


# Global rate limiter instance
rate_limiter = RateLimiter()


def validate_bulk_operation_data(operations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Validate and sanitize bulk operation data.
    
    Args:
        operations: List of operation dictionaries
        
    Returns:
        List of validated and sanitized operations
        
    Raises:
        ValidationError: If validation fails
    """
    if not operations:
        raise ValidationError("No operations provided")
    
    if len(operations) > 100:
        raise ValidationError("Too many operations (maximum 100 allowed)")
    
    validated_operations = []
    
    for i, operation in enumerate(operations):
        try:
            # Validate operation type
            op_type = operation.get('operation', '').lower()
            if op_type not in ['activate', 'deactivate', 'delete', 'update_role']:
                raise ValidationError(f"Invalid operation type: {op_type}")
            
            # Validate user IDs
            user_ids = operation.get('user_ids', [])
            if not user_ids:
                raise ValidationError("No user IDs provided")
            
            if len(user_ids) > 50:
                raise ValidationError("Too many user IDs in single operation (maximum 50)")
            
            validated_user_ids = []
            for user_id in user_ids:
                if not InputSanitizer.validate_user_id(user_id):
                    raise ValidationError(f"Invalid user ID format: {user_id}")
                validated_user_ids.append(user_id)
            
            # Sanitize parameters
            parameters = operation.get('parameters', {})
            sanitized_params = {}
            for key, value in parameters.items():
                if isinstance(value, str):
                    sanitized_params[key] = InputSanitizer.sanitize_string(value, max_length=500)
                else:
                    sanitized_params[key] = value
            
            validated_operations.append({
                'operation': op_type,
                'user_ids': validated_user_ids,
                'parameters': sanitized_params
            })
            
        except ValidationError as e:
            raise ValidationError(f"Operation {i + 1}: {e.message}")
    
    return validated_operations


def validate_date_range(start_date: Optional[datetime], end_date: Optional[datetime]) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    Validate and normalize date range parameters.
    
    Args:
        start_date: Start date
        end_date: End date
        
    Returns:
        Tuple of validated (start_date, end_date)
        
    Raises:
        ValidationError: If date range is invalid
    """
    if start_date and end_date:
        if start_date >= end_date:
            raise ValidationError("Start date must be before end date")
        
        # Check if date range is reasonable (not more than 2 years)
        if (end_date - start_date).days > 730:
            raise ValidationError("Date range cannot exceed 2 years")
    
    # Ensure dates are not in the future beyond reasonable limits
    now = datetime.utcnow()
    future_limit = now + timedelta(days=1)  # Allow 1 day in future for timezone issues
    
    if start_date and start_date > future_limit:
        raise ValidationError("Start date cannot be in the future")
    
    if end_date and end_date > future_limit:
        raise ValidationError("End date cannot be in the future")
    
    return start_date, end_date


def sanitize_sort_parameters(sort_by: str, sort_order: str) -> tuple[str, str]:
    """
    Sanitize and validate sort parameters.
    
    Args:
        sort_by: Field to sort by
        sort_order: Sort order (asc/desc)
        
    Returns:
        Tuple of validated (sort_by, sort_order)
        
    Raises:
        ValidationError: If sort parameters are invalid
    """
    # Allowed sort fields (whitelist approach for security)
    allowed_sort_fields = {
        'username', 'email', 'created_at', 'updated_at', 'role', 'points'
    }
    
    sort_by = sort_by.lower().strip()
    if sort_by not in allowed_sort_fields:
        raise ValidationError(f"Invalid sort field: {sort_by}")
    
    sort_order = sort_order.lower().strip()
    if sort_order not in ['asc', 'desc']:
        raise ValidationError(f"Invalid sort order: {sort_order}")
    
    return sort_by, sort_order