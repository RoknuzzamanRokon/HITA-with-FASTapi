from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime

# --- User Schemas ---
class UserCreate(BaseModel):
    username: str = Field(..., max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    @validator("username")
    def validate_username(cls, value):
        if not value.isalnum():
            raise ValueError("Username must be alphanumeric.")
        return value

class User(BaseModel):
    id: str
    username: str
    email: EmailStr

    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: str
    username: str
    email: EmailStr
    user_status: str
    created_at: datetime

    class Config:
        orm_mode = True

# --- Hotel Schemas ---
class LocationCreate(BaseModel):
    city_name: Optional[str] = Field(None, max_length=100)
    state_name: Optional[str] = Field(None, max_length=100)
    state_code: Optional[str] = Field(None, max_length=10)
    country_name: Optional[str] = Field(None, max_length=100)
    country_code: Optional[str] = Field(None, max_length=2)
    master_city_name: Optional[str] = Field(None, max_length=100)
    city_code: Optional[str] = Field(None, max_length=50)
    city_location_id: Optional[str] = Field(None, max_length=50)

class ProviderMappingCreate(BaseModel):
    provider_name: str = Field(..., max_length=50)
    provider_id: str = Field(..., max_length=50)
    system_type: str = Field(..., max_length=20)
    vervotech_id: Optional[str] = Field(None, max_length=50)
    giata_code: Optional[str] = Field(None, max_length=50)

class ContactCreate(BaseModel):
    contact_type: str = Field(..., max_length=20)
    value: str = Field(..., max_length=255)

class ChainCreate(BaseModel):
    chain_name: Optional[str] = Field(None, max_length=100)
    chain_code: Optional[str] = Field(None, max_length=50)
    brand_name: Optional[str] = Field(None, max_length=100)



class HotelCreateDemo(BaseModel):
    ittid: str = Field(..., max_length=50)
    name: str = Field(..., max_length=255)
    latitude: Optional[str] = Field(None, max_length=50)
    longitude: Optional[str] = Field(None, max_length=50)
    rating: Optional[str] = Field(None, max_length=10)
    address_line1: Optional[str] = Field(None, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city_name: Optional[str] = Field(None, max_length=100)
    state_name: Optional[str] = Field(None, max_length=100)
    state_code: Optional[str] = Field(None, max_length=10)
    country_name: Optional[str] = Field(None, max_length=100)
    country_code: Optional[str] = Field(None, max_length=10)
    postal_code: Optional[str] = Field(None, max_length=20)
    city_code: Optional[str] = Field(None, max_length=50)
    city_location_id: Optional[str] = Field(None, max_length=50)
    master_city_name: Optional[str] = Field(None, max_length=100)
    location_ids: Optional[str] = Field(None, max_length=255)



class HotelReadDemo(HotelCreateDemo):
    id: int

    class Config:
        orm_mode = True





class HotelCreate(BaseModel):
    ittid: str = Field(..., max_length=50)
    name: str = Field(..., max_length=255)
    latitude: Optional[str] = Field(None, max_length=50)
    longitude: Optional[str] = Field(None, max_length=50)
    address_line1: Optional[str] = Field(None, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    postal_code: Optional[str] = Field(None, max_length=20)
    rating: Optional[str] = Field(None, max_length=10)
    property_type: Optional[str] = Field(None, max_length=100)
    map_status: Optional[str] = Field(None, max_length=20)
    content_update_status: Optional[str] = Field(None, max_length=20)
    locations: List[LocationCreate] = []
    provider_mappings: List[ProviderMappingCreate] = []
    contacts: List[ContactCreate] = []
    chains: List[ChainCreate] = []

class HotelRead(HotelCreate):
    id: int

    class Config:
        orm_mode = True

class HotelUpdate(BaseModel):
    ittid: Optional[str] = Field(None, max_length=50)
    name: Optional[str] = Field(None, max_length=255)
    latitude: Optional[str]
    longitude: Optional[str]
    address_line1: Optional[str]
    address_line2: Optional[str]
    postal_code: Optional[str]
    rating: Optional[str]
    property_type: Optional[str]
    map_status: Optional[str]
    content_update_status: Optional[str]
    locations: Optional[List[LocationCreate]] = []
    provider_mappings: Optional[List[ProviderMappingCreate]] = []
    contacts: Optional[List[ContactCreate]] = []
    chains: Optional[List[ChainCreate]] = []

# Rebuild forward references
UserCreate.model_rebuild()
HotelCreate.model_rebuild()
HotelCreateDemo.model_rebuild()
User.model_rebuild()
Token.model_rebuild()
UserResponse.model_rebuild()