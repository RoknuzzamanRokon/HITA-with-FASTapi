"""
API Logging Middleware for comprehensive user activity tracking

This middleware automatically logs all API requests to track user activity,
endpoint usage, and system interactions for the user activity dashboard.
"""

import time
import json
from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
from sqlalchemy.orm import Session
from database import get_db
from security.audit_logging import AuditLogger, ActivityType, SecurityLevel
import models


class APILoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all API requests for user activity tracking"""

    def __init__(self, app, exclude_paths: Optional[list] = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/favicon.ico",
            "/health",
            "/metrics",
        ]

    async def dispatch(self, request: Request, call_next):
        # Skip logging for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)

        # Record start time
        start_time = time.time()

        # Extract user information if available
        user_id = None
        user_email = None

        # Try to get user from request state (set by auth middleware)
        if hasattr(request.state, "user") and request.state.user:
            user_id = request.state.user.id
            user_email = request.state.user.email

        # Process the request
        response = await call_next(request)

        # Calculate processing time
        process_time = time.time() - start_time

        # Log the API access
        await self._log_api_access(
            request=request,
            response=response,
            user_id=user_id,
            user_email=user_email,
            process_time=process_time,
        )

        return response

    async def _log_api_access(
        self,
        request: Request,
        response: StarletteResponse,
        user_id: Optional[str],
        user_email: Optional[str],
        process_time: float,
    ):
        """Log API access to the database"""

        try:
            # Get database session
            db_gen = get_db()
            db: Session = next(db_gen)

            try:
                audit_logger = AuditLogger(db)

                # Extract request details
                method = request.method
                endpoint = request.url.path
                query_params = (
                    dict(request.query_params) if request.query_params else {}
                )
                status_code = response.status_code

                # Determine if this was a successful request
                is_success = 200 <= status_code < 400

                # Prepare activity details
                details = {
                    "endpoint": endpoint,
                    "method": method,
                    "status_code": status_code,
                    "process_time_ms": round(process_time * 1000, 2),
                    "query_params": query_params,
                    "user_email": user_email,
                    "timestamp": datetime.utcnow().isoformat(),
                }

                # Add request body size if available
                if hasattr(request, "content_length") and request.content_length:
                    details["request_size_bytes"] = request.content_length

                # Add response size if available
                if hasattr(response, "content_length") and response.content_length:
                    details["response_size_bytes"] = response.content_length

                # Determine security level based on endpoint and status
                security_level = SecurityLevel.LOW
                if status_code >= 400:
                    security_level = SecurityLevel.MEDIUM
                if status_code >= 500:
                    security_level = SecurityLevel.HIGH

                # Special handling for sensitive endpoints
                sensitive_endpoints = [
                    "/v1.0/auth/login",
                    "/v1.0/auth/register",
                    "/v1.0/user/create",
                    "/v1.0/user/points/give",
                ]

                if any(endpoint.startswith(path) for path in sensitive_endpoints):
                    security_level = SecurityLevel.MEDIUM

                # Log the activity
                audit_logger.log_activity(
                    activity_type=ActivityType.API_ACCESS,
                    user_id=user_id,
                    details=details,
                    request=request,
                    security_level=security_level,
                    success=is_success,
                )

                # Log errors separately for better tracking
                if not is_success:
                    audit_logger.log_activity(
                        activity_type=ActivityType.API_ERROR,
                        user_id=user_id,
                        details={
                            **details,
                            "error_category": self._categorize_error(status_code),
                            "requires_attention": status_code >= 500,
                        },
                        request=request,
                        security_level=security_level,
                        success=False,
                    )

            finally:
                db.close()

        except Exception as e:
            # Don't let logging failures break the API
            print(f"Failed to log API access: {e}")

    def _categorize_error(self, status_code: int) -> str:
        """Categorize errors based on status code"""
        if status_code == 400:
            return "Bad Request"
        elif status_code == 401:
            return "Unauthorized"
        elif status_code == 403:
            return "Forbidden"
        elif status_code == 404:
            return "Not Found"
        elif status_code == 422:
            return "Validation Error"
        elif status_code == 429:
            return "Rate Limited"
        elif 400 <= status_code < 500:
            return "Client Error"
        elif 500 <= status_code < 600:
            return "Server Error"
        else:
            return "Unknown Error"


class EnhancedAPILoggingMiddleware(BaseHTTPMiddleware):
    """Enhanced version with more detailed logging and performance metrics"""

    def __init__(
        self,
        app,
        exclude_paths: Optional[list] = None,
        log_request_body: bool = False,
        log_response_body: bool = False,
        max_body_size: int = 1024,  # Max body size to log in bytes
    ):
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/favicon.ico",
            "/health",
            "/metrics",
        ]
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self.max_body_size = max_body_size

    async def dispatch(self, request: Request, call_next):
        # Skip logging for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)

        # Record detailed timing
        start_time = time.time()

        # Extract comprehensive request information
        request_info = await self._extract_request_info(request)

        # Process the request
        response = await call_next(request)

        # Calculate timing
        end_time = time.time()
        process_time = end_time - start_time

        # Extract response information
        response_info = self._extract_response_info(response)

        # Log comprehensive API access
        await self._log_comprehensive_access(
            request=request,
            response=response,
            request_info=request_info,
            response_info=response_info,
            process_time=process_time,
        )

        return response

    async def _extract_request_info(self, request: Request) -> Dict[str, Any]:
        """Extract comprehensive request information"""
        info = {
            "method": request.method,
            "endpoint": request.url.path,
            "query_params": dict(request.query_params),
            "headers": dict(request.headers),
            "client_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "content_type": request.headers.get("content-type"),
            "content_length": request.headers.get("content-length"),
        }

        # Extract user information if available
        if hasattr(request.state, "user") and request.state.user:
            info.update(
                {
                    "user_id": request.state.user.id,
                    "user_email": request.state.user.email,
                    "user_role": request.state.user.role.value,
                }
            )

        # Log request body if enabled and size is reasonable
        if self.log_request_body and info.get("content_length"):
            try:
                content_length = int(info["content_length"])
                if content_length <= self.max_body_size:
                    body = await request.body()
                    if body:
                        # Try to parse as JSON, fallback to string
                        try:
                            info["request_body"] = json.loads(body.decode())
                        except:
                            info["request_body"] = body.decode()[: self.max_body_size]
            except:
                pass

        return info

    def _extract_response_info(self, response: StarletteResponse) -> Dict[str, Any]:
        """Extract response information"""
        info = {
            "status_code": response.status_code,
            "headers": dict(response.headers) if hasattr(response, "headers") else {},
        }

        # Add response body if enabled (be careful with large responses)
        if self.log_response_body and hasattr(response, "body"):
            try:
                if len(response.body) <= self.max_body_size:
                    try:
                        info["response_body"] = json.loads(response.body.decode())
                    except:
                        info["response_body"] = response.body.decode()[
                            : self.max_body_size
                        ]
            except:
                pass

        return info

    async def _log_comprehensive_access(
        self,
        request: Request,
        response: StarletteResponse,
        request_info: Dict[str, Any],
        response_info: Dict[str, Any],
        process_time: float,
    ):
        """Log comprehensive API access information"""

        try:
            # Get database session
            db_gen = get_db()
            db: Session = next(db_gen)

            try:
                audit_logger = AuditLogger(db)

                # Combine all information
                details = {
                    **request_info,
                    **response_info,
                    "process_time_ms": round(process_time * 1000, 2),
                    "timestamp": datetime.utcnow().isoformat(),
                    "performance_category": self._categorize_performance(process_time),
                    "endpoint_category": self._categorize_endpoint(
                        request_info["endpoint"]
                    ),
                }

                # Remove sensitive information from headers
                if "headers" in details:
                    sensitive_headers = ["authorization", "cookie", "x-api-key"]
                    details["headers"] = {
                        k: "[REDACTED]" if k.lower() in sensitive_headers else v
                        for k, v in details["headers"].items()
                    }

                # Determine activity type and security level
                activity_type = ActivityType.API_ACCESS
                security_level = SecurityLevel.LOW
                is_success = 200 <= response_info["status_code"] < 400

                if not is_success:
                    activity_type = ActivityType.API_ERROR
                    security_level = (
                        SecurityLevel.MEDIUM
                        if response_info["status_code"] < 500
                        else SecurityLevel.HIGH
                    )

                # Log the activity
                audit_logger.log_activity(
                    activity_type=activity_type,
                    user_id=request_info.get("user_id"),
                    details=details,
                    request=request,
                    security_level=security_level,
                    success=is_success,
                )

            finally:
                db.close()

        except Exception as e:
            # Don't let logging failures break the API
            print(f"Failed to log comprehensive API access: {e}")

    def _categorize_performance(self, process_time: float) -> str:
        """Categorize request performance"""
        if process_time < 0.1:
            return "fast"
        elif process_time < 0.5:
            return "normal"
        elif process_time < 2.0:
            return "slow"
        else:
            return "very_slow"

    def _categorize_endpoint(self, endpoint: str) -> str:
        """Categorize endpoint type"""
        if "/auth/" in endpoint:
            return "authentication"
        elif "/user/" in endpoint:
            return "user_management"
        elif "/hotel" in endpoint:
            return "hotel_data"
        elif "/location" in endpoint:
            return "location_search"
        elif "/mapping" in endpoint:
            return "provider_mapping"
        elif "/dashboard" in endpoint:
            return "dashboard"
        else:
            return "other"


def create_api_logging_middleware(enhanced: bool = False, **kwargs):
    """Factory function to create API logging middleware"""
    if enhanced:

        class ConfiguredEnhancedAPILoggingMiddleware(EnhancedAPILoggingMiddleware):
            def __init__(self, app):
                super().__init__(app, **kwargs)

        return ConfiguredEnhancedAPILoggingMiddleware
    else:

        class ConfiguredAPILoggingMiddleware(APILoggingMiddleware):
            def __init__(self, app):
                super().__init__(app, **kwargs)

        return ConfiguredAPILoggingMiddleware
