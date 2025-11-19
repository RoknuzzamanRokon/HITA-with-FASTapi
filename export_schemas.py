from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum


# --- Export Format Enum ---
class ExportFormat(str, Enum):
    """Supported export file formats"""
    CSV = "csv"
    JSON = "json"
    EXCEL = "excel"


# --- Export Filter Schemas ---
class HotelExportFilters(BaseModel):
    """Filters for hotel data export"""
    suppliers: Optional[Union[List[str], str]] = Field(None, description="List of supplier names to filter by, or 'All' for all permitted suppliers")
    country_codes: Optional[Union[List[str], str]] = Field(None, description="List of ISO country codes (e.g., ['US', 'GB']), or 'All' for all countries")
    min_rating: Optional[float] = Field(None, ge=0, le=5, description="Minimum hotel rating (0-5)")
    max_rating: Optional[float] = Field(None, ge=0, le=5, description="Maximum hotel rating (0-5)")
    date_from: Optional[datetime] = Field(None, description="Filter hotels updated after this date")
    date_to: Optional[datetime] = Field(None, description="Filter hotels updated before this date")
    ittids: Optional[Union[List[str], str]] = Field(None, description="List of specific ITTIDs to export, or 'All' for all hotels")
    property_types: Optional[Union[List[str], str]] = Field(None, description="List of property types (e.g., ['Hotel', 'Resort']), or 'All' for all property types")
    page: int = Field(1, ge=1, description="Page number for pagination")
    page_size: int = Field(1000, ge=1, le=10000, description="Number of records per page")
    max_records: Optional[Union[int, str]] = Field(None, description="Maximum number of records to export (1-100,000), or 'All' to export all records")

    @validator("suppliers")
    def validate_suppliers(cls, v):
        """Validate supplier list is not empty if provided, or accept 'All' keyword"""
        if v is not None:
            # Accept "All" as a special keyword
            if isinstance(v, str):
                if v.lower() != "all":
                    raise ValueError("suppliers must be a list of supplier names or the keyword 'All'")
                return v
            # If it's a list, ensure it's not empty
            elif isinstance(v, list) and len(v) == 0:
                raise ValueError("suppliers list cannot be empty if provided")
        return v

    @validator("country_codes")
    def validate_country_codes(cls, v):
        """Validate country codes are uppercase 2-letter codes, or accept 'All' keyword"""
        if v is not None:
            # Accept "All" as a special keyword
            if isinstance(v, str):
                if v.lower() != "all":
                    raise ValueError("country_codes must be a list of ISO codes or the keyword 'All'")
                return v
            # If it's a list, validate each code
            elif isinstance(v, list):
                if len(v) == 0:
                    raise ValueError("country_codes list cannot be empty if provided")
                for code in v:
                    if not code or len(code) != 2 or not code.isupper():
                        raise ValueError(f"Invalid country code '{code}'. Must be 2-letter uppercase ISO code (e.g., 'US', 'GB')")
        return v

    @validator("min_rating")
    def validate_min_rating(cls, v):
        """Validate minimum rating is within valid range"""
        if v is not None and (v < 0 or v > 5):
            raise ValueError("min_rating must be between 0 and 5")
        return v

    @validator("max_rating")
    def validate_rating_range(cls, v, values):
        """Ensure max_rating is greater than min_rating and within valid range"""
        if v is not None:
            if v < 0 or v > 5:
                raise ValueError("max_rating must be between 0 and 5")
            if "min_rating" in values and values["min_rating"] is not None:
                if v < values["min_rating"]:
                    raise ValueError("max_rating must be greater than or equal to min_rating")
        return v

    @validator("date_from")
    def validate_date_from(cls, v):
        """Validate date_from is not in the future"""
        if v is not None and v > datetime.utcnow():
            raise ValueError("date_from cannot be in the future")
        return v

    @validator("date_to")
    def validate_date_range(cls, v, values):
        """Ensure date_to is after date_from and not in the future"""
        if v is not None:
            if v > datetime.utcnow():
                raise ValueError("date_to cannot be in the future")
            if "date_from" in values and values["date_from"] is not None:
                if v < values["date_from"]:
                    raise ValueError("date_to must be after date_from")
        return v

    @validator("ittids")
    def validate_ittids(cls, v):
        """Validate ITTID list is not empty if provided, or accept 'All' keyword"""
        if v is not None:
            # Accept "All" as a special keyword
            if isinstance(v, str):
                if v.lower() != "all":
                    raise ValueError("ittids must be a list of ITTIDs or the keyword 'All'")
                return v
            # If it's a list, ensure it's not empty
            elif isinstance(v, list) and len(v) == 0:
                raise ValueError("ittids list cannot be empty if provided")
        return v

    @validator("property_types")
    def validate_property_types(cls, v):
        """Validate property types list is not empty if provided, or accept 'All' keyword"""
        if v is not None:
            # Accept "All" as a special keyword
            if isinstance(v, str):
                if v.lower() != "all":
                    raise ValueError("property_types must be a list of property types or the keyword 'All'")
                return v
            # If it's a list, ensure it's not empty
            elif isinstance(v, list) and len(v) == 0:
                raise ValueError("property_types list cannot be empty if provided")
        return v

    @validator("page_size")
    def validate_page_size(cls, v):
        """Validate page size is reasonable"""
        if v > 10000:
            raise ValueError("page_size cannot exceed 10,000 records per page")
        return v

    @validator("max_records")
    def validate_max_records(cls, v):
        """Validate max_records is either a valid integer or 'All' keyword"""
        if v is not None:
            # Accept "All" as a special keyword
            if isinstance(v, str):
                if v.lower() != "all":
                    raise ValueError("max_records must be an integer (1-100,000) or the keyword 'All'")
                return v
            # If it's an integer, validate the range
            elif isinstance(v, int):
                if v < 1 or v > 100000:
                    raise ValueError("max_records must be between 1 and 100,000")
        return v


