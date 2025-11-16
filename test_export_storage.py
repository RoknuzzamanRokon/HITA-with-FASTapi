"""
Test script for export file storage functionality.

This script tests the basic functionality of the ExportFileStorage class
without requiring a full database setup.
"""

import os
import sys
import tempfile
from datetime import datetime

# Add utils to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'utils'))
from export_file_storage import ExportFileStorage


def test_storage_initialization():
    """Test storage initialization and directory creation."""
    print("Testing storage initialization...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = ExportFileStorage(temp_dir)
        
        assert os.path.exists(temp_dir), "Storage directory should exist"
        assert storage.base_storage_path == temp_dir, "Storage path should match"
        
        print("✓ Storage initialization successful")


def test_file_path_generation():
    """Test file path generation with naming convention."""
    print("\nTesting file path generation...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = ExportFileStorage(temp_dir)
        
        # Test CSV file path
        csv_path = storage.get_file_path(
            job_id="exp_test123",
            export_type="hotels",
            format="csv",
            timestamp=datetime(2023, 11, 16, 14, 30, 22)
        )
        
        expected_filename = "hotels_exp_test123_20231116_143022.csv"
        assert expected_filename in csv_path, f"Expected {expected_filename} in {csv_path}"
        
        # Test JSON file path
        json_path = storage.get_file_path(
            job_id="exp_test456",
            export_type="mappings",
            format="json",
            timestamp=datetime(2023, 11, 16, 15, 45, 30)
        )
        
        expected_filename = "mappings_exp_test456_20231116_154530.json"
        assert expected_filename in json_path, f"Expected {expected_filename} in {json_path}"
        
        # Test Excel file path
        excel_path = storage.get_file_path(
            job_id="exp_test789",
            export_type="supplier_summary",
            format="excel",
            timestamp=datetime(2023, 11, 16, 16, 21, 45)
        )
        
        expected_filename = "supplier_summary_exp_test789_20231116_162145.xlsx"
        assert expected_filename in excel_path, f"Expected {expected_filename} in {excel_path}"
        
        print("✓ File path generation successful")


def test_file_operations():
    """Test file operations (create, permissions, size, delete)."""
    print("\nTesting file operations...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = ExportFileStorage(temp_dir)
        
        # Create a test file
        file_path = storage.get_file_path(
            job_id="exp_test_ops",
            export_type="hotels",
            format="csv"
        )
        
        # Write some test data
        test_data = "test,data,here\n1,2,3\n"
        with open(file_path, 'w') as f:
            f.write(test_data)
        
        assert os.path.exists(file_path), "File should exist after creation"
        
        # Test file permissions
        storage.set_file_permissions(file_path)
        print("✓ File permissions set")
        
        # Test file size
        size = storage.get_file_size(file_path)
        assert size == len(test_data), f"File size should be {len(test_data)}, got {size}"
        print(f"✓ File size correct: {size} bytes")
        
        # Test file deletion
        deleted = storage.delete_file(file_path)
        assert deleted, "File should be deleted successfully"
        assert not os.path.exists(file_path), "File should not exist after deletion"
        print("✓ File deletion successful")


def test_storage_stats():
    """Test storage statistics."""
    print("\nTesting storage statistics...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = ExportFileStorage(temp_dir)
        
        # Create some test files
        for i in range(3):
            file_path = storage.get_file_path(
                job_id=f"exp_test_{i}",
                export_type="hotels",
                format="csv"
            )
            with open(file_path, 'w') as f:
                f.write(f"test data {i}\n" * 100)
        
        # Get statistics
        stats = storage.get_storage_stats()
        
        assert stats['total_files'] == 3, f"Should have 3 files, got {stats['total_files']}"
        assert stats['total_size_bytes'] > 0, "Total size should be greater than 0"
        assert stats['oldest_file'] is not None, "Should have oldest file timestamp"
        assert stats['newest_file'] is not None, "Should have newest file timestamp"
        
        print(f"✓ Storage stats: {stats['total_files']} files, {stats['total_size_mb']} MB")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Export File Storage Tests")
    print("=" * 60)
    
    try:
        test_storage_initialization()
        test_file_path_generation()
        test_file_operations()
        test_storage_stats()
        
        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
