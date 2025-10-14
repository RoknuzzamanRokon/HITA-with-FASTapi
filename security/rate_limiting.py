"""
Rate Limiting for User Management Operations

This module provides rate limiting functionality to prevent abuse of sensitive
operations like user creation, password resets, and login attempts.
"""

import time
import json
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from fastapi import HTTPException, Request, status
from functools import wraps
import redis
import logging

logger = logging.getLogger(__name__)


class InMemoryRateLimiter:
    """In-memory rate limiter for development/testing"""
    
    def __init__(self):
        self.requests: Dict[str, list] = defaultdict(list)
        self.blocked_ips: Dict[str, datetime] = {}
    
    def is_allowed(self, key: str, limit: int, window_seconds: int) -> Tuple[bool, Dict[str, any]]:
        """
        Check if request is allowed based on rate limit
        
        Args:
            key: Unique identifier for the client (IP, user ID, etc.)
            limit: Maximum number of requests allowed
            window_seconds: Time window in seconds
            
        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        now = time.time()
        window_start = now - window_seconds
        
        # Clean old requests
        self.requests[key] = [req_time for req_time in self.requests[key] if req_time > window_start]
        
        # Check if blocked
        if key in self.blocked_ips and self.blocked_ips[key] > datetime.utcnow():
            return False, {
                'allowed': False,
                'limit': limit,
                'remaining': 0,
                'reset_time': int(self.blocked_ips[key].timestamp()),
                'blocked_until': self.blocked_ips[key].isoformat()
            }
        
        # Check rate limit
        current_requests = len(self.requests[key])
        
        if current_requests >= limit:
            # Block for extended period if repeatedly hitting limit
            if current_requests >= limit * 2:
                self.blocked_ips[key] = datetime.utcnow() + timedelta(hours=1)
            
            return False, {
                'allowed': False,
                'limit': limit,
                'remaining': 0,
                'reset_time': int(window_start + window_seconds),
                'retry_after': window_seconds
            }
        
        # Allow request
        self.requests[key].append(now)
        
        return True, {
            'allowed': True,
            'limit': limit,
            'remaining': limit - current_requests - 1,
            'reset_time': int(window_start + window_seconds)
        }
    
    def block_key(self, key: str, duration_minutes: int = 60):
        """Block a key for specified duration"""
        self.blocked_ips[key] = datetime.utcnow() + timedelta(minutes=duration_minutes)
    
    def unblock_key(self, key: str):
        """Unblock a key"""
        if key in self.blocked_ips:
            del self.blocked_ips[key]


class RedisRateLimiter:
    """Redis-based rate limiter for production"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    def is_allowed(self, key: str, limit: int, window_seconds: int) -> Tuple[bool, Dict[str, any]]:
        """
        Check if request is allowed using Redis sliding window
        
        Args:
            key: Unique identifier for the client
            limit: Maximum number of requests allowed
            window_seconds: Time window in seconds
            
        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        try:
            now = time.time()
            pipeline = self.redis.pipeline()
            
            # Remove old entries
            pipeline.zremrangebyscore(key, 0, now - window_seconds)
            
            # Count current requests
            pipeline.zcard(key)
            
            # Add current request
            pipeline.zadd(key, {str(now): now})
            
            # Set expiration
            pipeline.expire(key, window_seconds)
            
            results = pipeline.execute()
            current_requests = results[1]
            
            if current_requests >= limit:
                # Remove the request we just added since it's not allowed
                self.redis.zrem(key, str(now))
                
                return False, {
                    'allowed': False,
                    'limit': limit,
                    'remaining': 0,
                    'reset_time': int(now + window_seconds),
                    'retry_after': window_seconds
                }
            
            return True, {
                'allowed': True,
                'limit': limit,
                'remaining': limit - current_requests - 1,
                'reset_time': int(now + window_seconds)
            }
            
        except Exception as e:
            logger.error(f"Redis rate limiter error: {e}")
            # Fall back to allowing the request if Redis is unavailable
            return True, {
                'allowed': True,
                'limit': limit,
                'remaining': limit - 1,
                'reset_time': int(time.time() + window_seconds),
                'fallback': True
            }
    
    def block_key(self, key: str, duration_minutes: int = 60):
        """Block a key for specified duration"""
        block_key = f"blocked:{key}"
        self.redis.setex(block_key, duration_minutes * 60, "blocked")
    
    def is_blocked(self, key: str) -> bool:
        """Check if a key is blocked"""
        block_key = f"blocked:{key}"
        return self.redis.exists(block_key)


class RateLimitManager:
    """Main rate limit manager"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        if redis_client:
            self.limiter = RedisRateLimiter(redis_client)
        else:
            self.limiter = InMemoryRateLimiter()
        
        # Rate limit configurations
        self.limits = {
            'user_creation': {'limit': 5, 'window': 300},      # 5 per 5 minutes
            'password_reset': {'limit': 3, 'window': 300},     # 3 per 5 minutes
            'login_attempt': {'limit': 10, 'window': 300},     # 10 per 5 minutes
            'user_update': {'limit': 20, 'window': 300},       # 20 per 5 minutes
            'user_deletion': {'limit': 10, 'window': 300},     # 10 per 5 minutes
            'search_query': {'limit': 100, 'window': 300},     # 100 per 5 minutes
            'bulk_operations': {'limit': 2, 'window': 300},    # 2 per 5 minutes
        }
    
    def check_rate_limit(self, operation: str, identifier: str) -> Tuple[bool, Dict[str, any]]:
        """
        Check rate limit for an operation
        
        Args:
            operation: Type of operation (user_creation, login_attempt, etc.)
            identifier: Unique identifier (IP address, user ID, etc.)
            
        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        if operation not in self.limits:
            logger.warning(f"Unknown rate limit operation: {operation}")
            return True, {'allowed': True, 'unknown_operation': True}
        
        config = self.limits[operation]
        key = f"rate_limit:{operation}:{identifier}"
        
        return self.limiter.is_allowed(key, config['limit'], config['window'])
    
    def block_identifier(self, identifier: str, duration_minutes: int = 60):
        """Block an identifier across all operations"""
        self.limiter.block_key(f"blocked:{identifier}", duration_minutes)
    
    def get_client_identifier(self, request: Request, user_id: Optional[str] = None) -> str:
        """
        Get unique identifier for rate limiting
        
        Args:
            request: FastAPI request object
            user_id: Optional user ID for authenticated requests
            
        Returns:
            Unique identifier string
        """
        # For authenticated users, use user ID
        if user_id:
            return f"user:{user_id}"
        
        # For unauthenticated requests, use IP address
        client_ip = self._get_client_ip(request)
        return f"ip:{client_ip}"
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        # Check for forwarded headers (when behind proxy/load balancer)
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        # Fall back to direct client IP
        return request.client.host if request.client else 'unknown'


# Global rate limit manager instance
rate_limit_manager = RateLimitManager()


def rate_limit(operation: str, use_user_id: bool = False):
    """
    Decorator for rate limiting endpoints
    
    Args:
        operation: Type of operation for rate limiting
        use_user_id: Whether to use user ID for authenticated requests
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request and current_user from function arguments
            request = None
            current_user = None
            
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request:
                # Try to find request in kwargs
                for key, value in kwargs.items():
                    if isinstance(value, Request):
                        request = value
                        break
            
            if use_user_id:
                # Try to find current_user in kwargs
                for key, value in kwargs.items():
                    if hasattr(value, 'id') and hasattr(value, 'email'):
                        current_user = value
                        break
            
            if not request:
                logger.warning("Could not find request object for rate limiting")
                return await func(*args, **kwargs)
            
            # Get client identifier
            user_id = current_user.id if current_user and use_user_id else None
            identifier = rate_limit_manager.get_client_identifier(request, user_id)
            
            # Check rate limit
            is_allowed, rate_info = rate_limit_manager.check_rate_limit(operation, identifier)
            
            if not is_allowed:
                # Log rate limit violation
                logger.warning(
                    f"Rate limit exceeded for {operation} by {identifier}. "
                    f"Limit: {rate_info.get('limit')}, Reset: {rate_info.get('reset_time')}"
                )
                
                # Return rate limit error
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": True,
                        "message": f"Rate limit exceeded for {operation}",
                        "error_code": "RATE_LIMIT_EXCEEDED",
                        "rate_limit_info": rate_info
                    },
                    headers={
                        "X-RateLimit-Limit": str(rate_info.get('limit', 0)),
                        "X-RateLimit-Remaining": str(rate_info.get('remaining', 0)),
                        "X-RateLimit-Reset": str(rate_info.get('reset_time', 0)),
                        "Retry-After": str(rate_info.get('retry_after', 300))
                    }
                )
            
            # Add rate limit headers to successful responses
            response = await func(*args, **kwargs)
            
            # If response is a dict, we can't add headers directly
            # Headers should be added by middleware or in the endpoint
            
            return response
        
        return wrapper
    return decorator


