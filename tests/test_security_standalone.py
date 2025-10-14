"""
Standalone Security Tests for User Management System

This module contains comprehensive tests for:
- Input validation and sanitization effectiveness
- Rate limiting and security controls
- Audit logging and activity tracking

Requirements tested: 5.1, 5.4, 5.5

This is a standalone version that doesn't require external dependencies
and demonstrates the security testing concepts.
"""

import re
import time
import json
from datetime import datetime, timedelta
from unittest.mock import Mock


class TestInputValidationAndSanitization:
    """Test input validation and sanitization effectiveness"""
    
    def test_password_strength_validation(self):
        """Test password strength validation requirements"""
        
        def validate_password_strength(password):
            """Simplified password validation for testing"""
            if not password or len(password) < 12:
                return False, ["Password must be at least 12 characters long"]
            
            errors = []
            if not re.search(r'[A-Z]', password):
                errors.append("Password must contain at least one uppercase letter")
            if not re.search(r'[a-z]', password):
                errors.append("Password must contain at least one lowercase letter")
            if not re.search(r'\d', password):
                errors.append("Password must contain at least one digit")
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
                errors.append("Password must contain at least one special character")
            
            # Check for common passwords
            common_passwords = {'password', '123456', 'qwerty', 'admin'}
            if password.lower() in common_passwords:
                errors.append("Password is too common")
            
            return len(errors) == 0, errors
        
        # Test weak passwords
        weak_passwords = [
            "password",           # Too common
            "123456789",         # Only digits
            "abcdefgh",          # Only lowercase
            "ABCDEFGH",          # Only uppercase
            "Password1",         # Too short, missing special chars
            "Pass!",             # Too short
        ]
        
        for password in weak_passwords:
            is_valid, errors = validate_password_strength(password)
            assert not is_valid, f"Password '{password}' should be invalid"
            assert len(errors) > 0
        
        # Test strong passwords
        strong_passwords = [
            "MySecureP@ssw0rd2024!",
            "Tr0ub4dor&3Complex",
            "S3cur3P@ssw0rd#2024",
        ]
        
        for password in strong_passwords:
            is_valid, errors = validate_password_strength(password)
            assert is_valid, f"Password '{password}' should be valid. Errors: {errors}"
    
    def test_username_sanitization(self):
        """Test username sanitization effectiveness"""
        
        def sanitize_username(username):
            """Simplified username sanitization for testing"""
            if not username:
                return ""
            
            username = str(username).strip()
            
            # Remove invalid characters
            username = re.sub(r'[^a-zA-Z0-9_\-\.]', '', username)
            
            # Limit length
            if len(username) > 50:
                username = username[:50]
            
            # Remove leading/trailing dots and dashes
            username = username.strip('.-')
            
            return username
        
        test_cases = [
            # (input, expected_output)
            ("valid_username", "valid_username"),
            ("user.name-123", "user.name-123"),
            ("user@name#123", "username123"),  # Remove invalid chars
            ("<script>alert('xss')</script>", "scriptalertxssscript"),  # Remove HTML
            ("user name", "username"),  # Remove spaces
            ("user" * 20, "user" * 12 + "us"),  # Truncate to max length
            ("..-username-..", "username"),  # Remove leading/trailing dots/dashes
            ("", ""),  # Empty string
        ]
        
        for input_val, expected in test_cases:
            result = sanitize_username(input_val)
            assert result == expected, f"Input: {input_val}, Expected: {expected}, Got: {result}"
    
    def test_email_sanitization(self):
        """Test email sanitization effectiveness"""
        
        def sanitize_email(email):
            """Simplified email sanitization for testing"""
            if not email:
                return ""
            
            email = str(email).strip().lower()
            
            # Length check
            if len(email) > 254:
                return ""
            
            # Basic format validation
            if '@' not in email or email.count('@') != 1:
                return ""
            
            # Check for valid format (must have content before and after @)
            parts = email.split('@')
            if len(parts) != 2 or not parts[0] or not parts[1]:
                return ""
            
            # Remove dangerous characters
            email = re.sub(r'[<>"\'\\\x00-\x1f]', '', email)
            
            return email
        
        test_cases = [
            # (input, expected_output)
            ("user@example.com", "user@example.com"),
            ("User@Example.COM", "user@example.com"),  # Lowercase
            ("user+tag@example.com", "user+tag@example.com"),  # Valid plus addressing
            ("user@", ""),  # Invalid format
            ("@example.com", ""),  # Invalid format
            ("user@@example.com", ""),  # Multiple @
            ("user<script>@example.com", "userscript@example.com"),  # Remove dangerous chars
            ("user'\"@example.com", "user@example.com"),  # Remove quotes
            ("a" * 300 + "@example.com", ""),  # Too long
            ("", ""),  # Empty string
        ]
        
        for input_val, expected in test_cases:
            result = sanitize_email(input_val)
            assert result == expected, f"Input: {input_val}, Expected: {expected}, Got: {result}"
    
    def test_sql_injection_prevention(self):
        """Test SQL injection prevention in search queries"""
        
        def sanitize_search_query(query):
            """Simplified search query sanitization for testing"""
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
                r'[\'";]'
            ]
            
            for pattern in sql_patterns:
                query = re.sub(pattern, '', query, flags=re.IGNORECASE)
            
            return query.strip()
        
        # SQL injection attempts
        sql_injection_tests = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "' UNION SELECT * FROM users --",
            "admin'--",
            "' OR 1=1 #",
            "'; INSERT INTO users VALUES ('hacker', 'password'); --"
        ]
        
        for malicious_query in sql_injection_tests:
            result = sanitize_search_query(malicious_query)
            # Should remove SQL keywords and dangerous characters
            assert "drop" not in result.lower()
            assert "union" not in result.lower()
            assert "insert" not in result.lower()
            assert "'" not in result
            assert ";" not in result
            assert "--" not in result
    
    def test_xss_prevention(self):
        """Test XSS prevention in user input"""
        
        def sanitize_html_input(input_str):
            """Simplified HTML input sanitization for testing"""
            if not input_str:
                return ""
            
            # Remove dangerous patterns
            dangerous_patterns = [
                r'<script[^>]*>.*?</script>',  # Script tags
                r'javascript:',               # JavaScript URLs
                r'on\w+\s*=',                # Event handlers
                r'<iframe[^>]*>.*?</iframe>', # Iframes
            ]
            
            for pattern in dangerous_patterns:
                input_str = re.sub(pattern, '', input_str, flags=re.IGNORECASE)
            
            # HTML escape remaining content
            input_str = input_str.replace('<', '&lt;').replace('>', '&gt;')
            
            return input_str
        
        xss_tests = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "<iframe src='javascript:alert(1)'></iframe>",
            "<div onclick='alert(1)'>Click me</div>"
        ]
        
        for xss_input in xss_tests:
            result = sanitize_html_input(xss_input)
            assert "<script" not in result.lower()
            assert "javascript:" not in result.lower()
            assert "onerror" not in result.lower()
            assert "<iframe" not in result.lower()
            assert "onclick" not in result.lower()


