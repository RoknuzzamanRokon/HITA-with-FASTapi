"""
Export API Routes

Provides endpoints for exporting hotel data, provider mappings, and supplier summaries
in multiple formats (CSV, JSON, Excel).

Features:
- Synchronous exports for small datasets (<5000 records)
- Asynchronous exports for large datasets (>=5000 records)
- Role-based access control and permission validation
- Point deduction for general users
- Audit logging for all export operations
- Progress tracking and status checking for async exports
"""

import os
import uuid
import logging
from typing import Annotated, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db
from routes.auth import get_current_user, authenticate_api_key, authenticate_for_export
import models
from models import User, UserRole, ExportJob
from export_schemas import (
    ExportHotelsRequest,
    ExportMappingsRequest,
    ExportSupplierSummaryRequest,
    ExportJobResponse,
    ExportJobStatusResponse,
    ExportErrorResponse,
    ExportFormat,
)
from services.export_permission_service import ExportPermissionService
from services.export_filter_service import ExportFilterService
from services.export_engine import ExportEngine
from services.export_worker import get_export_worker
from security.audit_logging import AuditLogger, ActivityType, SecurityLevel
from utils import deduct_points_for_general_user

# Configure logging
logger = logging.getLogger(__name__)

# Router setup
router = APIRouter(
    prefix="/v1.0/export",
    tags=["Export"],
    responses={404: {"description": "Not found"}},
)

# Get export storage path from environment or use default
EXPORT_STORAGE_PATH = os.getenv(
    "EXPORT_STORAGE_PATH", os.path.join(os.getcwd(), "exports")
)


@router.get("/my-validation")
async def validate_api_key(
    request: Request,
    current_user: Annotated[User, Depends(authenticate_for_export)],
    db: Session = Depends(get_db),
):
    """
    Validate API Key for Export Endpoints

    This endpoint checks if the provided API key is valid and grants access
    to all /v1.0/export endpoints.

    **Authentication:**
    - Requires valid API key in X-API-Key header
    - API key must be active and not expired

    **Returns:**
    - User information if API key is valid
    - 401 error if API key is invalid or expired

    **Use Cases:**
    - Pre-validate API key before making export requests
    - Check API key status and expiration
    - Verify user permissions for exports
    """
    logger.info(f"API key validation successful for user {current_user.id}")

    return {
        "valid": True,
        "message": "API key is valid and active",
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "role": current_user.role,
            "api_key_expires_at": (
                current_user.api_key_expires_at.isoformat()
                if current_user.api_key_expires_at
                else None
            ),
        },
        "access": {
            "export_endpoints": True,
            "message": "You have access to all /v1.0/export endpoints",
        },
    }


