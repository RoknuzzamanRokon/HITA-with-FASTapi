from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import distinct
from typing import List, Optional
from database import get_db
from models import Location
from pydantic import BaseModel

# Router setup
router = APIRouter(
    prefix="/v1.0/locations",
    tags=["Locations"],
    responses={404: {"description": "Not found"}},
)

# Response Models
class CityResponse(BaseModel):
    city_name: str
    
    class Config:
        from_attributes = True

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

class CountryCodeResponse(BaseModel):
    country_code: str
    
    class Config:
        from_attributes = True

class CountryCodesListResponse(BaseModel):
    total_country_code: int
    country_code: List[str]
    
    class Config:
        from_attributes = True

class CityWithCountryResponse(BaseModel):
    city_name: str
    country_name: str
    
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


@router.get("/cities", response_model=CitiesListResponse)
async def get_all_cities(db: Session = Depends(get_db)):
    """
    Get all unique cities from locations in a consolidated format.
    
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
    """
    try:
        cities = db.query(distinct(Location.city_name)).filter(
            Location.city_name.isnot(None),
            Location.city_name != ""
        ).all()
        
        # Extract city names and filter out None values
        city_names = [city[0] for city in cities if city[0]]
        
        return {
            "total_city": len(city_names),
            "city_name": city_names
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching cities: {str(e)}")


@router.get("/countries", response_model=CountriesListResponse)
async def get_all_countries(db: Session = Depends(get_db)):
    """
    Get all unique countries from locations in a consolidated format.
    
    Returns a single object containing the total count of countries and 
    an array of all unique country names.
    
    Returns:
        CountriesListResponse: Object containing:
            - total_country: Total number of unique countries
            - country_name: Array of all unique country names
    
    Example Response:
        {
            "total_country": 195,
            "country_name": ["United States", "Canada", "United Kingdom", "France"]
        }
    """
    try:
        countries = db.query(distinct(Location.country_name)).filter(
            Location.country_name.isnot(None),
            Location.country_name != ""
        ).all()
        
        # Extract country names and filter out None values
        country_names = [country[0] for country in countries if country[0]]
        
        return {
            "total_country": len(country_names),
            "country_name": country_names
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching countries: {str(e)}")


@router.get("/country_codes", response_model=CountryCodesListResponse)
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


@router.get("/cities_with_countries", response_model=List[CityWithCountryResponse])
async def get_cities_with_countries(db: Session = Depends(get_db)):
    """
    Get all unique cities with their corresponding countries
    """
    try:
        cities_countries = db.query(
            Location.city_name, Location.country_name
        ).distinct().filter(
            Location.city_name.isnot(None),
            Location.city_name != "",
            Location.country_name.isnot(None),
            Location.country_name != ""
        ).all()
        
        return [
            {"city_name": city[0], "country_name": city[1]} 
            for city in cities_countries if city[0] and city[1]
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching cities with countries: {str(e)}")


@router.get("/search")
async def search_locations(
    city: Optional[str] = Query(None, description="Filter by city name"),
    country: Optional[str] = Query(None, description="Filter by country name"),
    country_code: Optional[str] = Query(None, description="Filter by country code"),
    state: Optional[str] = Query(None, description="Filter by state name"),
    limit: int = Query(100, ge=1, le=1000, description="Limit number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
):
    """
    Search locations with various filters
    """
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


@router.get("/{location_id}", response_model=LocationDetailResponse)
async def get_location_by_id(location_id: int, db: Session = Depends(get_db)):
    """
    Get a specific location by ID
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