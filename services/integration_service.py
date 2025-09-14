import logging
from typing import Optional
from supabase import Client
from services.onboarding_service import OnboardingService, OnboardingState

logger = logging.getLogger(__name__)


class IntegrationService:
    """Service for managing user integrations and auto-completing onboarding"""
    
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self.onboarding_service = OnboardingService(None)  # We'll pass auth_service when needed
    
    async def check_and_complete_onboarding(self, user_id: str) -> bool:
        """
        Check if user has completed both Google and Canvas integrations
        and auto-complete onboarding if they have
        
        Args:
            user_id: User's profile ID
            
        Returns:
            True if onboarding was completed, False otherwise
        """
        try:
            # Get user profile with integration status
            result = self.supabase.table("user_profiles").select(
                "id, google, canvas, onboarding_completed, email_verified"
            ).eq("id", user_id).execute()
            
            if not result.data:
                logger.error(f"User profile not found: {user_id}")
                return False
            
            profile = result.data[0]
            
            # Check if user already has onboarding completed
            if profile.get("onboarding_completed", False):
                logger.info(f"User {user_id} already has onboarding completed")
                return True
            
            # Check if user has email verified (required before checking integrations)
            if not profile.get("email_verified", False):
                logger.info(f"User {user_id} email not verified yet")
                return False
            
            # Check if both Google and Canvas integrations are complete
            google_complete = profile.get("google", False)
            canvas_complete = profile.get("canvas", False)
            
            if google_complete and canvas_complete:
                # Both integrations complete - mark onboarding as completed
                await self._complete_onboarding_with_integrations(user_id)
                logger.info(f"Auto-completed onboarding for user {user_id} - both integrations done")
                return True
            else:
                logger.info(f"User {user_id} integrations not complete - Google: {google_complete}, Canvas: {canvas_complete}")
                return False
                
        except Exception as e:
            logger.error(f"Error checking integrations for user {user_id}: {str(e)}")
            return False
    
    async def _complete_onboarding_with_integrations(self, user_id: str) -> None:
        """Complete onboarding when integrations are done"""
        try:
            update_data = {
                "onboarding_completed": True,
                "onboarding_state": OnboardingState.COMPLETED.value,
                "updated_at": "now()"
            }
            
            result = self.supabase.table("user_profiles").update(update_data).eq("id", user_id).execute()
            
            if not result.data:
                raise Exception("Failed to complete onboarding with integrations")
                
            logger.info(f"Completed onboarding for user {user_id} with integrations")
            
        except Exception as e:
            logger.error(f"Error completing onboarding with integrations: {str(e)}")
            raise
    
    async def update_integration_status(self, user_id: str, integration_type: str, status: bool) -> bool:
        """
        Update integration status and check if onboarding should be completed
        
        Args:
            user_id: User's profile ID
            integration_type: 'google' or 'canvas'
            status: True if integration is complete, False otherwise
            
        Returns:
            True if onboarding was auto-completed, False otherwise
        """
        try:
            if integration_type not in ['google', 'canvas']:
                raise ValueError(f"Invalid integration type: {integration_type}")
            
            # Update the integration status
            update_data = {integration_type: status}
            result = self.supabase.table("user_profiles").update(update_data).eq("id", user_id).execute()
            
            if not result.data:
                raise Exception(f"Failed to update {integration_type} integration status")
            
            logger.info(f"Updated {integration_type} integration to {status} for user {user_id}")
            
            # Check if onboarding should be completed
            if status:  # Only check when setting to True
                return await self.check_and_complete_onboarding(user_id)
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating integration status: {str(e)}")
            return False