@router.post("/hotels")
async def export_hotels(
    request: Request,
    export_request: ExportHotelsRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(authenticate_for_export)],
    db: Session = Depends(get_db),
):
    """
    Export hotel data with filters in specified format.

    ALL exports are processed asynchronously in the background to ensure
    zero impact on other API endpoints.

    Returns job_id immediately. Use /status/{job_id} to check progress
    and /download/{job_id} to download when complete.

    Requires authentication and appropriate supplier permissions.
    General users will have points deducted.
    """
    logger.info(
        f"Hotel export requested by user {current_user.id} in {export_request.format.value} format"
    )

    try:
        # Initialize services
        permission_service = ExportPermissionService(db)
        filter_service = ExportFilterService(db)
        export_engine = ExportEngine(db, EXPORT_STORAGE_PATH)
        audit_logger = AuditLogger(db)

        # Step 1: Validate permissions
        requested_suppliers = export_request.filters.suppliers
        permission_result = permission_service.validate_export_access(
            user=current_user, request=request, requested_suppliers=requested_suppliers
        )

        if not permission_result.is_authorized:
            logger.warning(
                f"Export access denied for user {current_user.id}: {permission_result.error_message}"
            )

            # Log failed attempt
            audit_logger.log_activity(
                activity_type=ActivityType.EXPORT_DATA,
                user_id=current_user.id,
                details={
                    "export_type": "hotels",
                    "format": export_request.format.value,
                    "error": "INSUFFICIENT_PERMISSIONS",
                    "denied_suppliers": permission_result.denied_suppliers,
                },
                request=request,
                security_level=SecurityLevel.HIGH,
                success=False,
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "INSUFFICIENT_PERMISSIONS",
                    "message": permission_result.error_message,
                    "denied_suppliers": permission_result.denied_suppliers,
                    "allowed_suppliers": permission_result.allowed_suppliers,
                },
            )

        logger.info(
            f"User {current_user.id} authorized to export from {len(permission_result.allowed_suppliers)} suppliers"
        )

        # Step 2: Deduct points for general users
        if current_user.role == UserRole.GENERAL_USER:
            try:
                deduct_points_for_general_user(current_user, db)
                logger.info(f"Points deducted for user {current_user.id}")
            except HTTPException as e:
                logger.warning(f"Insufficient points for user {current_user.id}")

                # Log failed attempt
                audit_logger.log_activity(
                    activity_type=ActivityType.EXPORT_DATA,
                    user_id=current_user.id,
                    details={
                        "export_type": "hotels",
                        "format": export_request.format.value,
                        "error": "INSUFFICIENT_POINTS",
                    },
                    request=request,
                    security_level=SecurityLevel.HIGH,
                    success=False,
                )

                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail={
                        "error": "INSUFFICIENT_POINTS",
                        "message": "Insufficient points to perform export operation",
                    },
                )

        # Step 3: Validate filters
        is_valid, error_message = filter_service.validate_filters(
            export_request.filters
        )
        if not is_valid:
            logger.warning(
                f"Invalid filters for user {current_user.id}: {error_message}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_FILTERS", "message": error_message},
            )

        # Step 4: Build query with filters
        query = filter_service.build_hotel_query(
            filters=export_request.filters,
            allowed_suppliers=permission_result.allowed_suppliers,
            include_locations=export_request.include_locations,
            include_contacts=export_request.include_contacts,
            include_mappings=export_request.include_mappings,
        )

        # Step 5: Get actual count of records to be exported
        # This ensures accurate progress tracking and time estimates
        actual_count = query.count()
        estimated_count = actual_count
        logger.info(
            f"Actual count: {estimated_count} hotel records for export"
        )

        # Check maximum export size (only for numeric estimates)
        MAX_EXPORT_SIZE = 100000
        if isinstance(estimated_count, int) and estimated_count > MAX_EXPORT_SIZE:
            logger.warning(
                f"Export size {estimated_count} exceeds maximum {MAX_EXPORT_SIZE}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "EXPORT_TOO_LARGE",
                    "message": f"Export size ({estimated_count} records) exceeds maximum allowed ({MAX_EXPORT_SIZE}). Please use more specific filters or pagination.",
                },
            )

        # Step 6: Prepare filters for logging
        filters_applied = {
            "suppliers": export_request.filters.suppliers,
            "country_codes": export_request.filters.country_codes,
            "min_rating": export_request.filters.min_rating,
            "max_rating": export_request.filters.max_rating,
            "date_from": (
                export_request.filters.date_from.isoformat()
                if export_request.filters.date_from
                else None
            ),
            "date_to": (
                export_request.filters.date_to.isoformat()
                if export_request.filters.date_to
                else None
            ),
            "ittids": export_request.filters.ittids,
            "property_types": export_request.filters.property_types,
            "include_locations": export_request.include_locations,
            "include_contacts": export_request.include_contacts,
            "include_mappings": export_request.include_mappings,
        }

        # Step 7: Always use asynchronous export to avoid blocking other endpoints
        # Asynchronous export using dedicated worker
        logger.info(f"Processing asynchronous export for {estimated_count} records")

        # Create export job record
        # Note: total_records in DB must be int, so use 0 for "All" (unknown count)
        job_id = f"exp_{uuid.uuid4().hex[:16]}"
        export_job = ExportJob(
            id=job_id,
            user_id=current_user.id,
            export_type="hotels",
            format=export_request.format.value,
            filters=filters_applied,
            status="pending",
            progress_percentage=0,
            processed_records=0,
            total_records=0 if isinstance(estimated_count, str) else estimated_count,
            file_path=None,
            file_size_bytes=None,
            error_message=None,
            created_at=datetime.utcnow(),
            started_at=None,
            completed_at=None,
            expires_at=None,
        )

        db.add(export_job)
        db.commit()
        db.refresh(export_job)

        # Submit to dedicated export worker
        worker = get_export_worker()
        query_params = {
            "filters": {
                "suppliers": export_request.filters.suppliers,
                "country_codes": export_request.filters.country_codes,
                "min_rating": export_request.filters.min_rating,
                "max_rating": export_request.filters.max_rating,
                "date_from": (
                    export_request.filters.date_from.isoformat()
                    if export_request.filters.date_from
                    else None
                ),
                "date_to": (
                    export_request.filters.date_to.isoformat()
                    if export_request.filters.date_to
                    else None
                ),
                "ittids": export_request.filters.ittids,
                "property_types": export_request.filters.property_types,
            },
            "allowed_suppliers": permission_result.allowed_suppliers,
            "include_locations": export_request.include_locations,
            "include_contacts": export_request.include_contacts,
            "include_mappings": export_request.include_mappings,
        }

        worker.submit_export_job(
            job_id=job_id,
            export_type="hotels",
            query_params=query_params,
            format=export_request.format,
            user_data={"id": current_user.id, "username": current_user.username},
            filters_applied=filters_applied,
            include_locations=export_request.include_locations,
            include_contacts=export_request.include_contacts,
            include_mappings=export_request.include_mappings,
        )

        # Log async export job creation
        audit_logger.log_activity(
            activity_type=ActivityType.EXPORT_DATA,
            user_id=current_user.id,
            details={
                "export_type": "hotels",
                "format": export_request.format.value,
                "job_id": export_job.id,
                "estimated_records": estimated_count,
                "sync": False,
                "status": "pending",
                "filters": filters_applied,
            },
            request=request,
            security_level=SecurityLevel.HIGH,
            success=True,
        )

        # Calculate estimated completion time
        # More realistic estimate: ~60 records per second (based on actual performance)
        estimated_seconds = estimated_count / 60
        if estimated_seconds < 60:
            estimated_time = f"{int(estimated_seconds)} seconds"
        elif estimated_seconds < 3600:
            estimated_minutes = int(estimated_seconds / 60)
            estimated_time = f"{estimated_minutes} minutes"
        else:
            estimated_hours = int(estimated_seconds / 3600)
            estimated_time = f"{estimated_hours} hours"

        message = "Export job created successfully. Use the job_id to check status and download when complete."

        return ExportJobResponse(
            job_id=export_job.id,
            status=export_job.status,
            estimated_records=estimated_count,
            estimated_completion_time=estimated_time,
            created_at=export_job.created_at,
            message=message,
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except IOError as e:
        logger.error(
            f"File I/O error in hotel export for user {current_user.id}: {str(e)}"
        )

        # Log error
        try:
            audit_logger.log_activity(
                activity_type=ActivityType.EXPORT_DATA,
                user_id=current_user.id,
                details={
                    "export_type": "hotels",
                    "format": export_request.format.value,
                    "error": "FILE_IO_ERROR",
                    "error_details": str(e),
                },
                request=request,
                security_level=SecurityLevel.HIGH,
                success=False,
            )
        except:
            pass

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "FILE_IO_ERROR",
                "message": "An error occurred while writing the export file",
            },
        )
    except Exception as e:
        logger.error(f"Error in hotel export for user {current_user.id}: {str(e)}")

        # Log error
        try:
            audit_logger.log_activity(
                activity_type=ActivityType.EXPORT_DATA,
                user_id=current_user.id,
                details={
                    "export_type": "hotels",
                    "format": export_request.format.value,
                    "error": str(e),
                },
                request=request,
                security_level=SecurityLevel.HIGH,
                success=False,
            )
        except:
            pass

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "EXPORT_FAILED",
                "message": "An error occurred while processing the export request",
            },
        )


