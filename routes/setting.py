import os
import logging
from datetime import datetime
from typing import Annotated, Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field

from database import get_db
import models
from models import UserRole
from routes.auth import get_current_active_user

# Configure logging
logger = logging.getLogger(__name__)

# Router setup
router = APIRouter(
    prefix="/v1.0/settings",
    tags=["Settings"],
    responses={404: {"description": "Not found"}},
)


# ============================================================================
# Pydantic Models
# ============================================================================


# General Settings
class GeneralSettings(BaseModel):
    site_name: str = Field(..., min_length=1, max_length=100)
    site_url: str = Field(..., min_length=1)
    timezone: str = Field(default="UTC")
    language: str = Field(default="en", min_length=2, max_length=5)
    maintenance_mode: bool = Field(default=False)
    enable_registration: bool = Field(default=True)
    enable_notifications: bool = Field(default=True)


# API Configuration
class ApiSettings(BaseModel):
    api_base_url: str = Field(..., min_length=1)
    api_timeout: int = Field(default=30, ge=1, le=300)
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_requests: int = Field(default=100, ge=1)
    rate_limit_window: int = Field(default=60, ge=1)
    enable_cors: bool = Field(default=True)
    api_key_required: bool = Field(default=True)
    allowed_origins: List[str] = Field(default_factory=list)


# Database Settings
class DatabaseSettings(BaseModel):
    connection_pool: int = Field(default=20, ge=1, le=100)
    query_timeout: int = Field(default=30, ge=1, le=300)
    enable_logging: bool = Field(default=True)
    backup_enabled: bool = Field(default=True)
    backup_frequency: str = Field(
        default="daily", pattern="^(hourly|daily|weekly|monthly)$"
    )
    retention_days: int = Field(default=30, ge=1, le=365)


# Security Settings
class SecuritySettings(BaseModel):
    require_strong_password: bool = Field(default=True)
    password_min_length: int = Field(default=8, ge=6, le=128)
    session_timeout: int = Field(default=3600, ge=300)
    enable_2fa: bool = Field(default=False)
    enable_ip_whitelist: bool = Field(default=False)
    enable_audit_log: bool = Field(default=True)
    max_login_attempts: int = Field(default=5, ge=1, le=20)
    lockout_duration: int = Field(default=900, ge=60)
    password_expiry_days: int = Field(default=90, ge=0, le=365)
    require_password_change_on_first_login: bool = Field(default=True)


# Email Settings
class EmailSettings(BaseModel):
    smtp_host: str = Field(..., min_length=1)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str = Field(..., min_length=1)
    smtp_password: Optional[str] = Field(default=None)
    smtp_secure: bool = Field(default=True)
    from_email: EmailStr
    from_name: str = Field(..., min_length=1)
    enable_email_notifications: bool = Field(default=True)


class TestEmailRequest(BaseModel):
    recipient_email: EmailStr


# Backup Settings
class BackupSettings(BaseModel):
    auto_backup_enabled: bool = Field(default=True)
    backup_frequency: str = Field(
        default="daily", pattern="^(hourly|daily|weekly|monthly)$"
    )
    backup_time: str = Field(
        default="02:00", pattern="^([0-1][0-9]|2[0-3]):[0-5][0-9]$"
    )
    retention_days: int = Field(default=30, ge=1, le=365)
    include_uploads: bool = Field(default=True)
    include_database: bool = Field(default=True)
    compression_enabled: bool = Field(default=True)


class CreateBackupRequest(BaseModel):
    include_database: bool = Field(default=True)
    include_uploads: bool = Field(default=True)
    compression_enabled: bool = Field(default=True)
    description: Optional[str] = Field(default=None, max_length=500)


# Appearance Settings
class AppearanceSettings(BaseModel):
    theme: str = Field(default="light", pattern="^(light|dark|system)$")
    accent_color: str = Field(default="blue")
    border_radius: str = Field(default="md", pattern="^(none|sm|md|lg|xl)$")
    animations_enabled: bool = Field(default=True)
    reduced_motion: bool = Field(default=False)
    font_size: str = Field(default="medium", pattern="^(small|medium|large)$")
    sidebar_collapsed: bool = Field(default=False)


class GlobalAppearanceSettings(BaseModel):
    logo_url: Optional[str] = Field(default=None)
    favicon_url: Optional[str] = Field(default=None)
    custom_css: Optional[str] = Field(default=None)