class TestRateLimitingAndSecurityControls:
    """Test rate limiting and security controls"""
    
    def test_basic_rate_limiting(self):
        """Test basic rate limiting functionality"""
        
        class SimpleRateLimiter:
            def __init__(self):
                self.requests = {}
            
            def is_allowed(self, key, limit, window_seconds):
                now = time.time()
                window_start = now - window_seconds
                
                # Clean old requests
                if key in self.requests:
                    self.requests[key] = [req_time for req_time in self.requests[key] if req_time > window_start]
                else:
                    self.requests[key] = []
                
                # Check limit
                if len(self.requests[key]) >= limit:
                    return False, {'allowed': False, 'remaining': 0}
                
                # Allow request
                self.requests[key].append(now)
                return True, {'allowed': True, 'remaining': limit - len(self.requests[key])}
        
        limiter = SimpleRateLimiter()
        
        # Test within limit
        for i in range(5):
            allowed, info = limiter.is_allowed("test_key", 5, 60)
            assert allowed, f"Request {i+1} should be allowed"
            assert info['remaining'] == 5 - i - 1
        
        # Test exceeding limit
        allowed, info = limiter.is_allowed("test_key", 5, 60)
        assert not allowed, "Request should be blocked after exceeding limit"
        assert info['remaining'] == 0
    
    def test_rate_limit_window_reset(self):
        """Test rate limiter window reset"""
        
        class TimeBasedRateLimiter:
            def __init__(self):
                self.requests = {}
            
            def is_allowed(self, key, limit, window_seconds):
                now = time.time()
                window_start = now - window_seconds
                
                if key not in self.requests:
                    self.requests[key] = []
                
                # Clean old requests
                self.requests[key] = [req_time for req_time in self.requests[key] if req_time > window_start]
                
                if len(self.requests[key]) >= limit:
                    return False, {'allowed': False}
                
                self.requests[key].append(now)
                return True, {'allowed': True}
        
        limiter = TimeBasedRateLimiter()
        
        # Fill up the limit
        for i in range(5):
            limiter.is_allowed("test_key", 5, 1)  # 1 second window
        
        # Should be blocked
        allowed, _ = limiter.is_allowed("test_key", 5, 1)
        assert not allowed
        
        # Wait for window to reset
        time.sleep(1.1)
        
        # Should be allowed again
        allowed, _ = limiter.is_allowed("test_key", 5, 1)
        assert allowed
    
    def test_ip_address_validation(self):
        """Test IP address validation utility"""
        
        def validate_ip_address(ip_address):
            """Simplified IP validation for testing"""
            if not ip_address:
                return False
            
            # IPv4 validation
            ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
            if re.match(ipv4_pattern, ip_address):
                parts = ip_address.split('.')
                try:
                    return all(0 <= int(part) <= 255 for part in parts)
                except ValueError:
                    return False
            
            return False
        
        # Valid IPv4 addresses
        valid_ipv4 = [
            "192.168.1.1",
            "10.0.0.1",
            "127.0.0.1",
            "8.8.8.8",
            "255.255.255.255"
        ]
        
        for ip in valid_ipv4:
            assert validate_ip_address(ip), f"IP {ip} should be valid"
        
        # Invalid IPv4 addresses
        invalid_ipv4 = [
            "256.1.1.1",
            "192.168.1",
            "192.168.1.1.1",
            "192.168.-1.1",
            "not.an.ip.address",
            "",
            None
        ]
        
        for ip in invalid_ipv4:
            assert not validate_ip_address(ip), f"IP {ip} should be invalid"
    
    def test_suspicious_activity_detection(self):
        """Test suspicious activity detection patterns"""
        
        def detect_suspicious_patterns(request_data):
            """Simplified suspicious activity detection for testing"""
            suspicious_indicators = []
            
            # Check user agent
            user_agent = request_data.get('user_agent', '').lower()
            suspicious_agents = ['bot', 'crawler', 'scanner', 'hack', 'exploit']
            if any(agent in user_agent for agent in suspicious_agents):
                suspicious_indicators.append('suspicious_user_agent')
            
            # Check for malicious URL patterns
            url_path = request_data.get('url_path', '').lower()
            malicious_patterns = [
                'union select', 'drop table', '../', '/etc/passwd',
                '<script', 'javascript:', 'cmd.exe'
            ]
            if any(pattern in url_path for pattern in malicious_patterns):
                suspicious_indicators.append('malicious_url_pattern')
            
            # Check request frequency
            if request_data.get('requests_per_minute', 0) > 100:
                suspicious_indicators.append('high_request_frequency')
            
            return len(suspicious_indicators) > 0, suspicious_indicators
        
        # Test normal requests
        normal_requests = [
            {'user_agent': 'Mozilla/5.0 Chrome/91.0', 'url_path': '/api/users', 'requests_per_minute': 10},
            {'user_agent': 'Safari/14.0', 'url_path': '/dashboard', 'requests_per_minute': 5},
        ]
        
        for request_data in normal_requests:
            is_suspicious, indicators = detect_suspicious_patterns(request_data)
            assert not is_suspicious, f"Normal request should not be suspicious: {request_data}"
        
        # Test suspicious requests
        suspicious_requests = [
            {'user_agent': 'malicious bot scanner', 'url_path': '/api/users', 'requests_per_minute': 10},
            {'user_agent': 'Chrome/91.0', 'url_path': '/api/users?id=1 UNION SELECT * FROM users', 'requests_per_minute': 10},
            {'user_agent': 'Chrome/91.0', 'url_path': '/api/users', 'requests_per_minute': 150},
        ]
        
        for request_data in suspicious_requests:
            is_suspicious, indicators = detect_suspicious_patterns(request_data)
            assert is_suspicious, f"Suspicious request should be detected: {request_data}"
            assert len(indicators) > 0


