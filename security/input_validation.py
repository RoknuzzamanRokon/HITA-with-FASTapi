"""
Enhanced Input Validation and Sanitization for User Management

This module provides comprehensive input validation, sanitization, and security
controls for all user-provided data in the user management system.
"""

import re
import html
import bleach
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, validator
from email_validator import validate_email, EmailNotValidError
import secrets
import string


class SecurityConfig:
    """Security configuration constants"""
    
    # Password security requirements
    MIN_PASSWORD_LENGTH = 12  # Increased from 8 for better security
    MAX_PASSWORD_LENGTH = 128
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGITS = True
    REQUIRE_SPECIAL_CHARS = True
    MIN_SPECIAL_CHARS = 2
    
    # Username security
    MIN_USERNAME_LENGTH = 3
    MAX_USERNAME_LENGTH = 50
    ALLOWED_USERNAME_CHARS = r'^[a-zA-Z0-9_\-\.]+$'
    
    # Email security
    MAX_EMAIL_LENGTH = 254
    BLOCKED_EMAIL_DOMAINS = [
        'tempmail.com', '10minutemail.com', 'guerrillamail.com',
        'mailinator.com', 'throwaway.email', 'temp-mail.org'
    ]
    
    # Input sanitization
    MAX_INPUT_LENGTH = 1000
    DANGEROUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'javascript:',               # JavaScript URLs
        r'on\w+\s*=',                # Event handlers
        r'<iframe[^>]*>.*?</iframe>', # Iframes
        r'<object[^>]*>.*?</object>', # Objects
        r'<embed[^>]*>.*?</embed>',   # Embeds
    ]
    
    # Rate limiting (requests per minute)
    USER_CREATION_RATE_LIMIT = 5
    PASSWORD_RESET_RATE_LIMIT = 3
    LOGIN_ATTEMPT_RATE_LIMIT = 10


