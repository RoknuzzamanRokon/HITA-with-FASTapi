from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
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
    suppliers: Optional[List[str]] = Field(None, description="List of supplier names to filter by")
    country_codes: Optional[List[str]] = Field(None, description="List of ISO country codes (e.g., ['US', 'GB'])")
    min_rating: Optional[float] = Field(None, ge=0, le=5, description="Minimum hotel rating (0-5)")
    max_rating: Optional[float] = Field(None, ge=0, le=5, description="Maximum hotel rating (0-5)")
    date_from: Optional[datetime] = Field(None, description="Filter hotels updated after this date")
    date_to: Optional[datetime] = Field(None, description="Filter hotels updated before this date")
    ittids: Optional[List[str]] = Field(None, description="List of specific ITTIDs to export")
    property_types: Optional[List[str]] = Field(None, description="List of property types (e.g., ['Hotel', 'Resort'])")
    page: int = Field(1, ge=1, description="Page number for pagination")
    page_size: int = Field(1000, ge=1, le=10000, description="Number of records per page")
    max_records: Optional[int] = Field(None, ge=1, le=100000, description="Maximum number of records to export (limit: 100,000)")

    @validator("suppliers")
    def validate_suppliers(cls, v):
        """Validate supplier list is not empty if provided"""
        if v is not None and len(v) == 0:
            raise ValueError("suppliers list cannot be empty if provided")
        return v

    @validator("country_codes")
    def validate_country_codes(cls, v):
        """Validate country codes are uppercase 2-letter codes"""
        if v is not None:
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
        """Validate ITTID list is not empty if provided"""
        if v is not None and len(v) == 0:
            raise ValueError("ittids list cannot be empty if provided")
        return v

    @validator("property_types")
    def validate_property_types(cls, v):
        """Validate property types list is not empty if provided"""
        if v is not None and len(v) == 0:
            raise ValueError("property_types list cannot be empty if provided")
        return v

    @validator("page_size")
    def validate_page_size(cls, v):
        """Validate page size is reasonable"""
        if v > 10000:
            raise ValueError("page_size cannot exceed 10,000 records per page")
        return v


class MappingExportFilters(BaseModel):
    """Filters for provider mapping export"""
    suppliers: Optional[List[str]] = Field(None, description="List of supplier names to filter by")
    ittids: Optional[List[str]] = Field(None, description="List of specific ITTIDs to export mappings for")
    date_from: Optional[datetime] = Field(None, description="Filter mappings created/updated after this date")
    date_to: Optional[datetime] = Field(None, description="Filter mappings created/updated before this date")
    max_records: Optional[int] = Field(None, ge=1, le=100000, description="Maximum number of records to export (limit: 100,000)")

    @validator("suppliers")
    def validate_suppliers(cls, v):
        """Validate supplier list is not empty if provided"""
        if v is not None and len(v) == 0:
            raise ValueError("suppliers list cannot be empty if provided")
        return v

    @validator("ittids")
    def validate_ittids(cls, v):
        """Validate ITTID list is not empty if provided"""
        if v is not None and len(v) == 0:
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


class SupplierSummaryFilters(BaseModel):
    """Filters for supplier summary statistics export"""
    suppliers: Optional[List[str]] = Field(None, description="List of supplier names to include in summary")
    include_country_breakdown: bool = Field(False, description="Include hotel counts by country per supplier")

    @validator("suppliers")
    def validate_suppliers(cls, v):
        """Validate supplier list is not empty if provided"""
        if v is not None and len(v) == 0:
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
    estimated_records: int = Field(..., description="Estimated number of records to be exported")
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