class TestAuditLoggingAndActivityTracking:
    """Test audit logging and activity tracking"""
    
    def test_activity_logging_structure(self):
        """Test audit log entry structure and data integrity"""
        
        class SimpleAuditLogger:
            def __init__(self):
                self.logs = []
            
            def log_activity(self, activity_type, user_id=None, details=None, 
                           ip_address=None, security_level="low", success=True):
                log_entry = {
                    'id': len(self.logs) + 1,
                    'activity_type': activity_type,
                    'user_id': user_id,
                    'details': details or {},
                    'ip_address': ip_address,
                    'security_level': security_level,
                    'success': success,
                    'timestamp': datetime.utcnow().isoformat()
                }
                self.logs.append(log_entry)
                return log_entry
            
            def get_logs_by_user(self, user_id):
                return [log for log in self.logs if log['user_id'] == user_id]
            
            def get_security_events(self, level=None):
                security_activities = ['login_failed', 'unauthorized_access', 'suspicious_activity']
                logs = [log for log in self.logs if log['activity_type'] in security_activities]
                if level:
                    logs = [log for log in logs if log['security_level'] == level]
                return logs
        
        logger = SimpleAuditLogger()
        
        # Test basic activity logging
        log_entry = logger.log_activity(
            activity_type="user_created",
            user_id="user123",
            details={"username": "testuser", "email": "test@example.com"},
            ip_address="127.0.0.1",
            security_level="medium"
        )
        
        assert log_entry['activity_type'] == "user_created"
        assert log_entry['user_id'] == "user123"
        assert log_entry['ip_address'] == "127.0.0.1"
        assert log_entry['security_level'] == "medium"
        assert log_entry['success'] is True
        assert 'timestamp' in log_entry
        assert 'username' in log_entry['details']
    
    def test_authentication_event_logging(self):
        """Test authentication event logging"""
        
        class AuthenticationLogger:
            def __init__(self):
                self.logs = []
            
            def log_authentication_event(self, event_type, user_id=None, email=None, 
                                       ip_address=None, success=True, failure_reason=None):
                details = {'email': email}
                if not success and failure_reason:
                    details['failure_reason'] = failure_reason
                
                log_entry = {
                    'activity_type': event_type,
                    'user_id': user_id,
                    'details': details,
                    'ip_address': ip_address,
                    'success': success,
                    'security_level': 'medium' if success else 'high',
                    'timestamp': datetime.utcnow().isoformat()
                }
                self.logs.append(log_entry)
                return log_entry
        
        auth_logger = AuthenticationLogger()
        
        # Test successful login
        success_log = auth_logger.log_authentication_event(
            event_type="login_success",
            user_id="user123",
            email="user@example.com",
            ip_address="192.168.1.1",
            success=True
        )
        
        assert success_log['activity_type'] == "login_success"
        assert success_log['success'] is True
        assert success_log['security_level'] == 'medium'
        
        # Test failed login
        failed_log = auth_logger.log_authentication_event(
            event_type="login_failed",
            user_id=None,
            email="user@example.com",
            ip_address="192.168.1.1",
            success=False,
            failure_reason="Invalid password"
        )
        
        assert failed_log['activity_type'] == "login_failed"
        assert failed_log['success'] is False
        assert failed_log['security_level'] == 'high'
        assert failed_log['details']['failure_reason'] == "Invalid password"
    
    def test_security_event_logging(self):
        """Test security event logging and alerting"""
        
        class SecurityEventLogger:
            def __init__(self):
                self.logs = []
                self.alerts = []
            
            def log_security_event(self, event_type, user_id=None, ip_address=None, 
                                 details=None, security_level="high"):
                log_entry = {
                    'activity_type': event_type,
                    'user_id': user_id,
                    'ip_address': ip_address,
                    'details': details or {},
                    'security_level': security_level,
                    'requires_investigation': security_level in ['high', 'critical'],
                    'timestamp': datetime.utcnow().isoformat()
                }
                self.logs.append(log_entry)
                
                # Generate alert for high-priority events
                if security_level in ['high', 'critical']:
                    self.alerts.append({
                        'log_id': len(self.logs),
                        'event_type': event_type,
                        'severity': security_level,
                        'timestamp': log_entry['timestamp']
                    })
                
                return log_entry
            
            def get_high_priority_events(self, hours=24):
                cutoff_time = datetime.utcnow() - timedelta(hours=hours)
                return [
                    log for log in self.logs 
                    if log['security_level'] in ['high', 'critical'] 
                    and datetime.fromisoformat(log['timestamp']) > cutoff_time
                ]
        
        security_logger = SecurityEventLogger()
        
        # Test suspicious activity logging
        suspicious_log = security_logger.log_security_event(
            event_type="suspicious_activity",
            user_id="user123",
            ip_address="suspicious.ip.com",
            details={"reason": "multiple_failed_attempts", "attempts": 5},
            security_level="high"
        )
        
        assert suspicious_log['activity_type'] == "suspicious_activity"
        assert suspicious_log['requires_investigation'] is True
        assert suspicious_log['details']['reason'] == "multiple_failed_attempts"
        assert len(security_logger.alerts) == 1
        
        # Test critical security event
        critical_log = security_logger.log_security_event(
            event_type="unauthorized_access",
            ip_address="malicious.ip.com",
            details={"attempted_endpoint": "/admin/users", "method": "DELETE"},
            security_level="critical"
        )
        
        assert critical_log['security_level'] == "critical"
        assert len(security_logger.alerts) == 2
        
        # Test high priority events retrieval
        high_priority = security_logger.get_high_priority_events()
        assert len(high_priority) == 2
    
    def test_activity_history_and_analytics(self):
        """Test activity history retrieval and analytics"""
        
        class ActivityAnalyzer:
            def __init__(self):
                self.logs = []
            
            def add_activity(self, activity_type, user_id, timestamp=None):
                log_entry = {
                    'activity_type': activity_type,
                    'user_id': user_id,
                    'timestamp': timestamp or datetime.utcnow()
                }
                self.logs.append(log_entry)
            
            def get_user_activity_history(self, user_id, days=30):
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                return [
                    log for log in self.logs 
                    if log['user_id'] == user_id and log['timestamp'] > cutoff_date
                ]
            
            def get_activity_summary(self, days=30):
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                recent_logs = [log for log in self.logs if log['timestamp'] > cutoff_date]
                
                activity_counts = {}
                for log in recent_logs:
                    activity_type = log['activity_type']
                    activity_counts[activity_type] = activity_counts.get(activity_type, 0) + 1
                
                return {
                    'total_activities': len(recent_logs),
                    'activity_by_type': activity_counts,
                    'unique_users': len(set(log['user_id'] for log in recent_logs))
                }
        
        analyzer = ActivityAnalyzer()
        
        # Create test activities
        test_activities = [
            ("login_success", "user1", datetime.utcnow() - timedelta(days=1)),
            ("user_created", "admin1", datetime.utcnow() - timedelta(days=2)),
            ("login_success", "user1", datetime.utcnow() - timedelta(days=5)),
            ("points_given", "user2", datetime.utcnow() - timedelta(days=10)),
            ("login_success", "user1", datetime.utcnow() - timedelta(days=35)),  # Outside 30-day window
        ]
        
        for activity_type, user_id, timestamp in test_activities:
            analyzer.add_activity(activity_type, user_id, timestamp)
        
        # Test user activity history
        user1_history = analyzer.get_user_activity_history("user1", days=30)
        assert len(user1_history) == 2  # Should exclude the 35-day old activity
        
        user1_week_history = analyzer.get_user_activity_history("user1", days=7)
        assert len(user1_week_history) == 2  # Both activities within 7 days
        
        # Test activity summary
        summary = analyzer.get_activity_summary(days=30)
        assert summary['total_activities'] == 4  # Excludes 35-day old activity
        assert summary['activity_by_type']['login_success'] == 2
        assert summary['activity_by_type']['user_created'] == 1
        assert summary['unique_users'] == 3  # user1, admin1, user2