class AdvancedPasswordValidator:
    """Advanced password validation with security requirements"""
    
    def __init__(self):
        self.config = SecurityConfig()
        
        # Common passwords list (subset for demonstration)
        self.common_passwords = {
            'password', '123456', '123456789', 'qwerty', 'abc123',
            'password123', 'admin', 'letmein', 'welcome', 'monkey',
            'dragon', 'master', 'shadow', 'superman', 'michael',
            'football', 'baseball', 'liverpool', 'jordan', 'harley'
        }
        
        # Keyboard patterns
        self.keyboard_patterns = [
            'qwerty', 'asdf', 'zxcv', '1234', '4321', 'abcd', 'dcba'
        ]
    
    def validate_password(self, password: str) -> Dict[str, Any]:
        """
        Comprehensive password validation
        
        Args:
            password: Password to validate
            
        Returns:
            Dictionary with validation results
        """
        result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'strength_score': 0,
            'strength_level': 'weak'
        }
        
        if not password:
            result['is_valid'] = False
            result['errors'].append('Password is required')
            return result
        
        # Length validation
        if len(password) < self.config.MIN_PASSWORD_LENGTH:
            result['is_valid'] = False
            result['errors'].append(
                f'Password must be at least {self.config.MIN_PASSWORD_LENGTH} characters long'
            )
        
        if len(password) > self.config.MAX_PASSWORD_LENGTH:
            result['is_valid'] = False
            result['errors'].append(
                f'Password must not exceed {self.config.MAX_PASSWORD_LENGTH} characters'
            )
        
        # Character requirements
        has_upper = bool(re.search(r'[A-Z]', password))
        has_lower = bool(re.search(r'[a-z]', password))
        has_digit = bool(re.search(r'\d', password))
        has_special = bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password))
        special_count = len(re.findall(r'[!@#$%^&*(),.?":{}|<>]', password))
        
        if self.config.REQUIRE_UPPERCASE and not has_upper:
            result['is_valid'] = False
            result['errors'].append('Password must contain at least one uppercase letter')
        
        if self.config.REQUIRE_LOWERCASE and not has_lower:
            result['is_valid'] = False
            result['errors'].append('Password must contain at least one lowercase letter')
        
        if self.config.REQUIRE_DIGITS and not has_digit:
            result['is_valid'] = False
            result['errors'].append('Password must contain at least one digit')
        
        if self.config.REQUIRE_SPECIAL_CHARS and not has_special:
            result['is_valid'] = False
            result['errors'].append('Password must contain at least one special character')
        
        if special_count < self.config.MIN_SPECIAL_CHARS:
            result['is_valid'] = False
            result['errors'].append(
                f'Password must contain at least {self.config.MIN_SPECIAL_CHARS} special characters'
            )
        
        # Common password check
        if password.lower() in self.common_passwords:
            result['is_valid'] = False
            result['errors'].append('Password is too common. Please choose a more secure password')
        
        # Keyboard pattern check
        password_lower = password.lower()
        for pattern in self.keyboard_patterns:
            if pattern in password_lower or pattern[::-1] in password_lower:
                result['warnings'].append('Password contains keyboard patterns which may be less secure')
                break
        
        # Sequential characters check
        if self._has_sequential_chars(password):
            result['warnings'].append('Password contains sequential characters which may be less secure')
        
        # Repeated characters check
        if self._has_repeated_chars(password):
            result['warnings'].append('Password contains repeated character patterns')
        
        # Calculate strength score
        result['strength_score'] = self._calculate_strength_score(password)
        result['strength_level'] = self._get_strength_level(result['strength_score'])
        
        # Minimum strength requirement
        if result['strength_score'] < 60:
            result['is_valid'] = False
            result['errors'].append('Password is too weak. Please create a stronger password')
        
        return result
    
    def _has_sequential_chars(self, password: str) -> bool:
        """Check for sequential characters"""
        sequences = ['123', '234', '345', '456', '567', '678', '789', '890',
                    'abc', 'bcd', 'cde', 'def', 'efg', 'fgh', 'ghi', 'hij']
        password_lower = password.lower()
        return any(seq in password_lower or seq[::-1] in password_lower for seq in sequences)
    
    def _has_repeated_chars(self, password: str) -> bool:
        """Check for repeated character patterns"""
        # Check for 3+ repeated characters
        if re.search(r'(.)\1{2,}', password):
            return True
        
        # Check for repeated patterns
        for i in range(len(password) - 3):
            pattern = password[i:i+2]
            if pattern * 2 in password:
                return True
        
        return False
    
    def _calculate_strength_score(self, password: str) -> int:
        """Calculate password strength score (0-100)"""
        score = 0
        
        # Length bonus
        score += min(len(password) * 2, 25)
        
        # Character variety bonus
        if re.search(r'[a-z]', password):
            score += 10
        if re.search(r'[A-Z]', password):
            score += 10
        if re.search(r'\d', password):
            score += 10
        if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            score += 15
        
        # Unique characters bonus
        unique_chars = len(set(password))
        score += min(unique_chars * 2, 20)
        
        # Penalty for common patterns
        if self._has_sequential_chars(password):
            score -= 10
        if self._has_repeated_chars(password):
            score -= 10
        
        return max(0, min(score, 100))
    
    def _get_strength_level(self, score: int) -> str:
        """Get strength level based on score"""
        if score >= 80:
            return 'very_strong'
        elif score >= 70:
            return 'strong'
        elif score >= 60:
            return 'moderate'
        elif score >= 40:
            return 'weak'
        else:
            return 'very_weak'


