from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class User(BaseModel):
    """User model for BlueBubbles integration"""
    id: Optional[str] = None
    guid: str
    phone_number: Optional[str] = None
    chat_identifier: Optional[str] = None
    onboarding_completed: bool = False
    first_interaction_at: Optional[datetime] = None
    last_interaction_at: Optional[datetime] = None
    interaction_count: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserCreate(BaseModel):
    """Model for creating a new user"""
    guid: str
    phone_number: Optional[str] = None
    chat_identifier: Optional[str] = None


class UserUpdate(BaseModel):
    """Model for updating user information"""
    onboarding_completed: Optional[bool] = None
    phone_number: Optional[str] = None
    chat_identifier: Optional[str] = None
    interaction_count: Optional[int] = None
