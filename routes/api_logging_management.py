"""
API Logging Configuration Management Routes

This module provides endpoints for managing the API logging configuration,
allowing administrators to control which endpoints are counted in usage logs.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import BaseModel

from database import get_db
from routes.auth import get_current_user
from utils.api_logging_config import api_logging_config
import models


router = APIRouter(
    prefix="/v1.0/admin/api-logging",
    tags=["API Logging Management"],
    responses={404: {"description": "Not found"}},
)


class EndpointConfigRequest(BaseModel):
    endpoint: str


class BulkEndpointConfigRequest(BaseModel):
    endpoints: List[str]


class ConfigSummaryResponse(BaseModel):
    total_count_endpoints: int
    total_exclude_endpoints: int
    count_endpoints: List[str]
    exclude_endpoints: List[str]


@router.get("/config", response_model=ConfigSummaryResponse)
async def get_api_logging_config(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Get API Logging Configuration**

    Retrieve the current API logging configuration showing which endpoints
    are counted and which are excluded from usage logs.

    **Access Control:**
    - SUPER_USER: Full access
    - ADMIN_USER: Full access
    - GENERAL_USER: Access denied

    **Returns:**
    - total_count_endpoints: Number of endpoints that are counted
    - total_exclude_endpoints: Number of endpoints that are excluded
    - count_endpoints: List of endpoints that are counted in usage logs
    - exclude_endpoints: List of endpoints that are excluded from logs
    """
    # Check permissions
    if current_user.role not in [
        models.UserRole.SUPER_USER,
        models.UserRole.ADMIN_USER,
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only super users and admin users can view API logging configuration.",
        )

    config_summary = api_logging_config.get_config_summary()
    return ConfigSummaryResponse(**config_summary)


