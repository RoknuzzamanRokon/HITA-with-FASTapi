import pytest
import sys
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import Base, get_db
from main import app
from models import Location, Hotel

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_locations.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(scope="module")
def setup_database():
    """Setup test database with sample data"""
    Base.metadata.create_all(bind=engine)
    
    db = TestingSessionLocal()
    
    # Create sample hotels first (required for foreign key)
    sample_hotels = [
        Hotel(ittid="HTL001", name="Test Hotel 1"),
        Hotel(ittid="HTL002", name="Test Hotel 2"),
        Hotel(ittid="HTL003", name="Test Hotel 3"),
    ]
    
    for hotel in sample_hotels:
        db.add(hotel)
    
    # Create sample locations
    sample_locations = [
        Location(
            ittid="HTL001",
            city_name="New York",
            state_name="New York",
            state_code="NY",
            country_name="United States",
            country_code="US",
            master_city_name="New York City",
            city_code="NYC",
            city_location_id="LOC001"
        ),
        Location(
            ittid="HTL002",
            city_name="London",
            state_name="England",
            state_code="ENG",
            country_name="United Kingdom",
            country_code="GB",
            master_city_name="London",
            city_code="LON",
            city_location_id="LOC002"
        ),
        Location(
            ittid="HTL003",
            city_name="Paris",
            state_name="Île-de-France",
            state_code="IDF",
            country_name="France",
            country_code="FR",
            master_city_name="Paris",
            city_code="PAR",
            city_location_id="LOC003"
        ),
        Location(
            ittid="HTL001",  # Same hotel, different location
            city_name="Los Angeles",
            state_name="California",
            state_code="CA",
            country_name="United States",
            country_code="US",
            master_city_name="Los Angeles",
            city_code="LAX",
            city_location_id="LOC004"
        ),
    ]
    
    for location in sample_locations:
        db.add(location)
    
    db.commit()
    db.close()
    
    yield
    
    # Cleanup
    Base.metadata.drop_all(bind=engine)

def test_get_all_cities(setup_database):
    """Test getting all unique cities"""
    response = client.get("/v1.0/locations/cities")
    assert response.status_code == 200
    
    cities = response.json()
    city_names = [city["city_name"] for city in cities]
    
    assert "New York" in city_names
    assert "London" in city_names
    assert "Paris" in city_names
    assert "Los Angeles" in city_names
    assert len(set(city_names)) == len(city_names)  # Check uniqueness

def test_get_all_countries(setup_database):
    """Test getting all unique countries"""
    response = client.get("/v1.0/locations/countries")
    assert response.status_code == 200
    
    countries = response.json()
    country_names = [country["country_name"] for country in countries]
    
    assert "United States" in country_names
    assert "United Kingdom" in country_names
    assert "France" in country_names
    assert len(set(country_names)) == len(country_names)  # Check uniqueness

def test_get_all_country_codes(setup_database):
    """Test getting all unique country codes"""
    response = client.get("/v1.0/locations/country-codes")
    assert response.status_code == 200
    
    codes = response.json()
    country_codes = [code["country_code"] for code in codes]
    
    assert "US" in country_codes
    assert "GB" in country_codes
    assert "FR" in country_codes
    assert len(set(country_codes)) == len(country_codes)  # Check uniqueness

def test_get_cities_with_countries(setup_database):
    """Test getting cities with their countries"""
    response = client.get("/v1.0/locations/cities-with-countries")
    assert response.status_code == 200
    
    cities_countries = response.json()
    
    # Check if we have the expected combinations
    combinations = [(item["city_name"], item["country_name"]) for item in cities_countries]
    
    assert ("New York", "United States") in combinations
    assert ("London", "United Kingdom") in combinations
    assert ("Paris", "France") in combinations
    assert ("Los Angeles", "United States") in combinations

def test_search_locations_by_city(setup_database):
    """Test searching locations by city"""
    response = client.get("/v1.0/locations/search?city=New York")
    assert response.status_code == 200
    
    data = response.json()
    assert data["total"] == 1
    assert len(data["locations"]) == 1
    assert data["locations"][0]["city_name"] == "New York"

def test_search_locations_by_country(setup_database):
    """Test searching locations by country"""
    response = client.get("/v1.0/locations/search?country=United States")
    assert response.status_code == 200
    
    data = response.json()
    assert data["total"] == 2  # New York and Los Angeles
    assert len(data["locations"]) == 2

def test_search_locations_by_country_code(setup_database):
    """Test searching locations by country code"""
    response = client.get("/v1.0/locations/search?country_code=US")
    assert response.status_code == 200
    
    data = response.json()
    assert data["total"] == 2  # New York and Los Angeles
    assert len(data["locations"]) == 2

def test_search_locations_with_pagination(setup_database):
    """Test pagination in location search"""
    response = client.get("/v1.0/locations/search?limit=2&offset=0")
    assert response.status_code == 200
    
    data = response.json()
    assert data["limit"] == 2
    assert data["offset"] == 0
    assert len(data["locations"]) <= 2

def test_get_location_by_id(setup_database):
    """Test getting a specific location by ID"""
    # First, get all locations to find a valid ID
    response = client.get("/v1.0/locations/search")
    assert response.status_code == 200
    
    locations = response.json()["locations"]
    if locations:
        location_id = locations[0]["id"]
        
        # Test getting specific location
        response = client.get(f"/v1.0/locations/{location_id}")
        assert response.status_code == 200
        
        location = response.json()
        assert location["id"] == location_id

def test_get_location_by_invalid_id(setup_database):
    """Test getting location with invalid ID"""
    response = client.get("/v1.0/locations/99999")
    assert response.status_code == 404
    response_data = response.json()
    # Check if the error message is in the response, regardless of the key structure
    assert "Location not found" in str(response_data)

def test_search_locations_case_insensitive(setup_database):
    """Test case insensitive search"""
    response = client.get("/v1.0/locations/search?city=new york")
    assert response.status_code == 200
    
    data = response.json()
    assert data["total"] == 1
    assert data["locations"][0]["city_name"] == "New York"

def test_search_locations_partial_match(setup_database):
    """Test partial matching in search"""
    response = client.get("/v1.0/locations/search?city=York")
    assert response.status_code == 200
    
    data = response.json()
    assert data["total"] == 1
    assert "York" in data["locations"][0]["city_name"]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])