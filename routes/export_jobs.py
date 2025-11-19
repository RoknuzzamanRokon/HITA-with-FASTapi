"""
Export Jobs Management API Routes

Provides endpoints for managing export jobs - viewing, deleting, and clearing completed jobs.
This enables cross-device access to export history and better job management.

Features:
- Get all export jobs for authenticated user with filtering and pagination
- Get single export job details
- Delete specific export job
- Clear completed/failed/expired jobs
- Role-based access control
- Audit logging for all operations
"""

import logging
import os
from typing import Annotated, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc

from database import get_db
from routes.auth import authenticate_for_export
from models import User, ExportJob
from export_schemas import (
    ExportJobListResponse,
    ExportJobDetailResponse,
    ExportJobDeleteResponse,
    ExportJobsClearResponse,
    ExportJobSummary
)
from security.audit_logging import AuditLogger, ActivityType, SecurityLevel

# Configure logging
logger = logging.getLogger(__name__)

# Router setup
router = APIRouter(
    prefix="/v1.0/export/jobs",
    tags=["Export Jobs"],
    responses={404: {"description": "Not found"}},
)


@router.get("", response_model=ExportJobListResponse)
async def get_export_jobs(
    request: Request,
    current_user: Annotated[User, Depends(authenticate_for_export)],
    db: Session = Depends(get_db),
    status_filter: Optional[str] = Query(None, description="Filter by status (pending, processing, completed, failed, expired)"),
    export_type: Optional[str] = Query(None, description="Filter by type (hotels, mappings, supplier_summary)"),
    limit: int = Query(100, ge=1, le=500, description="Number of jobs to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    sort: str = Query("created_desc", description="Sort order (created_desc, created_asc, status)")
):
    """
    Get all export jobs for the authenticated user.
    
    **Query Parameters:**
    - status_filter: Filter by job status (pending, processing, completed, failed, expired)
    - export_type: Filter by export type (hotels, mappings, supplier_summary)
    - limit: Number of jobs to return (default: 100, max: 500)
    - offset: Pagination offset (default: 0)
    - sort: Sort order (created_desc, created_asc, status)
    
    **Returns:**
    - List of export jobs with pagination info
    - Total count of jobs matching filters
    
    **Authentication:**
    - Requires valid API key or JWT token
    - Users can only see their own jobs
    """
    logger.info(f"Get export jobs requested by user {current_user.id}")
    
    try:
        # Build base query for user's jobs
        query = db.query(ExportJob).filter(ExportJob.user_id == current_user.id)
        
        # Apply status filter
        if status_filter:
            valid_statuses = ["pending", "processing", "completed", "failed", "expired"]
            if status_filter.lower() not in valid_statuses:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status filter. Must be one of: {', '.join(valid_statuses)}"
                )
            query = query.filter(ExportJob.status == status_filter.lower())
        
        # Apply export type filter
        if export_type:
            valid_types = ["hotels", "mappings", "supplier_summary"]
            if export_type.lower() not in valid_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid export type. Must be one of: {', '.join(valid_types)}"
                )
            query = query.filter(ExportJob.export_type == export_type.lower())
        
        # Get total count before pagination
        total = query.count()
        
        # Apply sorting
        if sort == "created_desc":
            query = query.order_by(desc(ExportJob.created_at))
        elif sort == "created_asc":
            query = query.order_by(asc(ExportJob.created_at))
        elif sort == "status":
            query = query.order_by(ExportJob.status, desc(ExportJob.created_at))
        else:
            # Default to created_desc
            query = query.order_by(desc(ExportJob.created_at))
        
        # Apply pagination
        jobs = query.limit(limit).offset(offset).all()
        
        # Build response
        job_summaries = []
        for job in jobs:
            download_url = None
            if job.status == "completed" and job.file_path:
                download_url = f"/v1.0/export/download/{job.id}"
            
            job_summaries.append(ExportJobSummary(
                job_id=job.id,
                export_type=job.export_type,
                format=job.format,
                status=job.status,
                progress_percentage=job.progress_percentage,
                processed_records=job.processed_records,
                total_records=job.total_records,
                created_at=job.created_at,
                completed_at=job.completed_at,
                download_url=download_url,
                expires_at=job.expires_at,
                file_size_bytes=job.file_size_bytes
            ))
        
        # Log activity
        audit_logger = AuditLogger(db)
        audit_logger.log_activity(
            activity_type=ActivityType.API_ACCESS,
            user_id=current_user.id,
            details={
                "action": "list_export_jobs",
                "total_jobs": total,
                "filters": {
                    "status": status_filter,
                    "export_type": export_type,
                    "limit": limit,
                    "offset": offset
                }
            },
            request=request,
            security_level=SecurityLevel.LOW,
            success=True
        )
        
        logger.info(f"Returning {len(job_summaries)} export jobs for user {current_user.id}")
        
        return ExportJobListResponse(
            jobs=job_summaries,
            total=total,
            limit=limit,
            offset=offset
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting export jobs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve export jobs"
        )