@router.post("/mappings")
async def export_mappings(
    request: Request,
    export_request: ExportMappingsRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(authenticate_for_export)],
    db: Session = Depends(get_db),
):
    """
    Export provider mapping data with filters in specified format.

    ALL exports are processed asynchronously in the background to ensure
    zero impact on other API endpoints.

    Returns job_id immediately. Use /status/{job_id} to check progress
    and /download/{job_id} to download when complete.

    Includes Giata codes and Vervotech IDs in the export.
    Requires authentication and appropriate supplier permissions.
    """
    logger.info(
        f"Mapping export requested by user {current_user.id} in {export_request.format.value} format"
    )

    try:
        # Initialize services
        permission_service = ExportPermissionService(db)
        filter_service = ExportFilterService(db)
        export_engine = ExportEngine(db, EXPORT_STORAGE_PATH)
        audit_logger = AuditLogger(db)

        # Step 1: Validate permissions
        requested_suppliers = export_request.filters.suppliers
        permission_result = permission_service.validate_export_access(
            user=current_user, request=request, requested_suppliers=requested_suppliers
        )

        if not permission_result.is_authorized:
            logger.warning(
                f"Mapping export access denied for user {current_user.id}: {permission_result.error_message}"
            )

            # Log failed attempt
            audit_logger.log_activity(
                activity_type=ActivityType.EXPORT_DATA,
                user_id=current_user.id,
                details={
                    "export_type": "mappings",
                    "format": export_request.format.value,
                    "error": "INSUFFICIENT_PERMISSIONS",
                    "denied_suppliers": permission_result.denied_suppliers,
                },
                request=request,
                security_level=SecurityLevel.HIGH,
                success=False,
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "INSUFFICIENT_PERMISSIONS",
                    "message": permission_result.error_message,
                    "denied_suppliers": permission_result.denied_suppliers,
                    "allowed_suppliers": permission_result.allowed_suppliers,
                },
            )

        logger.info(
            f"User {current_user.id} authorized to export mappings from {len(permission_result.allowed_suppliers)} suppliers"
        )

        # Step 2: Validate filters
        is_valid, error_message = filter_service.validate_filters(
            export_request.filters
        )
        if not is_valid:
            logger.warning(
                f"Invalid filters for user {current_user.id}: {error_message}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_FILTERS", "message": error_message},
            )

        # Step 3: Build query with filters
        query = filter_service.build_mapping_query(
            filters=export_request.filters,
            allowed_suppliers=permission_result.allowed_suppliers,
        )

        # Step 4: Determine actual count based on max_records
        if export_request.filters.max_records is not None:
            if isinstance(export_request.filters.max_records, int):
                # Get actual count but limit to max_records
                actual_count = query.count()
                estimated_count = min(actual_count, export_request.filters.max_records)
                logger.info(
                    f"Actual count: {actual_count}, limited to max_records: {estimated_count}"
                )
            elif (
                isinstance(export_request.filters.max_records, str)
                and export_request.filters.max_records.lower() == "all"
            ):
                # Get actual count for "All"
                actual_count = query.count()
                estimated_count = actual_count
                logger.info(f"Actual count for all mapping records: {estimated_count}")
        else:
            # No max_records specified - get actual count
            actual_count = query.count()
            estimated_count = actual_count
            logger.info(
                f"Actual count: {estimated_count} mapping records for export"
            )

        # Check maximum export size (only for numeric estimates)
        MAX_EXPORT_SIZE = 100000
        if isinstance(estimated_count, int) and estimated_count > MAX_EXPORT_SIZE:
            logger.warning(
                f"Export size {estimated_count} exceeds maximum {MAX_EXPORT_SIZE}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "EXPORT_TOO_LARGE",
                    "message": f"Export size ({estimated_count} records) exceeds maximum allowed ({MAX_EXPORT_SIZE}). Please use more specific filters.",
                },
            )

        # Step 5: Prepare filters for logging
        filters_applied = {
            "suppliers": export_request.filters.suppliers,
            "ittids": export_request.filters.ittids,
            "date_from": (
                export_request.filters.date_from.isoformat()
                if export_request.filters.date_from
                else None
            ),
            "date_to": (
                export_request.filters.date_to.isoformat()
                if export_request.filters.date_to
                else None
            ),
            "max_records": export_request.filters.max_records,
        }

        # Step 6: Always use asynchronous export to avoid blocking other endpoints
        # Asynchronous export using dedicated worker
        logger.info(
            f"Processing asynchronous mapping export for {estimated_count} records"
        )

        # Create export job record
        # Note: total_records in DB must be int, so use 0 for "All" (unknown count)
        job_id = f"exp_{uuid.uuid4().hex[:16]}"
        export_job = ExportJob(
            id=job_id,
            user_id=current_user.id,
            export_type="mappings",
            format=export_request.format.value,
            filters=filters_applied,
            status="pending",
            progress_percentage=0,
            processed_records=0,
            total_records=0 if isinstance(estimated_count, str) else estimated_count,
            file_path=None,
            file_size_bytes=None,
            error_message=None,
            created_at=datetime.utcnow(),
            started_at=None,
            completed_at=None,
            expires_at=None,
        )

        db.add(export_job)
        db.commit()
        db.refresh(export_job)

        # Submit to dedicated export worker
        worker = get_export_worker()
        query_params = {
            "filters": {
                "suppliers": export_request.filters.suppliers,
                "ittids": export_request.filters.ittids,
                "date_from": (
                    export_request.filters.date_from.isoformat()
                    if export_request.filters.date_from
                    else None
                ),
                "date_to": (
                    export_request.filters.date_to.isoformat()
                    if export_request.filters.date_to
                    else None
                ),
                "max_records": export_request.filters.max_records,
            },
            "allowed_suppliers": permission_result.allowed_suppliers,
        }

        worker.submit_export_job(
            job_id=job_id,
            export_type="mappings",
            query_params=query_params,
            format=export_request.format,
            user_data={"id": current_user.id, "username": current_user.username},
            filters_applied=filters_applied,
        )

        # Log async export job creation
        audit_logger.log_activity(
            activity_type=ActivityType.EXPORT_DATA,
            user_id=current_user.id,
            details={
                "export_type": "mappings",
                "format": export_request.format.value,
                "job_id": export_job.id,
                "estimated_records": estimated_count,
                "sync": False,
                "status": "pending",
                "filters": filters_applied,
            },
            request=request,
            security_level=SecurityLevel.HIGH,
            success=True,
        )

        # Calculate estimated completion time
        # More realistic estimate: ~60 records per second (based on actual performance)
        estimated_seconds = estimated_count / 60
        if estimated_seconds < 60:
            estimated_time = f"{int(estimated_seconds)} seconds"
        elif estimated_seconds < 3600:
            estimated_minutes = int(estimated_seconds / 60)
            estimated_time = f"{estimated_minutes} minutes"
        else:
            estimated_hours = int(estimated_seconds / 3600)
            estimated_time = f"{estimated_hours} hours"

        message = "Mapping export job created successfully. Use the job_id to check status and download when complete."

        return ExportJobResponse(
            job_id=export_job.id,
            status=export_job.status,
            estimated_records=estimated_count,
            estimated_completion_time=estimated_time,
            created_at=export_job.created_at,
            message=message,
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except IOError as e:
        logger.error(
            f"File I/O error in mapping export for user {current_user.id}: {str(e)}"
        )

        # Log error
        try:
            audit_logger.log_activity(
                activity_type=ActivityType.EXPORT_DATA,
                user_id=current_user.id,
                details={
                    "export_type": "mappings",
                    "format": export_request.format.value,
                    "error": "FILE_IO_ERROR",
                    "error_details": str(e),
                },
                request=request,
                security_level=SecurityLevel.HIGH,
                success=False,
            )
        except:
            pass

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "FILE_IO_ERROR",
                "message": "An error occurred while writing the export file",
            },
        )
    except Exception as e:
        logger.error(f"Error in mapping export for user {current_user.id}: {str(e)}")

        # Log error
        try:
            audit_logger.log_activity(
                activity_type=ActivityType.EXPORT_DATA,
                user_id=current_user.id,
                details={
                    "export_type": "mappings",
                    "format": export_request.format.value,
                    "error": str(e),
                },
                request=request,
                security_level=SecurityLevel.HIGH,
                success=False,
            )
        except:
            pass

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "EXPORT_FAILED",
                "message": "An error occurred while processing the mapping export request",
            },
        )


