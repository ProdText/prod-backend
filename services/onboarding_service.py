from enum import Enum
from typing import Dict, Any, Optional
import logging
from supabase import Client
from .auth_user_service import AuthUserService, AuthUserWithProfile
from models.user import UserProfile

logger = logging.getLogger(__name__)


class OnboardingState(Enum):
    NOT_STARTED = "not_started"
    AWAITING_EMAIL = "awaiting_email"
    AWAITING_EMAIL_OTP = "awaiting_email_otp"
    COMPLETED = "completed"


class OnboardingService:
    """Service for handling user onboarding with OTP verification"""
    
    def __init__(self, auth_user_service: AuthUserService):
        self.auth_user_service = auth_user_service
    
    async def start_onboarding(
        self, 
        user_with_profile: AuthUserWithProfile
    ) -> Dict[str, Any]:
        """
        Start the onboarding process by asking for user's email
        
        Args:
            user_with_profile: User with profile data
            
        Returns:
            Dict with onboarding status and next steps
        """
        try:
            # Update user onboarding state to awaiting email
            await self._update_onboarding_state(
                user_with_profile.profile.id, 
                OnboardingState.AWAITING_EMAIL
            )
            
            logger.info(f"Started onboarding for user {user_with_profile.profile.id}")
            return {
                "success": True,
                "state": OnboardingState.AWAITING_EMAIL.value,
                "message": "Onboarding started - awaiting email",
                "response_text": (
                    "👋 Welcome! To get started, I need to verify your email address.\n\n"
                    "Please reply with your email address and I'll send you a verification code."
                )
            }
                
        except Exception as e:
            logger.error(f"Error starting onboarding: {str(e)}")
            return {
                "success": False,
                "state": OnboardingState.NOT_STARTED.value,
                "message": f"Onboarding error: {str(e)}",
                "response_text": "Sorry, there was an error starting the verification process. Please try again."
            }
    
    async def send_email_otp(
        self, 
        user_with_profile: AuthUserWithProfile,
        user_email: str
    ) -> Dict[str, Any]:
        """
        Send email OTP to user's email address and update user with real email
        
        Args:
            user_with_profile: User with profile data
            user_email: The user's email address for OTP
            
        Returns:
            Dict with OTP send status and response
        """
        try:
            # First, update the auth user with the real email address
            await self._update_user_email(user_with_profile.auth_user.id, user_email)
            
            # Update user onboarding state with email
            await self._update_onboarding_state(
                user_with_profile.profile.id, 
                OnboardingState.AWAITING_EMAIL_OTP,
                {"email": user_email}
            )
            
            # Send OTP via Supabase Auth
            otp_result = await self._send_email_otp(user_email)
            
            if otp_result["success"]:
                logger.info(f"Email OTP sent to {user_email} for user {user_with_profile.profile.id}")
                return {
                    "success": True,
                    "state": OnboardingState.AWAITING_EMAIL_OTP.value,
                    "message": "Email OTP sent successfully",
                    "response_text": (
                        f"📧 Perfect! I've sent a verification code to {user_email}.\n\n"
                        "Please check your email and reply with the 6-digit code you received."
                    )
                }
            else:
                logger.error(f"Failed to send email OTP to {user_email}: {otp_result.get('error')}")
                return {
                    "success": False,
                    "state": OnboardingState.AWAITING_EMAIL.value,
                    "message": f"Email OTP send error: {otp_result.get('error')}",
                    "response_text": "Sorry, there was an error sending the verification code. Please check your email address and try again."
                }
                
        except Exception as e:
            logger.error(f"Error sending email OTP: {str(e)}")
            return {
                "success": False,
                "state": OnboardingState.AWAITING_EMAIL.value,
                "message": f"Email OTP error: {str(e)}",
                "response_text": "Sorry, there was an error sending the verification code. Please try again."
            }
    
    async def verify_otp(
        self, 
        user_with_profile: AuthUserWithProfile,
        otp_code: str,
        user_email: str
    ) -> Dict[str, Any]:
        """
        Verify the OTP code provided by user
        
        Args:
            user_with_profile: User with profile data
            otp_code: The OTP code provided by user
            user_email: The user's email address
            
        Returns:
            Dict with verification status and response
        """
        try:
            # Verify OTP with Supabase Auth
            verification_result = await self._verify_otp_code(user_email, otp_code)
            
            if verification_result["success"]:
                # Complete onboarding
                await self._complete_onboarding(user_with_profile.profile.id)
                
                logger.info(f"Email OTP verified for user {user_with_profile.profile.id}")
                return {
                    "success": True,
                    "state": OnboardingState.COMPLETED.value,
                    "message": "Email OTP verified successfully",
                    "response_text": (
                        "🎉 Perfect! Your email has been verified.\n\n"
                        "You're all set up! I can now help you with your messages and queries. "
                        "What would you like to know?"
                    )
                }
            else:
                logger.error(f"Email OTP verification failed for user {user_with_profile.profile.id}")
                return {
                    "success": False,
                    "state": OnboardingState.AWAITING_EMAIL_OTP.value,
                    "message": "Email OTP verification failed",
                    "response_text": (
                        "❌ That code doesn't look right. Please check your email and try again.\n\n"
                        "Reply 'RESEND' if you need a new code."
                    )
                }
                
        except Exception as e:
            logger.error(f"Error verifying email OTP: {str(e)}")
            return {
                "success": False,
                "state": OnboardingState.AWAITING_EMAIL_OTP.value,
                "message": f"Email OTP verification error: {str(e)}",
                "response_text": "Sorry, there was an error verifying your code. Please try again."
            }
    
    async def resend_otp(
        self, 
        user_with_profile: AuthUserWithProfile,
        user_email: str
    ) -> Dict[str, Any]:
        """
        Resend OTP to user's email
        
        Args:
            user_with_profile: User with profile data
            user_email: The user's email address
            
        Returns:
            Dict with resend status and response
        """
        try:
            # Send new OTP
            otp_result = await self._send_email_otp(user_email)
            
            if otp_result["success"]:
                logger.info(f"Email OTP resent to {user_email} for user {user_with_profile.profile.id}")
                return {
                    "success": True,
                    "state": OnboardingState.AWAITING_EMAIL_OTP.value,
                    "message": "Email OTP resent successfully",
                    "response_text": (
                        f"📧 I've sent a new verification code to {user_email}.\n\n"
                        "Please reply with the 6-digit code you received."
                    )
                }
            else:
                logger.error(f"Failed to resend email OTP to {user_email}")
                return {
                    "success": False,
                    "state": OnboardingState.AWAITING_EMAIL_OTP.value,
                    "message": "Failed to resend OTP",
                    "response_text": "Sorry, I couldn't send a new verification code. Please try again later."
                }
                
        except Exception as e:
            logger.error(f"Error resending OTP: {str(e)}")
            return {
                "success": False,
                "state": OnboardingState.AWAITING_EMAIL_OTP.value,
                "message": f"OTP resend error: {str(e)}",
                "response_text": "Sorry, there was an error sending a new code. Please try again."
            }
    
    def get_onboarding_state(self, user_profile: UserProfile) -> OnboardingState:
        """
        Get current onboarding state for user
        
        Args:
            user_profile: User profile data
            
        Returns:
            Current onboarding state
        """
        if user_profile.onboarding_completed:
            return OnboardingState.COMPLETED
        
        # Check if user is in the middle of OTP verification
        # This would be stored in user metadata or profile data
        if hasattr(user_profile, 'onboarding_state'):
            try:
                return OnboardingState(user_profile.onboarding_state)
            except ValueError:
                pass
        
        return OnboardingState.NOT_STARTED
    
    async def _send_email_otp(self, email: str) -> Dict[str, Any]:
        """
        Send OTP via Supabase Auth API to email
        
        Args:
            email: Email address to send OTP to
            
        Returns:
            Dict with success status and any error info
        """
        try:
            # Use Supabase Auth API to send email OTP
            response = self.auth_user_service.supabase.auth.sign_in_with_otp({
                "email": email
            })
            
            return {
                "success": True,
                "message": "Email OTP sent successfully"
            }
            
        except Exception as e:
            logger.error(f"Error sending email OTP to {email}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _verify_otp_code(self, email: str, otp_code: str) -> Dict[str, Any]:
        """
        Verify OTP code with Supabase Auth
        
        Args:
            email: Email address that received the OTP
            otp_code: The OTP code to verify
            
        Returns:
            Dict with verification result
        """
        try:
            # Use Supabase Auth API to verify OTP
            response = self.auth_user_service.supabase.auth.verify_otp({
                "email": email,
                "token": otp_code,
                "type": "email"
            })
            
            if response.user:
                return {
                    "success": True,
                    "message": "OTP verified successfully"
                }
            else:
                return {
                    "success": False,
                    "error": "Invalid OTP code"
                }
                
        except Exception as e:
            logger.error(f"Error verifying OTP for {email}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _update_onboarding_state(
        self, 
        profile_id: str, 
        state: OnboardingState,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Update user's onboarding state in the database
        
        Args:
            profile_id: User profile ID
            state: New onboarding state
            additional_data: Additional data to store
        """
        try:
            update_data = {
                "onboarding_state": state.value,
                "updated_at": "now()"
            }
            
            if additional_data:
                update_data.update(additional_data)
            
            # Update user profile with new state
            result = self.auth_user_service.supabase.table("user_profiles").update(
                update_data
            ).eq("id", profile_id).execute()
            
            if not result.data:
                raise Exception("Failed to update onboarding state")
                
            logger.info(f"Updated onboarding state to {state.value} for profile {profile_id}")
            
        except Exception as e:
            logger.error(f"Error updating onboarding state: {str(e)}")
            raise
    
    async def _update_user_email(self, user_id: str, email: str) -> None:
        """
        Update the auth user's email address
        
        Args:
            user_id: Auth user ID
            email: New email address
        """
        try:
            # Update the auth user's email using admin API
            self.auth_user_service.admin_auth.update_user_by_id(user_id, {
                "email": email
            })
            logger.info(f"Updated user {user_id} email to {email}")
        except Exception as e:
            logger.error(f"Error updating user email: {str(e)}")
            raise
    
    async def _complete_onboarding(self, user_id: str) -> None:
        """Mark onboarding as completed for user"""
        try:
            update_data = {
                "onboarding_completed": True,
                "onboarding_state": OnboardingState.COMPLETED.value,
                "email_verified": True,
                "verified_at": "now()"
            }
            
            result = self.auth_user_service.supabase.table("user_profiles").update(update_data).eq("id", user_id).execute()
            
            if not result.data:
                raise Exception("Failed to update onboarding completion")
                
        except Exception as e:
            logger.error(f"Error completing onboarding: {str(e)}")
            raise