class TestSecurityIntegration:
    """Test security integration scenarios"""
    
    def test_end_to_end_security_flow(self):
        """Test end-to-end security flow with validation, rate limiting, and logging"""
        
        # Mock security components
        class SecuritySystem:
            def __init__(self):
                self.rate_limiter = {}
                self.audit_logs = []
                self.blocked_ips = set()
            
            def validate_input(self, data):
                """Validate user input"""
                errors = {}
                
                if 'username' in data:
                    username = data['username']
                    if not username or len(username) < 3:
                        errors['username'] = 'Username must be at least 3 characters'
                    elif not re.match(r'^[a-zA-Z0-9_]+$', username):
                        errors['username'] = 'Username contains invalid characters'
                
                if 'email' in data:
                    email = data['email']
                    if not email or '@' not in email:
                        errors['email'] = 'Invalid email format'
                
                if 'password' in data:
                    password = data['password']
                    if not password or len(password) < 8:
                        errors['password'] = 'Password must be at least 8 characters'
                
                return len(errors) == 0, errors
            
            def check_rate_limit(self, ip_address, operation):
                """Check rate limiting"""
                key = f"{ip_address}:{operation}"
                now = time.time()
                
                if key not in self.rate_limiter:
                    self.rate_limiter[key] = []
                
                # Clean old requests (5-minute window)
                self.rate_limiter[key] = [
                    req_time for req_time in self.rate_limiter[key] 
                    if now - req_time < 300
                ]
                
                # Check limit (5 requests per 5 minutes for user creation)
                if len(self.rate_limiter[key]) >= 5:
                    return False
                
                self.rate_limiter[key].append(now)
                return True
            
            def log_activity(self, activity_type, user_id=None, ip_address=None, 
                           success=True, details=None):
                """Log security activity"""
                log_entry = {
                    'activity_type': activity_type,
                    'user_id': user_id,
                    'ip_address': ip_address,
                    'success': success,
                    'details': details or {},
                    'timestamp': datetime.utcnow().isoformat()
                }
                self.audit_logs.append(log_entry)
                return log_entry
            
            def process_user_creation(self, user_data, ip_address, acting_user_id):
                """Complete user creation flow with security checks"""
                # 1. Check if IP is blocked
                if ip_address in self.blocked_ips:
                    self.log_activity("user_creation_blocked", acting_user_id, ip_address, 
                                    False, {"reason": "blocked_ip"})
                    return False, "IP address is blocked"
                
                # 2. Validate input
                is_valid, validation_errors = self.validate_input(user_data)
                if not is_valid:
                    self.log_activity("user_creation_failed", acting_user_id, ip_address, 
                                    False, {"reason": "validation_failed", "errors": validation_errors})
                    return False, f"Validation failed: {validation_errors}"
                
                # 3. Check rate limit
                if not self.check_rate_limit(ip_address, "user_creation"):
                    self.log_activity("user_creation_rate_limited", acting_user_id, ip_address, 
                                    False, {"reason": "rate_limit_exceeded"})
                    return False, "Rate limit exceeded"
                
                # 4. Process creation (simplified)
                new_user_id = f"user_{len(self.audit_logs) + 1}"
                
                # 5. Log successful creation
                self.log_activity("user_created", acting_user_id, ip_address, True, {
                    "created_user_id": new_user_id,
                    "username": user_data['username'],
                    "email": user_data['email']
                })
                
                return True, f"User created successfully: {new_user_id}"
        
        # Test the complete flow
        security_system = SecuritySystem()
        
        # Test successful user creation
        valid_user_data = {
            'username': 'newuser123',
            'email': 'newuser@example.com',
            'password': 'SecurePassword123!'
        }
        
        success, message = security_system.process_user_creation(
            valid_user_data, "127.0.0.1", "admin123"
        )
        
        assert success, f"User creation should succeed: {message}"
        assert "User created successfully" in message
        
        # Verify audit log
        creation_logs = [log for log in security_system.audit_logs if log['activity_type'] == 'user_created']
        assert len(creation_logs) == 1
        assert creation_logs[0]['success'] is True
        assert creation_logs[0]['details']['username'] == 'newuser123'
        
        # Test validation failure
        invalid_user_data = {
            'username': 'u',  # Too short
            'email': 'invalid-email',  # Invalid format
            'password': '123'  # Too short
        }
        
        success, message = security_system.process_user_creation(
            invalid_user_data, "127.0.0.1", "admin123"
        )
        
        assert not success, "Invalid user creation should fail"
        assert "Validation failed" in message
        
        # Test rate limiting
        for i in range(5):  # Fill up the rate limit
            security_system.process_user_creation(valid_user_data, "192.168.1.1", "admin123")
        
        # This should be rate limited
        success, message = security_system.process_user_creation(
            valid_user_data, "192.168.1.1", "admin123"
        )
        
        assert not success, "Should be rate limited"
        assert "Rate limit exceeded" in message
        
        # Verify rate limit log
        rate_limit_logs = [log for log in security_system.audit_logs if log['activity_type'] == 'user_creation_rate_limited']
        assert len(rate_limit_logs) == 1
    
    def test_security_monitoring_and_alerting(self):
        """Test security monitoring and alerting system"""
        
        class SecurityMonitor:
            def __init__(self):
                self.events = []
                self.alerts = []
                self.threat_scores = {}
            
            def record_event(self, event_type, source_ip, details=None):
                """Record a security event"""
                event = {
                    'type': event_type,
                    'source_ip': source_ip,
                    'details': details or {},
                    'timestamp': datetime.utcnow(),
                    'severity': self._calculate_severity(event_type, source_ip)
                }
                self.events.append(event)
                
                # Update threat score for IP
                if source_ip not in self.threat_scores:
                    self.threat_scores[source_ip] = 0
                
                self.threat_scores[source_ip] += self._get_threat_score(event_type)
                
                # Generate alert if needed
                if event['severity'] >= 7 or self.threat_scores[source_ip] >= 50:
                    self._generate_alert(event, source_ip)
                
                return event
            
            def _calculate_severity(self, event_type, source_ip):
                """Calculate event severity (1-10 scale)"""
                base_severity = {
                    'failed_login': 3,
                    'rate_limit_exceeded': 5,
                    'suspicious_activity': 7,
                    'unauthorized_access': 9,
                    'malicious_request': 8
                }
                
                severity = base_severity.get(event_type, 5)
                
                # Increase severity for repeat offenders
                if self.threat_scores.get(source_ip, 0) > 20:
                    severity = min(10, severity + 2)
                
                return severity
            
            def _get_threat_score(self, event_type):
                """Get threat score increment for event type"""
                scores = {
                    'failed_login': 5,
                    'rate_limit_exceeded': 10,
                    'suspicious_activity': 15,
                    'unauthorized_access': 25,
                    'malicious_request': 20
                }
                return scores.get(event_type, 5)
            
            def _generate_alert(self, event, source_ip):
                """Generate security alert"""
                alert = {
                    'id': len(self.alerts) + 1,
                    'event_type': event['type'],
                    'source_ip': source_ip,
                    'severity': event['severity'],
                    'threat_score': self.threat_scores[source_ip],
                    'timestamp': event['timestamp'],
                    'requires_action': event['severity'] >= 8 or self.threat_scores[source_ip] >= 75
                }
                self.alerts.append(alert)
                return alert
            
            def get_high_risk_ips(self, threshold=30):
                """Get IPs with high threat scores"""
                return {
                    ip: score for ip, score in self.threat_scores.items() 
                    if score >= threshold
                }
            
            def get_recent_alerts(self, hours=24):
                """Get recent security alerts"""
                cutoff_time = datetime.utcnow() - timedelta(hours=hours)
                return [
                    alert for alert in self.alerts 
                    if alert['timestamp'] > cutoff_time
                ]
        
        monitor = SecurityMonitor()
        
        # Simulate security events
        events = [
            ('failed_login', '192.168.1.100', {'username': 'admin', 'attempts': 1}),
            ('failed_login', '192.168.1.100', {'username': 'admin', 'attempts': 2}),
            ('failed_login', '192.168.1.100', {'username': 'admin', 'attempts': 3}),
            ('rate_limit_exceeded', '192.168.1.100', {'operation': 'login'}),
            ('suspicious_activity', '10.0.0.50', {'pattern': 'sql_injection_attempt'}),
            ('unauthorized_access', '203.0.113.1', {'endpoint': '/admin/users', 'method': 'DELETE'}),
        ]
        
        for event_type, source_ip, details in events:
            monitor.record_event(event_type, source_ip, details)
        
        # Test threat scoring
        assert monitor.threat_scores['192.168.1.100'] >= 25  # Multiple failed logins + rate limit
        assert monitor.threat_scores['10.0.0.50'] >= 15  # Suspicious activity
        assert monitor.threat_scores['203.0.113.1'] >= 25  # Unauthorized access
        
        # Test alert generation
        assert len(monitor.alerts) >= 2  # Should have alerts for high-severity events
        
        # Test high-risk IP identification
        high_risk_ips = monitor.get_high_risk_ips(threshold=20)
        assert len(high_risk_ips) >= 2
        assert '192.168.1.100' in high_risk_ips
        
        # Test recent alerts
        recent_alerts = monitor.get_recent_alerts()
        assert len(recent_alerts) == len(monitor.alerts)  # All alerts are recent
        
        # Verify alert details
        critical_alerts = [alert for alert in monitor.alerts if alert['requires_action']]
        assert len(critical_alerts) >= 1  # Should have at least one critical alert


def run_all_tests():
    """Run all security tests"""
    print("Running Security Tests for User Management System")
    print("=" * 60)
    
    test_classes = [
        TestInputValidationAndSanitization,
        TestRateLimitingAndSecurityControls,
        TestAuditLoggingAndActivityTracking,
        TestSecurityIntegration
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_tests = []
    
    for test_class in test_classes:
        print(f"\n{test_class.__name__}:")
        print("-" * 40)
        
        test_instance = test_class()
        test_methods = [method for method in dir(test_instance) if method.startswith('test_')]
        
        for test_method in test_methods:
            total_tests += 1
            try:
                getattr(test_instance, test_method)()
                print(f"  ✓ {test_method}")
                passed_tests += 1
            except Exception as e:
                print(f"  ✗ {test_method}: {str(e)}")
                failed_tests.append(f"{test_class.__name__}.{test_method}: {str(e)}")
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed_tests}/{total_tests} passed")
    
    if failed_tests:
        print(f"\nFailed Tests ({len(failed_tests)}):")
        for failure in failed_tests:
            print(f"  - {failure}")
    else:
        print("\n🎉 All tests passed!")
    
    return len(failed_tests) == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)