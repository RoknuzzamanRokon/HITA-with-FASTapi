"""
Export Worker Service

Dedicated worker for processing export jobs in complete isolation from the main API.
Uses a separate database connection pool and thread pool to ensure no impact on other endpoints.

Features:
- Separate database connection pool for exports
- Thread pool executor for parallel processing
- Resource limits and throttling
- Automatic cleanup of old export files
- Health monitoring
"""

import os
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

from models import ExportJob
from export_schemas import ExportFormat
from services.export_engine import ExportEngine
from services.notification_service import NotificationService

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)


class ExportWorker:
    """
    Dedicated worker for processing export jobs in isolation.

    Uses separate resources to ensure no impact on main API:
    - Separate database connection pool
    - Dedicated thread pool executor
    - Resource limits and throttling
    """

    def __init__(self, max_workers: int = 3, pool_size: int = 3, max_overflow: int = 5):
        """
        Initialize export worker with dedicated resources.

        Args:
            max_workers: Maximum concurrent export jobs (default: 3)
            pool_size: Database connection pool size (default: 3)
            max_overflow: Additional database connections (default: 5)
        """
        self.max_workers = max_workers

        # Create separate database engine for exports
        DATABASE_URL = os.getenv("DB_CONNECTION")

        # Configure engine with better concurrency settings
        connect_args = {}
        if "sqlite" in DATABASE_URL.lower():
            # SQLite-specific optimizations for better concurrency
            connect_args = {
                "check_same_thread": False,
                "timeout": 30,  # Increase timeout for lock waits
            }

        self.export_engine = create_engine(
            DATABASE_URL,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=60,
            pool_recycle=3600,
            pool_pre_ping=True,
            echo=False,
            connect_args=connect_args,
            isolation_level="READ UNCOMMITTED",  # Allow dirty reads to reduce locking
        )

        # Enable WAL mode for SQLite to allow concurrent reads during writes
        if "sqlite" in DATABASE_URL.lower():
            from sqlalchemy import event

            @event.listens_for(self.export_engine, "connect")
            def set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")  # Faster writes
                cursor.execute("PRAGMA busy_timeout=30000")  # 30 second timeout
                cursor.close()

            logger.info("SQLite WAL mode enabled for export worker")

        # Create session factory
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.export_engine
        )

        # Create thread pool executor
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="export_worker"
        )

        # Track active jobs and cancellation flags
        self.active_jobs = {}
        self.cancelled_jobs = set()  # Set of job_ids that should be cancelled
        self.lock = threading.Lock()

        # Get export storage path
        self.storage_path = os.getenv(
            "EXPORT_STORAGE_PATH", os.path.join(os.getcwd(), "exports")
        )

        logger.info(
            f"ExportWorker initialized: max_workers={max_workers}, "
            f"pool_size={pool_size}, storage_path={self.storage_path}"
        )

    def submit_export_job(
        self,
        job_id: str,
        export_type: str,
        query_params: dict,
        format: ExportFormat,
        user_data: dict,
        filters_applied: dict = None,
        **kwargs,
    ) -> bool:
        """
        Submit an export job to the worker queue.

        Args:
            job_id: Unique export job ID
            export_type: Type of export (hotels, mappings, supplier_summary)
            query_params: Parameters to rebuild the query
            format: Export format
            user_data: User information (id, username)
            filters_applied: Filters applied to the query
            **kwargs: Additional export-specific parameters

        Returns:
            True if job was submitted successfully, False otherwise
        """
        with self.lock:
            # Check if we're at capacity
            if len(self.active_jobs) >= self.max_workers:
                logger.warning(
                    f"Export worker at capacity ({self.max_workers} jobs). "
                    f"Job {job_id} will be queued."
                )

            # Submit job to executor
            future = self.executor.submit(
                self._process_export_job,
                job_id=job_id,
                export_type=export_type,
                query_params=query_params,
                format=format,
                user_data=user_data,
                filters_applied=filters_applied,
                **kwargs,
            )

            self.active_jobs[job_id] = {
                "future": future,
                "submitted_at": datetime.utcnow(),
                "export_type": export_type,
            }

            # Add callback to remove from active jobs when done
            future.add_done_callback(lambda f: self._job_completed(job_id))

            logger.info(
                f"Export job {job_id} submitted to worker. "
                f"Active jobs: {len(self.active_jobs)}"
            )

            return True

    def _job_completed(self, job_id: str):
        """Callback when a job completes."""
        with self.lock:
            if job_id in self.active_jobs:
                job_info = self.active_jobs.pop(job_id)
                duration = (
                    datetime.utcnow() - job_info["submitted_at"]
                ).total_seconds()
                logger.info(
                    f"Export job {job_id} completed. "
                    f"Duration: {duration:.2f}s. "
                    f"Active jobs: {len(self.active_jobs)}"
                )

    def _process_export_job(
        self,
        job_id: str,
        export_type: str,
        query_params: dict,
        format: ExportFormat,
        user_data: dict,
        filters_applied: dict = None,
        **kwargs,
    ):
        """
        Process an export job in a worker thread.

        This runs in a separate thread with its own database session,
        completely isolated from the main API.
        """
        logger.info(f"Worker processing export job {job_id} (type: {export_type})")

        # Create dedicated database session for this job
        db = self.SessionLocal()

        try:
            # Get export job from database
            export_job = db.query(ExportJob).filter(ExportJob.id == job_id).first()

            if not export_job:
                logger.error(f"Export job {job_id} not found in database")
                return

            # Update status to processing
            export_job.status = "processing"
            export_job.started_at = datetime.utcnow()
            db.commit()

            logger.info(f"Export job {job_id} status updated to processing")

            # Create export engine with dedicated session
            export_engine = ExportEngine(db, self.storage_path)

            # Rebuild query based on export type and parameters
            query = self._rebuild_query(
                db=db, export_type=export_type, query_params=query_params
            )

            # Create user object from user_data
            from models import User

            user = User(id=user_data["id"], username=user_data["username"])

            # Process based on export type
            if export_type == "hotels":
                self._process_hotel_export(
                    export_engine=export_engine,
                    export_job=export_job,
                    query=query,
                    format=format,
                    user=user,
                    db=db,
                    **kwargs,
                )

            elif export_type == "mappings":
                self._process_mapping_export(
                    export_engine=export_engine,
                    export_job=export_job,
                    query=query,
                    format=format,
                    user=user,
                    db=db,
                )

            elif export_type == "supplier_summary":
                # Extract country_breakdown from query_params
                include_country_breakdown = query_params.get("filters", {}).get(
                    "include_country_breakdown", False
                )

                self._process_supplier_summary_export(
                    export_engine=export_engine,
                    export_job=export_job,
                    query=query,
                    format=format,
                    user=user,
                    db=db,
                    include_country_breakdown=include_country_breakdown,
                    **kwargs,
                )

            else:
                raise ValueError(f"Unknown export type: {export_type}")

            logger.info(f"Export job {job_id} completed successfully")

        except Exception as e:
            logger.error(f"Error processing export job {job_id}: {str(e)}")

            # Update job as failed
            try:
                export_job = db.query(ExportJob).filter(ExportJob.id == job_id).first()

                if export_job:
                    export_job.status = "failed"
                    export_job.error_message = str(e)
                    export_job.completed_at = datetime.utcnow()
                    db.commit()
                    logger.info(f"Export job {job_id} marked as failed")

            except Exception as update_error:
                logger.error(f"Error updating failed job status: {str(update_error)}")

        finally:
            # Always close the database session
            db.close()

    def _rebuild_query(self, db: Session, export_type: str, query_params: dict):
        """
        Rebuild the query from stored parameters.

        This is necessary because SQLAlchemy Query objects cannot be
        passed between threads/processes.
        """
        from services.export_filter_service import ExportFilterService

        filter_service = ExportFilterService(db)

        if export_type == "hotels":
            # Rebuild hotel query
            from export_schemas import HotelExportFilters

            filters = HotelExportFilters(**query_params.get("filters", {}))

            query = filter_service.build_hotel_query(
                filters=filters,
                allowed_suppliers=query_params.get("allowed_suppliers"),
                include_locations=query_params.get("include_locations", True),
                include_contacts=query_params.get("include_contacts", True),
                include_mappings=query_params.get("include_mappings", True),
            )

        elif export_type == "mappings":
            # Rebuild mapping query
            from export_schemas import MappingExportFilters

            filter_params = query_params.get("filters", {})
            logger.info(
                f"[WORKER] Rebuilding mapping filters with params: {filter_params}"
            )
            logger.info(
                f"[WORKER] max_records value: {filter_params.get('max_records')}, type: {type(filter_params.get('max_records'))}"
            )

            filters = MappingExportFilters(**filter_params)
            logger.info(
                f"[WORKER] Filters rebuilt - max_records: {filters.max_records}, type: {type(filters.max_records)}"
            )

            query = filter_service.build_mapping_query(
                filters=filters, allowed_suppliers=query_params.get("allowed_suppliers")
            )

        elif export_type == "supplier_summary":
            # Rebuild supplier summary query
            from export_schemas import SupplierSummaryFilters

            filters = SupplierSummaryFilters(**query_params.get("filters", {}))

            query = filter_service.build_supplier_summary_query(
                filters=filters, allowed_suppliers=query_params.get("allowed_suppliers")
            )

        else:
            raise ValueError(f"Unknown export type: {export_type}")

        return query

    def _process_hotel_export(
        self,
        export_engine: ExportEngine,
        export_job: ExportJob,
        query,
        format: ExportFormat,
        user,
        db: Session,
        **kwargs,
    ):
        """Process hotel export with progress tracking."""
        include_locations = kwargs.get("include_locations", True)
        include_contacts = kwargs.get("include_contacts", True)
        include_mappings = kwargs.get("include_mappings", True)

        export_engine.process_async_hotel_export(
            job_id=export_job.id,
            query=query,
            format=format,
            user=user,
            include_locations=include_locations,
            include_contacts=include_contacts,
            include_mappings=include_mappings,
        )

    def _process_mapping_export(
        self,
        export_engine: ExportEngine,
        export_job: ExportJob,
        query,
        format: ExportFormat,
        user,
        db: Session,
    ):
        """Process mapping export with progress tracking."""
        export_engine.process_async_mapping_export(
            job_id=export_job.id, query=query, format=format, user=user
        )

    def _process_supplier_summary_export(
        self,
        export_engine: ExportEngine,
        export_job: ExportJob,
        query,
        format: ExportFormat,
        user,
        db: Session,
        include_country_breakdown: bool = False,
        **kwargs,
    ):
        """Process supplier summary export with progress tracking."""
        # The export_engine expects country_breakdown as a dict or None
        # If include_country_breakdown is True, pass an empty dict to trigger breakdown
        country_breakdown = {} if include_country_breakdown else None

        export_engine.process_async_supplier_summary_export(
            job_id=export_job.id,
            query=query,
            format=format,
            user=user,
            country_breakdown=country_breakdown,
        )

    def get_worker_status(self) -> dict:
        """Get current worker status."""
        with self.lock:
            return {
                "max_workers": self.max_workers,
                "active_jobs": len(self.active_jobs),
                "available_slots": self.max_workers - len(self.active_jobs),
                "jobs": [
                    {
                        "job_id": job_id,
                        "export_type": info["export_type"],
                        "submitted_at": info["submitted_at"].isoformat(),
                    }
                    for job_id, info in self.active_jobs.items()
                ],
            }

    def cleanup_old_exports(self, max_age_hours: int = 24):
        """
        Clean up export files older than specified age.

        Args:
            max_age_hours: Maximum age of export files in hours
        """
        logger.info(f"Starting cleanup of exports older than {max_age_hours} hours")

        db = self.SessionLocal()
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

            # Find expired export jobs
            expired_jobs = (
                db.query(ExportJob)
                .filter(
                    ExportJob.completed_at < cutoff_time,
                    ExportJob.status == "completed",
                )
                .all()
            )

            cleaned_count = 0
            for job in expired_jobs:
                if job.file_path and os.path.exists(job.file_path):
                    try:
                        os.remove(job.file_path)
                        logger.debug(f"Deleted expired export file: {job.file_path}")
                        cleaned_count += 1
                    except Exception as e:
                        logger.error(f"Error deleting file {job.file_path}: {str(e)}")

            logger.info(f"Cleanup completed: {cleaned_count} files deleted")

        except Exception as e:
            logger.error(f"Error during export cleanup: {str(e)}")

        finally:
            db.close()

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel an active export job.

        Args:
            job_id: The job ID to cancel

        Returns:
            True if job was marked for cancellation, False if not found
        """
        with self.lock:
            if job_id in self.active_jobs:
                self.cancelled_jobs.add(job_id)
                logger.info(f"Job {job_id} marked for cancellation")
                return True
            else:
                logger.warning(f"Job {job_id} not found in active jobs")
                return False

    def is_cancelled(self, job_id: str) -> bool:
        """Check if a job has been cancelled."""
        with self.lock:
            return job_id in self.cancelled_jobs

    def shutdown(self):
        """Gracefully shutdown the worker."""
        logger.info("Shutting down export worker...")

        # Wait for active jobs to complete
        self.executor.shutdown(wait=True)

        # Dispose database engine
        self.export_engine.dispose()

        logger.info("Export worker shutdown complete")


# Global worker instance
_export_worker: Optional[ExportWorker] = None


def get_export_worker() -> ExportWorker:
    """Get or create the global export worker instance."""
    global _export_worker

    if _export_worker is None:
        # Create worker with configuration from environment
        max_workers = int(os.getenv("EXPORT_MAX_WORKERS", "3"))
        pool_size = int(os.getenv("EXPORT_POOL_SIZE", "3"))
        max_overflow = int(os.getenv("EXPORT_MAX_OVERFLOW", "5"))

        _export_worker = ExportWorker(
            max_workers=max_workers, pool_size=pool_size, max_overflow=max_overflow
        )

    return _export_worker


def shutdown_export_worker():
    """Shutdown the global export worker."""
    global _export_worker

    if _export_worker is not None:
        _export_worker.shutdown()
        _export_worker = None
