from pydantic import BaseModel
from typing import Optional

# Schema for creating a new user
class UserCreate(BaseModel):
    username: str
    email: str
    password: str

# Schema for returning user details
class User(BaseModel):
    id: int
    username: str
    email: str

    class Config:
        from_attributes = True

# Schema for token response
class Token(BaseModel):
    access_token: str
    token_type: str