@router.post("/supplier-summary")
async def export_supplier_summary(
    request: Request,
    export_request: ExportSupplierSummaryRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(authenticate_for_export)],
    db: Session = Depends(get_db),
):
    """
    Export supplier summary statistics in specified format.

    ALL exports are processed asynchronously in the background to ensure
    zero impact on other API endpoints.

    Returns job_id immediately. Use /status/{job_id} to check progress
    and /download/{job_id} to download when complete.

    Includes total hotels, total mappings, and last update timestamps per supplier.
    Optionally includes country breakdown if requested.
    Requires authentication and appropriate supplier permissions.
    """
    logger.info(
        f"Supplier summary export requested by user {current_user.id} in {export_request.format.value} format"
    )

    try:
        # Initialize services
        permission_service = ExportPermissionService(db)
        filter_service = ExportFilterService(db)
        export_engine = ExportEngine(db, EXPORT_STORAGE_PATH)
        audit_logger = AuditLogger(db)

        # Step 1: Validate permissions
        requested_suppliers = export_request.filters.suppliers

        # For supplier summary, determine allowed suppliers based on role
        if current_user.role in [UserRole.SUPER_USER, UserRole.ADMIN_USER]:
            # Admin/Super users can access all suppliers
            allowed_suppliers = None  # None means no restriction
        else:
            # General users need permission validation
            permission_result = permission_service.validate_export_access(
                user=current_user,
                request=request,
                requested_suppliers=requested_suppliers,
            )

            if not permission_result.is_authorized:
                logger.warning(
                    f"Supplier summary export access denied for user {current_user.id}: {permission_result.error_message}"
                )

                # Log failed attempt
                audit_logger.log_activity(
                    activity_type=ActivityType.EXPORT_DATA,
                    user_id=current_user.id,
                    details={
                        "export_type": "supplier_summary",
                        "format": export_request.format.value,
                        "error": "INSUFFICIENT_PERMISSIONS",
                        "denied_suppliers": permission_result.denied_suppliers,
                    },
                    request=request,
                    security_level=SecurityLevel.HIGH,
                    success=False,
                )

                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "INSUFFICIENT_PERMISSIONS",
                        "message": permission_result.error_message,
                        "denied_suppliers": permission_result.denied_suppliers,
                        "allowed_suppliers": permission_result.allowed_suppliers,
                    },
                )

            allowed_suppliers = permission_result.allowed_suppliers

        logger.info(f"User {current_user.id} authorized to export supplier summary")

        # Step 2: Build query with filters
        query = filter_service.build_supplier_summary_query(
            filters=export_request.filters, allowed_suppliers=allowed_suppliers
        )

        # Step 3: Estimate result count (quick estimate, not exact)
        estimated_count = 10  # Supplier summary is always small, just estimate
        logger.info(f"Estimated {estimated_count} supplier summary records for export")

        # Step 4: Skip country breakdown here - let worker handle it
        # (Country breakdown query is slow and would block the response)

        # Step 5: Prepare filters for logging
        filters_applied = {
            "suppliers": export_request.filters.suppliers,
            "include_country_breakdown": export_request.filters.include_country_breakdown,
        }

        # Step 6: Always use asynchronous export to avoid blocking other endpoints
        # Asynchronous export using dedicated worker
        logger.info(
            f"Processing asynchronous supplier summary export for {estimated_count} records"
        )

        # Create export job record
        job_id = f"exp_{uuid.uuid4().hex[:16]}"
        export_job = ExportJob(
            id=job_id,
            user_id=current_user.id,
            export_type="supplier_summary",
            format=export_request.format.value,
            filters=filters_applied,
            status="pending",
            progress_percentage=0,
            processed_records=0,
            total_records=estimated_count,
            file_path=None,
            file_size_bytes=None,
            error_message=None,
            created_at=datetime.utcnow(),
            started_at=None,
            completed_at=None,
            expires_at=None,
        )

        db.add(export_job)
        db.commit()
        db.refresh(export_job)

        # Submit to dedicated export worker
        worker = get_export_worker()
        query_params = {
            "filters": {
                "suppliers": export_request.filters.suppliers,
                "include_country_breakdown": export_request.filters.include_country_breakdown,
            },
            "allowed_suppliers": allowed_suppliers,
        }

        worker.submit_export_job(
            job_id=job_id,
            export_type="supplier_summary",
            query_params=query_params,
            format=export_request.format,
            user_data={"id": current_user.id, "username": current_user.username},
            filters_applied=filters_applied,
        )

        # Log async export job creation
        audit_logger.log_activity(
            activity_type=ActivityType.EXPORT_DATA,
            user_id=current_user.id,
            details={
                "export_type": "supplier_summary",
                "format": export_request.format.value,
                "job_id": export_job.id,
                "estimated_records": estimated_count,
                "sync": False,
                "status": "pending",
                "filters": filters_applied,
            },
            request=request,
            security_level=SecurityLevel.HIGH,
            success=True,
        )

        # Calculate estimated completion time
        estimated_seconds = max(1, estimated_count / 1000)
        if estimated_seconds < 60:
            estimated_time = f"{int(estimated_seconds)} seconds"
        else:
            estimated_minutes = int(estimated_seconds / 60)
            estimated_time = f"{estimated_minutes} minutes"

        return ExportJobResponse(
            job_id=export_job.id,
            status=export_job.status,
            estimated_records=estimated_count,
            estimated_completion_time=estimated_time,
            created_at=export_job.created_at,
            message="Supplier summary export job created successfully. Use the job_id to check status and download when complete.",
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except IOError as e:
        logger.error(
            f"File I/O error in supplier summary export for user {current_user.id}: {str(e)}"
        )

        # Log error
        try:
            audit_logger.log_activity(
                activity_type=ActivityType.EXPORT_DATA,
                user_id=current_user.id,
                details={
                    "export_type": "supplier_summary",
                    "format": export_request.format.value,
                    "error": "FILE_IO_ERROR",
                    "error_details": str(e),
                },
                request=request,
                security_level=SecurityLevel.HIGH,
                success=False,
            )
        except:
            pass

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "FILE_IO_ERROR",
                "message": "An error occurred while writing the export file",
            },
        )
    except Exception as e:
        logger.error(
            f"Error in supplier summary export for user {current_user.id}: {str(e)}"
        )

        # Log error
        try:
            audit_logger.log_activity(
                activity_type=ActivityType.EXPORT_DATA,
                user_id=current_user.id,
                details={
                    "export_type": "supplier_summary",
                    "format": export_request.format.value,
                    "error": str(e),
                },
                request=request,
                security_level=SecurityLevel.HIGH,
                success=False,
            )
        except:
            pass

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "EXPORT_FAILED",
                "message": "An error occurred while processing the supplier summary export request",
            },
        )


