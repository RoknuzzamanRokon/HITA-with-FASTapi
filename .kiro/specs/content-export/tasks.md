# Implementation Plan

- [x] 1. Set up project structure and core models when finish this tusk

  - Create directory structure for export services and utilities
  - Define Pydantic schemas for export requests and responses
  - Create ExportJob database model with migration script
  - _Requirements: 1.1, 6.1, 8.1_

- [x] 1.1 Create export request and response schemas

  - Implement ExportFormat enum (CSV, JSON, EXCEL)
  - Create HotelExportFilters, MappingExportFilters, SupplierSummaryFilters schemas
  - Create ExportHotelsRequest, ExportMappingsRequest, ExportSupplierSummaryRequest schemas
  - Create ExportJobResponse, ExportJobStatusResponse, ExportMetadata schemas
  - Create ExportErrorResponse schema with error codes
  - _Requirements: 1.1, 2.1, 3.1, 9.1_

- [x] 1.2 Create ExportJob database model

  - Define ExportJob model with all required fields (id, user_id, export_type, format, filters, status, progress, etc.)
  - Add relationship to User model
  - Create Alembic migration script for export_jobs table
  - Add indexes on user_id, status, created_at, expires_at columns
  - _Requirements: 6.1, 6.2, 8.1_

- [x] 2. Implement permission validation service and when finish, commit with only headlin.

  - Create ExportPermissionService class
  - Implement validate_export_access method with role-based logic
  - Implement get_user_suppliers method to fetch active supplier permissions
  - Handle TEMP*DEACTIVATED* supplier prefix logic
  - Integrate IP whitelist validation from existing check_ip_whitelist function
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 3. Implement filter builder service and when finish, commit with only headlin.

  - Create ExportFilterService class
  - Implement build_hotel_query method with all filter types (suppliers, countries, ratings, dates, ittids, property types)
  - Implement build_mapping_query method with supplier and ITTID filters
  - Implement build_supplier_summary_query method
  - Implement estimate_result_count method using COUNT queries
  - Add query optimization with selective column loading and indexes
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 10.1, 10.4_

- [x] 4. Implement export format handlers and when finish, commit with only headlin.

  - Create ExportFormatHandler class
  - Implement to_csv method with UTF-8 encoding and streaming
  - Implement to_json method with pretty-printing and metadata
  - Implement to_excel method with multiple sheets and formatting
  - Implement flatten_hotel_data helper for CSV flattening
  - Add proper Content-Type headers and filename generation
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 4.1 Implement CSV export format handler

  - Create CSV writer with UTF-8 BOM encoding
  - Implement streaming CSV generation with batch processing
  - Flatten nested hotel data (locations, contacts, mappings) into single row
  - Add proper header row with all column names
  - Handle special characters and escaping
  - _Requirements: 7.1, 10.2, 10.3_

- [x] 4.2 Implement JSON export format handler

  - Create JSON writer with streaming support
  - Implement nested structure preservation for relationships
  - Add export metadata header (timestamp, user, filters, record count)
  - Use ISO 8601 datetime formatting
  - Implement pretty-printing with 2-space indentation
  - _Requirements: 7.2, 8.4_

- [x] 4.3 Implement Excel export format handler

  - Create XLSX writer using openpyxl library
  - Implement multi-sheet structure (Hotels, Locations, Contacts, Mappings, Summary)
  - Add formatted headers with bold text and colored background
  - Implement auto-column sizing
  - Add freeze panes on header rows
  - Create summary dashboard sheet with key metrics
  - _Requirements: 7.3, 3.5_

- [x] 5. Implement core export engine and when finish, commit with only headlin.

  - Create ExportEngine class with batch processing logic
  - Implement stream_query_results method using yield_per for memory efficiency
  - Implement sync/async decision logic based on record count threshold (5000)
  - Implement synchronous export flow for small datasets
  - Implement asynchronous export flow with background task creation
  - Add progress tracking and status updates for async exports
  - _Requirements: 6.1, 6.2, 6.3, 10.2, 10.3, 10.5_

- [x] 5.1 Implement synchronous export processing

  - Create export_hotels_sync method for <5000 records
  - Stream query results in batches of 1000 records
  - Transform data using format handler
  - Return FileResponse with appropriate headers
  - Add memory management and cleanup
  - _Requirements: 1.1, 10.2, 10.3_

- [x] 5.2 Implement asynchronous export processing

  - Create export_hotels_async method for >=5000 records
  - Generate unique job ID and create ExportJob record
  - Implement background task with process_async_export
  - Update job status and progress every 10% completion
  - Write output to file storage incrementally
  - Handle errors and update job status to "failed" on exceptions
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 10.2_

- [x] 6. Implement export API endpoints and when finish, commit with only headlin.

  - Create routes/export.py router with /v1.0/export prefix
  - Implement POST /export/hotels endpoint
  - Implement POST /export/mappings endpoint
  - Implement POST /export/supplier-summary endpoint
  - Implement GET /export/status/{job_id} endpoint
  - Implement GET /export/download/{job_id} endpoint
  - Add authentication dependency (get_current_user)
  - _Requirements: 1.1, 2.1, 3.1, 6.3, 6.5_

- [x] 6.1 Implement hotel export endpoint

  - Create POST /v1.0/export/hotels endpoint
  - Validate request body using ExportHotelsRequest schema
  - Call permission validator to check user access
  - Deduct points for general users
  - Build query using filter service
  - Estimate result count and decide sync vs async
  - Call export engine and return appropriate response
  - Add audit logging for export operation
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 5.1, 5.5, 8.1, 8.2, 9.1, 9.2_

