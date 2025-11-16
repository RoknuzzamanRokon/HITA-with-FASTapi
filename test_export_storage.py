"""
Test Export File Storage Implementation

This script verifies that the export file storage system is working correctly.
"""

import os
import sys
from datetime import datetime

# Add utils directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'utils'))

from export_file_storage import ExportFileStorage


def test_storage_initialization():
    """Test that storage can be initialized"""
    print("Testing storage initialization...")
    storage = ExportFileStorage()
    print(f"✓ Storage initialized with path: {storage.base_storage_path}")
    assert os.path.exists(storage.base_storage_path), "Storage directory should exist"
    print("✓ Storage directory exists")
    return storage


def test_file_path_generation(storage):
    """Test file path generation"""
    print("\nTesting file path generation...")
    
    # Test CSV file path
    csv_path = storage.get_file_path(
        job_id="test_abc123",
        export_type="hotels",
        format="csv",
        timestamp=datetime(2023, 11, 16, 14, 30, 22)
    )
    print(f"✓ CSV path: {csv_path}")
    assert "hotels_test_abc123_20231116_143022.csv" in csv_path
    
    # Test JSON file path
    json_path = storage.get_file_path(
        job_id="test_def456",
        export_type="mappings",
        format="json",
        timestamp=datetime(2023, 11, 16, 15, 45, 30)
    )
    print(f"✓ JSON path: {json_path}")
    assert "mappings_test_def456_20231116_154530.json" in json_path
    
    # Test Excel file path
    excel_path = storage.get_file_path(
        job_id="test_ghi789",
        export_type="supplier_summary",
        format="excel",
        timestamp=datetime(2023, 11, 16, 16, 21, 45)
    )
    print(f"✓ Excel path: {excel_path}")
    assert "supplier_summary_test_ghi789_20231116_162145.xlsx" in excel_path
    
    print("✓ All file path formats correct")


def test_file_operations(storage):
    """Test file operations"""
    print("\nTesting file operations...")
    
    # Create a test file
    test_path = storage.get_file_path(
        job_id="test_xyz999",
        export_type="hotels",
        format="csv"
    )
    
    # Write test content
    with open(test_path, 'w') as f:
        f.write("test,data\n1,2\n")
    print(f"✓ Created test file: {test_path}")
    
    # Set permissions
    storage.set_file_permissions(test_path)
    print("✓ Set file permissions")
    
    # Get file size
    size = storage.get_file_size(test_path)
    print(f"✓ File size: {size} bytes")
    assert size > 0, "File should have content"
    
    # Delete file
    deleted = storage.delete_file(test_path)
    print(f"✓ Deleted file: {deleted}")
    assert deleted, "File should be deleted successfully"
    assert not os.path.exists(test_path), "File should not exist after deletion"
    
    print("✓ All file operations successful")


def test_storage_stats(storage):
    """Test storage statistics"""
    print("\nTesting storage statistics...")
    
    stats = storage.get_storage_stats()
    print(f"✓ Total files: {stats['total_files']}")
    print(f"✓ Total size: {stats['total_size_mb']} MB")
    print(f"✓ Oldest file: {stats['oldest_file']}")
    print(f"✓ Newest file: {stats['newest_file']}")
    
    print("✓ Storage statistics retrieved successfully")


def test_error_handling(storage):
    """Test error handling"""
    print("\nTesting error handling...")
    
    # Test getting size of non-existent file
    size = storage.get_file_size("/nonexistent/file.csv")
    assert size is None, "Should return None for non-existent file"
    print("✓ Handles non-existent file correctly")
    
    # Test deleting non-existent file
    deleted = storage.delete_file("/nonexistent/file.csv")
    assert not deleted, "Should return False for non-existent file"
    print("✓ Handles deletion of non-existent file correctly")
    
    # Test setting permissions on non-existent file
    storage.set_file_permissions("/nonexistent/file.csv")
    print("✓ Handles permission setting on non-existent file gracefully")
    
    print("✓ All error handling tests passed")


def main():
    """Run all tests"""
    print("=" * 60)
    print("Export File Storage Test Suite")
    print("=" * 60)
    
    try:
        storage = test_storage_initialization()
        test_file_path_generation(storage)
        test_file_operations(storage)
        test_storage_stats(storage)
        test_error_handling(storage)
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