@router.get("/status/{job_id}", response_model=ExportJobStatusResponse)
async def get_export_status(
    job_id: str,
    current_user: Annotated[User, Depends(authenticate_for_export)],
    db: Session = Depends(get_db),
):
    """
    Check the status of an asynchronous export job.

    Returns:
    - Job status (pending, processing, completed, failed)
    - Progress percentage
    - Processed and total record counts
    - Download URL if completed
    - Error message if failed

    Requires authentication. Users can only check their own export jobs.
    """
    logger.info(
        f"Export status check requested for job {job_id} by user {current_user.id}"
    )

    try:
        # Query export job
        export_job = db.query(ExportJob).filter(ExportJob.id == job_id).first()

        if not export_job:
            logger.warning(f"Export job {job_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "JOB_NOT_FOUND",
                    "message": f"Export job with ID {job_id} not found",
                },
            )

        # Verify user owns the export job
        if export_job.user_id != current_user.id:
            logger.warning(
                f"User {current_user.id} attempted to access job {job_id} owned by {export_job.user_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "UNAUTHORIZED_ACCESS",
                    "message": "You do not have permission to access this export job",
                },
            )

        # Build download URL if job is completed
        download_url = None
        if export_job.status == "completed" and export_job.file_path:
            download_url = f"/v1.0/export/download/{job_id}"

        logger.info(
            f"Export job {job_id} status: {export_job.status}, progress: {export_job.progress_percentage}%"
        )

        return ExportJobStatusResponse(
            job_id=export_job.id,
            status=export_job.status,
            progress_percentage=export_job.progress_percentage,
            processed_records=export_job.processed_records,
            total_records=export_job.total_records or 0,
            created_at=export_job.created_at,
            started_at=export_job.started_at,
            completed_at=export_job.completed_at,
            error_message=export_job.error_message,
            download_url=download_url,
            expires_at=export_job.expires_at,
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error checking export status for job {job_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "STATUS_CHECK_FAILED",
                "message": "An error occurred while checking export job status",
            },
        )