class MappingExportFilters(BaseModel):
    """Filters for provider mapping export"""
    suppliers: Optional[Union[List[str], str]] = Field(None, description="List of supplier names to filter by, or 'All' for all permitted suppliers")
    ittids: Optional[Union[List[str], str]] = Field(None, description="List of specific ITTIDs to export mappings for, or 'All' for all mappings")
    date_from: Optional[datetime] = Field(None, description="Filter mappings created/updated after this date")
    date_to: Optional[datetime] = Field(None, description="Filter mappings created/updated before this date")
    max_records: Optional[Union[int, str]] = Field(None, description="Maximum number of records to export (1-100,000), or 'All' to export all records")

    @validator("suppliers")
    def validate_suppliers(cls, v):
        """Validate supplier list is not empty if provided, or accept 'All' keyword"""
        if v is not None:
            # Accept "All" as a special keyword
            if isinstance(v, str):
                if v.lower() != "all":
                    raise ValueError("suppliers must be a list of supplier names or the keyword 'All'")
                return v
            # If it's a list, ensure it's not empty
            elif isinstance(v, list) and len(v) == 0:
                raise ValueError("suppliers list cannot be empty if provided")
        return v

    @validator("ittids")
    def validate_ittids(cls, v):
        """Validate ITTID list is not empty if provided, or accept 'All' keyword"""
        if v is not None:
            # Accept "All" as a special keyword
            if isinstance(v, str):
                if v.lower() != "all":
                    raise ValueError("ittids must be a list of ITTIDs or the keyword 'All'")
                return v
            # If it's a list, ensure it's not empty
            elif isinstance(v, list) and len(v) == 0:
                raise ValueError("ittids list cannot be empty if provided")
        return v

    @validator("date_from")
    def validate_date_from(cls, v):
        """Validate date_from is not in the future"""
        if v is not None and v > datetime.utcnow():
            raise ValueError("date_from cannot be in the future")
        return v

    @validator("date_to")
    def validate_date_range(cls, v, values):
        """Ensure date_to is after date_from and not in the future"""
        if v is not None:
            if v > datetime.utcnow():
                raise ValueError("date_to cannot be in the future")
            if "date_from" in values and values["date_from"] is not None:
                if v < values["date_from"]:
                    raise ValueError("date_to must be after date_from")
        return v

    @validator("max_records")
    def validate_max_records(cls, v):
        """Validate max_records is either a valid integer or 'All' keyword"""
        if v is not None:
            # Accept "All" as a special keyword
            if isinstance(v, str):
                if v.lower() != "all":
                    raise ValueError("max_records must be an integer (1-100,000) or the keyword 'All'")
                return v
            # If it's an integer, validate the range
            elif isinstance(v, int):
                if v < 1 or v > 100000:
                    raise ValueError("max_records must be between 1 and 100,000")
        return v


