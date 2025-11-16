from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import distinct, text
from typing import List, Optional, Annotated
from database import get_db
from models import Location, UserIPWhitelist
from pydantic import BaseModel
from fastapi_cache.decorator import cache
import asyncio
from datetime import datetime
from collections import defaultdict
from routes.auth import get_current_user
from middleware.ip_middleware import get_client_ip
import models
import json
import os
from pathlib import Path

# Router setup
router = APIRouter(
    prefix="/v1.0/locations",
    tags=["Locations"],
    responses={404: {"description": "Not found"}},
)


def check_ip_whitelist(user_id: str, request: Request, db: Session) -> bool:
    """
    Check if the user's IP address is in the whitelist.
    
    Args:
        user_id (str): The user ID to check
        request (Request): The FastAPI request object
        db (Session): Database session
    
    Returns:
        bool: True if IP is whitelisted, False otherwise
    """
    try:
        # Get client IP using the middleware function
        client_ip = get_client_ip(request)
        
        if not client_ip:
            return False
        
        # Check if the user has any active IP whitelist entries for this IP
        whitelist_entry = db.query(UserIPWhitelist).filter(
            UserIPWhitelist.user_id == user_id,
            UserIPWhitelist.ip_address == client_ip,
            UserIPWhitelist.is_active == True
        ).first()
        
        return whitelist_entry is not None
        
    except Exception as e:
        print(f"Error checking IP whitelist: {str(e)}")
        return False
    

class CitiesListResponse(BaseModel):
    total_city: int
    city_name: List[str]
    
    class Config:
        from_attributes = True

class CountryResponse(BaseModel):
    country_name: str
    
    class Config:
        from_attributes = True

class CountriesListResponse(BaseModel):
    total_country: int
    country_name: List[str]
    
    class Config:
        from_attributes = True

class CountryCodesListResponse(BaseModel):
    total_country_code: int
    country_code: List[str]
    
    class Config:
        from_attributes = True

class CountryWithCitiesItem(BaseModel):
    country_name: str
    total: int
    city_name: List[str]
    
    class Config:
        from_attributes = True

class CitiesWithCountriesGroupedResponse(BaseModel):
    total_country: int
    last_update: str
    countries: List[CountryWithCitiesItem]
    
    class Config:
        from_attributes = True

class LocationDetailResponse(BaseModel):
    id: int
    ittid: str
    city_name: Optional[str]
    state_name: Optional[str]
    state_code: Optional[str]
    country_name: Optional[str]
    country_code: Optional[str]
    master_city_name: Optional[str]
    city_code: Optional[str]
    city_location_id: Optional[str]
    
    class Config:
        from_attributes = True

# Hotel Search Models
class HotelSearchRequest(BaseModel):
    lat: str
    lon: str
    radius: str 
    supplier: List[str]
    country_code: str
    
    class Config:
        from_attributes = True

class HotelItemRate(BaseModel):
    a: float 
    b: float  
    name: str
    addr: str
    type: Optional[str] = "" 
    photo: str
    star: Optional[float] = None
    ittid: Optional[str] = None
    rName: Optional[str] = None
    total: Optional[float] = None
    fare: Optional[float] = None
    tax: Optional[float] = None
    fees: Optional[float] = None
    
    class Config:
        from_attributes = True
        extra = "allow"  

class HotelSearchResponseRate(BaseModel):
    total_hotels: int
    hotels: List[HotelItemRate]
    
    class Config:
        from_attributes = True        

class HotelItem(BaseModel):
    a: float 
    b: float  
    name: str
    addr: str
    type: Optional[str] = "" 
    photo: str
    star: Optional[float] = None
    vervotech: Optional[str] = None
    giata: Optional[str] = None
    
    class Config:
        from_attributes = True
        extra = "allow"  

class HotelSearchResponse(BaseModel):
    total_hotels: int
    hotels: List[HotelItem]
    
    class Config:
        from_attributes = True


# Search Location with location.
class CityByCountryItem(BaseModel):
    country_name: str
    country_code: str
    total_city: int
    last_update: str
    city_list: List[str]
    
    class Config:
        from_attributes = True

class CitiesByCountryResponse(BaseModel):
    data: List[CityByCountryItem]
    
    class Config:
        from_attributes = True

class CountryFilterRequest(BaseModel):
    country_name: Optional[str] = None
    country_code: Optional[str] = None
    
    class Config:
        from_attributes = True

class CountryISOFilterRequest(BaseModel):
    country_code: Optional[str] = None
    
    class Config:
        from_attributes = True