@router.get("/download/{job_id}")
async def download_export(
    job_id: str,
    current_user: Annotated[User, Depends(authenticate_for_export)],
    db: Session = Depends(get_db),
):
    """
    Download a completed export file.

    Returns the export file as a downloadable attachment.

    Requirements:
    - Job must be completed
    - File must exist
    - File must not be expired (>24 hours old)
    - User must own the export job

    Requires authentication. Users can only download their own export files.
    """
    logger.info(f"Export download requested for job {job_id} by user {current_user.id}")

    try:
        # Query export job
        export_job = db.query(ExportJob).filter(ExportJob.id == job_id).first()

        if not export_job:
            logger.warning(f"Export job {job_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "JOB_NOT_FOUND",
                    "message": f"Export job with ID {job_id} not found",
                },
            )

        # Verify user owns the export job
        if export_job.user_id != current_user.id:
            logger.warning(
                f"User {current_user.id} attempted to download job {job_id} owned by {export_job.user_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "UNAUTHORIZED_ACCESS",
                    "message": "You do not have permission to access this export job",
                },
            )

        # Check if job is completed
        if export_job.status != "completed":
            logger.warning(
                f"Export job {job_id} is not completed (status: {export_job.status})"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "JOB_NOT_COMPLETED",
                    "message": f"Export job is not completed yet. Current status: {export_job.status}",
                    "status": export_job.status,
                    "progress_percentage": export_job.progress_percentage,
                },
            )

        # Check if file exists
        if not export_job.file_path:
            logger.error(f"Export job {job_id} has no file_path set in database")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "FILE_NOT_FOUND",
                    "message": "Export file path not set. Export may have failed.",
                },
            )

        # Normalize the file path for the current OS
        normalized_path = os.path.normpath(export_job.file_path)

        if not os.path.exists(normalized_path):
            logger.error(f"Export file not found for job {job_id}")
            logger.error(f"Original path from DB: {export_job.file_path}")
            logger.error(f"Normalized path: {normalized_path}")
            logger.error(
                f"File exists (original): {os.path.exists(export_job.file_path)}"
            )
            logger.error(f"File exists (normalized): {os.path.exists(normalized_path)}")
            logger.error(f"Current working directory: {os.getcwd()}")

            # Try to find the file in the exports directory
            exports_dir = os.path.join(os.getcwd(), "exports")
            if os.path.exists(exports_dir):
                logger.error(f"Exports directory exists: {exports_dir}")
                # List files in exports directory
                try:
                    for root, dirs, files in os.walk(exports_dir):
                        logger.error(f"Directory: {root}")
                        for file in files:
                            if job_id in file:
                                actual_file_path = os.path.join(root, file)
                                logger.error(
                                    f"Found file with job_id: {actual_file_path}"
                                )
                                # Update the database with the correct path
                                export_job.file_path = actual_file_path
                                db.commit()
                                logger.info(
                                    f"Updated file_path in database to: {actual_file_path}"
                                )
                                # Use this path instead
                                normalized_path = actual_file_path
                                break
                except Exception as e:
                    logger.error(f"Error listing exports directory: {str(e)}")

            # Check again after potential fix
            if not os.path.exists(normalized_path):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "FILE_NOT_FOUND",
                        "message": "Export file not found. It may have been deleted.",
                        "expected_path": export_job.file_path,
                    },
                )

        # Use the normalized path for file operations
        export_job.file_path = normalized_path

        # Check if export has expired
        if export_job.expires_at and export_job.expires_at < datetime.utcnow():
            logger.warning(
                f"Export job {job_id} has expired (expired at: {export_job.expires_at})"
            )

            # Clean up expired file
            try:
                if os.path.exists(export_job.file_path):
                    os.remove(export_job.file_path)
                    logger.info(f"Deleted expired export file: {export_job.file_path}")
            except Exception as cleanup_error:
                logger.error(f"Error deleting expired file: {str(cleanup_error)}")

            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail={
                    "error": "EXPORT_EXPIRED",
                    "message": "Export file has expired and is no longer available. Please create a new export.",
                    "expired_at": export_job.expires_at.isoformat(),
                },
            )

        # Get file info
        file_path = export_job.file_path
        filename = os.path.basename(file_path)

        # Determine content type based on format
        from services.export_format_handler import ExportFormatHandler

        format_handler = ExportFormatHandler()
        content_type = format_handler.get_content_type(export_job.format)

        logger.info(f"Serving export file {filename} for job {job_id}")

        # Return file response
        return FileResponse(
            path=file_path,
            media_type=content_type,
            filename=filename,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Export-ID": export_job.id,
                "X-Export-Type": export_job.export_type,
                "X-Record-Count": str(export_job.processed_records),
                "X-Generated-At": (
                    export_job.completed_at.isoformat()
                    if export_job.completed_at
                    else ""
                ),
                "X-Expires-At": (
                    export_job.expires_at.isoformat() if export_job.expires_at else ""
                ),
            },
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error downloading export for job {job_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "DOWNLOAD_FAILED",
                "message": "An error occurred while downloading the export file",
            },
        )