class SupplierSummaryFilters(BaseModel):
    """Filters for supplier summary statistics export"""
    suppliers: Optional[Union[List[str], str]] = Field(None, description="List of supplier names to include in summary, or 'All' for all permitted suppliers")
    include_country_breakdown: bool = Field(False, description="Include hotel counts by country per supplier")

    @validator("suppliers")
    def validate_suppliers(cls, v):
        """Validate supplier list is not empty if provided, or accept 'All' keyword"""
        if v is not None:
            # Accept "All" as a special keyword
            if isinstance(v, str):
                if v.lower() != "all":
                    raise ValueError("suppliers must be a list of supplier names or the keyword 'All'")
                return v
            # If it's a list, ensure it's not empty
            elif isinstance(v, list) and len(v) == 0:
                raise ValueError("suppliers list cannot be empty if provided")
        return v


# --- Export Request Schemas ---
class ExportHotelsRequest(BaseModel):
    """Request schema for hotel data export"""
    filters: HotelExportFilters = Field(..., description="Filters to apply to hotel export")
    format: ExportFormat = Field(..., description="Export file format (csv, json, or excel)")
    include_locations: bool = Field(True, description="Include location data in export")
    include_contacts: bool = Field(True, description="Include contact information in export")
    include_mappings: bool = Field(True, description="Include provider mappings in export")

    @validator("format")
    def validate_format(cls, v):
        """Ensure format is valid"""
        if v not in [ExportFormat.CSV, ExportFormat.JSON, ExportFormat.EXCEL]:
            raise ValueError(f"Invalid format. Must be one of: {', '.join([f.value for f in ExportFormat])}")
        return v


class ExportMappingsRequest(BaseModel):
    """Request schema for provider mapping export"""
    filters: MappingExportFilters = Field(..., description="Filters to apply to mapping export")
    format: ExportFormat = Field(..., description="Export file format (csv, json, or excel)")

    @validator("format")
    def validate_format(cls, v):
        """Ensure format is valid"""
        if v not in [ExportFormat.CSV, ExportFormat.JSON, ExportFormat.EXCEL]:
            raise ValueError(f"Invalid format. Must be one of: {', '.join([f.value for f in ExportFormat])}")
        return v


class ExportSupplierSummaryRequest(BaseModel):
    """Request schema for supplier summary export"""
    filters: SupplierSummaryFilters = Field(..., description="Filters to apply to supplier summary export")
    format: ExportFormat = Field(..., description="Export file format (csv, json, or excel)")

    @validator("format")
    def validate_format(cls, v):
        """Ensure format is valid"""
        if v not in [ExportFormat.CSV, ExportFormat.JSON, ExportFormat.EXCEL]:
            raise ValueError(f"Invalid format. Must be one of: {', '.join([f.value for f in ExportFormat])}")
        return v


# --- Export Response Schemas ---
class ExportJobResponse(BaseModel):
    """Response schema for asynchronous export job creation"""
    job_id: str = Field(..., description="Unique identifier for the export job")
    status: str = Field(..., description="Current job status (pending, processing, completed, failed)")
    estimated_records: Union[int, str] = Field(..., description="Estimated number of records to be exported, or 'All' for unlimited")
    estimated_completion_time: str = Field(..., description="Estimated time to completion (e.g., '2 minutes')")
    created_at: datetime = Field(..., description="Timestamp when the job was created")
    message: str = Field(..., description="Human-readable message about the export job")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "exp_1234567890abcdef",
                "status": "pending",
                "estimated_records": 15000,
                "estimated_completion_time": "2 minutes",
                "created_at": "2024-11-16T10:30:00",
                "message": "Export job created successfully. Use the job_id to check status and download when complete."
            }
        }


