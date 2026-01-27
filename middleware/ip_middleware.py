"""
IP Address Middleware for FastAPI

This middleware properly extracts client IP addresses from various proxy headers
and makes them available to the application for audit logging.
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional
import ipaddress


class IPAddressMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and validate real client IP addresses"""

    def __init__(self, app, trusted_proxies: Optional[list] = None):
        super().__init__(app)
        self.trusted_proxies = trusted_proxies or []

    async def dispatch(self, request: Request, call_next):
        # Extract real IP address
        real_ip = self._get_real_ip(request)

        # Store the real IP in request state for later use
        request.state.real_ip = real_ip

        response = await call_next(request)
        return response

    def _get_real_ip(self, request: Request) -> Optional[str]:
        """
        Extract real client IP address from request headers

        Priority order:
        1. X-Forwarded-For (first IP if multiple)
        2. X-Real-IP
        3. X-Client-IP
        4. CF-Connecting-IP (Cloudflare)
        5. Direct client IP
        """

        # Check X-Forwarded-For header (most common)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain (original client)
            ip = forwarded_for.split(",")[0].strip()
            if self._is_valid_ip(ip):
                return ip

        # Check X-Real-IP header (nginx)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip and self._is_valid_ip(real_ip):
            return real_ip

        # Check X-Client-IP header
        client_ip = request.headers.get("X-Client-IP")
        if client_ip and self._is_valid_ip(client_ip):
            return client_ip

        # Check CF-Connecting-IP (Cloudflare)
        cf_ip = request.headers.get("CF-Connecting-IP")
        if cf_ip and self._is_valid_ip(cf_ip):
            return cf_ip

        # Check Forwarded header (RFC 7239)
        forwarded = request.headers.get("Forwarded")
        if forwarded:
            # Parse "for=" parameter
            for part in forwarded.split(";"):
                if part.strip().startswith("for="):
                    ip = part.split("=")[1].strip().strip('"')
                    # Remove port if present
                    if ":" in ip and not ip.startswith("["):
                        ip = ip.split(":")[0]
                    elif ip.startswith("[") and "]:" in ip:
                        ip = ip.split("]:")[0][1:]
                    if self._is_valid_ip(ip):
                        return ip

        # Fall back to direct client IP
        if request.client and self._is_valid_ip(request.client.host):
            return request.client.host

        return None

    def _is_valid_ip(self, ip: str) -> bool:
        """Validate IP address format"""
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    def _is_private_ip(self, ip: str) -> bool:
        """Check if IP is private/internal"""
        try:
            ip_obj = ipaddress.ip_address(ip)
            return ip_obj.is_private
        except ValueError:
            return False


def get_client_ip(request: Request) -> Optional[str]:
    """
    Helper function to get client IP from request

    This function should be used in route handlers to get the real client IP
    that was extracted by the IPAddressMiddleware.
    """
    # First try to get from middleware state (but only if it's a valid string)
    if (
        hasattr(request.state, "real_ip")
        and request.state.real_ip
        and isinstance(request.state.real_ip, str)
    ):
        return request.state.real_ip

    # Fallback to direct extraction (if middleware not used)
    middleware = IPAddressMiddleware(None)
    return middleware._get_real_ip(request)


# Configuration for common deployment scenarios
DEPLOYMENT_CONFIGS = {
    "nginx": {
        "headers": ["X-Real-IP", "X-Forwarded-For"],
        "trusted_proxies": ["127.0.0.1", "::1"],
    },
    "cloudflare": {
        "headers": ["CF-Connecting-IP", "X-Forwarded-For"],
        "trusted_proxies": [],  # Cloudflare IPs would go here
    },
    "aws_alb": {"headers": ["X-Forwarded-For"], "trusted_proxies": []},  # AWS ALB IPs
    "local_dev": {
        "headers": ["X-Forwarded-For", "X-Real-IP"],
        "trusted_proxies": ["127.0.0.1", "::1", "192.168.0.0/16", "10.0.0.0/8"],
    },
}
