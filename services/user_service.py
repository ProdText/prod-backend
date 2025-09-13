import logging
from typing import Optional, Dict, Any
from datetime import datetime
from supabase import Client
from models.user import User, UserCreate, UserUpdate

logger = logging.getLogger(__name__)


class UserService:
    """Service for managing users in Supabase"""
    
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
    
    async def get_or_create_user(self, guid: str, phone_number: Optional[str] = None, chat_identifier: Optional[str] = None) -> User:
        """
        Get existing user by GUID or create a new one
        
        Args:
            guid: BlueBubbles message/chat GUID
            phone_number: Optional phone number from handle
            chat_identifier: Optional chat identifier
            
        Returns:
            User object
        """
        try:
            # Try to get existing user
            result = self.supabase.table("users").select("*").eq("guid", guid).execute()
            
            if result.data:
                # User exists, update last interaction
                user_data = result.data[0]
                updated_user = await self.update_user_interaction(user_data["id"])
                return User(**updated_user)
            else:
                # Create new user
                user_create = UserCreate(
                    guid=guid,
                    phone_number=phone_number,
                    chat_identifier=chat_identifier
                )
                return await self.create_user(user_create)
                
        except Exception as e:
            logger.error(f"Error getting or creating user {guid}: {str(e)}")
            raise
    
    async def create_user(self, user_data: UserCreate) -> User:
        """Create a new user"""
        try:
            result = self.supabase.table("users").insert({
                "guid": user_data.guid,
                "phone_number": user_data.phone_number,
                "chat_identifier": user_data.chat_identifier,
                "onboarding_completed": False,
                "interaction_count": 1
            }).execute()
            
            if result.data:
                logger.info(f"Created new user with GUID: {user_data.guid}")
                return User(**result.data[0])
            else:
                raise Exception("Failed to create user")
                
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            raise
    
    async def update_user_interaction(self, user_id: str) -> Dict[str, Any]:
        """Update user's last interaction time and increment count"""
        try:
            result = self.supabase.table("users").update({
                "last_interaction_at": datetime.utcnow().isoformat(),
                "interaction_count": self.supabase.rpc("increment_interaction_count", {"user_id": user_id})
            }).eq("id", user_id).execute()
            
            if result.data:
                return result.data[0]
            else:
                raise Exception("Failed to update user interaction")
                
        except Exception as e:
            logger.error(f"Error updating user interaction: {str(e)}")
            # Fallback: simple update without RPC
            result = self.supabase.table("users").update({
                "last_interaction_at": datetime.utcnow().isoformat()
            }).eq("id", user_id).execute()
            
            return result.data[0] if result.data else {}
    
    async def complete_onboarding(self, user_id: str) -> User:
        """Mark user's onboarding as completed"""
        try:
            result = self.supabase.table("users").update({
                "onboarding_completed": True
            }).eq("id", user_id).execute()
            
            if result.data:
                logger.info(f"Completed onboarding for user: {user_id}")
                return User(**result.data[0])
            else:
                raise Exception("Failed to complete onboarding")
                
        except Exception as e:
            logger.error(f"Error completing onboarding: {str(e)}")
            raise
    
    async def get_user_by_guid(self, guid: str) -> Optional[User]:
        """Get user by GUID"""
        try:
            result = self.supabase.table("users").select("*").eq("guid", guid).execute()
            
            if result.data:
                return User(**result.data[0])
            return None
            
        except Exception as e:
            logger.error(f"Error getting user by GUID {guid}: {str(e)}")
            return None
