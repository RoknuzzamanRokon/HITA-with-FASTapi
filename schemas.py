from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

# --- User Schemas ---
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

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
class HotelBase(BaseModel):
    ittid: str = Field(..., max_length=50)
    name: str = Field(..., max_length=255)
    latitude: Optional[str] = Field(None, max_length=50)
    longitude: Optional[str] = Field(None, max_length=50)
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
    akbar_status: bool = Field(...)

class HotelCreate(HotelBase):
    pass

class HotelUpdate(BaseModel):
    ittid: Optional[str] = Field(None, max_length=50)
    name: Optional[str] = Field(None, max_length=255)
    latitude: Optional[str]
    longitude: Optional[str]
    address_line1: Optional[str]
    address_line2: Optional[str]
    city_name: Optional[str]
    state_name: Optional[str]
    state_code: Optional[str]
    country_name: Optional[str]
    country_code: Optional[str]
    postal_code: Optional[str]
    city_code: Optional[str]
    city_location_id: Optional[str]
    master_city_name: Optional[str]
    location_ids: Optional[str]
    akbar_status: Optional[bool]

class HotelRead(HotelBase):
    id: int

    class Config:
        orm_mode = True


# Rebuild forward references
UserCreate.model_rebuild()
HotelCreate.model_rebuild()
User.model_rebuild()
Token.model_rebuild()
UserResponse.model_rebuild()