class ExportJobStatusResponse(BaseModel):
    """Response schema for export job status check"""
    job_id: str = Field(..., description="Unique identifier for the export job")
    status: str = Field(..., description="Current job status (pending, processing, completed, failed)")
    progress_percentage: int = Field(..., ge=0, le=100, description="Progress percentage (0-100)")
    processed_records: int = Field(..., description="Number of records processed so far")
    total_records: int = Field(..., description="Total number of records to process")
    created_at: datetime = Field(..., description="Timestamp when the job was created")
    started_at: Optional[datetime] = Field(None, description="Timestamp when processing started")
    completed_at: Optional[datetime] = Field(None, description="Timestamp when processing completed")
    error_message: Optional[str] = Field(None, description="Error message if job failed")
    download_url: Optional[str] = Field(None, description="Download URL if job is completed")
    expires_at: Optional[datetime] = Field(None, description="Timestamp when the export file will expire")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "exp_1234567890abcdef",
                "status": "processing",
                "progress_percentage": 45,
                "processed_records": 6750,
                "total_records": 15000,
                "created_at": "2024-11-16T10:30:00",
                "started_at": "2024-11-16T10:30:15",
                "completed_at": None,
                "error_message": None,
                "download_url": None,
                "expires_at": None
            }
        }


class ExportMetadata(BaseModel):
    """Metadata included in export files"""
    export_id: str = Field(..., description="Unique identifier for this export")
    generated_at: datetime = Field(..., description="Timestamp when export was generated")
    generated_by: str = Field(..., description="Username of the user who generated the export")
    user_id: str = Field(..., description="User ID of the user who generated the export")
    filters_applied: Dict[str, Any] = Field(..., description="Filters that were applied to this export")
    total_records: int = Field(..., description="Total number of records in the export")
    format: str = Field(..., description="Export file format")
    version: str = Field(default="1.0", description="Export schema version")

    class Config:
        json_schema_extra = {
            "example": {
                "export_id": "exp_1234567890abcdef",
                "generated_at": "2024-11-16T10:35:00",
                "generated_by": "john_doe",
                "user_id": "abc1234567",
                "filters_applied": {
                    "suppliers": ["Agoda", "Booking"],
                    "country_codes": ["US", "GB"],
                    "min_rating": 3.0
                },
                "total_records": 15000,
                "format": "csv",
                "version": "1.0"
            }
        }


# --- Export Error Response Schema ---
class ExportErrorResponse(BaseModel):
    """Error response schema for export operations"""
    error: bool = Field(True, description="Always true for error responses")
    message: str = Field(..., description="Human-readable error message")
    error_code: str = Field(..., description="Machine-readable error code")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when error occurred")

    class Config:
        json_schema_extra = {
            "example": {
                "error": True,
                "message": "You do not have permission to export data for the requested suppliers",
                "error_code": "INSUFFICIENT_PERMISSIONS",
                "details": {
                    "requested_suppliers": ["Agoda", "Booking", "EAN"],
                    "allowed_suppliers": ["Agoda"],
                    "denied_suppliers": ["Booking", "EAN"]
                },
                "timestamp": "2024-11-16T10:30:00"
            }
        }


# --- Export Job Management Schemas ---
class ExportJobSummary(BaseModel):
    """Summary information for a single export job"""
    job_id: str = Field(..., description="Unique identifier for the export job")
    export_type: str = Field(..., description="Type of export (hotels, mappings, supplier_summary)")
    format: str = Field(..., description="Export file format (csv, json, excel)")
    status: str = Field(..., description="Current job status")
    progress_percentage: int = Field(..., ge=0, le=100, description="Progress percentage")
    processed_records: int = Field(..., description="Number of records processed")
    total_records: Optional[int] = Field(None, description="Total number of records")
    created_at: datetime = Field(..., description="When job was created")
    completed_at: Optional[datetime] = Field(None, description="When job completed")
    download_url: Optional[str] = Field(None, description="Download URL if completed")
    expires_at: Optional[datetime] = Field(None, description="When export file expires")
    file_size_bytes: Optional[int] = Field(None, description="File size in bytes")

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "exp_1234567890abcdef",
                "export_type": "hotels",
                "format": "csv",
                "status": "completed",
                "progress_percentage": 100,
                "processed_records": 15000,
                "total_records": 15000,
                "created_at": "2024-11-16T10:30:00",
                "completed_at": "2024-11-16T10:35:00",
                "download_url": "/v1.0/export/download/exp_1234567890abcdef",
                "expires_at": "2024-11-17T10:35:00",
                "file_size_bytes": 2048576
            }
        }


