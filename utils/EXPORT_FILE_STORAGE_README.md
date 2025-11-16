# Export File Storage

This document describes the file storage and cleanup system for export operations.

## Overview

The export file storage system manages the lifecycle of export files, including:

- Directory structure creation
- File naming conventions
- File permissions and security
- Automatic cleanup of expired files
- Storage error handling

## Components

### 1. ExportFileStorage Class (`utils/export_file_storage.py`)

Core utility class that handles all file storage operations.

**Key Features:**

- Automatic directory creation with secure permissions (0o750)
- Standardized file naming: `{export_type}_{job_id}_{timestamp}.{extension}`
- File permission management (0o600 for files)
- File size tracking
- Cleanup of expired and failed exports
- Storage statistics and monitoring

**Usage Example:**

```python
from utils.export_file_storage import ExportFileStorage

# Initialize storage manager
storage = ExportFileStorage("/path/to/exports")

# Generate file path
file_path = storage.get_file_path(
    job_id="exp_abc123",
    export_type="hotels",
    format="csv",
    timestamp=datetime.utcnow()
)

# Set secure permissions
storage.set_file_permissions(file_path)

# Get file size
size = storage.get_file_size(file_path)

# Clean up expired files
files_deleted, files_failed = storage.cleanup_expired_files(db, retention_hours=24)
```

### 2. Cleanup Script (`utils/cleanup_export_files.py`)

Scheduled job script for automatic cleanup of expired export files.

**Features:**

- Cleans up completed exports older than 24 hours (configurable)
- Cleans up failed exports older than 1 hour
- Dry-run mode for testing
- Detailed logging to file and console
- Storage statistics before and after cleanup

**Usage:**

```bash
# Run cleanup with default settings (24 hour retention)
python utils/cleanup_export_files.py

# Run with custom retention period
python utils/cleanup_export_files.py --retention-hours 48

# Dry run (show what would be deleted without deleting)
python utils/cleanup_export_files.py --dry-run
```

**Scheduling:**

On Windows (Task Scheduler):

```powershell
# Run every hour
schtasks /create /tn "Export Cleanup" /tr "python D:\path\to\backend\utils\cleanup_export_files.py" /sc hourly
```

On Linux (cron):

```bash
# Add to crontab (run every hour)
0 * * * * cd /path/to/backend && python utils/cleanup_export_files.py >> /var/log/export_cleanup.log 2>&1
```

### 3. Integration with ExportEngine (`services/export_engine.py`)

The ExportEngine now uses ExportFileStorage for all file operations:

**Changes:**

- File paths generated using `storage.get_file_path()`
- File permissions set automatically after file creation
- File sizes retrieved using `storage.get_file_size()`
- Consistent naming across sync and async exports

## File Naming Convention

Export files follow this naming pattern:

```
{export_type}_{job_id}_{timestamp}.{extension}
```

**Examples:**

- `hotels_exp_a1b2c3d4e5f6_20231116_143022.csv`
- `mappings_exp_x9y8z7w6v5u4_20231116_150530.json`
- `supplier_summary_exp_m5n4o3p2q1r0_20231116_162145.xlsx`

**Components:**

- `export_type`: Type of export (hotels, mappings, supplier_summary)
- `job_id`: Unique job identifier (16 character hex)
- `timestamp`: UTC timestamp in format YYYYMMDD_HHMMSS
- `extension`: File extension based on format (csv, json, xlsx)

## File Permissions

### Directory Permissions (0o750)

- Owner: Read, Write, Execute
- Group: Read, Execute
- Others: None

### File Permissions (0o600)

- Owner: Read, Write
- Group: None
- Others: None

This ensures that only the application owner can read/write export files, preventing unauthorized access.

## Storage Directory Structure

```
exports/
├── hotels_exp_abc123_20231116_143022.csv
├── hotels_exp_def456_20231116_144530.json
├── mappings_exp_ghi789_20231116_150000.xlsx
└── supplier_summary_exp_jkl012_20231116_162145.csv
```

All export files are stored in a flat structure in the exports directory.

## Cleanup Process