class RateLimitMiddleware:
    """Middleware to add rate limit headers to responses"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Store rate limit info in scope for later use
        scope["rate_limit_info"] = {}
        
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                
                # Add rate limit headers if available
                rate_info = scope.get("rate_limit_info", {})
                if rate_info:
                    if "limit" in rate_info:
                        headers.append((b"x-ratelimit-limit", str(rate_info["limit"]).encode()))
                    if "remaining" in rate_info:
                        headers.append((b"x-ratelimit-remaining", str(rate_info["remaining"]).encode()))
                    if "reset_time" in rate_info:
                        headers.append((b"x-ratelimit-reset", str(rate_info["reset_time"]).encode()))
                
                message["headers"] = headers
            
            await send(message)
        
        await self.app(scope, receive, send_wrapper)


def check_suspicious_activity(identifier: str, operation: str) -> bool:
    """
    Check for suspicious activity patterns
    
    Args:
        identifier: Client identifier
        operation: Operation type
        
    Returns:
        True if activity is suspicious
    """
    # This is a simplified implementation
    # In production, you might want more sophisticated detection
    
    # Check if identifier is making too many different types of requests
    key_pattern = f"rate_limit:*:{identifier}"
    
    # For now, just return False
    # In a real implementation, you might check:
    # - Multiple failed login attempts
    # - Rapid user creation attempts
    # - Unusual request patterns
    
    return False


def get_rate_limit_status(operation: str, identifier: str) -> Dict[str, any]:
    """
    Get current rate limit status for an identifier
    
    Args:
        operation: Operation type
        identifier: Client identifier
        
    Returns:
        Rate limit status information
    """
    if operation not in rate_limit_manager.limits:
        return {'error': 'Unknown operation'}
    
    config = rate_limit_manager.limits[operation]
    key = f"rate_limit:{operation}:{identifier}"
    
    # This would need to be implemented based on the limiter type
    # For now, return basic info
    return {
        'operation': operation,
        'limit': config['limit'],
        'window_seconds': config['window'],
        'identifier': identifier
    }