@router.post("/count-endpoints/add")
async def add_count_endpoint(
    request: EndpointConfigRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Add Endpoint to Count List**

    Add an API endpoint to the list of endpoints that should be counted in usage logs.

    **Request Body:**
    - endpoint: The API endpoint path (e.g., "/v1.0/user/all-general-user")

    **Access Control:**
    - SUPER_USER: Full access
    - ADMIN_USER: Full access
    - GENERAL_USER: Access denied
    """
    # Check permissions
    if current_user.role not in [
        models.UserRole.SUPER_USER,
        models.UserRole.ADMIN_USER,
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only super users and admin users can modify API logging configuration.",
        )

    # Add endpoint to count list
    api_logging_config.add_count_endpoint(request.endpoint)

    return {
        "message": f"Endpoint '{request.endpoint}' added to count list successfully",
        "endpoint": request.endpoint,
        "action": "added_to_count_list",
        "timestamp": models.datetime.utcnow().isoformat(),
    }


@router.post("/exclude-endpoints/add")
async def add_exclude_endpoint(
    request: EndpointConfigRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Add Endpoint to Exclude List**

    Add an API endpoint to the list of endpoints that should NOT be counted in usage logs.

    **Request Body:**
    - endpoint: The API endpoint path (e.g., "/v1.0/auth/check-me")

    **Access Control:**
    - SUPER_USER: Full access
    - ADMIN_USER: Full access
    - GENERAL_USER: Access denied
    """
    # Check permissions
    if current_user.role not in [
        models.UserRole.SUPER_USER,
        models.UserRole.ADMIN_USER,
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only super users and admin users can modify API logging configuration.",
        )

    # Add endpoint to exclude list
    api_logging_config.add_exclude_endpoint(request.endpoint)

    return {
        "message": f"Endpoint '{request.endpoint}' added to exclude list successfully",
        "endpoint": request.endpoint,
        "action": "added_to_exclude_list",
        "timestamp": models.datetime.utcnow().isoformat(),
    }


@router.delete("/count-endpoints/remove")
async def remove_count_endpoint(
    request: EndpointConfigRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Remove Endpoint from Count List**

    Remove an API endpoint from the list of endpoints that are counted in usage logs.

    **Request Body:**
    - endpoint: The API endpoint path to remove
    """
    # Check permissions
    if current_user.role not in [
        models.UserRole.SUPER_USER,
        models.UserRole.ADMIN_USER,
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only super users and admin users can modify API logging configuration.",
        )

    # Remove endpoint from count list
    api_logging_config.remove_count_endpoint(request.endpoint)

    return {
        "message": f"Endpoint '{request.endpoint}' removed from count list successfully",
        "endpoint": request.endpoint,
        "action": "removed_from_count_list",
        "timestamp": models.datetime.utcnow().isoformat(),
    }


@router.delete("/exclude-endpoints/remove")
async def remove_exclude_endpoint(
    request: EndpointConfigRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Remove Endpoint from Exclude List**

    Remove an API endpoint from the list of endpoints that are excluded from usage logs.

    **Request Body:**
    - endpoint: The API endpoint path to remove
    """
    # Check permissions
    if current_user.role not in [
        models.UserRole.SUPER_USER,
        models.UserRole.ADMIN_USER,
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only super users and admin users can modify API logging configuration.",
        )

    # Remove endpoint from exclude list
    api_logging_config.remove_exclude_endpoint(request.endpoint)

    return {
        "message": f"Endpoint '{request.endpoint}' removed from exclude list successfully",
        "endpoint": request.endpoint,
        "action": "removed_from_exclude_list",
        "timestamp": models.datetime.utcnow().isoformat(),
    }


@router.post("/count-endpoints/bulk-add")
async def bulk_add_count_endpoints(
    request: BulkEndpointConfigRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Bulk Add Endpoints to Count List**

    Add multiple API endpoints to the count list in a single operation.

    **Request Body:**
    - endpoints: List of API endpoint paths to add
    """
    # Check permissions
    if current_user.role not in [
        models.UserRole.SUPER_USER,
        models.UserRole.ADMIN_USER,
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only super users and admin users can modify API logging configuration.",
        )

    # Add all endpoints to count list
    for endpoint in request.endpoints:
        api_logging_config.add_count_endpoint(endpoint)

    return {
        "message": f"Successfully added {len(request.endpoints)} endpoints to count list",
        "endpoints": request.endpoints,
        "action": "bulk_added_to_count_list",
        "count": len(request.endpoints),
        "timestamp": models.datetime.utcnow().isoformat(),
    }


@router.post("/exclude-endpoints/bulk-add")
async def bulk_add_exclude_endpoints(
    request: BulkEndpointConfigRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Bulk Add Endpoints to Exclude List**

    Add multiple API endpoints to the exclude list in a single operation.

    **Request Body:**
    - endpoints: List of API endpoint paths to add
    """
    # Check permissions
    if current_user.role not in [
        models.UserRole.SUPER_USER,
        models.UserRole.ADMIN_USER,
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only super users and admin users can modify API logging configuration.",
        )

    # Add all endpoints to exclude list
    for endpoint in request.endpoints:
        api_logging_config.add_exclude_endpoint(endpoint)

    return {
        "message": f"Successfully added {len(request.endpoints)} endpoints to exclude list",
        "endpoints": request.endpoints,
        "action": "bulk_added_to_exclude_list",
        "count": len(request.endpoints),
        "timestamp": models.datetime.utcnow().isoformat(),
    }


@router.post("/reload")
async def reload_config(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    **Reload API Logging Configuration**

    Reload the API logging configuration from the JSON file.
    Useful when the configuration file has been modified externally.

    **Access Control:**
    - SUPER_USER: Full access
    - ADMIN_USER: Full access
    - GENERAL_USER: Access denied
    """
    # Check permissions
    if current_user.role not in [
        models.UserRole.SUPER_USER,
        models.UserRole.ADMIN_USER,
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only super users and admin users can reload API logging configuration.",
        )

    # Reload configuration
    api_logging_config.reload_config()

    # Get updated summary
    config_summary = api_logging_config.get_config_summary()

    return {
        "message": "API logging configuration reloaded successfully",
        "action": "config_reloaded",
        "timestamp": models.datetime.utcnow().isoformat(),
        "config_summary": config_summary,
    }
