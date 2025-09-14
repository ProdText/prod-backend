import logging
from typing import Optional, Dict, Any
from datetime import datetime
from supabase import Client
from supabase.lib.client_options import ClientOptions
from models.auth_user import AuthUser, UserProfileCreate, UserProfileUpdate
from models.user import UserProfile

class AuthUserWithProfile:
    """Combined auth user with profile data"""
    def __init__(self, auth_user, profile):
        self.auth_user = auth_user
        self.user = auth_user  # For backward compatibility
        self.profile = profile

logger = logging.getLogger(__name__)


class AuthUserService:
    """Service for managing users with Supabase Auth integration"""
    
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        # Access the admin auth API for server-side operations
        self.admin_auth = supabase_client.auth.admin
    
    async def get_or_create_user_by_guid(
        self, 
        bluebubbles_guid: str, 
        phone_number: Optional[str] = None, 
        chat_identifier: Optional[str] = None
    ) -> AuthUserWithProfile:
        """
        Get existing user by BlueBubbles GUID or create a new authenticated user
        
        Args:
            bluebubbles_guid: BlueBubbles message/chat GUID
            phone_number: Optional phone number from handle
            chat_identifier: Optional chat identifier
            
        Returns:
            AuthUserWithProfile object
        """
        try:
            # First, try to find existing profile by BlueBubbles GUID
            profile_result = self.supabase.table("user_profiles").select("*").eq(
                "bluebubbles_guid", bluebubbles_guid
            ).execute()
            
            if profile_result.data:
                # User exists, update interaction
                profile_data = profile_result.data[0]
                updated_profile = await self.update_user_interaction(profile_data["id"])
                
                # Get the auth user
                auth_user = await self.get_auth_user(profile_data["id"])
                
                return AuthUserWithProfile(
                    auth_user=auth_user,
                    profile=UserProfile(**updated_profile)
                )
            else:
                # Create new user with auth and profile
                return await self.create_authenticated_user(
                    bluebubbles_guid, phone_number, chat_identifier
                )
                
        except Exception as e:
            logger.error(f"Error getting or creating user {bluebubbles_guid}: {str(e)}")
            raise
    
    async def create_authenticated_user(
        self, 
        bluebubbles_guid: str, 
        phone_number: str,
        email: str,
        chat_identifier: Optional[str] = None
    ) -> AuthUserWithProfile:
        """Create a new authenticated user with profile using real email address"""
        try:
            if not phone_number:
                raise Exception("Phone number is required for user creation")
            
            if not email:
                raise Exception("Email is required for user creation")
            
            # Create auth user with real email address
            auth_response = self.admin_auth.create_user({
                "email": email,
                "email_confirm": False,  # User must verify via OTP
                "user_metadata": {
                    "bluebubbles_guid": bluebubbles_guid,
                    "phone_number": phone_number,  # Store phone number
                    "source": "bluebubbles_webhook"
                }
            })
            
            if not auth_response.user:
                raise Exception("Failed to create auth user")
            
            auth_user_data = auth_response.user
            
            # Create user profile - handle potential trigger conflicts
            try:
                profile_result = self.supabase.table("user_profiles").insert({
                    "id": auth_user_data.id,
                    "bluebubbles_guid": bluebubbles_guid,
                    "phone_number": phone_number,
                    "chat_identifier": chat_identifier,
                    "interaction_count": 1,
                    "onboarding_completed": False,
                    "onboarding_state": "not_started",
                    "email_verified": False
                }).execute()
            except Exception as profile_error:
                # If profile creation fails due to existing record, try to get it
                if "already exists" in str(profile_error):
                    profile_result = self.supabase.table("user_profiles").select("*").eq("id", auth_user_data.id).execute()
                    if not profile_result.data:
                        # If we can't find it, something is wrong
                        raise Exception(f"Profile exists but can't be retrieved: {str(profile_error)}")
                else:
                    raise profile_error
            
            if not profile_result.data:
                raise Exception("Failed to create user profile")
            
            logger.info(f"Created new authenticated user with GUID: {bluebubbles_guid}")
            
            return AuthUserWithProfile(
                auth_user=AuthUser(
                    id=auth_user_data.id,
                    email=None,  # No email for phone-only auth
                    phone=auth_user_data.phone,
                    created_at=auth_user_data.created_at,
                    updated_at=auth_user_data.updated_at
                ),
                profile=UserProfile(**profile_result.data[0])
            )
            
        except Exception as e:
            logger.error(f"Error creating authenticated user: {str(e)}")
            raise
    
    def _normalize_phone_number(self, phone_number: str) -> str:
        """
        Normalize phone number to E.164 format
        
        Args:
            phone_number: Raw phone number from BlueBubbles
            
        Returns:
            E.164 formatted phone number
        """
        if not phone_number:
            return ""
        
        # Remove all non-digit characters
        digits_only = ''.join(filter(str.isdigit, phone_number))
        
        # Handle US numbers
        if len(digits_only) == 10:
            return f"+1{digits_only}"
        elif len(digits_only) == 11 and digits_only.startswith('1'):
            return f"+{digits_only}"
        elif phone_number.startswith('+'):
            return phone_number
        else:
            # Default to US format
            return f"+1{digits_only[-10:]}" if len(digits_only) >= 10 else f"+1{digits_only}"
    
    async def get_auth_user(self, user_id: str) -> AuthUser:
        """Get auth user by ID"""
        try:
            auth_response = self.admin_auth.get_user_by_id(user_id)
            
            if not auth_response.user:
                raise Exception(f"Auth user not found: {user_id}")
            
            user_data = auth_response.user
            return AuthUser(
                id=user_data.id,
                email=None,  # No email for phone-only auth
                phone=user_data.phone,
                created_at=user_data.created_at,
                updated_at=user_data.updated_at,
                email_confirmed_at=None,  # No email confirmation
                phone_confirmed_at=user_data.phone_confirmed_at,
                last_sign_in_at=user_data.last_sign_in_at
            )
            
        except Exception as e:
            logger.error(f"Error getting auth user {user_id}: {str(e)}")
            raise
    
    async def update_user_interaction(self, user_id: str) -> Dict[str, Any]:
        """Update user's last interaction time and increment count"""
        try:
            # Update profile with new interaction
            result = self.supabase.table("user_profiles").update({
                "last_interaction_at": datetime.utcnow().isoformat(),
                "interaction_count": self.supabase.rpc("increment", {"table_name": "user_profiles", "row_id": user_id, "column_name": "interaction_count"})
            }).eq("id", user_id).execute()
            
            if result.data:
                return result.data[0]
            else:
                # Fallback: simple update without RPC
                result = self.supabase.table("user_profiles").update({
                    "last_interaction_at": datetime.utcnow().isoformat()
                }).eq("id", user_id).execute()
                
                return result.data[0] if result.data else {}
                
        except Exception as e:
            logger.error(f"Error updating user interaction: {str(e)}")
            # Return existing data on error
            result = self.supabase.table("user_profiles").select("*").eq("id", user_id).execute()
            return result.data[0] if result.data else {}
    
    async def complete_onboarding(self, user_id: str) -> UserProfile:
        """Mark user's onboarding as completed"""
        try:
            result = self.supabase.table("user_profiles").update({
                "onboarding_completed": True
            }).eq("id", user_id).execute()
            
            if result.data:
                logger.info(f"Completed onboarding for user: {user_id}")
                return UserProfile(**result.data[0])
            else:
                raise Exception("Failed to complete onboarding")
                
        except Exception as e:
            logger.error(f"Error completing onboarding: {str(e)}")
            raise
    
    async def get_user_profile_by_guid(self, bluebubbles_guid: str) -> Optional[UserProfile]:
        """Get user profile by BlueBubbles GUID"""
        try:
            result = self.supabase.table("user_profiles").select("*").eq(
                "bluebubbles_guid", bluebubbles_guid
            ).execute()
            
            if result.data:
                return UserProfile(**result.data[0])
            return None
            
        except Exception as e:
            logger.error(f"Error getting user profile by GUID {bluebubbles_guid}: {str(e)}")
            return None
    
    async def get_user_by_phone_number(self, phone_number: str) -> Optional[AuthUserWithProfile]:
        """Get authenticated user with profile by phone number"""
        try:
            # Get user profile by phone number
            profile_result = self.supabase.table("user_profiles").select("*").eq(
                "phone_number", phone_number
            ).execute()
            
            if not profile_result.data:
                return None
            
            profile_data = profile_result.data[0]
            user_profile = UserProfile(**profile_data)
            
            # Get auth user data
            auth_user_result = self.admin_auth.get_user_by_id(profile_data["id"])
            if not auth_user_result.user:
                return None
            
            return AuthUserWithProfile(
                auth_user=auth_user_result.user,
                profile=user_profile
            )
            
        except Exception as e:
            logger.error(f"Error getting user by phone number {phone_number}: {str(e)}")
            return None

    async def get_user_by_guid(self, bluebubbles_guid: str) -> Optional[AuthUserWithProfile]:
        """Get authenticated user with profile by BlueBubbles GUID"""
        try:
            # Get user profile first
            profile_result = self.supabase.table("user_profiles").select("*").eq(
                "bluebubbles_guid", bluebubbles_guid
            ).execute()
            
            if not profile_result.data:
                return None
            
            profile_data = profile_result.data[0]
            user_profile = UserProfile(**profile_data)
            
            # Get auth user data
            auth_user_result = self.admin_auth.get_user_by_id(profile_data["id"])
            if not auth_user_result.user:
                return None
            
            return AuthUserWithProfile(
                auth_user=auth_user_result.user,
                profile=user_profile
            )
            
        except Exception as e:
            logger.error(f"Error getting user by GUID {bluebubbles_guid}: {str(e)}")
            return None

    async def update_user_profile(self, user_id: str, updates: UserProfileUpdate) -> UserProfile:
        """Update user profile"""
        try:
            update_data = {k: v for k, v in updates.dict().items() if v is not None}
            
            result = self.supabase.table("user_profiles").update(update_data).eq("id", user_id).execute()
            
            if result.data:
                return UserProfile(**result.data[0])
            else:
                raise Exception("Failed to update user profile")
                
        except Exception as e:
            logger.error(f"Error updating user profile: {str(e)}")
            raise