@router.get("/cities", response_model=CitiesListResponse)
@cache(expire=3600)  # Cache for 1 hour
async def get_all_cities(db: Session = Depends(get_db)):
    """
    Get all unique cities from locations in a consolidated format.
    
    OPTIMIZED VERSION - Uses caching and efficient query execution.
    
    Returns a single object containing the total count of cities and 
    an array of all unique city names.
    
    Returns:
        CitiesListResponse: Object containing:
            - total_city: Total number of unique cities
            - city_name: Array of all unique city names
    
    Example Response:
        {
            "total_city": 5465645,
            "city_name": ["Hong Kong", "Macau", "Medjugorje", "Mostar"]
        }
    
    Performance Features:
        - ✅ 1-hour caching (3600 seconds)
        - ✅ Async execution in thread pool
        - ✅ Sorted output for consistency
    """
    try:
        def get_cities_sync():
            cities = db.query(distinct(Location.city_name)).filter(
                Location.city_name.isnot(None),
                Location.city_name != ""
            ).all()
            return [city[0] for city in cities if city[0]]
        
        # Execute in thread pool for better async performance
        loop = asyncio.get_event_loop()
        city_names = await loop.run_in_executor(None, get_cities_sync)
        
        return {
            "total_city": len(city_names),
            "city_name": sorted(city_names)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching cities: {str(e)}")


@router.get("/countries", response_model=CountriesListResponse)
async def get_all_countries_fast(db: Session = Depends(get_db)):
    try:
        # Use raw SQL for maximum performance
        raw_sql = text("""
            SELECT DISTINCT country_name 
            FROM locations 
            WHERE country_name IS NOT NULL 
            AND country_name != '' 
            ORDER BY country_name
        """)
        
        def execute_raw_query():
            result = db.execute(raw_sql)
            return [row[0] for row in result.fetchall()]
        
        # Execute in thread pool
        loop = asyncio.get_event_loop()
        country_names = await loop.run_in_executor(None, execute_raw_query)
        
        return {
            "total_country": len(country_names),
            "country_name": country_names
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching countries: {str(e)}")


@router.get("/country-iso", response_model=CountryCodesListResponse)
async def get_all_country_codes(db: Session = Depends(get_db)):
    """
    Get all unique country codes from locations in a consolidated format.
    
    Returns a single object containing the total count of country codes and 
    an array of all unique country codes (ISO format).
    
    Returns:
        CountryCodesListResponse: Object containing:
            - total_country_code: Total number of unique country codes
            - country_code: Array of all unique country codes
    
    Example Response:
        {
            "total_country_code": 195,
            "country_code": ["US", "CA", "GB", "FR", "DE", "JP"]
        }
    """
    try:
        country_codes = db.query(distinct(Location.country_code)).filter(
            Location.country_code.isnot(None),
            Location.country_code != ""
        ).all()
        
        # Extract country codes and filter out None values
        codes = [code[0] for code in country_codes if code[0]]
        
        return {
            "total_country_code": len(codes),
            "country_code": codes
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching country codes: {str(e)}")


@router.get("/cities-with-countries", response_model=CitiesWithCountriesGroupedResponse)
@cache(expire=3600)  # Cache for 1 hour
async def get_cities_with_countries(db: Session = Depends(get_db)):
    """
    ULTRA-OPTIMIZED cities with countries endpoint.
    
    **PERFORMANCE OPTIMIZATIONS:**
    - ✅ Aggressive SQL optimization with DISTINCT and GROUP BY
    - ✅ Minimal data transfer from database
    - ✅ Efficient memory usage
    - ✅ 1-hour caching for instant subsequent requests
    - ✅ Parallel processing with asyncio
    
    **Expected Performance:**
    - First request: 2-10 seconds (vs 1+ minute before)
    - Cached requests: ~1ms (instant)
    
    **CRITICAL:** Run the database optimization script for best performance!
    """
    try:
        # ULTRA-OPTIMIZED SQL - Uses DISTINCT and aggregation for minimal data transfer
        optimized_sql = text("""
            SELECT 
                country_name,
                STRING_AGG(DISTINCT TRIM(city_name), '|' ORDER BY TRIM(city_name)) as cities,
                COUNT(DISTINCT TRIM(city_name)) as city_count
            FROM locations 
            WHERE country_name IS NOT NULL 
                AND country_name != ''
                AND city_name IS NOT NULL 
                AND city_name != ''
                AND TRIM(city_name) != ''
            GROUP BY country_name
            ORDER BY country_name
        """)
        
        def execute_ultra_fast_query():
            try:
                result = db.execute(optimized_sql)
                countries_list = []
                
                for row in result.fetchall():
                    country_name = row[0]
                    cities_string = row[1] if row[1] else ""
                    city_count = row[2] if row[2] else 0
                    
                    # Split cities and clean them
                    if cities_string:
                        city_names = [city.strip() for city in cities_string.split('|') if city.strip()]
                        city_names = sorted(list(set(city_names)))  # Remove duplicates and sort
                    else:
                        city_names = []
                    
                    countries_list.append({
                        "country_name": country_name,
                        "total": len(city_names),
                        "city_name": city_names
                    })
                
                return countries_list
                
            except Exception as e:
                # Fallback to simpler query if STRING_AGG is not supported
                print(f"Advanced SQL failed, using fallback: {str(e)}")
                
                fallback_sql = text("""
                    SELECT DISTINCT country_name, TRIM(city_name) as city_name
                    FROM locations 
                    WHERE country_name IS NOT NULL 
                        AND country_name != ''
                        AND city_name IS NOT NULL 
                        AND city_name != ''
                        AND TRIM(city_name) != ''
                    ORDER BY country_name, city_name
                    LIMIT 50000
                """)
                
                result = db.execute(fallback_sql)
                country_cities = defaultdict(set)
                
                for row in result.fetchall():
                    country_name = row[0]
                    city_name = row[1]
                    if country_name and city_name:
                        country_cities[country_name].add(city_name)
                
                countries_list = []
                for country_name, cities_set in sorted(country_cities.items()):
                    cities_list = sorted(list(cities_set))
                    countries_list.append({
                        "country_name": country_name,
                        "total": len(cities_list),
                        "city_name": cities_list
                    })
                
                return countries_list
        
        # Execute in thread pool for better async performance
        loop = asyncio.get_event_loop()
        countries_data = await loop.run_in_executor(None, execute_ultra_fast_query)
        
        return {
            "total_country": len(countries_data),
            "last_update": datetime.utcnow().isoformat(),
            "countries": countries_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching cities with countries: {str(e)}")


@router.get("/search")
async def search_locations(
    http_request: Request,
    current_user: Annotated[models.User, Depends(get_current_user)],
    city: Optional[str] = Query(None, description="Filter by city name"),
    country: Optional[str] = Query(None, description="Filter by country name"),
    country_code: Optional[str] = Query(None, description="Filter by country code"),
    state: Optional[str] = Query(None, description="Filter by state name"),
    limit: int = Query(100, ge=1, le=1000, description="Limit number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
):
    """
    Search and filter locations with multiple criteria.
    
    **SECURITY:** Requires authentication and IP whitelist validation.
    
    **What it does:**
    Find locations using flexible search filters with pagination support.
    
    **Search filters:**
    - `city` - Search by city name (partial match)
    - `country` - Search by country name (partial match)  
    - `country_code` - Search by country code (e.g., "US", "GB")
    - `state` - Search by state/province name (partial match)
    
    **Pagination:**
    - `limit` - Max results per page (1-1000, default: 100)
    - `offset` - Skip number of results (default: 0)
    
    **Example usage:**
    - `/search?city=New York` - Find cities containing "New York"
    - `/search?country=United&limit=50` - Find countries containing "United"
    - `/search?country_code=US&state=California` - US locations in California
    
    **Response format:**
    ```json
    {
        "total": 1250,
        "limit": 100,
        "offset": 0,
        "locations": [
            {
                "id": 1,
                "city_name": "New York",
                "country_name": "United States",
                "country_code": "US"
            }
        ]
    }
    ```
    """
    # 🔒 IP WHITELIST VALIDATION
    print(f"🚀 IP whitelist check for user: {current_user.id} in search_locations")
    if not check_ip_whitelist(current_user.id, http_request, db):
        # Extract client IP for error message
        client_ip = get_client_ip(http_request) or "unknown"
            
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": True,
                "message": "Access denied: IP address not whitelisted",
                "error_code": "IP_NOT_WHITELISTED",
                "details": {
                    "status_code": 403,
                    "client_ip": client_ip,
                    "user_id": current_user.id,
                    "message": "Your IP address is not in the whitelist. Please contact your administrator to add your IP address to the whitelist."
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    try:
        query = db.query(Location)
        
        # Apply filters
        if city:
            query = query.filter(Location.city_name.ilike(f"%{city}%"))
        if country:
            query = query.filter(Location.country_name.ilike(f"%{country}%"))
        if country_code:
            query = query.filter(Location.country_code.ilike(f"%{country_code}%"))
        if state:
            query = query.filter(Location.state_name.ilike(f"%{state}%"))
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        locations = query.offset(offset).limit(limit).all()
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "locations": [LocationDetailResponse.model_validate(location) for location in locations]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching locations: {str(e)}")


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the distance between two points on Earth using the Haversine formula.
    
    Args:
        lat1, lon1: Latitude and longitude of first point
        lat2, lon2: Latitude and longitude of second point
    
    Returns:
        Distance in kilometers
    """
    from math import radians, sin, cos, sqrt, atan2
    
    # Earth's radius in kilometers
    R = 6371.0
    
    # Convert degrees to radians
    lat1_rad = radians(lat1)
    lon1_rad = radians(lon1)
    lat2_rad = radians(lat2)
    lon2_rad = radians(lon2)
    
    # Differences
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    # Haversine formula
    a = sin(dlat / 2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    distance = R * c
    return distance


@router.post("/search-hotel-with-location", response_model=HotelSearchResponse)
async def search_hotel_with_location(
    request: HotelSearchRequest,
    db: Session = Depends(get_db)
):
    """
    Search hotels within a specified radius from a given location.
    
    **What it does:**
    Searches for hotels from specified suppliers within a given radius of coordinates.
    Uses JSON files stored in static/countryJson/{supplier}/{country_code}.json
    
    **Request body examples:**
    
    **Example 1: Specific supplier**
    ```json
    {
        "lat": "25.2048493",
        "lon": "55.2707828",
        "radius": "10",
        "supplier": ["agoda"],
        "country_code": "AI"
    }
    ```
    
    **Example 2: All suppliers (NEW FEATURE)**
    ```json
    {
        "lat": "25.2048493",
        "lon": "55.2707828",
        "radius": "10",
        "supplier": ["All"],
        "country_code": "AI"
    }
    ```
    
    **Response format:**
    ```json
    {
        "total_hotels": 2,
        "hotels": [
            {
                "a": 18.17,
                "b": -63.1423,
                "name": "Sheriva Luxury Villas and Suites",
                "addr": "Maundays Bay Rd",
                "type": "Villa",
                "photo": "https://...",
                "star": 4.0,
                "vervotech": "15392205",
                "giata": "291678",
                "agoda": ["55395643"]
            }
        ]
    }
    ```
    
    **Parameters:**
    - lat: Latitude of search center
    - lon: Longitude of search center
    - radius: Search radius in kilometers
    - supplier: List of suppliers to search
      * Specific suppliers: ["agoda", "booking", "expedia"]
      * All suppliers: ["All"] or ["all"] (case-insensitive)
      * Mixed: ["All", "ean"] - searches all suppliers (specific ones are ignored when "All" is present)
    - country_code: ISO country code (e.g., "AI")
    
    **Supplier "All" Feature:**
    When "All" or "all" is included in the supplier list:
    - Searches ALL suppliers available in the system (from supplier_summary table)
    - Case-insensitive: "All", "all", "ALL" all work
    - If "All" is present, other specific suppliers in the list are ignored
    """
    
    try:
        # Convert input parameters
        search_lat = float(request.lat)
        search_lon = float(request.lon)
        radius_km = float(request.radius)
        
        all_hotels = []
        
        # Check if "All" or "all" is in the supplier list
        use_all_suppliers = any(s.lower() == "all" for s in request.supplier)
        
        # Determine which suppliers to search
        suppliers_to_search = []
        
        if use_all_suppliers:
            # Get all available suppliers from the system
            all_system_suppliers = db.query(models.SupplierSummary.provider_name).all()
            suppliers_to_search = [supplier[0] for supplier in all_system_suppliers]
            print(f"✅ Searching ALL suppliers: {len(suppliers_to_search)} suppliers")
        else:
            # Use the specific suppliers requested
            suppliers_to_search = request.supplier
        
        # Process each supplier
        for supplier in suppliers_to_search:
            # Construct file path
            json_file_path = Path(f"static/countryJson/{supplier}/{request.country_code}.json")
            
            # Check if file exists
            if not json_file_path.exists():
                continue
            
            # Read JSON file
            with open(json_file_path, 'r', encoding='utf-8') as f:
                hotels_data = json.load(f)
            
            # Filter hotels within radius
            for hotel in hotels_data:
                hotel_lat = hotel.get('lat')
                hotel_lon = hotel.get('lon')
                
                if hotel_lat is None or hotel_lon is None:
                    continue
                
                # Calculate distance
                distance = calculate_distance(search_lat, search_lon, hotel_lat, hotel_lon)
                
                # Check if within radius
                if distance <= radius_km:
                    # Transform to output format
                    hotel_item = {
                        "a": hotel_lat,
                        "b": hotel_lon,
                        "name": hotel.get('name') or '',
                        "addr": hotel.get('addr') or '',
                        "type": hotel.get('ptype') or '',
                        "photo": hotel.get('photo') or '',
                        "star": hotel.get('star', 0.0),
                        "vervotech": hotel.get('vervotech') or '',
                        "giata": hotel.get('giata'),
                    }
                    
                    # Add supplier-specific IDs
                    if supplier in hotel:
                        hotel_item[supplier] = hotel[supplier]
                    
                    all_hotels.append(hotel_item)
        
        return {
            "total_hotels": len(all_hotels),
            "hotels": all_hotels
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid input parameters: {str(e)}"
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Hotel data not found for the specified country/supplier"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error searching hotels: {str(e)}"
        )


@router.post("/search-hotel-with-location-with-rate", response_model=HotelSearchResponseRate)
async def search_hotel_with_location(
    http_request: Request,
    request: HotelSearchRequest,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Session = Depends(get_db)
):
    """
    Search hotels within a specified radius from a given location with rate information.
    
    **SECURITY:** Requires authentication, IP whitelist validation, and supplier permission checks.
    
    **What it does:**
    Searches for hotels from specified suppliers within a given radius of coordinates.
    Uses JSON files stored in static/countryJsonWithRate/{supplier}/{country_code}.json
    
    **Price Selection Logic:**
    When a hotel has multiple price options, the endpoint automatically selects the price 
    with the HIGHEST total value. For example:
    - If price[0].total = 83.17 and price[1].total = 0.0, returns price[0]
    - If price[0].total = 0.0 and price[1].total = 116.15, returns price[1]
    
    **Request body examples:**
    
    **Example 1: Specific suppliers**
    ```json
    {
        "lat": "42.5081",
        "lon": "1.53423",
        "radius": "10",
        "supplier": ["agoda"],
        "country_code": "AI"
    }
    ```
    
    **Example 2: All suppliers (NEW FEATURE)**
    ```json
    {
        "lat": "42.5081",
        "lon": "1.53423",
        "radius": "10",
        "supplier": ["All"],
        "country_code": "AI"
    }
    ```
    
    **Example 3: Mix of All and specific suppliers**
    ```json
    {
        "lat": "42.5081",
        "lon": "1.53423",
        "radius": "10",
        "supplier": ["All", "ean"],
        "country_code": "AI"
    }
    ```
    
    **Response format:**
    ```json
    {
        "total_hotels": 2,
        "hotels": [
            {
                "a": 42.5081,
                "b": 1.53423,
                "name": "Hotel Exe Princep",
                "addr": "Carrer de la Unio, 5",
                "type": "Hotel",
                "photo": "https://...",
                "star": 3.0,
                "rName": "Economy Double or Twin Room with no View",
                "total": 83.17,
                "fare": 79.37,
                "tax": 3.8,
                "fees": 0.0,
                "ittid": "10060288",
                "agoda": ["128414", "32653486"]
            }
        ]
    }
    ```
    
    **Parameters:**
    - lat: Latitude of search center (required)
    - lon: Longitude of search center (required)
    - radius: Search radius in kilometers (required)
    - supplier: List of suppliers to search (required)
      * Specific suppliers: ["agoda", "booking", "expedia"]
      * All suppliers: ["All"] or ["all"] (case-insensitive)
      * Mixed: ["All", "ean"] - searches all suppliers (specific ones are ignored when "All" is present)
    - country_code: ISO country code (required, e.g., "AI")
    
    **Supplier "All" Feature:**
    When "All" or "all" is included in the supplier list:
    - **Super User/Admin User**: Searches ALL suppliers in the system (from supplier_summary table)
    - **General User**: Searches ALL suppliers they have permission for
    - Case-insensitive: "All", "all", "ALL" all work
    - If "All" is present, other specific suppliers in the list are ignored
    
    **Response fields:**
    - a: Hotel latitude
    - b: Hotel longitude
    - name: Hotel name
    - addr: Hotel address
    - type: Property type (Hotel, Villa, etc.)
    - photo: Hotel photo URL
    - star: Star rating (0.0 to 5.0)
    - rName: Room name (from selected price)
    - total: Total price (highest available)
    - fare: Base fare
    - tax: Tax amount
    - fees: Additional fees
    - ittid: ITT hotel ID
    - {supplier}: List of supplier-specific property IDs (e.g., "agoda": ["128414"])
    
    **Security & Access Control:**
    - **Super User/Admin User**: 
      * Can access all requested suppliers
      * "All" returns results from all system suppliers
    - **General User**: 
      * Only searches suppliers with explicit permissions
      * "All" returns results from all permitted suppliers only
      * Unauthorized suppliers are silently filtered out (no error thrown)
    
    **Supplier Filtering:**
    If a user requests multiple suppliers but only has permission for some, the endpoint will:
    - Search only the authorized suppliers
    - Return results from authorized suppliers only
    - Silently skip unauthorized suppliers (no error thrown)
    - Return empty result if no suppliers are authorized
    
    **Examples:**
    
    1. **Search specific supplier:**
       - Request: `{"supplier": ["agoda"]}`
       - Result: Hotels from Agoda only
    
    2. **Search all suppliers (Admin/Super):**
       - Request: `{"supplier": ["All"]}`
       - Result: Hotels from all system suppliers (agoda, booking, expedia, etc.)
    
    3. **Search all suppliers (General User):**
       - Request: `{"supplier": ["All"]}`
       - User has permissions: agoda, booking
       - Result: Hotels from agoda and booking only
    
    4. **Mixed request (All + specific):**
       - Request: `{"supplier": ["All", "ean"]}`
       - Result: Same as ["All"] - searches all suppliers (specific ones ignored)
    """

    
    # 🔒 IP WHITELIST VALIDATION
    print(f"🚀 IP whitelist check for user: {current_user.id} in search_hotel_with_location_with_rate")
    if not check_ip_whitelist(current_user.id, http_request, db):
        client_ip = get_client_ip(http_request) or "unknown"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": True,
                "message": "Access denied: IP address not whitelisted",
                "error_code": "IP_NOT_WHITELISTED",
                "details": {
                    "status_code": 403,
                    "client_ip": client_ip,
                    "user_id": current_user.id,
                    "message": "Your IP address is not in the whitelist. Please contact your administrator to add your IP address to the whitelist."
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    # 🔒 SUPPLIER PERMISSION VALIDATION & FILTERING
    # Check if "All" or "all" is in the supplier list
    use_all_suppliers = any(s.lower() == "all" for s in request.supplier)
    
    allowed_suppliers = []
    
    if use_all_suppliers:
        # User requested all suppliers
        if current_user.role in [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER]:
            # Admin and super users: get all available suppliers from the system
            all_system_suppliers = db.query(models.SupplierSummary.provider_name).all()
            allowed_suppliers = [supplier[0] for supplier in all_system_suppliers]
            print(f"✅ Admin/Super user requested ALL suppliers: {len(allowed_suppliers)} suppliers")
        else:
            # General users: get all suppliers they have permission for
            user_permissions = db.query(models.UserProviderPermission.provider_name).filter(
                models.UserProviderPermission.user_id == current_user.id
            ).all()
            allowed_suppliers = [perm[0] for perm in user_permissions]
            print(f"✅ General user requested ALL suppliers: {len(allowed_suppliers)} permitted suppliers")
    else:
        # User requested specific suppliers
        if current_user.role in [models.UserRole.SUPER_USER, models.UserRole.ADMIN_USER]:
            # Admin and super users can access all requested suppliers
            allowed_suppliers = request.supplier
        else:
            # General users: filter suppliers based on permissions
            for supplier in request.supplier:
                user_supplier_permission = db.query(models.UserProviderPermission).filter(
                    models.UserProviderPermission.user_id == current_user.id,
                    models.UserProviderPermission.provider_name == supplier
                ).first()
                
                if user_supplier_permission:
                    allowed_suppliers.append(supplier)
                else:
                    print(f"⚠️ User {current_user.id} does not have permission for supplier '{supplier}' - skipping")
    
    # If no suppliers are allowed, return empty result
    if not allowed_suppliers:
        return {
            "total_hotels": 0,
            "hotels": []
        }
    
    print(f"🔍 Searching {len(allowed_suppliers)} suppliers: {allowed_suppliers}")
    
    try:
        # Convert input parameters
        search_lat = float(request.lat)
        search_lon = float(request.lon)
        radius_km = float(request.radius)
        
        all_hotels = []
        
        # Process only allowed suppliers
        for supplier in allowed_suppliers:
            # Construct file path
            json_file_path = Path(f"static/countryJsonWithRate/{supplier}/{request.country_code}.json")
            
            # Check if file exists
            if not json_file_path.exists():
                continue
            
            # Read JSON file
            with open(json_file_path, 'r', encoding='utf-8') as f:
                hotels_data = json.load(f)
            
            # Filter hotels within radius
            for hotel in hotels_data:
                hotel_lat = hotel.get('lat')
                hotel_lon = hotel.get('lon')
                
                if hotel_lat is None or hotel_lon is None:
                    continue
                
                # Calculate distance
                distance = calculate_distance(search_lat, search_lon, hotel_lat, hotel_lon)
                
                # Check if within radius
                if distance <= radius_km:
                    # Transform to output format
                    hotel_item = {
                        "a": hotel_lat,
                        "b": hotel_lon,
                        "name": hotel.get('name') or '',
                        "addr": hotel.get('addr') or '',
                        "type": hotel.get('ptype') or '',
                        "photo": hotel.get('photo') or '',
                        "star": hotel.get('star', 0.0),
                        "ittid": hotel.get('ittid') or '',
                    }
                    
                    # Add supplier-specific IDs
                    if supplier in hotel:
                        hotel_item[supplier] = hotel[supplier]
                    
                    # Process price information - select the highest total price
                    prices = hotel.get('price', [])
                    if prices and isinstance(prices, list):
                        # Find the price with the highest total
                        best_price = max(prices, key=lambda p: p.get('total', 0.0))
                        
                        # Add price fields to hotel item
                        hotel_item['rName'] = best_price.get('roomName') or ''
                        hotel_item['total'] = best_price.get('total', 0.0)
                        hotel_item['fare'] = best_price.get('fare', 0.0)
                        hotel_item['tax'] = best_price.get('tax', 0.0)
                        hotel_item['fees'] = best_price.get('fees', 0.0)
                    else:
                        # No price data available
                        hotel_item['rName'] = ''
                        hotel_item['total'] = 0.0
                        hotel_item['fare'] = 0.0
                        hotel_item['tax'] = 0.0
                        hotel_item['fees'] = 0.0
                    
                    all_hotels.append(hotel_item)
        
        return {
            "total_hotels": len(all_hotels),
            "hotels": all_hotels
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid input parameters: {str(e)}"
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Hotel data not found for the specified country/supplier"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error searching hotels: {str(e)}"
        )
            

@router.get("/{location_id}", response_model=LocationDetailResponse)
async def get_location_by_id(location_id: int, db: Session = Depends(get_db)):
    """
    Get detailed information for a specific location.
    
    **What it does:**
    Retrieve complete location details using the location ID.
    
    **Parameters:**
    - `location_id` - The unique ID of the location (required)
    
    **Response includes:**
    - Complete location information
    - City, state, and country details
    - Location codes and identifiers
    - Associated hotel ITTID
    
    **Example usage:**
    - `/123` - Get details for location ID 123
    
    **Response format:**
    ```json
    {
        "id": 123,
        "ittid": "ITT456789",
        "city_name": "New York",
        "state_name": "New York",
        "state_code": "NY",
        "country_name": "United States",
        "country_code": "US",
        "master_city_name": "New York City",
        "city_code": "NYC",
        "city_location_id": "NYC001"
    }
    ```
    
    **Errors:**
    - `404` - Location not found
    - `500` - Database error
    """
    try:
        location = db.query(Location).filter(Location.id == location_id).first()
        if not location:
            raise HTTPException(status_code=404, detail="Location not found")
        
        return LocationDetailResponse.model_validate(location)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching location: {str(e)}")


# Global cache for cities by country
_cities_by_country_cache = None
_cities_cache_timestamp = None


def _load_cities_by_country_cache(db: Session):
    """Load cities grouped by country into memory cache"""
    global _cities_by_country_cache, _cities_cache_timestamp
    
    from datetime import timedelta
    
    # Return cache if it exists and is less than 1 hour old
    if _cities_by_country_cache is not None and _cities_cache_timestamp is not None:
        if datetime.utcnow() - _cities_cache_timestamp < timedelta(hours=1):
            return _cities_by_country_cache
    
    try:
        # Optimized SQL query to get cities grouped by country (normalize to uppercase)
        sql = text("""
            SELECT 
                UPPER(country_name) as country_name,
                country_code,
                STRING_AGG(DISTINCT TRIM(city_name), '|' ORDER BY TRIM(city_name)) as cities,
                COUNT(DISTINCT TRIM(city_name)) as city_count
            FROM locations 
            WHERE country_name IS NOT NULL 
                AND country_name != ''
                AND country_code IS NOT NULL
                AND country_code != ''
                AND city_name IS NOT NULL 
                AND city_name != ''
                AND TRIM(city_name) != ''
            GROUP BY UPPER(country_name), country_code
            ORDER BY UPPER(country_name)
        """)
        
        result = db.execute(sql)
        country_dict = {}
        current_time = datetime.utcnow().isoformat()
        
        for row in result.fetchall():
            country_name = row[0]
            country_code = row[1]
            cities_string = row[2] if row[2] else ""
            
            # Split cities and clean them
            if cities_string:
                city_list = [city.strip() for city in cities_string.split('|') if city.strip()]
            else:
                city_list = []
            
            # Merge cities if country already exists (in case of multiple country_codes)
            if country_name in country_dict:
                existing_cities = set(country_dict[country_name]["city_list"])
                existing_cities.update(city_list)
                country_dict[country_name]["city_list"] = sorted(list(existing_cities))
                country_dict[country_name]["total_city"] = len(country_dict[country_name]["city_list"])
            else:
                country_dict[country_name] = {
                    "country_name": country_name,
                    "country_code": country_code,
                    "total_city": len(city_list),
                    "last_update": current_time,
                    "city_list": sorted(list(set(city_list)))
                }
        
        # Convert dict to list
        countries_data = list(country_dict.values())
        
        # Update cache
        _cities_by_country_cache = countries_data
        _cities_cache_timestamp = datetime.utcnow()
        
        return countries_data
        
    except Exception as e:
        # Fallback to simpler query if STRING_AGG is not supported
        print(f"Advanced SQL failed, using fallback: {str(e)}")
        
        fallback_sql = text("""
            SELECT DISTINCT UPPER(country_name) as country_name, country_code, TRIM(city_name) as city_name
            FROM locations 
            WHERE country_name IS NOT NULL 
                AND country_name != ''
                AND country_code IS NOT NULL
                AND country_code != ''
                AND city_name IS NOT NULL 
                AND city_name != ''
                AND TRIM(city_name) != ''
            ORDER BY UPPER(country_name), city_name
        """)
        
        result = db.execute(fallback_sql)
        country_data_dict = defaultdict(lambda: {"cities": set(), "code": ""})
        
        for row in result.fetchall():
            country_name = row[0]  # Already uppercase from query
            country_code = row[1]
            city_name = row[2]
            
            if country_name and city_name:
                country_data_dict[country_name]["cities"].add(city_name)
                country_data_dict[country_name]["code"] = country_code
        
        countries_data = []
        current_time = datetime.utcnow().isoformat()
        
        for country_name, data in sorted(country_data_dict.items()):
            city_list = sorted(list(data["cities"]))
            countries_data.append({
                "country_name": country_name,
                "country_code": data["code"],
                "total_city": len(city_list),
                "last_update": current_time,
                "city_list": city_list
            })
        
        # Update cache
        _cities_by_country_cache = countries_data
        _cities_cache_timestamp = datetime.utcnow()
        
        return countries_data


@router.post("/get-cities-follow-country", response_model=CitiesByCountryResponse)
async def get_cities_follow_countries(
    request: Optional[CountryFilterRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Get all cities grouped by countries with optional filtering and caching.
    
    **OPTIMIZED VERSION with 1-hour caching for ultra-fast performance.**
    
    Features:
    - In-memory caching for instant subsequent requests
    - Optional country name or country code filtering
    - Optimized SQL with aggregation
    - Complete city lists per country
    - Country codes included
    - Last update timestamp
    
    Request Body (Optional):
        {
            "country_name": "Bangladesh"  // Optional: filter by country name
            "country_code": "AF"          // Optional: filter by ISO country code
        }
    
    Returns:
        CitiesByCountryResponse: Object containing array of countries with:
            - country_name: Name of the country
            - country_code: ISO country code
            - total_city: Number of cities in that country
            - last_update: Timestamp of data
            - city_list: Array of all city names in that country
    
    Performance:
        - First request: ~2-10 seconds (loads and caches data)
        - Subsequent requests (within 1 hour): <10ms (uses cache)
        - Cache expires after 1 hour, then refreshes automatically
    
    Example Request (All countries):
        POST /v1.0/locations/get-cities-follow-country
        Body: {}
        
    Example Request (By country name):
        POST /v1.0/locations/get-cities-follow-country
        Body: {"country_name": "Bangladesh"}
        
    Example Request (By country code):
        POST /v1.0/locations/get-cities-follow-country
        Body: {"country_code": "AF"}
        
    Example Response:
        {
            "data": [
                {
                    "country_name": "AFGHANISTAN",
                    "country_code": "AF",
                    "total_city": 3,
                    "last_update": "2025-11-11T10:30:00",
                    "city_list": ["Afghanistan", "Badghis", "Kabul"]
                }
            ]
        }
    """
    try:
        def get_cities_data():
            return _load_cities_by_country_cache(db)
        
        # Execute in thread pool for better async performance
        loop = asyncio.get_event_loop()
        countries_data = await loop.run_in_executor(None, get_cities_data)
        
        # Filter by country name if provided
        if request and request.country_name:
            countries_data = [
                country for country in countries_data 
                if country["country_name"].lower() == request.country_name.lower()
            ]
        # Filter by country code if provided
        elif request and request.country_code:
            countries_data = [
                country for country in countries_data 
                if country["country_code"].upper() == request.country_code.upper()
            ]
        
        return {
            "data": countries_data
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching cities by countries: {str(e)}"
        )


@router.post("/get-cities-follow-countryISO", response_model=CitiesByCountryResponse)
async def get_cities_follow_country_iso(
    request: Optional[CountryISOFilterRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Get all cities grouped by countries with optional ISO code filtering and caching.
    
    **OPTIMIZED VERSION with 1-hour caching for ultra-fast performance.**
    
    Features:
    - In-memory caching for instant subsequent requests
    - Optional country ISO code filtering
    - Optimized SQL with aggregation
    - Complete city lists per country
    - Country codes included
    - Last update timestamp
    
    Request Body (Optional):
        {
            "country_code": "AF"  // Optional: filter by ISO country code
        }
    
    Returns:
        CitiesByCountryResponse: Object containing array of countries with:
            - country_code: ISO country code
            - country_name: Name of the country
            - total_city: Number of cities in that country
            - last_update: Timestamp of data
            - city_list: Array of all city names in that country
    
    Performance:
        - First request: ~2-10 seconds (loads and caches data)
        - Subsequent requests (within 1 hour): <10ms (uses cache)
        - Cache expires after 1 hour, then refreshes automatically
    
    Example Request (All countries):
        POST /v1.0/locations/get-cities-follow-countryISO
        Body: {}
        
    Example Request (Specific country by ISO):
        POST /v1.0/locations/get-cities-follow-countryISO
        Body: {"country_code": "AF"}
        
    Example Response:
        {
            "data": [
                {
                    "country_code": "AF",
                    "country_name": "AFGHANISTAN",
                    "total_city": 3,
                    "last_update": "2025-11-11T08:04:15.267438",
                    "city_list": ["Afghanistan", "Badghis", "Kabul"]
                }
            ]
        }
    """
    try:
        def get_cities_data():
            return _load_cities_by_country_cache(db)
        
        # Execute in thread pool for better async performance
        loop = asyncio.get_event_loop()
        countries_data = await loop.run_in_executor(None, get_cities_data)
        
        # Filter by country ISO code if provided
        if request and request.country_code:
            countries_data = [
                country for country in countries_data 
                if country["country_code"].upper() == request.country_code.upper()
            ]
        
        return {
            "data": countries_data
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching cities by country ISO: {str(e)}"
        )