class ExportJobListResponse(BaseModel):
    """Response schema for listing export jobs"""
    jobs: List[ExportJobSummary] = Field(..., description="List of export jobs")
    total: int = Field(..., description="Total number of jobs matching filters")
    limit: int = Field(..., description="Number of jobs per page")
    offset: int = Field(..., description="Pagination offset")

    class Config:
        json_schema_extra = {
            "example": {
                "jobs": [
                    {
                        "job_id": "exp_1234567890abcdef",
                        "export_type": "hotels",
                        "format": "csv",
                        "status": "completed",
                        "progress_percentage": 100,
                        "processed_records": 15000,
                        "total_records": 15000,
                        "created_at": "2024-11-16T10:30:00",
                        "completed_at": "2024-11-16T10:35:00",
                        "download_url": "/v1.0/export/download/exp_1234567890abcdef",
                        "expires_at": "2024-11-17T10:35:00",
                        "file_size_bytes": 2048576
                    }
                ],
                "total": 1,
                "limit": 100,
                "offset": 0
            }
        }


class ExportJobDetailResponse(BaseModel):
    """Detailed response for a single export job"""
    job_id: str = Field(..., description="Unique identifier for the export job")
    user_id: str = Field(..., description="User who created the job")
    export_type: str = Field(..., description="Type of export")
    format: str = Field(..., description="Export file format")
    filters: Optional[Dict[str, Any]] = Field(None, description="Filters applied to export")
    status: str = Field(..., description="Current job status")
    progress_percentage: int = Field(..., ge=0, le=100, description="Progress percentage")
    processed_records: int = Field(..., description="Number of records processed")
    total_records: Optional[int] = Field(None, description="Total number of records")
    file_path: Optional[str] = Field(None, description="Server file path")
    file_size_bytes: Optional[int] = Field(None, description="File size in bytes")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    created_at: datetime = Field(..., description="When job was created")
    started_at: Optional[datetime] = Field(None, description="When processing started")
    completed_at: Optional[datetime] = Field(None, description="When job completed")
    expires_at: Optional[datetime] = Field(None, description="When export file expires")
    download_url: Optional[str] = Field(None, description="Download URL if completed")


class ExportJobDeleteResponse(BaseModel):
    """Response for deleting an export job"""
    success: bool = Field(..., description="Whether deletion was successful")
    message: str = Field(..., description="Human-readable message")
    job_id: str = Field(..., description="ID of deleted job")


class ExportJobsClearResponse(BaseModel):
    """Response for clearing multiple export jobs"""
    success: bool = Field(..., description="Whether operation was successful")
    message: str = Field(..., description="Human-readable message")
    deleted_count: int = Field(..., description="Number of jobs deleted")
    deleted_job_ids: List[str] = Field(..., description="IDs of deleted jobs")


class ExportJobStatusUpdateRequest(BaseModel):
    """Request to update export job status (internal use)"""
    status: str = Field(..., description="New status")
    progress_percentage: Optional[int] = Field(None, ge=0, le=100)
    processed_records: Optional[int] = Field(None)
    total_records: Optional[int] = Field(None)
    error_message: Optional[str] = Field(None)


class ExportJobStatusUpdateResponse(BaseModel):
    """Response for status update"""
    success: bool = Field(..., description="Whether update was successful")
    message: str = Field(..., description="Human-readable message")
    job_id: str = Field(..., description="ID of updated job")


# Rebuild forward references
HotelExportFilters.model_rebuild()
MappingExportFilters.model_rebuild()
SupplierSummaryFilters.model_rebuild()
ExportHotelsRequest.model_rebuild()
ExportMappingsRequest.model_rebuild()
ExportSupplierSummaryRequest.model_rebuild()
ExportJobResponse.model_rebuild()
ExportJobStatusResponse.model_rebuild()
ExportMetadata.model_rebuild()
ExportErrorResponse.model_rebuild()
ExportJobSummary.model_rebuild()
ExportJobListResponse.model_rebuild()
ExportJobDetailResponse.model_rebuild()
ExportJobDeleteResponse.model_rebuild()
ExportJobsClearResponse.model_rebuild()
ExportJobStatusUpdateRequest.model_rebuild()
ExportJobStatusUpdateResponse.model_rebuild()