@router.get("/{job_id}", response_model=ExportJobDetailResponse)
async def get_export_job(
    job_id: str,
    request: Request,
    current_user: Annotated[User, Depends(authenticate_for_export)],
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific export job.
    
    **Path Parameters:**
    - job_id: Unique identifier of the export job
    
    **Returns:**
    - Detailed export job information
    
    **Authentication:**
    - Requires valid API key or JWT token
    - Users can only access their own jobs
    """
    logger.info(f"Get export job {job_id} requested by user {current_user.id}")
    
    try:
        # Get job from database
        job = db.query(ExportJob).filter(
            ExportJob.id == job_id,
            ExportJob.user_id == current_user.id
        ).first()
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Export job {job_id} not found"
            )
        
        # Build download URL if completed
        download_url = None
        if job.status == "completed" and job.file_path:
            download_url = f"/v1.0/export/download/{job.id}"
        
        # Log activity
        audit_logger = AuditLogger(db)
        audit_logger.log_activity(
            activity_type=ActivityType.API_ACCESS,
            user_id=current_user.id,
            details={
                "action": "get_export_job",
                "job_id": job_id,
                "status": job.status
            },
            request=request,
            security_level=SecurityLevel.LOW,
            success=True
        )
        
        return ExportJobDetailResponse(
            job_id=job.id,
            user_id=job.user_id,
            export_type=job.export_type,
            format=job.format,
            filters=job.filters,
            status=job.status,
            progress_percentage=job.progress_percentage,
            processed_records=job.processed_records,
            total_records=job.total_records,
            file_path=job.file_path,
            file_size_bytes=job.file_size_bytes,
            error_message=job.error_message,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            expires_at=job.expires_at,
            download_url=download_url
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting export job {job_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve export job"
        )


@router.delete("/{job_id}", response_model=ExportJobDeleteResponse)
async def delete_export_job(
    job_id: str,
    request: Request,
    current_user: Annotated[User, Depends(authenticate_for_export)],
    db: Session = Depends(get_db)
):
    """
    Delete a specific export job and its associated file.
    
    **Path Parameters:**
    - job_id: Unique identifier of the export job
    
    **Returns:**
    - Confirmation of deletion
    
    **Authentication:**
    - Requires valid API key or JWT token
    - Users can only delete their own jobs
    """
    logger.info(f"Delete export job {job_id} requested by user {current_user.id}")
    
    try:
        # Get job from database
        job = db.query(ExportJob).filter(
            ExportJob.id == job_id,
            ExportJob.user_id == current_user.id
        ).first()
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Export job {job_id} not found"
            )
        
        # Delete file if it exists
        if job.file_path and os.path.exists(job.file_path):
            try:
                os.remove(job.file_path)
                logger.info(f"Deleted export file: {job.file_path}")
            except Exception as e:
                logger.error(f"Error deleting file {job.file_path}: {str(e)}")
        
        # Delete job from database
        db.delete(job)
        db.commit()
        
        # Log activity
        audit_logger = AuditLogger(db)
        audit_logger.log_activity(
            activity_type=ActivityType.DATA_EXPORT,
            user_id=current_user.id,
            details={
                "action": "delete_export_job",
                "job_id": job_id,
                "export_type": job.export_type,
                "status": job.status
            },
            request=request,
            security_level=SecurityLevel.MEDIUM,
            success=True
        )
        
        logger.info(f"Export job {job_id} deleted successfully")
        
        return ExportJobDeleteResponse(
            success=True,
            message=f"Export job {job_id} deleted successfully",
            job_id=job_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting export job {job_id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete export job"
        )


@router.delete("", response_model=ExportJobsClearResponse)
async def clear_export_jobs(
    request: Request,
    current_user: Annotated[User, Depends(authenticate_for_export)],
    db: Session = Depends(get_db),
    status_filter: Optional[str] = Query(None, description="Clear jobs with specific status (completed, failed, expired)")
):
    """
    Clear multiple export jobs at once.
    
    **Query Parameters:**
    - status_filter: Only clear jobs with this status (completed, failed, expired)
    
    **Returns:**
    - Count of deleted jobs and their IDs
    
    **Authentication:**
    - Requires valid API key or JWT token
    - Users can only clear their own jobs
    """
    logger.info(f"Clear export jobs requested by user {current_user.id}")
    
    try:
        # Build query for user's jobs
        query = db.query(ExportJob).filter(ExportJob.user_id == current_user.id)
        
        # Apply status filter if provided
        if status_filter:
            valid_statuses = ["completed", "failed", "expired"]
            if status_filter.lower() not in valid_statuses:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status filter. Must be one of: {', '.join(valid_statuses)}"
                )
            query = query.filter(ExportJob.status == status_filter.lower())
        else:
            # Default: only clear completed, failed, or expired jobs
            query = query.filter(ExportJob.status.in_(["completed", "failed", "expired"]))
        
        # Get jobs to delete
        jobs_to_delete = query.all()
        deleted_job_ids = []
        
        # Delete files and jobs
        for job in jobs_to_delete:
            # Delete file if it exists
            if job.file_path and os.path.exists(job.file_path):
                try:
                    os.remove(job.file_path)
                    logger.debug(f"Deleted export file: {job.file_path}")
                except Exception as e:
                    logger.error(f"Error deleting file {job.file_path}: {str(e)}")
            
            deleted_job_ids.append(job.id)
            db.delete(job)
        
        db.commit()
        
        # Log activity
        audit_logger = AuditLogger(db)
        audit_logger.log_activity(
            activity_type=ActivityType.BULK_OPERATION,
            user_id=current_user.id,
            details={
                "action": "clear_export_jobs",
                "deleted_count": len(deleted_job_ids),
                "status_filter": status_filter
            },
            request=request,
            security_level=SecurityLevel.MEDIUM,
            success=True
        )
        
        logger.info(f"Cleared {len(deleted_job_ids)} export jobs for user {current_user.id}")
        
        return ExportJobsClearResponse(
            success=True,
            message=f"Successfully cleared {len(deleted_job_ids)} export jobs",
            deleted_count=len(deleted_job_ids),
            deleted_job_ids=deleted_job_ids
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing export jobs: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear export jobs"
        )
