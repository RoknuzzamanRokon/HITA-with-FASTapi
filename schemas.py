from pydantic import BaseModel
from typing import Optional

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


# Rebuild forward references
UserCreate.model_rebuild()
HotelCreate.model_rebuild()
User.model_rebuild()
Token.model_rebuild()