"""
Export Query Performance Testing Utility

Tests and benchmarks export query performance with EXPLAIN ANALYZE.
Helps identify slow queries and optimization opportunities.
"""

import sys
import os
from pathlib import Path
import time
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from sqlalchemy import text
from models import Hotel, Location, ProviderMapping, SupplierSummary
from export_schemas import HotelExportFilters, MappingExportFilters, SupplierSummaryFilters
from services.export_filter_service import ExportFilterService
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def explain_query(db, query):
    """
    Run EXPLAIN QUERY PLAN on a SQLAlchemy query.
    
    Args:
        db: Database session
        query: SQLAlchemy Query object
        
    Returns:
        List of explanation rows
    """
    try:
        # Get the compiled SQL statement
        compiled = query.statement.compile(compile_kwargs={"literal_binds": True})
        sql = str(compiled)
        
        # Run EXPLAIN QUERY PLAN
        explain_sql = f"EXPLAIN QUERY PLAN {sql}"
        result = db.execute(text(explain_sql))
        
        return result.fetchall()
        
    except Exception as e:
        logger.error(f"Error running EXPLAIN: {str(e)}")
        return []


def benchmark_query(db, query, description):
    """
    Benchmark a query's execution time.
    
    Args:
        db: Database session
        query: SQLAlchemy Query object
        description: Description of the query being tested
        
    Returns:
        Tuple of (execution_time, record_count)
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing: {description}")
    logger.info(f"{'='*60}")
    
    # Run EXPLAIN QUERY PLAN
    logger.info("\nQuery Plan:")
    explain_results = explain_query(db, query)
    for row in explain_results:
        logger.info(f"  {row}")
    
    # Benchmark execution time
    logger.info("\nExecuting query...")
    start_time = time.time()
    
    try:
        # Count results
        count = query.count()
        
        execution_time = time.time() - start_time
        
        logger.info(f"✓ Query completed in {execution_time:.3f} seconds")
        logger.info(f"  Records returned: {count}")
        logger.info(f"  Records/second: {count/execution_time:.1f}" if execution_time > 0 else "  Records/second: N/A")
        
        return execution_time, count
        
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"✗ Query failed after {execution_time:.3f} seconds: {str(e)}")
        return execution_time, 0


def test_hotel_export_queries():
    """
    Test various hotel export query patterns.
    """
    logger.info("\n" + "="*60)
    logger.info("HOTEL EXPORT QUERY PERFORMANCE TESTS")
    logger.info("="*60)
    
    db = SessionLocal()
    filter_service = ExportFilterService(db)
    
    try:
        # Test 1: Basic hotel query with no filters
        logger.info("\n\nTest 1: Basic hotel query (no filters)")
        filters = HotelExportFilters(
            suppliers=None,
            country_codes=None,
            page=1,
            page_size=1000
        )
        query = filter_service.build_hotel_query(
            filters=filters,
            allowed_suppliers=["Agoda", "Booking", "EAN"],
            include_locations=True,
            include_contacts=True,
            include_mappings=True
        )
        benchmark_query(db, query, "Basic hotel query with eager loading")
        
        # Test 2: Hotel query with country filter
        logger.info("\n\nTest 2: Hotel query with country filter")
        filters = HotelExportFilters(
            suppliers=None,
            country_codes=["US", "GB", "FR"],
            page=1,
            page_size=1000
        )
        query = filter_service.build_hotel_query(
            filters=filters,
            allowed_suppliers=["Agoda", "Booking", "EAN"],
            include_locations=True,
            include_contacts=False,
            include_mappings=True
        )
        benchmark_query(db, query, "Hotel query with country filter")
        
        # Test 3: Hotel query with rating filter
        logger.info("\n\nTest 3: Hotel query with rating filter")
        filters = HotelExportFilters(
            suppliers=None,
            country_codes=None,
            min_rating=4.0,
            max_rating=5.0,
            page=1,
            page_size=1000
        )
        query = filter_service.build_hotel_query(
            filters=filters,
            allowed_suppliers=["Agoda", "Booking", "EAN"],
            include_locations=True,
            include_contacts=False,
            include_mappings=True
        )
        benchmark_query(db, query, "Hotel query with rating filter")
        
        # Test 4: Hotel query with date range filter
        logger.info("\n\nTest 4: Hotel query with date range filter")
        filters = HotelExportFilters(
            suppliers=None,
            country_codes=None,
            date_from=datetime.utcnow() - timedelta(days=30),
            date_to=datetime.utcnow(),
            page=1,
            page_size=1000
        )
        query = filter_service.build_hotel_query(
            filters=filters,
            allowed_suppliers=["Agoda", "Booking", "EAN"],
            include_locations=True,
            include_contacts=False,
            include_mappings=True
        )
        benchmark_query(db, query, "Hotel query with date range filter")
        
        # Test 5: Complex hotel query with multiple filters
        logger.info("\n\nTest 5: Complex hotel query with multiple filters")
        filters = HotelExportFilters(
            suppliers=["Agoda"],
            country_codes=["US"],
            min_rating=3.0,
            date_from=datetime.utcnow() - timedelta(days=90),
            page=1,
            page_size=1000
        )
        query = filter_service.build_hotel_query(
            filters=filters,
            allowed_suppliers=["Agoda", "Booking", "EAN"],
            include_locations=True,
            include_contacts=True,
            include_mappings=True
        )
        benchmark_query(db, query, "Complex hotel query with multiple filters")
        
    finally:
        db.close()


def test_mapping_export_queries():
    """
    Test provider mapping export query patterns.
    """
    logger.info("\n\n" + "="*60)
    logger.info("MAPPING EXPORT QUERY PERFORMANCE TESTS")
    logger.info("="*60)
    
    db = SessionLocal()
    filter_service = ExportFilterService(db)
    
    try:
        # Test 1: Basic mapping query
        logger.info("\n\nTest 1: Basic mapping query")
        filters = MappingExportFilters(
            suppliers=None,
            ittids=None
        )
        query = filter_service.build_mapping_query(
            filters=filters,
            allowed_suppliers=["Agoda", "Booking", "EAN"]
        )
        benchmark_query(db, query, "Basic mapping query")
        
        # Test 2: Mapping query with supplier filter
        logger.info("\n\nTest 2: Mapping query with supplier filter")
        filters = MappingExportFilters(
            suppliers=["Agoda"],
            ittids=None
        )
        query = filter_service.build_mapping_query(
            filters=filters,
            allowed_suppliers=["Agoda", "Booking", "EAN"]
        )
        benchmark_query(db, query, "Mapping query with supplier filter")
        
        # Test 3: Mapping query with date range
        logger.info("\n\nTest 3: Mapping query with date range")
        filters = MappingExportFilters(
            suppliers=None,
            ittids=None,
            date_from=datetime.utcnow() - timedelta(days=30),
            date_to=datetime.utcnow()
        )
        query = filter_service.build_mapping_query(
            filters=filters,
            allowed_suppliers=["Agoda", "Booking", "EAN"]
        )
        benchmark_query(db, query, "Mapping query with date range")
        
    finally:
        db.close()


def test_supplier_summary_queries():
    """
    Test supplier summary export query patterns.
    """
    logger.info("\n\n" + "="*60)
    logger.info("SUPPLIER SUMMARY QUERY PERFORMANCE TESTS")
    logger.info("="*60)
    
    db = SessionLocal()
    filter_service = ExportFilterService(db)
    
    try:
        # Test 1: Basic supplier summary query
        logger.info("\n\nTest 1: Basic supplier summary query")
        filters = SupplierSummaryFilters(
            suppliers=None,
            include_country_breakdown=False
        )
        query = filter_service.build_supplier_summary_query(
            filters=filters,
            allowed_suppliers=None
        )
        benchmark_query(db, query, "Basic supplier summary query")
        
        # Test 2: Supplier summary with specific suppliers
        logger.info("\n\nTest 2: Supplier summary with specific suppliers")
        filters = SupplierSummaryFilters(
            suppliers=["Agoda", "Booking"],
            include_country_breakdown=False
        )
        query = filter_service.build_supplier_summary_query(
            filters=filters,
            allowed_suppliers=["Agoda", "Booking", "EAN"]
        )
        benchmark_query(db, query, "Supplier summary with specific suppliers")
        
    finally:
        db.close()


def check_index_usage():
    """
    Check which indexes exist and are being used.
    """
    logger.info("\n\n" + "="*60)
    logger.info("INDEX USAGE ANALYSIS")
    logger.info("="*60)
    
    db = SessionLocal()
    
    try:
        # Get list of all indexes
        logger.info("\nExisting indexes:")
        result = db.execute(text(
            "SELECT name, tbl_name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%' ORDER BY tbl_name, name"
        ))
        
        indexes = result.fetchall()
        
        current_table = None
        for index_name, table_name in indexes:
            if table_name != current_table:
                logger.info(f"\n{table_name}:")
                current_table = table_name
            logger.info(f"  - {index_name}")
        
        logger.info(f"\nTotal indexes: {len(indexes)}")
        
    finally:
        db.close()


def main():
    """
    Run all performance tests.
    """
    logger.info("="*60)
    logger.info("EXPORT QUERY PERFORMANCE TEST SUITE")
    logger.info("="*60)
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    start_time = time.time()
    
    try:
        # Check indexes
        check_index_usage()
        
        # Test hotel queries
        test_hotel_export_queries()
        
        # Test mapping queries
        test_mapping_export_queries()
        
        # Test supplier summary queries
        test_supplier_summary_queries()
        
        total_time = time.time() - start_time
        
        logger.info("\n\n" + "="*60)
        logger.info("TEST SUITE COMPLETED")
        logger.info("="*60)
        logger.info(f"Total execution time: {total_time:.2f} seconds")
        logger.info(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        logger.error(f"\n\nTest suite failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
