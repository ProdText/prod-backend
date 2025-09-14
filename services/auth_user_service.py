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
        """Create a new authenticated user with profile using real email address - with concurrency safety"""
        try:
            if not phone_number:
                raise Exception("Phone number is required for user creation")
            
            if not email:
                raise Exception("Email is required for user creation")
            
            # Check for existing user by phone or email first (prevents race conditions)
            existing_by_phone = await self.get_user_by_phone_number(phone_number)
            if existing_by_phone:
                logger.info(f"User already exists with phone {phone_number}")
                return existing_by_phone
            
            existing_by_email = await self.get_user_by_email(email)
            if existing_by_email:
                logger.info(f"User already exists with email {email}")
                return existing_by_email
            
            # Create auth user with real email address
            from gotrue import AdminUserAttributes
            
            attrs = AdminUserAttributes(
                email=email,
                email_confirm=False,  # User must verify via OTP
                user_metadata={
                    "bluebubbles_guid": bluebubbles_guid,
                    "phone_number": phone_number,  # Store phone number
                    "source": "bluebubbles_webhook"
                }
            )
            
            try:
                auth_response = self.admin_auth.create_user(attrs)
                
                if not auth_response.user:
                    raise Exception("Failed to create auth user")
                
                auth_user_data = auth_response.user
            except Exception as auth_error:
                # Handle case where user exists in auth.users but not in user_profiles
                if "already been registered" in str(auth_error):
                    logger.info(f"User exists in auth.users but not in profiles, attempting to link: {email}")
                    
                    # Try to find the existing auth user by email
                    try:
                        # Get user by email from Supabase auth
                        auth_users = self.admin_auth.list_users()
                        existing_auth_user = None
                        
                        for user in auth_users:
                            if user.email == email:
                                existing_auth_user = user
                                break
                        
                        if not existing_auth_user:
                            raise Exception(f"Could not find existing auth user for email: {email}")
                        
                        auth_user_data = existing_auth_user
                        logger.info(f"Found existing auth user: {auth_user_data.id}")
                        
                    except Exception as find_error:
                        logger.error(f"Failed to find existing auth user: {str(find_error)}")
                        raise Exception(f"Email already registered but cannot access user: {str(auth_error)}")
                else:
                    raise auth_error
            
            # Handle profile creation with database trigger compatibility
            profile_result = None
            try:
                # First check if profile already exists (created by database trigger)
                existing_profile = self.supabase.table("user_profiles").select("*").eq("id", auth_user_data.id).execute()
                
                if existing_profile.data:
                    # Profile exists (created by trigger), update it with our data
                    logger.info(f"Profile exists from trigger, updating with BlueBubbles data for {auth_user_data.id}")
                    
                    profile_result = self.supabase.table("user_profiles").update({
                        "bluebubbles_guid": bluebubbles_guid,
                        "phone_number": phone_number,
                        "email": email,
                        "chat_identifier": chat_identifier,
                        "interaction_count": 1,
                        "onboarding_completed": False,
                        "onboarding_state": "not_started",
                        "email_verified": False
                    }).eq("id", auth_user_data.id).execute()
                    
                    logger.info(f"Updated existing profile for user {auth_user_data.id}")
                else:
                    # No profile exists, create new one
                    profile_result = self.supabase.table("user_profiles").insert({
                        "id": auth_user_data.id,
                        "bluebubbles_guid": bluebubbles_guid,
                        "phone_number": phone_number,
                        "email": email,
                        "chat_identifier": chat_identifier,
                        "interaction_count": 1,
                        "onboarding_completed": False,
                        "onboarding_state": "not_started",
                        "email_verified": False
                    }).execute()
                    
                    logger.info(f"Created new profile for user {auth_user_data.id}")
                    
            except Exception as profile_error:
                # Handle any remaining conflicts gracefully
                error_msg = str(profile_error).lower()
                if any(conflict in error_msg for conflict in ["already exists", "duplicate", "unique constraint"]):
                    # Another request created this user concurrently, fetch existing
                    logger.info(f"Concurrent user creation detected for {phone_number}, fetching existing")
                    existing_user = await self.get_user_by_phone_number(phone_number)
                    if existing_user:
                        return existing_user
                    
                    # Fallback: try to get by ID
                    profile_result = self.supabase.table("user_profiles").select("*").eq("id", auth_user_data.id).execute()
                    if not profile_result.data:
                        raise Exception(f"Profile creation conflict but can't retrieve: {str(profile_error)}")
                else:
                    raise profile_error
            
            if not profile_result or not profile_result.data:
                raise Exception("Failed to create user profile")
            
            logger.info(f"Created new authenticated user with GUID: {bluebubbles_guid}")
            
            return AuthUserWithProfile(
                auth_user=AuthUser(
                    id=auth_user_data.id,
                    email=email,  # Store email in auth user
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

    async def get_user_by_email(self, email: str) -> Optional[AuthUserWithProfile]:
        """Get authenticated user with profile by email address"""
        try:
            # Get user profile by email
            profile_result = self.supabase.table("user_profiles").select("*").eq(
                "email", email
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
            logger.error(f"Error getting user by email {email}: {str(e)}")
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
