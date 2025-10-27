from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import sys
import os
import logging
import json
import glob
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time
from functools import lru_cache

# Add the tests directory to the path to import mapping_3
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'ml'))

try:
    from mapping_3 import HotelMapper
except ImportError as e:
    logging.error(f"Failed to import HotelMapper: {e}")
    HotelMapper = None

try:
    from mapping_without_push import HotelMapper as HotelMapperWithoutPush
except ImportError as e:
    logging.error(f"Failed to import HotelMapperWithoutPush: {e}")
    HotelMapperWithoutPush = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1.0/ml_mapping",
    tags=["ML Hotel Mapping"],
    responses={404: {"description": "Not found"}},
)

class HotelMappingRequest(BaseModel):
    supplier_name: str = Field(..., description="Supplier name (e.g., 'agoda')")
    hotel_id: str = Field(..., description="Hotel ID from the supplier")

class BatchHotelMappingRequest(BaseModel):
    supplier_name: str = Field(..., description="Supplier name (e.g., 'agoda')")
    hotel_ids: List[str] = Field(..., description="List of hotel IDs from the supplier")

class ApiData(BaseModel):
    name: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None

class MatchedData(BaseModel):
    name: str
    city: str
    country: str

class MatchingInfo(BaseModel):
    confidence_score: float
    threshold_used: float
    total_candidates: int

class FindHotel(BaseModel):
    Id: int
    ittid: int
    supplier_name: str
    hotel_id: str
    api_data: ApiData
    matched_data: MatchedData
    matching_info: MatchingInfo

class HotelMappingResponse(BaseModel):
    find_hotel: FindHotel

class BatchHotelMappingResponse(BaseModel):
    successful_mappings: List[HotelMappingResponse]
    failed_mappings: List[Dict[str, str]]
    summary: Dict[str, int]

class NotMappedHotelRequest(BaseModel):
    supplier_name: str = Field(..., description="Supplier name (e.g., 'agoda')")

class NotMappedHotelResponse(BaseModel):
    supplier_name: str
    total_hotel_id: int
    hotel_id: List[int]

class NotUpdateContentHotelResponse(BaseModel):
    supplier_name: str
    total_hotel_id: int
    hotel_id: List[int]