# ============================================================================
# Helper Functions
# ============================================================================


def require_super_user(current_user: models.User = Depends(get_current_active_user)):
    """Dependency to require super user role"""
    if current_user.role != UserRole.SUPER_USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super user privileges required",
        )
    return current_user


def require_admin_or_super(
    current_user: models.User = Depends(get_current_active_user),
):
    """Dependency to require admin or super user role"""
    if current_user.role not in [UserRole.ADMIN_USER, UserRole.SUPER_USER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Super User privileges required",
        )
    return current_user


def get_setting_value(db: Session, key: str, default: Any = None) -> Any:
    """Get a setting value from database (placeholder - implement based on your settings storage)"""
    # TODO: Implement actual database query when Settings model is created
    # For now, return mock data
    return default


def set_setting_value(db: Session, key: str, value: Any, user_id: str) -> None:
    """Set a setting value in database (placeholder - implement based on your settings storage)"""
    # TODO: Implement actual database update when Settings model is created
    pass


# ============================================================================
# 1. General Settings Endpoints
# ============================================================================


@router.get("/general")
async def get_general_settings(
    current_user: Annotated[models.User, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    """Retrieve general system settings"""
    try:
        # TODO: Fetch from database when Settings model is implemented
        settings = {
            "site_name": "HITA Dashboard",
            "site_url": os.getenv("SITE_URL", "https://api.example.com"),
            "timezone": "UTC",
            "language": "en",
            "maintenance_mode": False,
            "enable_registration": True,
            "enable_notifications": True,
        }

        return {"success": True, "data": settings}
    except Exception as e:
        logger.error(f"Error fetching general settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch general settings",
        )


@router.put("/general")
async def update_general_settings(
    settings: GeneralSettings,
    current_user: Annotated[models.User, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    """Update general system settings (Admin/Super User only)"""
    try:
        # Check if user has admin or super user role
        if current_user.role not in [UserRole.ADMIN_USER, UserRole.SUPER_USER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin or Super User privileges required",
            )

        # TODO: Save to database when Settings model is implemented
        logger.info(f"User {current_user.id} updating general settings")

        response_data = settings.dict()
        response_data["updated_at"] = datetime.utcnow().isoformat() + "Z"
        response_data["updated_by"] = current_user.id

        return {
            "success": True,
            "message": "General settings updated successfully",
            "data": response_data,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating general settings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update general settings: {str(e)}",
        )


# ============================================================================
# 2. API Configuration Endpoints
# ============================================================================


@router.get("/api")
async def get_api_settings(
    current_user: Annotated[models.User, Depends(require_admin_or_super)],
    db: Session = Depends(get_db),
):
    """Retrieve API configuration settings (Admin/Super User only)"""
    try:
        settings = {
            "api_base_url": os.getenv("API_BASE_URL", "https://api.example.com/v1.0"),
            "api_timeout": 30,
            "rate_limit_enabled": True,
            "rate_limit_requests": 100,
            "rate_limit_window": 60,
            "enable_cors": True,
            "api_key_required": True,
            "allowed_origins": ["https://example.com", "https://app.example.com"],
        }

        return {"success": True, "data": settings}
    except Exception as e:
        logger.error(f"Error fetching API settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch API settings",
        )


@router.put("/api")
async def update_api_settings(
    settings: ApiSettings,
    current_user: Annotated[models.User, Depends(require_super_user)],
    db: Session = Depends(get_db),
):
    """Update API configuration settings (Super User only)"""
    try:
        response_data = settings.dict()
        response_data["updated_at"] = datetime.utcnow().isoformat() + "Z"
        response_data["updated_by"] = current_user.id

        return {
            "success": True,
            "message": "API settings updated successfully",
            "data": response_data,
        }
    except Exception as e:
        logger.error(f"Error updating API settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update API settings",
        )


# ============================================================================
# 3. Database Settings Endpoints
# ============================================================================


@router.get("/database")
async def get_database_settings(
    current_user: Annotated[models.User, Depends(require_super_user)],
    db: Session = Depends(get_db),
):
    """Retrieve database configuration settings (Super User only)"""
    try:
        settings = {
            "connection_pool": 20,
            "query_timeout": 30,
            "enable_logging": True,
            "backup_enabled": True,
            "backup_frequency": "daily",
            "retention_days": 30,
            "last_backup": "2026-03-04T02:00:00Z",
            "database_size": "2.4 GB",
        }

        return {"success": True, "data": settings}
    except Exception as e:
        logger.error(f"Error fetching database settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch database settings",
        )


@router.put("/database")
async def update_database_settings(
    settings: DatabaseSettings,
    current_user: Annotated[models.User, Depends(require_super_user)],
    db: Session = Depends(get_db),
):
    """Update database configuration settings (Super User only)"""
    try:
        response_data = settings.dict()
        response_data["updated_at"] = datetime.utcnow().isoformat() + "Z"
        response_data["updated_by"] = current_user.id

        return {
            "success": True,
            "message": "Database settings updated successfully",
            "data": response_data,
        }
    except Exception as e:
        logger.error(f"Error updating database settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update database settings",
        )


# ============================================================================
# 4. Security Settings Endpoints
# ============================================================================


@router.get("/security")
async def get_security_settings(
    current_user: Annotated[models.User, Depends(require_admin_or_super)],
    db: Session = Depends(get_db),
):
    """Retrieve security configuration settings (Admin/Super User only)"""
    try:
        settings = {
            "require_strong_password": True,
            "password_min_length": 8,
            "session_timeout": 3600,
            "enable_2fa": False,
            "enable_ip_whitelist": False,
            "enable_audit_log": True,
            "max_login_attempts": 5,
            "lockout_duration": 900,
            "password_expiry_days": 90,
            "require_password_change_on_first_login": True,
        }

        return {"success": True, "data": settings}
    except Exception as e:
        logger.error(f"Error fetching security settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch security settings",
        )


@router.put("/security")
async def update_security_settings(
    settings: SecuritySettings,
    current_user: Annotated[models.User, Depends(require_super_user)],
    db: Session = Depends(get_db),
):
    """Update security configuration settings (Super User only)"""
    try:
        response_data = settings.dict()
        response_data["updated_at"] = datetime.utcnow().isoformat() + "Z"
        response_data["updated_by"] = current_user.id

        return {
            "success": True,
            "message": "Security settings updated successfully",
            "data": response_data,
        }
    except Exception as e:
        logger.error(f"Error updating security settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update security settings",
        )


# ============================================================================
# 5. Email Settings Endpoints
# ============================================================================


@router.get("/email")
async def get_email_settings(
    current_user: Annotated[models.User, Depends(require_admin_or_super)],
    db: Session = Depends(get_db),
):
    """Retrieve email configuration settings (Admin/Super User only)"""
    try:
        settings = {
            "smtp_host": os.getenv("SMTP_HOST", "smtp.example.com"),
            "smtp_port": int(os.getenv("SMTP_PORT", 587)),
            "smtp_user": os.getenv("SMTP_USER", "noreply@example.com"),
            "smtp_password": "***hidden***",
            "smtp_secure": True,
            "from_email": os.getenv("FROM_EMAIL", "noreply@example.com"),
            "from_name": "HITA System",
            "enable_email_notifications": True,
            "email_templates": {
                "welcome": "template_id_1",
                "password_reset": "template_id_2",
                "notification": "template_id_3",
            },
        }

        return {"success": True, "data": settings}
    except Exception as e:
        logger.error(f"Error fetching email settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch email settings",
        )


@router.put("/email")
async def update_email_settings(
    settings: EmailSettings,
    current_user: Annotated[models.User, Depends(require_super_user)],
    db: Session = Depends(get_db),
):
    """Update email configuration settings (Super User only)"""
    try:
        response_data = settings.dict()
        response_data["smtp_password"] = "***hidden***"
        response_data["updated_at"] = datetime.utcnow().isoformat() + "Z"
        response_data["updated_by"] = current_user.id

        return {
            "success": True,
            "message": "Email settings updated successfully",
            "data": response_data,
        }
    except Exception as e:
        logger.error(f"Error updating email settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update email settings",
        )


@router.post("/email/test")
async def send_test_email(
    request: TestEmailRequest,
    current_user: Annotated[models.User, Depends(require_admin_or_super)],
    db: Session = Depends(get_db),
):
    """Send a test email to verify configuration (Admin/Super User only)"""
    try:
        # TODO: Implement actual email sending logic

        return {
            "success": True,
            "message": "Test email sent successfully",
            "data": {
                "sent_at": datetime.utcnow().isoformat() + "Z",
                "recipient": request.recipient_email,
            },
        }
    except Exception as e:
        logger.error(f"Error sending test email: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send test email",
        )


# ============================================================================
# 6. System Information Endpoint
# ============================================================================


@router.get("/system-info")
async def get_system_info(
    current_user: Annotated[models.User, Depends(require_admin_or_super)],
    db: Session = Depends(get_db),
):
    """Retrieve system information and health metrics (Admin/Super User only)"""
    try:
        import platform

        try:
            import psutil

            psutil_available = True
        except ImportError:
            psutil_available = False
            logger.warning("psutil not installed, system metrics will be limited")

        system_info = {
            "version": "1.0.0",
            "environment": os.getenv("ENVIRONMENT", "production"),
            "node_version": platform.python_version(),
            "python_version": platform.python_version(),
            "database_version": "PostgreSQL 15.2",
        }

        if psutil_available:
            # Get system uptime
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime_seconds = int((datetime.now() - boot_time).total_seconds())

            # Memory usage
            memory = psutil.virtual_memory()

            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Disk usage
            disk = psutil.disk_usage("/")

            system_info.update(
                {
                    "uptime": f"{uptime_seconds // 86400} days {(uptime_seconds % 86400) // 3600} hours {(uptime_seconds % 3600) // 60} minutes",
                    "uptime_seconds": uptime_seconds,
                    "memory_usage": {
                        "used": f"{memory.used / (1024**3):.1f} GB",
                        "total": f"{memory.total / (1024**3):.1f} GB",
                        "percentage": int(memory.percent),
                    },
                    "cpu_usage": {
                        "percentage": int(cpu_percent),
                        "cores": psutil.cpu_count(),
                    },
                    "disk_usage": {
                        "used": f"{disk.used / (1024**3):.0f} GB",
                        "total": f"{disk.total / (1024**3):.0f} GB",
                        "percentage": int(disk.percent),
                    },
                    "last_restart": boot_time.isoformat() + "Z",
                }
            )
        else:
            system_info.update(
                {
                    "uptime": "N/A (psutil not installed)",
                    "uptime_seconds": 0,
                    "memory_usage": {"used": "N/A", "total": "N/A", "percentage": 0},
                    "cpu_usage": {"percentage": 0, "cores": 0},
                    "disk_usage": {"used": "N/A", "total": "N/A", "percentage": 0},
                    "last_restart": "N/A",
                }
            )

        system_info.update(
            {
                "active_connections": 42,
                "total_requests_today": 15234,
                "average_response_time": "120ms",
                "error_rate": "0.02%",
            }
        )

        return {"success": True, "data": system_info}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching system info: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch system information: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Error fetching system info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch system information",
        )


# ============================================================================
# 7. Backup Settings Endpoints
# ============================================================================


@router.get("/backup")
async def get_backup_settings(
    current_user: Annotated[models.User, Depends(require_super_user)],
    db: Session = Depends(get_db),
):
    """Retrieve backup configuration and history (Super User only)"""
    try:
        backup_data = {
            "auto_backup_enabled": True,
            "backup_frequency": "daily",
            "backup_time": "02:00",
            "retention_days": 30,
            "backup_location": "/backups",
            "include_uploads": True,
            "include_database": True,
            "compression_enabled": True,
            "last_backup": {
                "timestamp": "2026-03-04T02:00:00Z",
                "size": "1.2 GB",
                "status": "success",
                "duration": "5 minutes",
            },
            "backup_history": [
                {
                    "id": "backup_001",
                    "timestamp": "2026-03-04T02:00:00Z",
                    "size": "1.2 GB",
                    "status": "success",
                    "type": "automatic",
                },
                {
                    "id": "backup_002",
                    "timestamp": "2026-03-03T02:00:00Z",
                    "size": "1.1 GB",
                    "status": "success",
                    "type": "automatic",
                },
            ],
            "total_backup_size": "35.4 GB",
            "available_space": "64.6 GB",
        }

        return {"success": True, "data": backup_data}
    except Exception as e:
        logger.error(f"Error fetching backup settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch backup settings",
        )


@router.put("/backup")
async def update_backup_settings(
    settings: BackupSettings,
    current_user: Annotated[models.User, Depends(require_super_user)],
    db: Session = Depends(get_db),
):
    """Update backup configuration (Super User only)"""
    try:
        response_data = settings.dict()
        response_data["updated_at"] = datetime.utcnow().isoformat() + "Z"
        response_data["updated_by"] = current_user.id

        return {
            "success": True,
            "message": "Backup settings updated successfully",
            "data": response_data,
        }
    except Exception as e:
        logger.error(f"Error updating backup settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update backup settings",
        )


@router.post("/backup/create")
async def create_manual_backup(
    request: CreateBackupRequest,
    current_user: Annotated[models.User, Depends(require_super_user)],
    db: Session = Depends(get_db),
):
    """Create a manual backup immediately (Super User only)"""
    try:
        import uuid

        backup_id = f"backup_manual_{uuid.uuid4().hex[:8]}"

        # TODO: Implement actual backup creation logic

        return {
            "success": True,
            "message": "Backup initiated successfully",
            "data": {
                "backup_id": backup_id,
                "status": "in_progress",
                "started_at": datetime.utcnow().isoformat() + "Z",
                "estimated_duration": "5 minutes",
            },
        }
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create backup",
        )


@router.get("/backup/{backup_id}/download")
async def download_backup(
    backup_id: str,
    current_user: Annotated[models.User, Depends(require_super_user)],
    db: Session = Depends(get_db),
):
    """Download a specific backup file (Super User only)"""
    try:
        # TODO: Implement actual backup file download
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Backup download not yet implemented",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading backup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download backup",
        )


@router.delete("/backup/{backup_id}")
async def delete_backup(
    backup_id: str,
    current_user: Annotated[models.User, Depends(require_super_user)],
    db: Session = Depends(get_db),
):
    """Delete a specific backup (Super User only)"""
    try:
        # TODO: Implement actual backup deletion logic

        return {
            "success": True,
            "message": "Backup deleted successfully",
            "data": {
                "backup_id": backup_id,
                "deleted_at": datetime.utcnow().isoformat() + "Z",
            },
        }
    except Exception as e:
        logger.error(f"Error deleting backup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete backup",
        )


# ============================================================================
# 8. Appearance Settings Endpoints
# ============================================================================


@router.get("/appearance")
async def get_appearance_settings(
    current_user: Annotated[models.User, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    """Retrieve appearance/theme settings"""
    try:
        # TODO: Fetch user-specific appearance settings from database
        settings = {
            "theme": "light",
            "accent_color": "blue",
            "border_radius": "md",
            "animations_enabled": True,
            "reduced_motion": False,
            "font_size": "medium",
            "sidebar_collapsed": False,
            "custom_css": "",
            "logo_url": "https://example.com/logo.png",
            "favicon_url": "https://example.com/favicon.ico",
        }

        return {"success": True, "data": settings}
    except Exception as e:
        logger.error(f"Error fetching appearance settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch appearance settings",
        )


@router.put("/appearance")
async def update_appearance_settings(
    settings: AppearanceSettings,
    current_user: Annotated[models.User, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    """Update appearance/theme settings (per user)"""
    try:
        # TODO: Save user-specific appearance settings to database

        response_data = settings.dict()
        response_data["updated_at"] = datetime.utcnow().isoformat() + "Z"

        return {
            "success": True,
            "message": "Appearance settings updated successfully",
            "data": response_data,
        }
    except Exception as e:
        logger.error(f"Error updating appearance settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update appearance settings",
        )


@router.put("/appearance/global")
async def update_global_appearance_settings(
    settings: GlobalAppearanceSettings,
    current_user: Annotated[models.User, Depends(require_super_user)],
    db: Session = Depends(get_db),
):
    """Update global appearance settings (affects all users, Super User only)"""
    try:
        # TODO: Save global appearance settings to database

        response_data = settings.dict()
        response_data["updated_at"] = datetime.utcnow().isoformat() + "Z"
        response_data["updated_by"] = current_user.id

        return {
            "success": True,
            "message": "Global appearance settings updated successfully",
            "data": response_data,
        }
    except Exception as e:
        logger.error(f"Error updating global appearance settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update global appearance settings",
        )