### Automatic Cleanup

The cleanup process runs periodically and performs two types of cleanup:

1. **Expired Completed Exports** (default: 24 hours)

   - Finds export jobs with status "completed"
   - Completed more than 24 hours ago
   - Deletes associated files
   - Updates database records

2. **Failed Exports** (default: 1 hour)
   - Finds export jobs with status "failed"
   - Created more than 1 hour ago
   - Deletes any partial files
   - Updates database records

### Manual Cleanup

You can also trigger cleanup manually:

```python
from database import SessionLocal
from utils.export_file_storage import ExportFileStorage

db = SessionLocal()
storage = ExportFileStorage()

# Clean up expired files
files_deleted, files_failed = storage.cleanup_expired_files(db, retention_hours=24)
print(f"Deleted: {files_deleted}, Failed: {files_failed}")

# Clean up failed exports
failed_deleted = storage.cleanup_failed_exports(db, age_hours=1)
print(f"Failed exports cleaned: {failed_deleted}")

db.close()
```

## Storage Statistics

Get information about the export storage:

```python
storage = ExportFileStorage()
stats = storage.get_storage_stats()

print(f"Total files: {stats['total_files']}")
print(f"Total size: {stats['total_size_mb']} MB")
print(f"Oldest file: {stats['oldest_file']}")
print(f"Newest file: {stats['newest_file']}")
```

## Error Handling

The storage system handles errors gracefully:

- **Permission Errors**: Logged but don't stop execution
- **Missing Files**: Handled without raising exceptions
- **Storage Full**: Errors are logged with context
- **Cleanup Failures**: Individual file failures don't stop batch cleanup

All errors are logged with full context for debugging.

## Configuration

### Environment Variables

```bash
# Set custom export storage path
export EXPORT_STORAGE_PATH="/custom/path/to/exports"
```

### Default Values

- **Storage Path**: `./exports/` (relative to application root)
- **Retention Period**: 24 hours for completed exports
- **Failed Export Cleanup**: 1 hour
- **Directory Permissions**: 0o750
- **File Permissions**: 0o600

## Database Integration

The ExportJob model tracks file information:

```python
class ExportJob(Base):
    id = Column(String(50), primary_key=True)
    file_path = Column(String(500), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    # ... other fields
```

- `file_path`: Full path to the export file
- `file_size_bytes`: Size of the file in bytes
- `expires_at`: When the file will be deleted (24 hours after completion)

## Monitoring

### Log Files

Cleanup operations are logged to:

- `export_cleanup.log` (when running cleanup script)
- Application logs (when using ExportFileStorage directly)

### Log Levels

- **INFO**: Normal operations, cleanup summaries
- **DEBUG**: Detailed file operations
- **WARNING**: Non-critical issues (missing files, permission warnings)
- **ERROR**: Critical errors that need attention

## Best Practices

1. **Run cleanup regularly**: Schedule the cleanup script to run hourly
2. **Monitor storage**: Check storage statistics periodically
3. **Adjust retention**: Increase retention period if users need longer access
4. **Check logs**: Review cleanup logs for any recurring errors
5. **Backup important exports**: Copy critical exports before they expire
6. **Test in dry-run**: Use `--dry-run` to verify cleanup behavior

## Troubleshooting

### Files not being deleted

1. Check file permissions
2. Verify cleanup script is running
3. Check database for correct `completed_at` timestamps
4. Review logs for error messages

### Permission denied errors

1. Ensure application has write access to exports directory
2. Check directory and file permissions
3. Verify user running the application

### Storage filling up

1. Reduce retention period
2. Run cleanup more frequently
3. Check for failed cleanup operations
4. Verify cleanup script is scheduled correctly

## Requirements

Requirements from task 9:

- ✅ Create export file storage directory structure
- ✅ Implement file naming convention (job_id + format extension)
- ✅ Set file permissions to restrict access
- ✅ Implement cleanup job to delete files older than 24 hours
- ✅ Add file size tracking in ExportJob model (already exists)
- ✅ Handle storage errors gracefully
- ✅ Requirements: 6.4, 6.5
