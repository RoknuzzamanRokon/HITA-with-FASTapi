from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import sys
import os
import logging
import json
import glob

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

def get_hotel_ids_from_folder(supplier_name: str) -> List[int]:
    """
    Get hotel IDs from JSON files in the supplier folder
    
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
        # Get all JSON files in the folder
        json_files = glob.glob(os.path.join(supplier_folder, "*.json"))
        
        # Extract hotel IDs from filenames (remove .json extension)
        hotel_ids = []
        for file_path in json_files:
            filename = os.path.basename(file_path)
            hotel_id_str = filename.replace('.json', '')
            
            # Try to convert to integer
            try:
                hotel_id = int(hotel_id_str)
                hotel_ids.append(hotel_id)
            except ValueError:
                logger.warning(f"Skipping non-numeric hotel ID: {hotel_id_str}")
                continue
        
        return sorted(hotel_ids)
        
    except Exception as e:
        logger.error(f"Error reading hotel IDs from folder {supplier_folder}: {str(e)}")
        return []

def get_hotel_ids_from_database(supplier_name: str) -> List[int]:
    """
    Get hotel IDs from database using the existing utility function logic
    
    Args:
        supplier_name: Name of the supplier (e.g., 'agoda')
        
    Returns:
        List of hotel IDs from database
    """
    try:
        # Import the utility function
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'utils'))
        from create_txt_file_follow_a_supplier import generate_hotel_id_files, provider_mappings, engine, table
        
        # Get columns for the specified supplier
        columns = provider_mappings.get(supplier_name)
        if not columns:
            logger.warning(f"Supplier {supplier_name} not found in provider mappings.")
            return []

        from sqlalchemy import text
        import pandas as pd
        import numpy as np
        
        selected_columns = ", ".join(columns)
        where_clause = " OR ".join([f"{col} IS NOT NULL AND {col} != ''" for col in columns])
        query = f"SELECT {selected_columns} FROM {table} WHERE {where_clause};"
        
        df = pd.read_sql(text(query), engine)
        
        hotel_ids = set()
        for col in columns:
            # Clean and collect non-empty IDs
            non_empty = df[col].astype(str).str.strip().replace(r'^\s*$', np.nan, regex=True).dropna()
            hotel_ids.update(non_empty.unique())
        
        # Convert to integers where possible
        numeric_ids = []
        for id_str in hotel_ids:
            try:
                numeric_ids.append(int(id_str))
            except ValueError:
                logger.warning(f"Skipping non-numeric hotel ID from database: {id_str}")
                continue
        
        return sorted(numeric_ids)
        
    except Exception as e:
        logger.error(f"Error getting hotel IDs from database for {supplier_name}: {str(e)}")
        return []

@router.post("/get_not_mapped_hotel_id_list", response_model=NotMappedHotelResponse)
async def get_not_mapped_hotel_id_list(request: NotMappedHotelRequest):
    """
    Get list of hotel IDs that exist in supplier folder but not in database
    
    This endpoint compares hotel IDs from JSON files in the supplier folder
    with hotel IDs stored in the database and returns the difference.
    
    Args:
        request: NotMappedHotelRequest containing supplier_name
        
    Returns:
        NotMappedHotelResponse with supplier name, total count, and list of unmapped hotel IDs
        
    Raises:
        HTTPException: If supplier folder not found or other errors occur
    """
    try:
        logger.info(f"Processing not mapped hotel ID request for supplier: {request.supplier_name}")
        
        # Step 1: Get hotel IDs from supplier folder (JSON files)
        folder_hotel_ids = get_hotel_ids_from_folder(request.supplier_name)
        logger.info(f"Found {len(folder_hotel_ids)} hotel IDs in folder")
        
        # Step 2: Get hotel IDs from database
        db_hotel_ids = get_hotel_ids_from_database(request.supplier_name)
        logger.info(f"Found {len(db_hotel_ids)} hotel IDs in database")
        
        # Step 3: Calculate difference (folder IDs - database IDs)
        folder_set = set(folder_hotel_ids)
        db_set = set(db_hotel_ids)
        not_mapped_ids = sorted(list(folder_set - db_set))
        
        logger.info(f"Found {len(not_mapped_ids)} unmapped hotel IDs")
        
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
    Get list of hotel IDs that exist in database but not in supplier folder
    
    This endpoint compares hotel IDs from the database with hotel IDs in JSON files
    in the supplier folder and returns hotel IDs that are in database but missing from folder.
    These are hotels that may need content updates.
    
    Args:
        request: NotMappedHotelRequest containing supplier_name
        
    Returns:
        NotUpdateContentHotelResponse with supplier name, total count, and list of hotel IDs
        
    Raises:
        HTTPException: If supplier folder not found or other errors occur
    """
    try:
        logger.info(f"Processing not update content hotel ID request for supplier: {request.supplier_name}")
        
        # Step 1: Get hotel IDs from supplier folder (JSON files)
        folder_hotel_ids = get_hotel_ids_from_folder(request.supplier_name)
        logger.info(f"Found {len(folder_hotel_ids)} hotel IDs in folder")
        
        # Step 2: Get hotel IDs from database
        db_hotel_ids = get_hotel_ids_from_database(request.supplier_name)
        logger.info(f"Found {len(db_hotel_ids)} hotel IDs in database")
        
        # Step 3: Calculate difference (database IDs - folder IDs)
        folder_set = set(folder_hotel_ids)
        db_set = set(db_hotel_ids)
        not_update_content_ids = sorted(list(db_set - folder_set))
        
        logger.info(f"Found {len(not_update_content_ids)} hotel IDs in database but not in folder")
        
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
    
    