@router.post("/find_match_data", response_model=List[HotelMappingResponse])
async def find_match_data(request: HotelMappingRequest):
    """
    Find matching hotel data using ML mapping algorithm
    
    This endpoint takes a supplier name and hotel ID, fetches hotel details from the supplier API,
    and matches it against the internal hotel database using advanced fuzzy matching algorithms.
    
    Args:
        request: HotelMappingRequest containing supplier_name and hotel_id
        
    Returns:
        List containing the matched hotel data with confidence scores and matching information
        
    Raises:
        HTTPException: If HotelMapper is not available, hotel not found, or other errors occur
    """
    if HotelMapper is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="HotelMapper module is not available. Please check the mapping_3.py file."
        )
    
    try:
        # Initialize the hotel mapper with the correct CSV path
        csv_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'hotelcontent', 'itt_hotel_basic_info.csv')
        mapper = HotelMapper(csv_file_path=csv_path)
        
        logger.info(f"Processing mapping request for {request.supplier_name}:{request.hotel_id}")
        
        # Perform the hotel mapping
        result = mapper.map_hotel(request.supplier_name, request.hotel_id)
        
        if result:
            # Return the result as a list (as requested in the example)
            return [result]
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No matching hotel found for {request.supplier_name}:{request.hotel_id}"
            )
            
    except Exception as e:
        logger.error(f"Error in find_match_data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.post("/batch_find_match_data", response_model=BatchHotelMappingResponse)
async def batch_find_match_data(request: BatchHotelMappingRequest):
    """
    Find matching hotel data for multiple hotels in batch
    
    This endpoint processes multiple hotel IDs from the same supplier in a single request,
    providing better efficiency for bulk operations.
    
    Args:
        request: BatchHotelMappingRequest containing supplier_name and list of hotel_ids
        
    Returns:
        BatchHotelMappingResponse with successful mappings, failed mappings, and summary
        
    Raises:
        HTTPException: If HotelMapper is not available or other errors occur
    """
    if HotelMapper is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="HotelMapper module is not available. Please check the mapping_3.py file."
        )
    
    try:
        # Initialize the hotel mapper
        csv_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'hotelcontent', 'itt_hotel_basic_info.csv')
        mapper = HotelMapper(csv_file_path=csv_path)
        
        logger.info(f"Processing batch mapping request for {request.supplier_name} with {len(request.hotel_ids)} hotels")
        
        successful_mappings = []
        failed_mappings = []
        
        for hotel_id in request.hotel_ids:
            try:
                result = mapper.map_hotel(request.supplier_name, hotel_id)
                if result:
                    successful_mappings.append(result)
                else:
                    failed_mappings.append({
                        "hotel_id": hotel_id,
                        "reason": "No match found"
                    })
            except Exception as e:
                logger.error(f"Error processing hotel {hotel_id}: {str(e)}")
                failed_mappings.append({
                    "hotel_id": hotel_id,
                    "reason": str(e)
                })
        
        return BatchHotelMappingResponse(
            successful_mappings=successful_mappings,
            failed_mappings=failed_mappings,
            summary={
                "total_hotels": len(request.hotel_ids),
                "successful": len(successful_mappings),
                "failed": len(failed_mappings)
            }
        )
        
    except Exception as e:
        logger.error(f"Error in batch_find_match_data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.post("/find_match_data_without_push", response_model=List[HotelMappingResponse])
async def find_match_data_without_push(request: HotelMappingRequest):
    """
    Find matching hotel data using ML mapping algorithm WITHOUT push step
    
    This endpoint takes a supplier name and hotel ID, fetches hotel details directly from 
    the /hotel/details endpoint (skipping the /hotel/pushhotel step), and matches it 
    against the internal hotel database using advanced fuzzy matching algorithms.
    
    Key differences from find_match_data:
    - No /hotel/pushhotel API call required
    - Faster execution (one API call instead of two)
    - Direct data retrieval from /hotel/details
    - Better reliability (no dependency on push success)
    
    Args:
        request: HotelMappingRequest containing supplier_name and hotel_id
        
    Returns:
        List containing the matched hotel data with confidence scores and matching information
        
    Raises:
        HTTPException: If HotelMapperWithoutPush is not available, hotel not found, or other errors occur
    """
    if HotelMapperWithoutPush is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="HotelMapperWithoutPush module is not available. Please check the mapping_without_push.py file."
        )
    
    try:
        # Initialize the hotel mapper with the correct CSV path
        csv_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'hotelcontent', 'itt_hotel_basic_info.csv')
        mapper = HotelMapperWithoutPush(csv_file_path=csv_path)
        
        logger.info(f"Processing mapping request WITHOUT PUSH for {request.supplier_name}:{request.hotel_id}")
        
        # Perform the hotel mapping (direct details retrieval)
        result = mapper.map_hotel(request.supplier_name, request.hotel_id)
        
        if result:
            # Return the result as a list (consistent with find_match_data endpoint)
            return [result]
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No matching hotel found for {request.supplier_name}:{request.hotel_id}"
            )
            
    except Exception as e:
        logger.error(f"Error in find_match_data_without_push: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/health")
async def health_check():
    """
    Health check endpoint for ML mapping service
    
    Returns:
        Dict with service status and HotelMapper availability
    """
    return {
        "status": "healthy",
        "service": "ML Hotel Mapping",
        "hotel_mapper_available": HotelMapper is not None,
        "hotel_mapper_without_push_available": HotelMapperWithoutPush is not None,
        "endpoints": {
            "find_match_data": "Standard mapping with push step",
            "find_match_data_without_push": "Direct mapping without push step",
            "batch_find_match_data": "Batch mapping with push step"
        },
        "version": "1.0"
    }

@router.get("/supported_suppliers")
async def get_supported_suppliers():
    """
    Get list of supported suppliers
    
    Returns:
        Dict with list of supported suppliers and their descriptions
    """
    return {
        "supported_suppliers": [
            {
                "name": "agoda",
                "description": "Agoda hotel supplier",
                "status": "active"
            }
            # Add more suppliers as they become available
        ],
        "total_count": 1
    }

@lru_cache(maxsize=10)
def get_hotel_ids_from_folder_cached(supplier_name: str) -> tuple:
    """
    Cached version of get_hotel_ids_from_folder that returns a tuple for caching
    """
    return tuple(get_hotel_ids_from_folder_fast(supplier_name))