@router.delete("/cancel/{job_id}")
async def cancel_export_job(
    job_id: str,
    current_user: Annotated[User, Depends(authenticate_for_export)],
    db: Session = Depends(get_db),
):
    """
    Cancel a stuck or processing export job.

    Useful for cleaning up jobs that got stuck due to server restarts.
    Only the user who created the job (or admin/super users) can cancel it.
    """
    logger.info(f"Cancel export job requested for {job_id} by user {current_user.id}")

    # Get export job
    export_job = db.query(ExportJob).filter(ExportJob.id == job_id).first()

    if not export_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export job {job_id} not found",
        )

    # Check permissions - only job owner or admin can cancel
    if export_job.user_id != current_user.id:
        if current_user.role not in [UserRole.SUPER_USER, UserRole.ADMIN_USER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only cancel your own export jobs",
            )

    # Can only cancel pending or processing jobs
    if export_job.status not in ["pending", "processing"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status: {export_job.status}",
        )

    # Signal the worker to stop processing this job
    from services.export_worker import get_export_worker

    worker = get_export_worker()
    worker_cancelled = worker.cancel_job(job_id)

    # Mark as failed/cancelled in database
    export_job.status = "failed"
    export_job.error_message = "Cancelled by user"
    export_job.completed_at = datetime.utcnow()
    db.commit()

    logger.info(
        f"Export job {job_id} cancelled successfully (worker notified: {worker_cancelled})"
    )

    return {
        "success": True,
        "message": f"Export job {job_id} has been cancelled",
        "job_id": job_id,
        "worker_notified": worker_cancelled,
    }
