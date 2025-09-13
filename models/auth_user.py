from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class AuthUser(BaseModel):
    """Supabase Auth User model"""
    id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    email_confirmed_at: Optional[datetime] = None
    phone_confirmed_at: Optional[datetime] = None
    last_sign_in_at: Optional[datetime] = None


class UserProfile(BaseModel):
    """User profile model linked to auth.users"""
    id: str  # References auth.users.id
    bluebubbles_guid: str
    phone_number: Optional[str] = None
    chat_identifier: Optional[str] = None
    onboarding_completed: bool = False
    first_interaction_at: Optional[datetime] = None
    last_interaction_at: Optional[datetime] = None
    interaction_count: int = 1
    metadata: Optional[Dict[str, Any]] = {}
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserProfileCreate(BaseModel):
    """Model for creating a new user profile"""
    bluebubbles_guid: str
    phone_number: Optional[str] = None
    chat_identifier: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}


class UserProfileUpdate(BaseModel):
    """Model for updating user profile"""
    phone_number: Optional[str] = None
    chat_identifier: Optional[str] = None
    onboarding_completed: Optional[bool] = None
    interaction_count: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class AuthUserWithProfile(BaseModel):
    """Combined auth user with profile data"""
    auth_user: AuthUser
    profile: UserProfile