def get_hotel_ids_from_folder_fast(supplier_name: str) -> List[int]:
    """
    Optimized version to get hotel IDs from JSON files in the supplier folder
    
    Args:
        supplier_name: Name of the supplier (e.g., 'agoda')
        
    Returns:
        List of hotel IDs extracted from JSON filenames
    """
    RAW_BASE_DIR = r"D:\content_for_hotel_json\cdn_row_collection"
    supplier_folder = os.path.join(RAW_BASE_DIR, supplier_name)
    
    if not os.path.exists(supplier_folder):
        logger.warning(f"Supplier folder not found: {supplier_folder}")
        return []
    
    try:
        start_time = time.time()
        
        # Use os.listdir instead of glob for better performance
        all_files = os.listdir(supplier_folder)
        
        # Filter and process JSON files in one pass
        hotel_ids = []
        for filename in all_files:
            if filename.endswith('.json'):
                hotel_id_str = filename[:-5]  # Remove .json extension
                
                # Quick numeric check before conversion
                if hotel_id_str.isdigit():
                    hotel_ids.append(int(hotel_id_str))
        
        # Sort once at the end
        result = sorted(hotel_ids)
        
        logger.info(f"Folder scan completed in {time.time() - start_time:.2f}s, found {len(result)} hotel IDs")
        return result
        
    except Exception as e:
        logger.error(f"Error reading hotel IDs from folder {supplier_folder}: {str(e)}")
        return []

def get_hotel_ids_from_folder(supplier_name: str) -> List[int]:
    """
    Get hotel IDs from JSON files using cached version
    """
    return list(get_hotel_ids_from_folder_cached(supplier_name))

@lru_cache(maxsize=10)
def get_hotel_ids_from_database_cached(supplier_name: str) -> tuple:
    """
    Cached version of get_hotel_ids_from_database that returns a tuple for caching
    """
    return tuple(get_hotel_ids_from_database_fast(supplier_name))

def get_hotel_ids_from_database_fast(supplier_name: str) -> List[int]:
    """
    Optimized version to get hotel IDs from database
    
    Args:
        supplier_name: Name of the supplier (e.g., 'agoda')
        
    Returns:
        List of hotel IDs from database
    """
    try:
        start_time = time.time()
        
        # Import the utility function
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'utils'))
        from create_txt_file_follow_a_supplier import provider_mappings, engine, table
        
        # Get columns for the specified supplier
        columns = provider_mappings.get(supplier_name)
        if not columns:
            logger.warning(f"Supplier {supplier_name} not found in provider mappings.")
            return []

        from sqlalchemy import text
        
        # Optimized query - use UNION ALL for better performance
        union_queries = []
        for col in columns:
            union_queries.append(f"SELECT DISTINCT {col} as hotel_id FROM {table} WHERE {col} IS NOT NULL AND {col} != '' AND {col} REGEXP '^[0-9]+$'")
        
        query = " UNION ALL ".join(union_queries)
        final_query = f"SELECT DISTINCT hotel_id FROM ({query}) as combined_ids ORDER BY CAST(hotel_id AS UNSIGNED)"
        
        # Execute query directly without pandas for better performance
        with engine.connect() as connection:
            result = connection.execute(text(final_query))
            hotel_ids = [int(row[0]) for row in result.fetchall()]
        
        logger.info(f"Database query completed in {time.time() - start_time:.2f}s, found {len(hotel_ids)} hotel IDs")
        return hotel_ids
        
    except Exception as e:
        logger.error(f"Error getting hotel IDs from database for {supplier_name}: {str(e)}")
        return []

def get_hotel_ids_from_database(supplier_name: str) -> List[int]:
    """
    Get hotel IDs from database using cached version
    """
    return list(get_hotel_ids_from_database_cached(supplier_name))

