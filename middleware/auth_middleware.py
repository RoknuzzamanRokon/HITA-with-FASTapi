
"""
Authentication Middleware - Add this to middleware/auth_middleware.py
"""

import time
from typing import Optional
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from database import get_db
import models
import os

class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware to extract user from JWT token and set request.state.user"""
    
    def __init__(self, app):
        super().__init__(app)
        self.SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
        self.ALGORITHM = "HS256"
        
        # Paths that don't require authentication
        self.public_paths = [
            "/docs",
            "/redoc", 
            "/openapi.json",
            "/favicon.ico",
            "/health",
            "/metrics",
            "/static",
            "/v1.0/auth/login",
            "/v1.0/auth/register"
        ]
    
    async def dispatch(self, request: Request, call_next):
        # Initialize user as None
        request.state.user = None
        request.state.user_id = None
        
        # Skip authentication for public paths
        if any(request.url.path.startswith(path) for path in self.public_paths):
            return await call_next(request)
        
        # Extract JWT token from Authorization header
        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            # No token provided - continue without user (some endpoints may be optional auth)
            return await call_next(request)
        
        token = authorization.split(" ")[1]
        
        try:
            # Decode JWT token
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            user_id = payload.get("user_id")
            
            if user_id:
                # Get database session
                db_gen = get_db()
                db: Session = next(db_gen)
                
                try:
                    # Get user from database
                    user = db.query(models.User).filter(
                        models.User.id == user_id,
                        models.User.is_active == True
                    ).first()
                    
                    if user:
                        # Set user in request state
                        request.state.user = user
                        request.state.user_id = user.id
                        print(f"🔐 AUTH MIDDLEWARE: Set user {user.id} ({user.email})")
                    else:
                        print(f"❌ AUTH MIDDLEWARE: User {user_id} not found or inactive")
                        
                finally:
                    db.close()
                    
        except JWTError as e:
            print(f"❌ AUTH MIDDLEWARE: JWT error: {e}")
        except Exception as e:
            print(f"❌ AUTH MIDDLEWARE: Error: {e}")
        
        # Continue with request
        response = await call_next(request)
        return response