- [x] 6.2 Implement mapping export endpoint

  - Create POST /v1.0/export/mappings endpoint
  - Validate request body using ExportMappingsRequest schema
  - Validate user permissions for requested suppliers
  - Build mapping query with filters (suppliers, ittids, dates)
  - Include Giata codes and Vervotech IDs in export
  - Handle Excel multi-sheet format for mappings
  - Add audit logging
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 8.1_

- [x] 6.3 Implement supplier summary export endpoint

  - Create POST /v1.0/export/supplier-summary endpoint
  - Validate request body using ExportSupplierSummaryRequest schema
  - Query supplier_summary table for statistics
  - Include country breakdown if requested
  - Generate chart-ready data for visualization
  - Create Excel dashboard sheet with key metrics
  - Add audit logging
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 8.1_

- [x] 6.4 Implement export status endpoint

  - Create GET /v1.0/export/status/{job_id} endpoint
  - Query ExportJob by job_id
  - Verify user owns the export job
  - Return job status, progress, and metadata
  - Include download URL if job is completed
  - Return 404 if job not found
  - _Requirements: 6.3, 6.4_

- [x] 6.5 Implement export download endpoint

  - Create GET /v1.0/export/download/{job_id} endpoint
  - Query ExportJob and verify ownership
  - Check if job is completed and file exists
  - Check if export has expired (>24 hours)
  - Stream file as FileResponse with appropriate headers
  - Return 404 if job not found, 410 if expired
  - _Requirements: 6.5_

- [x] 7. Implement request validation and when finish, commit with git only take headlin.

  - Add Pydantic validators for all filter fields
  - Validate export format is one of CSV, JSON, EXCEL
  - Validate date ranges (from < to)
  - Validate rating ranges (0-5)
  - Validate maximum export size (100,000 records)
  - Return 400 errors with specific field validation messages
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 8. Implement audit logging and when finish, git add amd commit with only headline.

  - Log all export requests with user ID, filters, and timestamp
  - Log export completion with record count and file size
  - Log export failures with error details
  - Use existing AuditLogger from security.audit_logging
  - Set security level to HIGH for export operations
  - Include IP address and user agent in logs
  - Store logs in user_activity_logs table
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 9. Implement file storage and cleanup and when finish, commit with only headline.

  - Create export file storage directory structure
  - Implement file naming convention (job_id + format extension)
  - Set file permissions to restrict access
  - Implement cleanup job to delete files older than 24 hours
  - Add file size tracking in ExportJob model
  - Handle storage errors gracefully
  - _Requirements: 6.4, 6.5_

- [ ] 10. Add error handling and edge cases and when finish, commit with only headline.

  - Implement comprehensive try-catch blocks in all services
  - Create error response formatter with ExportErrorResponse schema
  - Handle database connection errors
  - Handle file I/O errors
  - Handle permission denied scenarios
  - Handle insufficient points scenarios
  - Handle export job not found scenarios
  - Handle expired export file scenarios
  - _Requirements: 5.3, 9.2, 9.3_

- [ ] 11. Optimize database queries and when finish, commit with only headlin.

  - Add database indexes on frequently filtered columns
  - Implement query result streaming with yield_per
  - Use joinedload for eager loading relationships
  - Implement selective column loading (load only required fields)
  - Add query result caching for repeated exports
  - Test query performance with EXPLAIN ANALYZE
  - _Requirements: 10.1, 10.4, 10.5_

- [ ] 12. Register export router in main application and when finish, commit with only headlin.

  - Import export router in main.py
  - Register router with app.include_router
  - Add export endpoints to API documentation
  - Test all endpoints are accessible
  - _Requirements: 1.1, 2.1, 3.1_

- [ ]\* 13. Write unit tests for export services and when finish, remove test file and unnacecary file.

  - Test ExportPermissionService with different user roles
  - Test ExportFilterService query building
  - Test ExportFormatHandler for all formats
  - Test ExportEngine batch processing
  - Test edge cases and error scenarios
  - Achieve >80% code coverage
  - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1, 7.1, 9.1_

- [ ]\* 14. Write integration tests for export endpoints and when finish, remove test file and unnacecary file.

  - Test end-to-end hotel export in all formats
  - Test provider mapping export with filters
  - Test supplier summary export
  - Test async job creation and status checking
  - Test permission denial scenarios
  - Test large dataset handling (>10k records)
  - Test file download functionality
  - _Requirements: 1.1, 2.1, 3.1, 6.1, 6.3, 6.5_

- [ ]\* 15. Performance testing and optimization and when finish, remove test file and unnacecary file.

  - Benchmark export of 1,000 records (<5 seconds target)
  - Benchmark export of 10,000 records (<30 seconds target)
  - Benchmark export of 50,000 records (<3 minutes target)
  - Monitor memory usage (<500MB target)
  - Optimize slow queries identified in testing
  - Profile code to identify bottlenecks
  - _Requirements: 10.5_

- [ ]\* 16. Create API documentation and when finish, remove test file and unnacecary file.
  - Add comprehensive docstrings to all endpoints
  - Create example requests and responses
  - Document error codes and responses
  - Add usage examples for each export type
  - Document filter options and formats
  - Update OpenAPI schema in custom_openapi.py
  - _Requirements: 1.1, 2.1, 3.1, 7.1, 9.1_