class InputSanitizer:
    """Advanced input sanitization for user data"""
    
    def __init__(self):
        self.config = SecurityConfig()
        
        # Allowed HTML tags for rich text (if needed)
        self.allowed_tags = ['b', 'i', 'u', 'em', 'strong', 'p', 'br']
        self.allowed_attributes = {}
    
    def sanitize_string(self, input_str: str, max_length: Optional[int] = None) -> str:
        """
        Sanitize string input
        
        Args:
            input_str: Input string to sanitize
            max_length: Maximum allowed length
            
        Returns:
            Sanitized string
        """
        if not input_str:
            return ""
        
        # Convert to string if not already
        input_str = str(input_str)
        
        # Length check
        max_len = max_length or self.config.MAX_INPUT_LENGTH
        if len(input_str) > max_len:
            input_str = input_str[:max_len]
        
        # Remove dangerous patterns
        for pattern in self.config.DANGEROUS_PATTERNS:
            input_str = re.sub(pattern, '', input_str, flags=re.IGNORECASE)
        
        # HTML escape
        input_str = html.escape(input_str)
        
        # Remove null bytes and control characters
        input_str = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', input_str)
        
        # Normalize whitespace
        input_str = re.sub(r'\s+', ' ', input_str).strip()
        
        return input_str
    
    def sanitize_username(self, username: str) -> str:
        """
        Sanitize username input
        
        Args:
            username: Username to sanitize
            
        Returns:
            Sanitized username
        """
        if not username:
            return ""
        
        username = str(username).strip()
        
        # Length check
        if len(username) > self.config.MAX_USERNAME_LENGTH:
            username = username[:self.config.MAX_USERNAME_LENGTH]
        
        # Remove invalid characters
        username = re.sub(r'[^a-zA-Z0-9_\-\.]', '', username)
        
        # Remove leading/trailing dots and dashes
        username = username.strip('.-')
        
        return username
    
    def sanitize_email(self, email: str) -> str:
        """
        Sanitize email input
        
        Args:
            email: Email to sanitize
            
        Returns:
            Sanitized email
        """
        if not email:
            return ""
        
        email = str(email).strip().lower()
        
        # Length check
        if len(email) > self.config.MAX_EMAIL_LENGTH:
            return ""  # Invalid if too long
        
        # Basic format validation
        if '@' not in email or email.count('@') != 1:
            return ""
        
        # Remove dangerous characters
        email = re.sub(r'[<>"\'\\\x00-\x1f]', '', email)
        
        return email
    
    def sanitize_search_query(self, query: str) -> str:
        """
        Sanitize search query input
        
        Args:
            query: Search query to sanitize
            
        Returns:
            Sanitized search query
        """
        if not query:
            return ""
        
        query = str(query).strip()
        
        # Length check
        if len(query) > 100:
            query = query[:100]
        
        # Remove SQL injection patterns
        sql_patterns = [
            r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)',
            r'(--|#|/\*|\*/)',
            r'(\bOR\b.*=.*\bOR\b)',
            r'(\bAND\b.*=.*\bAND\b)',
            r'[\'";]'
        ]
        
        for pattern in sql_patterns:
            query = re.sub(pattern, '', query, flags=re.IGNORECASE)
        
        # Remove XSS patterns
        query = self.sanitize_string(query, 100)
        
        return query


class SecurityValidator:
    """Security validation for user operations"""
    
    def __init__(self):
        self.config = SecurityConfig()
        self.password_validator = AdvancedPasswordValidator()
        self.sanitizer = InputSanitizer()
    
    def validate_user_creation_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and sanitize user creation data
        
        Args:
            data: User creation data
            
        Returns:
            Validation result with sanitized data
        """
        result = {
            'is_valid': True,
            'errors': {},
            'warnings': [],
            'sanitized_data': {}
        }
        
        # Validate and sanitize username
        if 'username' in data:
            username = self.sanitizer.sanitize_username(data['username'])
            result['sanitized_data']['username'] = username
            
            if not username:
                result['is_valid'] = False
                result['errors']['username'] = ['Username is required']
            elif len(username) < self.config.MIN_USERNAME_LENGTH:
                result['is_valid'] = False
                result['errors']['username'] = [
                    f'Username must be at least {self.config.MIN_USERNAME_LENGTH} characters long'
                ]
            elif not re.match(self.config.ALLOWED_USERNAME_CHARS, username):
                result['is_valid'] = False
                result['errors']['username'] = [
                    'Username contains invalid characters. Only letters, numbers, dots, dashes, and underscores are allowed'
                ]
        
        # Validate and sanitize email
        if 'email' in data:
            email = self.sanitizer.sanitize_email(data['email'])
            result['sanitized_data']['email'] = email
            
            if not email:
                result['is_valid'] = False
                result['errors']['email'] = ['Valid email address is required']
            else:
                try:
                    validated_email = validate_email(email)
                    result['sanitized_data']['email'] = validated_email.email
                    
                    # Check blocked domains
                    domain = email.split('@')[1].lower()
                    if domain in self.config.BLOCKED_EMAIL_DOMAINS:
                        result['is_valid'] = False
                        result['errors']['email'] = [
                            f'Email addresses from domain "{domain}" are not allowed'
                        ]
                
                except EmailNotValidError as e:
                    result['is_valid'] = False
                    result['errors']['email'] = [f'Invalid email format: {str(e)}']
        
        # Validate password
        if 'password' in data:
            password_result = self.password_validator.validate_password(data['password'])
            result['sanitized_data']['password'] = data['password']  # Don't sanitize passwords
            
            if not password_result['is_valid']:
                result['is_valid'] = False
                result['errors']['password'] = password_result['errors']
            
            if password_result['warnings']:
                result['warnings'].extend(password_result['warnings'])
        
        return result
    
    def validate_search_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and sanitize search parameters
        
        Args:
            params: Search parameters
            
        Returns:
            Validation result with sanitized parameters
        """
        result = {
            'is_valid': True,
            'errors': {},
            'sanitized_params': {}
        }
        
        # Sanitize search query
        if 'search' in params and params['search']:
            sanitized_search = self.sanitizer.sanitize_search_query(params['search'])
            result['sanitized_params']['search'] = sanitized_search
            
            if not sanitized_search and params['search']:
                result['is_valid'] = False
                result['errors']['search'] = ['Search query contains invalid characters']
        
        # Validate pagination parameters
        if 'page' in params:
            try:
                page = int(params['page'])
                if page < 1:
                    result['is_valid'] = False
                    result['errors']['page'] = ['Page number must be greater than 0']
                elif page > 10000:  # Reasonable upper limit
                    result['is_valid'] = False
                    result['errors']['page'] = ['Page number is too large']
                else:
                    result['sanitized_params']['page'] = page
            except (ValueError, TypeError):
                result['is_valid'] = False
                result['errors']['page'] = ['Page must be a valid number']
        
        if 'limit' in params:
            try:
                limit = int(params['limit'])
                if limit < 1:
                    result['is_valid'] = False
                    result['errors']['limit'] = ['Limit must be greater than 0']
                elif limit > 100:
                    result['is_valid'] = False
                    result['errors']['limit'] = ['Limit cannot exceed 100 items per page']
                else:
                    result['sanitized_params']['limit'] = limit
            except (ValueError, TypeError):
                result['is_valid'] = False
                result['errors']['limit'] = ['Limit must be a valid number']
        
        # Validate sort parameters
        allowed_sort_fields = ['username', 'email', 'created_at', 'updated_at', 'role']
        if 'sort_by' in params and params['sort_by']:
            sort_by = self.sanitizer.sanitize_string(params['sort_by'], 50)
            if sort_by in allowed_sort_fields:
                result['sanitized_params']['sort_by'] = sort_by
            else:
                result['is_valid'] = False
                result['errors']['sort_by'] = [
                    f'Invalid sort field. Allowed fields: {", ".join(allowed_sort_fields)}'
                ]
        
        if 'sort_order' in params and params['sort_order']:
            sort_order = self.sanitizer.sanitize_string(params['sort_order'], 10).lower()
            if sort_order in ['asc', 'desc']:
                result['sanitized_params']['sort_order'] = sort_order
            else:
                result['is_valid'] = False
                result['errors']['sort_order'] = ['Sort order must be either "asc" or "desc"']
        
        return result


