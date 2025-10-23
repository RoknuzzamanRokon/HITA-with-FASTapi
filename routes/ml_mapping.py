from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import sys
import os
import logging

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