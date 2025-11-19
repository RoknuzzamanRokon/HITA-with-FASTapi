"""
Export Engine Service

Core export processing engine with streaming and batch processing.
Handles both synchronous and asynchronous export operations.

Features:
- Automatic sync/async decision based on record count
- Streaming query results for memory efficiency
- Batch processing with configurable batch size
- Progress tracking for async exports
- Background task processing
"""

import os
import uuid
import logging
from typing import Generator, List, Any, Union, Optional
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy.orm import Session, Query
from fastapi import BackgroundTasks
from fastapi.responses import FileResponse

from models import ExportJob, User
from export_schemas import ExportFormat, ExportMetadata
from services.export_format_handler import ExportFormatHandler
from security.audit_logging import AuditLogger, ActivityType, SecurityLevel
import sys
import os

# Add utils directory to path for import
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "utils"))
from export_file_storage import ExportFileStorage

# Configure logging
logger = logging.getLogger(__name__)


class ExportEngine:
    """
    Core export processing engine.

    Handles:
    - Synchronous exports for small datasets (<5000 records)
    - Asynchronous exports for large datasets (>=5000 records)
    - Streaming query results in batches
    - Progress tracking and status updates
    - File generation and storage
    """

    def __init__(self, db: Session, storage_path: str = None):
        """
        Initialize ExportEngine with database session.

        Args:
            db: SQLAlchemy database session
            storage_path: Path to store export files (default: ./exports/)
        """
        self.db = db
        self.batch_size = 1000
        self.async_threshold = 5000
        self.format_handler = ExportFormatHandler()

        # Initialize file storage manager
        self.file_storage = ExportFileStorage(storage_path)
        self.storage_path = self.file_storage.base_storage_path

        logger.info(f"ExportEngine initialized with storage path: {self.storage_path}")

    def stream_query_results(
        self,
        query: Query,
        batch_size: int = None,
        job_id: str = None,
        db_session: Session = None,
    ) -> Generator[List[Any], None, None]:
        """
        Stream query results in batches for memory efficiency.

        Uses SQLAlchemy's yield_per() for efficient streaming of large result sets.
        This prevents loading all records into memory at once.

        Optimizations:
        - Uses yield_per() to fetch records in batches from database
        - Enables query.execution_options(stream_results=True) for true streaming
        - Batches results before yielding to reduce overhead

        Args:
            query: SQLAlchemy Query object to stream results from
            batch_size: Number of records per batch (default: self.batch_size)

        Yields:
            Lists of records in batches
        """
        if batch_size is None:
            batch_size = self.batch_size

        logger.debug(f"Streaming query results with batch size: {batch_size}")

        try:
            import time

            # Use offset-based pagination to avoid cursor issues with MySQL
            # This fetches records in chunks without holding a cursor open
            logger.debug(f"Streaming query results using offset-based pagination...")

            offset = 0
            batch_num = 0

            while True:
                # Check for cancellation if job_id and db_session provided
                if job_id and db_session:
                    from models import ExportJob

                    export_job = (
                        db_session.query(ExportJob)
                        .filter(ExportJob.id == job_id)
                        .first()
                    )
                    if (
                        export_job
                        and export_job.status == "failed"
                        and export_job.error_message == "Cancelled by user"
                    ):
                        logger.warning(
                            f"[STREAM] Job {job_id} was cancelled, stopping stream"
                        )
                        raise Exception("Export cancelled by user")

                # Fetch a batch using offset and limit
                batch_query = query.offset(offset).limit(batch_size)
                batch_records = batch_query.all()

                if not batch_records:
                    # No more records
                    break

                batch_num += 1
                logger.debug(
                    f"Fetched batch {batch_num}: {len(batch_records)} records at offset {offset}"
                )

                yield batch_records

                # If we got fewer records than batch_size, we're done
                if len(batch_records) < batch_size:
                    break

                offset += batch_size

                # Small delay to allow other requests to process
                # This prevents the export from monopolizing database connections
                if batch_num % 10 == 0:  # Every 10 batches (10,000 records)
                    time.sleep(0.1)  # 100ms pause

            logger.debug(f"Finished streaming. Total batches: {batch_num}")

        except Exception as e:
            logger.error(f"Error streaming query results: {str(e)}")
            raise

    def export_hotels_sync(
        self,
        query: Query,
        format: ExportFormat,
        user: User,
        include_locations: bool = True,
        include_contacts: bool = True,
        include_mappings: bool = True,
    ) -> FileResponse:
        """
        Export hotel data synchronously for small datasets (<5000 records).

        Process:
        1. Stream query results in batches
        2. Transform data using format handler
        3. Write to temporary file
        4. Return FileResponse with appropriate headers
        5. Clean up resources

        Args:
            query: SQLAlchemy Query object for hotels
            format: Export format (CSV, JSON, EXCEL)
            user: User object who requested the export
            include_locations: Whether to include location data
            include_contacts: Whether to include contact data
            include_mappings: Whether to include provider mappings

        Returns:
            FileResponse with the export file
        """
        logger.info(
            f"Starting synchronous hotel export for user {user.id} in {format.value} format"
        )

        try:
            # Generate unique job ID for tracking
            job_id = f"exp_{uuid.uuid4().hex[:16]}"

            # Generate file path using storage manager
            timestamp = datetime.utcnow()
            output_path = self.file_storage.get_file_path(
                job_id=job_id,
                export_type="hotels",
                format=format.value,
                timestamp=timestamp,
            )

            logger.debug(f"Export file path: {output_path}")

            # Create metadata
            metadata = ExportMetadata(
                export_id=job_id,
                generated_at=timestamp,
                generated_by=user.username,
                user_id=user.id,
                filters_applied={},  # Will be populated by caller
                total_records=0,  # Will be updated after processing
                format=format.value,
                version="1.0",
            )

            # Stream query results
            data_generator = self.stream_query_results(query, self.batch_size)

            # Generate file based on format
            if format == ExportFormat.CSV:
                # Get CSV headers
                headers = self.format_handler.get_csv_headers_hotel()

                # Generate CSV with flattening function
                output_path = self.format_handler.to_csv(
                    data=data_generator,
                    output_path=output_path,
                    headers=headers,
                    flatten_func=self.format_handler.flatten_hotel_data,
                )

            elif format == ExportFormat.JSON:
                # Generate JSON with metadata
                output_path = self.format_handler.to_json(
                    data=data_generator,
                    output_path=output_path,
                    metadata=metadata,
                    preserve_structure=True,
                )

            elif format == ExportFormat.EXCEL:
                # Generate Excel with multiple sheets
                output_path = self.format_handler.to_excel_hotels(
                    hotels=data_generator, output_path=output_path, metadata=metadata
                )

            else:
                raise ValueError(f"Unsupported export format: {format}")

            # Set file permissions for security
            self.file_storage.set_file_permissions(output_path)

            # Get file size
            file_size = self.file_storage.get_file_size(output_path)
            logger.info(f"Export file generated: {output_path} ({file_size} bytes)")

            # Get content type
            content_type = self.format_handler.get_content_type(format.value)

            # Get filename for response
            filename = os.path.basename(output_path)

            # Return file response
            return FileResponse(
                path=output_path,
                media_type=content_type,
                filename=filename,
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "X-Export-ID": metadata.export_id,
                    "X-Generated-At": metadata.generated_at.isoformat(),
                },
            )

        except IOError as e:
            logger.error(f"File I/O error in synchronous hotel export: {str(e)}")
            # Clean up file if it exists
            if "output_path" in locals() and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                    logger.debug(f"Cleaned up failed export file: {output_path}")
                except Exception as cleanup_error:
                    logger.error(f"Error cleaning up file: {str(cleanup_error)}")
            raise Exception(f"File I/O error during export: {str(e)}")
        except Exception as e:
            logger.error(f"Error in synchronous hotel export: {str(e)}")
            # Clean up file if it exists
            if "output_path" in locals() and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                    logger.debug(f"Cleaned up failed export file: {output_path}")
                except Exception as cleanup_error:
                    logger.error(f"Error cleaning up file: {str(cleanup_error)}")
            raise Exception(f"Export processing failed: {str(e)}")

    def export_mappings_sync(
        self, query: Query, format: ExportFormat, user: User
    ) -> FileResponse:
        """
        Export provider mapping data synchronously.

        Args:
            query: SQLAlchemy Query object for provider mappings
            format: Export format (CSV, JSON, EXCEL)
            user: User object who requested the export

        Returns:
            FileResponse with the export file
        """
        logger.info(
            f"Starting synchronous mapping export for user {user.id} in {format.value} format"
        )

        try:
            # Generate unique job ID for tracking
            job_id = f"exp_{uuid.uuid4().hex[:16]}"

            # Generate file path using storage manager
            timestamp = datetime.utcnow()
            output_path = self.file_storage.get_file_path(
                job_id=job_id,
                export_type="mappings",
                format=format.value,
                timestamp=timestamp,
            )

            logger.debug(f"Export file path: {output_path}")

            # Create metadata
            metadata = ExportMetadata(
                export_id=job_id,
                generated_at=timestamp,
                generated_by=user.username,
                user_id=user.id,
                filters_applied={},
                total_records=0,
                format=format.value,
                version="1.0",
            )

            # Stream query results
            data_generator = self.stream_query_results(query, self.batch_size)

            # Generate file based on format
            if format == ExportFormat.CSV:
                headers = [
                    "ittid",
                    "provider_name",
                    "provider_id",
                    "system_type",
                    "vervotech_id",
                    "giata_code",
                    "created_at",
                    "updated_at",
                ]

                output_path = self.format_handler.to_csv(
                    data=data_generator, output_path=output_path, headers=headers
                )

            elif format == ExportFormat.JSON:
                output_path = self.format_handler.to_json(
                    data=data_generator,
                    output_path=output_path,
                    metadata=metadata,
                    preserve_structure=True,
                )

            elif format == ExportFormat.EXCEL:
                # For Excel, create a single sheet with mapping data
                output_path = self.format_handler.to_excel(
                    data={"Mappings": data_generator},
                    output_path=output_path,
                    metadata=metadata,
                )

            else:
                raise ValueError(f"Unsupported export format: {format}")

            # Set file permissions for security
            self.file_storage.set_file_permissions(output_path)

            # Get file size
            file_size = self.file_storage.get_file_size(output_path)
            logger.info(
                f"Mapping export file generated: {output_path} ({file_size} bytes)"
            )

            # Get content type
            content_type = self.format_handler.get_content_type(format.value)

            # Get filename for response
            filename = os.path.basename(output_path)

            # Return file response
            return FileResponse(
                path=output_path,
                media_type=content_type,
                filename=filename,
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "X-Export-ID": metadata.export_id,
                    "X-Generated-At": metadata.generated_at.isoformat(),
                },
            )

        except IOError as e:
            logger.error(f"File I/O error in synchronous mapping export: {str(e)}")
            # Clean up file if it exists
            if "output_path" in locals() and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                    logger.debug(f"Cleaned up failed export file: {output_path}")
                except Exception as cleanup_error:
                    logger.error(f"Error cleaning up file: {str(cleanup_error)}")
            raise Exception(f"File I/O error during export: {str(e)}")
        except Exception as e:
            logger.error(f"Error in synchronous mapping export: {str(e)}")
            # Clean up file if it exists
            if "output_path" in locals() and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                    logger.debug(f"Cleaned up failed export file: {output_path}")
                except Exception as cleanup_error:
                    logger.error(f"Error cleaning up file: {str(cleanup_error)}")
            raise Exception(f"Export processing failed: {str(e)}")

    def export_supplier_summary_sync(
        self,
        query: Query,
        format: ExportFormat,
        user: User,
        country_breakdown: dict = None,
    ) -> FileResponse:
        """
        Export supplier summary statistics synchronously.

        Args:
            query: SQLAlchemy Query object for supplier summary
            format: Export format (CSV, JSON, EXCEL)
            user: User object who requested the export
            country_breakdown: Optional country breakdown data

        Returns:
            FileResponse with the export file
        """
        logger.info(
            f"Starting synchronous supplier summary export for user {user.id} in {format.value} format"
        )

        try:
            # Generate unique job ID for tracking
            job_id = f"exp_{uuid.uuid4().hex[:16]}"

            # Generate file path using storage manager
            timestamp = datetime.utcnow()
            output_path = self.file_storage.get_file_path(
                job_id=job_id,
                export_type="supplier_summary",
                format=format.value,
                timestamp=timestamp,
            )

            logger.debug(f"Export file path: {output_path}")

            # Create metadata
            metadata = ExportMetadata(
                export_id=job_id,
                generated_at=timestamp,
                generated_by=user.username,
                user_id=user.id,
                filters_applied={},
                total_records=0,
                format=format.value,
                version="1.0",
            )

            # Stream query results
            data_generator = self.stream_query_results(query, self.batch_size)

            # Generate file based on format
            if format == ExportFormat.CSV:
                headers = [
                    "provider_name",
                    "total_hotels",
                    "total_mappings",
                    "last_updated",
                    "summary_generated_at",
                ]

                output_path = self.format_handler.to_csv(
                    data=data_generator, output_path=output_path, headers=headers
                )

            elif format == ExportFormat.JSON:
                output_path = self.format_handler.to_json(
                    data=data_generator,
                    output_path=output_path,
                    metadata=metadata,
                    preserve_structure=True,
                )

            elif format == ExportFormat.EXCEL:
                # For Excel, create summary sheet
                output_path = self.format_handler.to_excel(
                    data={"Supplier Summary": data_generator},
                    output_path=output_path,
                    metadata=metadata,
                )

            else:
                raise ValueError(f"Unsupported export format: {format}")

            # Set file permissions for security
            self.file_storage.set_file_permissions(output_path)

            # Get file size
            file_size = self.file_storage.get_file_size(output_path)
            logger.info(
                f"Supplier summary export file generated: {output_path} ({file_size} bytes)"
            )

            # Get content type
            content_type = self.format_handler.get_content_type(format.value)

            # Get filename for response
            filename = os.path.basename(output_path)

            # Return file response
            return FileResponse(
                path=output_path,
                media_type=content_type,
                filename=filename,
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "X-Export-ID": metadata.export_id,
                    "X-Generated-At": metadata.generated_at.isoformat(),
                },
            )

        except IOError as e:
            logger.error(
                f"File I/O error in synchronous supplier summary export: {str(e)}"
            )
            # Clean up file if it exists
            if "output_path" in locals() and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                    logger.debug(f"Cleaned up failed export file: {output_path}")
                except Exception as cleanup_error:
                    logger.error(f"Error cleaning up file: {str(cleanup_error)}")
            raise Exception(f"File I/O error during export: {str(e)}")
        except Exception as e:
            logger.error(f"Error in synchronous supplier summary export: {str(e)}")
            # Clean up file if it exists
            if "output_path" in locals() and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                    logger.debug(f"Cleaned up failed export file: {output_path}")
                except Exception as cleanup_error:
                    logger.error(f"Error cleaning up file: {str(cleanup_error)}")
            raise Exception(f"Export processing failed: {str(e)}")

    def export_hotels_async(
        self,
        query: Query,
        format: ExportFormat,
        user: User,
        background_tasks: BackgroundTasks,
        filters_applied: dict = None,
        include_locations: bool = True,
        include_contacts: bool = True,
        include_mappings: bool = True,
    ) -> ExportJob:
        """
        Export hotel data asynchronously for large datasets (>=5000 records).

        Process:
        1. Generate unique job ID
        2. Create ExportJob record in database
        3. Schedule background task for processing
        4. Return job information immediately

        Args:
            query: SQLAlchemy Query object for hotels
            format: Export format (CSV, JSON, EXCEL)
            user: User object who requested the export
            background_tasks: FastAPI BackgroundTasks for async processing
            filters_applied: Dictionary of filters applied to the query
            include_locations: Whether to include location data
            include_contacts: Whether to include contact data
            include_mappings: Whether to include provider mappings

        Returns:
            ExportJob object with job details
        """
        logger.info(
            f"Starting asynchronous hotel export for user {user.id} in {format.value} format"
        )

        try:
            # Generate unique job ID
            job_id = f"exp_{uuid.uuid4().hex[:16]}"

            # Estimate total records
            try:
                total_records = query.count()
            except Exception as e:
                logger.warning(f"Could not estimate record count: {str(e)}")
                total_records = None

            # Create export job record
            export_job = ExportJob(
                id=job_id,
                user_id=user.id,
                export_type="hotels",
                format=format.value,
                filters=filters_applied or {},
                status="pending",
                progress_percentage=0,
                processed_records=0,
                total_records=total_records,
                file_path=None,
                file_size_bytes=None,
                error_message=None,
                created_at=datetime.utcnow(),
                started_at=None,
                completed_at=None,
                expires_at=None,  # Will be set when completed
            )

            # Save to database
            self.db.add(export_job)
            self.db.commit()
            self.db.refresh(export_job)

            logger.info(f"Created export job {job_id} for user {user.id}")

            # Schedule background task
            background_tasks.add_task(
                self.process_async_hotel_export,
                job_id=job_id,
                query=query,
                format=format,
                user=user,
                include_locations=include_locations,
                include_contacts=include_contacts,
                include_mappings=include_mappings,
            )

            logger.info(f"Scheduled background task for export job {job_id}")

            return export_job

        except Exception as e:
            logger.error(f"Database error creating async hotel export job: {str(e)}")
            # Rollback transaction if needed
            try:
                self.db.rollback()
            except:
                pass
            raise Exception(f"Failed to create export job: {str(e)}")

    def process_async_hotel_export(
        self,
        job_id: str,
        query: Query,
        format: ExportFormat,
        user: User,
        include_locations: bool = True,
        include_contacts: bool = True,
        include_mappings: bool = True,
    ) -> None:
        """
        Background task to process asynchronous hotel export.

        Updates job status and progress every 10% completion.
        Writes output to file storage incrementally.
        Handles errors and updates job status to "failed" on exceptions.

        Args:
            job_id: Unique export job ID
            query: SQLAlchemy Query object for hotels
            format: Export format (CSV, JSON, EXCEL)
            user: User object who requested the export
            include_locations: Whether to include location data
            include_contacts: Whether to include contact data
            include_mappings: Whether to include provider mappings
        """
        logger.info(f"Processing async hotel export job {job_id}")

        # Create new database session for background task
        from database import SessionLocal

        db = SessionLocal()

        try:
            # Get export job
            export_job = db.query(ExportJob).filter(ExportJob.id == job_id).first()
            if not export_job:
                logger.error(f"Export job {job_id} not found")
                return

            # Update status to processing
            export_job.status = "processing"
            export_job.started_at = datetime.utcnow()
            db.commit()

            logger.info(f"Export job {job_id} status updated to processing")

            # Generate file path using storage manager
            timestamp = datetime.utcnow()
            output_path = self.file_storage.get_file_path(
                job_id=job_id,
                export_type="hotels",
                format=format.value,
                timestamp=timestamp,
                user_id=user.id,
            )

            logger.debug(f"Export file path: {output_path}")

            # Create metadata
            metadata = ExportMetadata(
                export_id=job_id,
                generated_at=timestamp,
                generated_by=user.username,
                user_id=user.id,
                filters_applied=export_job.filters or {},
                total_records=export_job.total_records or 0,
                format=format.value,
                version="1.0",
            )

            # Process export with progress tracking
            total_records = export_job.total_records or 0
            processed_records = 0
            last_progress_update = 0

            # Create a generator that tracks progress
            def progress_tracking_generator():
                nonlocal processed_records, last_progress_update

                for batch in self.stream_query_results(query, self.batch_size, job_id=job_id, db_session=db):
                    processed_records += len(batch)

                    # Update progress more frequently (every 1% or every batch if small dataset)
                    if total_records > 0:
                        progress = min(int((processed_records / total_records) * 100), 99)

                        # Update if progress changed by at least 1%
                        if progress > last_progress_update:
                            export_job.progress_percentage = progress
                            export_job.processed_records = processed_records
                            db.commit()
                            last_progress_update = progress
                            logger.info(f"[EXPORT] Job {job_id} progress: {progress}% ({processed_records}/{total_records} records)")

                    yield batch

            # Generate file based on format
            if format == ExportFormat.CSV:
                headers = self.format_handler.get_csv_headers_hotel()

                output_path = self.format_handler.to_csv(
                    data=progress_tracking_generator(),
                    output_path=output_path,
                    headers=headers,
                    flatten_func=self.format_handler.flatten_hotel_data,
                )

            elif format == ExportFormat.JSON:
                output_path = self.format_handler.to_json(
                    data=progress_tracking_generator(),
                    output_path=output_path,
                    metadata=metadata,
                    preserve_structure=True,
                )

            elif format == ExportFormat.EXCEL:
                output_path = self.format_handler.to_excel_hotels(
                    hotels=progress_tracking_generator(),
                    output_path=output_path,
                    metadata=metadata,
                )

            else:
                raise ValueError(f"Unsupported export format: {format}")

            # Set file permissions for security
            self.file_storage.set_file_permissions(output_path)

            # Get file size
            file_size = self.file_storage.get_file_size(output_path)

            # Update job as completed
            export_job.status = "completed"
            export_job.progress_percentage = 100
            export_job.processed_records = processed_records
            export_job.file_path = output_path
            export_job.file_size_bytes = file_size
            export_job.completed_at = datetime.utcnow()
            export_job.expires_at = datetime.utcnow() + timedelta(hours=24)
            db.commit()

            logger.info(
                f"Export job {job_id} completed successfully: {file_size} bytes, {processed_records} records"
            )

            # Log export completion
            audit_logger = AuditLogger(db)
            audit_logger.log_activity(
                activity_type=ActivityType.EXPORT_DATA,
                user_id=user.id,
                details={
                    "export_type": "hotels",
                    "format": format.value,
                    "job_id": job_id,
                    "record_count": processed_records,
                    "file_size_bytes": file_size,
                    "sync": False,
                    "status": "completed",
                },
                request=None,
                security_level=SecurityLevel.HIGH,
                success=True,
            )

        except Exception as e:
            logger.error(f"Error processing async hotel export job {job_id}: {str(e)}")

            # Update job as failed
            try:
                export_job = db.query(ExportJob).filter(ExportJob.id == job_id).first()
                if export_job:
                    export_job.status = "failed"
                    export_job.error_message = str(e)
                    export_job.completed_at = datetime.utcnow()
                    db.commit()
                    logger.info(f"Export job {job_id} marked as failed")

                    # Log export failure
                    audit_logger = AuditLogger(db)
                    audit_logger.log_activity(
                        activity_type=ActivityType.EXPORT_DATA,
                        user_id=user.id,
                        details={
                            "export_type": "hotels",
                            "format": format.value,
                            "job_id": job_id,
                            "error": str(e),
                            "sync": False,
                            "status": "failed",
                        },
                        request=None,
                        security_level=SecurityLevel.HIGH,
                        success=False,
                    )
            except Exception as update_error:
                logger.error(f"Error updating failed job status: {str(update_error)}")

        finally:
            # Close database session
            db.close()

    def export_mappings_async(
        self,
        query: Query,
        format: ExportFormat,
        user: User,
        background_tasks: BackgroundTasks,
        filters_applied: dict = None,
    ) -> ExportJob:
        """
        Export provider mapping data asynchronously for large datasets.

        Args:
            query: SQLAlchemy Query object for provider mappings
            format: Export format (CSV, JSON, EXCEL)
            user: User object who requested the export
            background_tasks: FastAPI BackgroundTasks for async processing
            filters_applied: Dictionary of filters applied to the query

        Returns:
            ExportJob object with job details
        """
        logger.info(
            f"Starting asynchronous mapping export for user {user.id} in {format.value} format"
        )

        try:
            # Generate unique job ID
            job_id = f"exp_{uuid.uuid4().hex[:16]}"

            # Estimate total records
            try:
                total_records = query.count()
            except Exception as e:
                logger.warning(f"Could not estimate record count: {str(e)}")
                total_records = None

            # Create export job record
            export_job = ExportJob(
                id=job_id,
                user_id=user.id,
                export_type="mappings",
                format=format.value,
                filters=filters_applied or {},
                status="pending",
                progress_percentage=0,
                processed_records=0,
                total_records=total_records,
                file_path=None,
                file_size_bytes=None,
                error_message=None,
                created_at=datetime.utcnow(),
                started_at=None,
                completed_at=None,
                expires_at=None,
            )

            # Save to database
            self.db.add(export_job)
            self.db.commit()
            self.db.refresh(export_job)

            logger.info(f"Created export job {job_id} for user {user.id}")

            # Schedule background task
            background_tasks.add_task(
                self.process_async_mapping_export,
                job_id=job_id,
                query=query,
                format=format,
                user=user,
            )

            logger.info(f"Scheduled background task for export job {job_id}")

            return export_job

        except Exception as e:
            logger.error(f"Database error creating async mapping export job: {str(e)}")
            # Rollback transaction if needed
            try:
                self.db.rollback()
            except:
                pass
            raise Exception(f"Failed to create export job: {str(e)}")

    def process_async_mapping_export(
        self, job_id: str, query: Query, format: ExportFormat, user: User
    ) -> None:
        """
        Background task to process asynchronous mapping export.

        Args:
            job_id: Unique export job ID
            query: SQLAlchemy Query object for provider mappings
            format: Export format (CSV, JSON, EXCEL)
            user: User object who requested the export
        """
        logger.info(f"Processing async mapping export job {job_id}")

        # Create new database session for background task
        from database import SessionLocal

        db = SessionLocal()

        try:
            # Get export job
            export_job = db.query(ExportJob).filter(ExportJob.id == job_id).first()
            if not export_job:
                logger.error(f"Export job {job_id} not found")
                return

            # Update status to processing
            export_job.status = "processing"
            export_job.started_at = datetime.utcnow()
            db.commit()

            logger.info(f"Export job {job_id} status updated to processing")

            # Generate file path using storage manager
            timestamp = datetime.utcnow()
            output_path = self.file_storage.get_file_path(
                job_id=job_id,
                export_type="mappings",
                format=format.value,
                timestamp=timestamp,
                user_id=user.id,
            )

            logger.debug(f"Export file path: {output_path}")

            # Create metadata
            metadata = ExportMetadata(
                export_id=job_id,
                generated_at=timestamp,
                generated_by=user.username,
                user_id=user.id,
                filters_applied=export_job.filters or {},
                total_records=export_job.total_records or 0,
                format=format.value,
                version="1.0",
            )

            # Process export with progress tracking
            total_records = export_job.total_records or 0
            processed_records = 0
            last_progress_update = 0

            logger.info(f"[EXPORT] Starting mapping export for job {job_id}")

            # Create a generator that tracks progress and checks for cancellation
            def progress_tracking_generator():
                nonlocal processed_records, last_progress_update
                batch_count = 0

                logger.info(f"[EXPORT] Beginning to stream query results...")
                for batch in self.stream_query_results(
                    query, self.batch_size, job_id=job_id, db_session=db
                ):
                    batch_count += 1
                    batch_size_actual = len(batch)
                    processed_records += batch_size_actual

                    logger.info(
                        f"[EXPORT] Batch {batch_count}: {batch_size_actual} records, Total so far: {processed_records}"
                    )

                    # Update progress more frequently (every 1% or every batch if small dataset)
                    if total_records > 0:
                        progress = min(int((processed_records / total_records) * 100), 99)

                        # Update if progress changed by at least 1%
                        if progress > last_progress_update:
                            export_job.progress_percentage = progress
                            export_job.processed_records = processed_records
                            db.commit()
                            last_progress_update = progress
                            logger.info(f"[EXPORT] Job {job_id} progress: {progress}% ({processed_records}/{total_records} records)")

                    yield batch

                logger.info(
                    f"[EXPORT] Finished streaming. Total batches: {batch_count}, Total records: {processed_records}"
                )

            # Generate file based on format
            if format == ExportFormat.CSV:
                headers = [
                    "ittid",
                    "provider_name",
                    "provider_id",
                    "created_at",
                    "updated_at",
                ]

                output_path = self.format_handler.to_csv(
                    data=progress_tracking_generator(),
                    output_path=output_path,
                    headers=headers,
                )

            elif format == ExportFormat.JSON:
                output_path = self.format_handler.to_json(
                    data=progress_tracking_generator(),
                    output_path=output_path,
                    metadata=metadata,
                    preserve_structure=True,
                )

            elif format == ExportFormat.EXCEL:
                output_path = self.format_handler.to_excel(
                    data={"Mappings": progress_tracking_generator()},
                    output_path=output_path,
                    metadata=metadata,
                )

            else:
                raise ValueError(f"Unsupported export format: {format}")

            # Set file permissions for security
            self.file_storage.set_file_permissions(output_path)

            # Get file size
            file_size = self.file_storage.get_file_size(output_path)

            # Update job as completed
            export_job.status = "completed"
            export_job.progress_percentage = 100
            export_job.processed_records = processed_records
            export_job.file_path = output_path
            export_job.file_size_bytes = file_size
            export_job.completed_at = datetime.utcnow()
            export_job.expires_at = datetime.utcnow() + timedelta(hours=24)
            db.commit()

            logger.info(
                f"Export job {job_id} completed successfully: {file_size} bytes, {processed_records} records"
            )

            # Log export completion
            audit_logger = AuditLogger(db)
            audit_logger.log_activity(
                activity_type=ActivityType.EXPORT_DATA,
                user_id=user.id,
                details={
                    "export_type": "mappings",
                    "format": format.value,
                    "job_id": job_id,
                    "record_count": processed_records,
                    "file_size_bytes": file_size,
                    "sync": False,
                    "status": "completed",
                },
                request=None,
                security_level=SecurityLevel.HIGH,
                success=True,
            )

        except Exception as e:
            logger.error(
                f"Error processing async mapping export job {job_id}: {str(e)}"
            )

            # Update job as failed
            try:
                export_job = db.query(ExportJob).filter(ExportJob.id == job_id).first()
                if export_job:
                    export_job.status = "failed"
                    export_job.error_message = str(e)
                    export_job.completed_at = datetime.utcnow()
                    db.commit()
                    logger.info(f"Export job {job_id} marked as failed")

                    # Log export failure
                    audit_logger = AuditLogger(db)
                    audit_logger.log_activity(
                        activity_type=ActivityType.EXPORT_DATA,
                        user_id=user.id,
                        details={
                            "export_type": "mappings",
                            "format": format.value,
                            "job_id": job_id,
                            "error": str(e),
                            "sync": False,
                            "status": "failed",
                        },
                        request=None,
                        security_level=SecurityLevel.HIGH,
                        success=False,
                    )
            except Exception as update_error:
                logger.error(f"Error updating failed job status: {str(update_error)}")

        finally:
            # Close database session
            db.close()

    def export_supplier_summary_async(
        self,
        query: Query,
        format: ExportFormat,
        user: User,
        background_tasks: BackgroundTasks,
        filters_applied: dict = None,
        country_breakdown: dict = None,
    ) -> ExportJob:
        """
        Export supplier summary statistics asynchronously.

        Args:
            query: SQLAlchemy Query object for supplier summary
            format: Export format (CSV, JSON, EXCEL)
            user: User object who requested the export
            background_tasks: FastAPI BackgroundTasks for async processing
            filters_applied: Dictionary of filters applied to the query
            country_breakdown: Optional country breakdown data

        Returns:
            ExportJob object with job details
        """
        logger.info(
            f"Starting asynchronous supplier summary export for user {user.id} in {format.value} format"
        )

        try:
            # Generate unique job ID
            job_id = f"exp_{uuid.uuid4().hex[:16]}"

            # Estimate total records
            try:
                total_records = query.count()
            except Exception as e:
                logger.warning(f"Could not estimate record count: {str(e)}")
                total_records = None

            # Create export job record
            export_job = ExportJob(
                id=job_id,
                user_id=user.id,
                export_type="supplier_summary",
                format=format.value,
                filters=filters_applied or {},
                status="pending",
                progress_percentage=0,
                processed_records=0,
                total_records=total_records,
                file_path=None,
                file_size_bytes=None,
                error_message=None,
                created_at=datetime.utcnow(),
                started_at=None,
                completed_at=None,
                expires_at=None,
            )

            # Save to database
            self.db.add(export_job)
            self.db.commit()
            self.db.refresh(export_job)

            logger.info(f"Created export job {job_id} for user {user.id}")

            # Schedule background task
            background_tasks.add_task(
                self.process_async_supplier_summary_export,
                job_id=job_id,
                query=query,
                format=format,
                user=user,
                country_breakdown=country_breakdown,
            )

            logger.info(f"Scheduled background task for export job {job_id}")

            return export_job

        except Exception as e:
            logger.error(
                f"Database error creating async supplier summary export job: {str(e)}"
            )
            # Rollback transaction if needed
            try:
                self.db.rollback()
            except:
                pass
            raise Exception(f"Failed to create export job: {str(e)}")

    def process_async_supplier_summary_export(
        self,
        job_id: str,
        query: Query,
        format: ExportFormat,
        user: User,
        country_breakdown: dict = None,
    ) -> None:
        """
        Background task to process asynchronous supplier summary export.

        Args:
            job_id: Unique export job ID
            query: SQLAlchemy Query object for supplier summary
            format: Export format (CSV, JSON, EXCEL)
            user: User object who requested the export
            country_breakdown: Optional country breakdown data
        """
        logger.info(f"Processing async supplier summary export job {job_id}")

        # Create new database session for background task
        from database import SessionLocal

        db = SessionLocal()

        try:
            # Get export job
            export_job = db.query(ExportJob).filter(ExportJob.id == job_id).first()
            if not export_job:
                logger.error(f"Export job {job_id} not found")
                return

            # Update status to processing
            export_job.status = "processing"
            export_job.started_at = datetime.utcnow()
            db.commit()

            logger.info(f"Export job {job_id} status updated to processing")

            # Generate file path using storage manager
            timestamp = datetime.utcnow()
            output_path = self.file_storage.get_file_path(
                job_id=job_id,
                export_type="supplier_summary",
                format=format.value,
                timestamp=timestamp,
                user_id=user.id,
            )

            logger.debug(f"Export file path: {output_path}")

            # Create metadata
            metadata = ExportMetadata(
                export_id=job_id,
                generated_at=timestamp,
                generated_by=user.username,
                user_id=user.id,
                filters_applied=export_job.filters or {},
                total_records=export_job.total_records or 0,
                format=format.value,
                version="1.0",
            )

            # Process export with progress tracking
            total_records = export_job.total_records or 0
            processed_records = 0
            last_progress_update = 0

            # Create a generator that tracks progress
            def progress_tracking_generator():
                nonlocal processed_records, last_progress_update

                for batch in self.stream_query_results(query, self.batch_size, job_id=job_id, db_session=db):
                    processed_records += len(batch)

                    # Update progress more frequently (every 1% or every batch if small dataset)
                    if total_records > 0:
                        progress = min(int((processed_records / total_records) * 100), 99)

                        # Update if progress changed by at least 1%
                        if progress > last_progress_update:
                            export_job.progress_percentage = progress
                            export_job.processed_records = processed_records
                            db.commit()
                            last_progress_update = progress
                            logger.info(f"[EXPORT] Job {job_id} progress: {progress}% ({processed_records}/{total_records} records)")

                    yield batch

            # Generate file based on format
            if format == ExportFormat.CSV:
                headers = [
                    "provider_name",
                    "total_hotels",
                    "total_mappings",
                    "last_updated",
                    "summary_generated_at",
                ]

                output_path = self.format_handler.to_csv(
                    data=progress_tracking_generator(),
                    output_path=output_path,
                    headers=headers,
                )

            elif format == ExportFormat.JSON:
                output_path = self.format_handler.to_json(
                    data=progress_tracking_generator(),
                    output_path=output_path,
                    metadata=metadata,
                    preserve_structure=True,
                )

            elif format == ExportFormat.EXCEL:
                output_path = self.format_handler.to_excel(
                    data={"Supplier Summary": progress_tracking_generator()},
                    output_path=output_path,
                    metadata=metadata,
                )

            else:
                raise ValueError(f"Unsupported export format: {format}")

            # Set file permissions for security
            self.file_storage.set_file_permissions(output_path)

            # Get file size
            file_size = self.file_storage.get_file_size(output_path)

            # Update job as completed
            export_job.status = "completed"
            export_job.progress_percentage = 100
            export_job.processed_records = processed_records
            export_job.file_path = output_path
            export_job.file_size_bytes = file_size
            export_job.completed_at = datetime.utcnow()
            export_job.expires_at = datetime.utcnow() + timedelta(hours=24)
            db.commit()

            logger.info(
                f"Export job {job_id} completed successfully: {file_size} bytes, {processed_records} records"
            )

            # Log export completion
            audit_logger = AuditLogger(db)
            audit_logger.log_activity(
                activity_type=ActivityType.EXPORT_DATA,
                user_id=user.id,
                details={
                    "export_type": "supplier_summary",
                    "format": format.value,
                    "job_id": job_id,
                    "record_count": processed_records,
                    "file_size_bytes": file_size,
                    "sync": False,
                    "status": "completed",
                },
                request=None,
                security_level=SecurityLevel.HIGH,
                success=True,
            )

        except Exception as e:
            logger.error(
                f"Error processing async supplier summary export job {job_id}: {str(e)}"
            )

            # Update job as failed
            try:
                export_job = db.query(ExportJob).filter(ExportJob.id == job_id).first()
                if export_job:
                    export_job.status = "failed"
                    export_job.error_message = str(e)
                    export_job.completed_at = datetime.utcnow()
                    db.commit()
                    logger.info(f"Export job {job_id} marked as failed")

                    # Log export failure
                    audit_logger = AuditLogger(db)
                    audit_logger.log_activity(
                        activity_type=ActivityType.EXPORT_DATA,
                        user_id=user.id,
                        details={
                            "export_type": "supplier_summary",
                            "format": format.value,
                            "job_id": job_id,
                            "error": str(e),
                            "sync": False,
                            "status": "failed",
                        },
                        request=None,
                        security_level=SecurityLevel.HIGH,
                        success=False,
                    )
            except Exception as update_error:
                logger.error(f"Error updating failed job status: {str(update_error)}")

        finally:
            # Close database session
            db.close()