def generate_secure_password(length: int = 16) -> str:
    """
    Generate a secure password
    
    Args:
        length: Password length
        
    Returns:
        Secure password string
    """
    if length < 12:
        length = 12
    
    # Ensure we have at least one character from each required category
    password_chars = []
    
    # Add required characters
    password_chars.append(secrets.choice(string.ascii_uppercase))
    password_chars.append(secrets.choice(string.ascii_lowercase))
    password_chars.append(secrets.choice(string.digits))
    password_chars.append(secrets.choice('!@#$%^&*(),.?":{}|<>'))
    password_chars.append(secrets.choice('!@#$%^&*(),.?":{}|<>'))  # Second special char
    
    # Fill the rest with random characters
    all_chars = string.ascii_letters + string.digits + '!@#$%^&*(),.?":{}|<>'
    for _ in range(length - len(password_chars)):
        password_chars.append(secrets.choice(all_chars))
    
    # Shuffle the password
    secrets.SystemRandom().shuffle(password_chars)
    
    return ''.join(password_chars)


def validate_ip_address(ip_address: str) -> bool:
    """
    Validate IP address format
    
    Args:
        ip_address: IP address to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not ip_address:
        return False
    
    # IPv4 validation
    ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if re.match(ipv4_pattern, ip_address):
        parts = ip_address.split('.')
        return all(0 <= int(part) <= 255 for part in parts)
    
    # IPv6 validation (basic)
    ipv6_pattern = r'^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$'
    if re.match(ipv6_pattern, ip_address):
        return True
    
    return False


def sanitize_user_agent(user_agent: str) -> str:
    """
    Sanitize user agent string
    
    Args:
        user_agent: User agent string
        
    Returns:
        Sanitized user agent string
    """
    if not user_agent:
        return ""
    
    # Limit length
    if len(user_agent) > 500:
        user_agent = user_agent[:500]
    
    # Remove dangerous characters
    user_agent = re.sub(r'[<>"\'\\\x00-\x1f]', '', user_agent)
    
    return user_agent.strip()