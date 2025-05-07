from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# Schema for creating a new user
class UserCreate(BaseModel):
    username: str
    email: str
    password: str

# Schema for returning user details
class User(BaseModel):
    id: str
    username: str
    email: str

    class Config:
        from_attributes = True

# Schema for token response
class Token(BaseModel):
    access_token: str
    token_type: str

class HotelCreate(BaseModel):
    name: str
    location: str
    price: int

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    user_status: str
    created_at: datetime

    class Config:
        orm_mode = True


# Rebuild forward references
UserCreate.model_rebuild()
HotelCreate.model_rebuild()
User.model_rebuild()
Token.model_rebuild()
UserResponse.model_rebuild()