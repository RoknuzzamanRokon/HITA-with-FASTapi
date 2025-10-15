from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Annotated
import json, os
from routes.path import RAW_BASE_DIR
from database import get_db
from routes.auth import get_current_user
import models
from security.audit_logging import AuditLogger, ActivityType, SecurityLevel


router = APIRouter()

router = APIRouter(
    prefix='/v1.0/hotel',
    tags=["Raw Hotel Content"],
    responses={404: {"description": "Not found"}},
)


class ProviderRequest(BaseModel):
    supplier_code: str
    hotel_id: str


@router.post("/supplier", status_code=status.HTTP_200_OK)
async def get_row_content(
    request_body: ProviderRequest,
    request: Request,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    """Get raw hotel content from supplier (Super User and Admin User only)"""
    
    # 🔒 SECURITY CHECK: Only super users and admin users can access supplier data
    if current_user.role not in [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only super users and admin users can access supplier data."
        )
    
    # 📝 AUDIT LOG: Record supplier data access
    audit_logger = AuditLogger(db)
    audit_logger.log_activity(
        activity_type=ActivityType.API_ACCESS,
        user_id=current_user.id,
        details={
            "endpoint": "/v1.0/hotel/supplier",
            "action": "access_supplier_data",
            "supplier_code": request_body.supplier_code,
            "hotel_id": request_body.hotel_id
        },
        request=request,
        security_level=SecurityLevel.HIGH,
        success=True
    )
    hotel_id = request_body.hotel_id
    supplier_code = request_body.supplier_code
    base_dir = RAW_BASE_DIR
    file_path = os.path.join(base_dir, supplier_code, f"{hotel_id}.json")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = json.load(f)
        return content
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid JSON file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