@router.post("/get_not_mapped_hotel_id_list", response_model=NotMappedHotelResponse)
async def get_not_mapped_hotel_id_list(request: NotMappedHotelRequest):
    """
    OPTIMIZED: Get list of hotel IDs that exist in supplier folder but not in database
    
    This endpoint compares hotel IDs from JSON files in the supplier folder
    with hotel IDs stored in the database and returns the difference.
    
    Performance optimizations:
    - Async processing with ThreadPoolExecutor
    - Cached database and folder queries
    - Optimized SQL queries
    - Faster file system operations
    
    Args:
        request: NotMappedHotelRequest containing supplier_name
        
    Returns:
        NotMappedHotelResponse with supplier name, total count, and list of unmapped hotel IDs
        
    Raises:
        HTTPException: If supplier folder not found or other errors occur
    """
    try:
        start_time = time.time()
        logger.info(f"Processing OPTIMIZED not mapped hotel ID request for supplier: {request.supplier_name}")
        
        # Use ThreadPoolExecutor to run both operations concurrently
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submit both tasks concurrently
            folder_future = executor.submit(get_hotel_ids_from_folder, request.supplier_name)
            db_future = executor.submit(get_hotel_ids_from_database, request.supplier_name)
            
            # Wait for both to complete
            folder_hotel_ids = folder_future.result()
            db_hotel_ids = db_future.result()
        
        logger.info(f"Found {len(folder_hotel_ids)} hotel IDs in folder")
        logger.info(f"Found {len(db_hotel_ids)} hotel IDs in database")
        
        # Step 3: Calculate difference (folder IDs - database IDs) using sets for O(n) performance
        folder_set = set(folder_hotel_ids)
        db_set = set(db_hotel_ids)
        not_mapped_ids = sorted(list(folder_set - db_set))
        
        total_time = time.time() - start_time
        logger.info(f"Found {len(not_mapped_ids)} unmapped hotel IDs")
        logger.info(f"Total processing time: {total_time:.2f} seconds")
        
        return NotMappedHotelResponse(
            supplier_name=request.supplier_name,
            total_hotel_id=len(not_mapped_ids),
            hotel_id=not_mapped_ids
        )
        
    except Exception as e:
        logger.error(f"Error in get_not_mapped_hotel_id_list: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.post("/get_not_update_content_hotel_id_list", response_model=NotUpdateContentHotelResponse)
async def get_not_update_content_hotel_id_list(request: NotMappedHotelRequest):
    """
    OPTIMIZED: Get list of hotel IDs that exist in database but not in supplier folder
    
    This endpoint compares hotel IDs from the database with hotel IDs in JSON files
    in the supplier folder and returns hotel IDs that are in database but missing from folder.
    These are hotels that may need content updates.
    
    Performance optimizations:
    - Async processing with ThreadPoolExecutor
    - Cached database and folder queries
    - Optimized SQL queries
    - Faster file system operations
    
    Args:
        request: NotMappedHotelRequest containing supplier_name
        
    Returns:
        NotUpdateContentHotelResponse with supplier name, total count, and list of hotel IDs
        
    Raises:
        HTTPException: If supplier folder not found or other errors occur
    """
    try:
        start_time = time.time()
        logger.info(f"Processing OPTIMIZED not update content hotel ID request for supplier: {request.supplier_name}")
        
        # Use ThreadPoolExecutor to run both operations concurrently
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submit both tasks concurrently
            folder_future = executor.submit(get_hotel_ids_from_folder, request.supplier_name)
            db_future = executor.submit(get_hotel_ids_from_database, request.supplier_name)
            
            # Wait for both to complete
            folder_hotel_ids = folder_future.result()
            db_hotel_ids = db_future.result()
        
        logger.info(f"Found {len(folder_hotel_ids)} hotel IDs in folder")
        logger.info(f"Found {len(db_hotel_ids)} hotel IDs in database")
        
        # Step 3: Calculate difference (database IDs - folder IDs) using sets for O(n) performance
        folder_set = set(folder_hotel_ids)
        db_set = set(db_hotel_ids)
        not_update_content_ids = sorted(list(db_set - folder_set))
        
        total_time = time.time() - start_time
        logger.info(f"Found {len(not_update_content_ids)} hotel IDs in database but not in folder")
        logger.info(f"Total processing time: {total_time:.2f} seconds")
        
        return NotUpdateContentHotelResponse(
            supplier_name=request.supplier_name,
            total_hotel_id=len(not_update_content_ids),
            hotel_id=not_update_content_ids
        )
        
    except Exception as e:
        logger.error(f"Error in get_not_update_content_hotel_id_list: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.post("/clear_cache")
async def clear_hotel_id_cache():
    """
    Clear the cached hotel ID data for all suppliers
    
    Use this endpoint when:
    - New hotel data is added to the database
    - New JSON files are added to supplier folders
    - You want to refresh the cached data
    
    Returns:
        Dict with cache clearing status
    """
    try:
        # Clear the LRU caches
        get_hotel_ids_from_folder_cached.cache_clear()
        get_hotel_ids_from_database_cached.cache_clear()
        
        logger.info("Hotel ID caches cleared successfully")
        
        return {
            "success": True,
            "message": "Hotel ID caches cleared successfully",
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error clearing caches: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error clearing caches: {str(e)}"
        )
    
    