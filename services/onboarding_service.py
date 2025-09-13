import logging
from typing import Optional, Dict, Any
from enum import Enum
from models.auth_user import AuthUserWithProfile, UserProfile
from services.auth_user_service import AuthUserService

logger = logging.getLogger(__name__)


class OnboardingState(Enum):
    """Onboarding states for user flow"""
    NOT_STARTED = "not_started"
    AWAITING_OTP = "awaiting_otp"
    COMPLETED = "completed"


class OnboardingService:
    """Service for handling user onboarding with OTP verification"""
    
    def __init__(self, auth_user_service: AuthUserService):
        self.auth_user_service = auth_user_service
    
    async def start_onboarding(
        self, 
        user_with_profile: AuthUserWithProfile,
        original_phone: str
    ) -> Dict[str, Any]:
        """
        Start the onboarding process by sending OTP to user's phone
        
        Args:
            user_with_profile: User with profile data
            original_phone: The user's actual phone number for OTP
            
        Returns:
            Dict with onboarding status and next steps
        """
        try:
            # Update user profile to awaiting OTP state
            await self._update_onboarding_state(
                user_with_profile.profile.id, 
                OnboardingState.AWAITING_OTP,
                {"original_phone": original_phone}
            )
            
            # Send OTP via Supabase Auth
            otp_result = await self._send_otp(original_phone)
            
            if otp_result["success"]:
                logger.info(f"OTP sent to {original_phone} for user {user_with_profile.profile.id}")
                return {
                    "success": True,
                    "state": OnboardingState.AWAITING_OTP.value,
                    "message": "OTP sent successfully",
                    "response_text": (
                        "👋 Welcome! To get started, I need to verify your phone number.\n\n"
                        f"I've sent a verification code to {original_phone}. "
                        "Please reply with the 6-digit code you received."
                    )
                }
            else:
                logger.error(f"Failed to send OTP to {original_phone}: {otp_result.get('error')}")
                return {
                    "success": False,
                    "state": OnboardingState.NOT_STARTED.value,
                    "message": "Failed to send OTP",
                    "response_text": (
                        "Sorry, I couldn't send a verification code to your phone. "
                        "Please try again later or contact support."
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
    
    async def verify_otp(
        self, 
        user_with_profile: AuthUserWithProfile,
        otp_code: str,
        original_phone: str
    ) -> Dict[str, Any]:
        """
        Verify the OTP code provided by user
        
        Args:
            user_with_profile: User with profile data
            otp_code: The OTP code provided by user
            original_phone: The user's actual phone number
            
        Returns:
            Dict with verification status and response
        """
        try:
            # Verify OTP with Supabase Auth
            verification_result = await self._verify_otp_code(original_phone, otp_code)
            
            if verification_result["success"]:
                # Complete onboarding
                await self._update_onboarding_state(
                    user_with_profile.profile.id,
                    OnboardingState.COMPLETED,
                    {"phone_verified": True, "verified_at": "now()"}
                )
                
                # Mark onboarding as completed in auth service
                await self.auth_user_service.complete_onboarding(user_with_profile.profile.id)
                
                logger.info(f"OTP verification successful for user {user_with_profile.profile.id}")
                return {
                    "success": True,
                    "state": OnboardingState.COMPLETED.value,
                    "message": "OTP verification successful",
                    "response_text": (
                        "✅ Phone verification successful! Welcome aboard!\n\n"
                        "You're all set up and ready to go. I'm your AI assistant and I can help you with "
                        "questions, tasks, and more. What would you like to know?"
                    )
                }
            else:
                logger.warning(f"OTP verification failed for user {user_with_profile.profile.id}")
                return {
                    "success": False,
                    "state": OnboardingState.AWAITING_OTP.value,
                    "message": "Invalid OTP code",
                    "response_text": (
                        "❌ The verification code you entered is incorrect or expired.\n\n"
                        "Please check the code and try again, or reply 'RESEND' to get a new code."
                    )
                }
                
        except Exception as e:
            logger.error(f"Error verifying OTP: {str(e)}")
            return {
                "success": False,
                "state": OnboardingState.AWAITING_OTP.value,
                "message": f"OTP verification error: {str(e)}",
                "response_text": "Sorry, there was an error verifying your code. Please try again."
            }
    
    async def resend_otp(
        self, 
        user_with_profile: AuthUserWithProfile,
        original_phone: str
    ) -> Dict[str, Any]:
        """
        Resend OTP to user's phone
        
        Args:
            user_with_profile: User with profile data
            original_phone: The user's actual phone number
            
        Returns:
            Dict with resend status and response
        """
        try:
            # Send new OTP
            otp_result = await self._send_otp(original_phone)
            
            if otp_result["success"]:
                logger.info(f"OTP resent to {original_phone} for user {user_with_profile.profile.id}")
                return {
                    "success": True,
                    "state": OnboardingState.AWAITING_OTP.value,
                    "message": "OTP resent successfully",
                    "response_text": (
                        f"📱 I've sent a new verification code to {original_phone}.\n\n"
                        "Please reply with the 6-digit code you received."
                    )
                }
            else:
                logger.error(f"Failed to resend OTP to {original_phone}")
                return {
                    "success": False,
                    "state": OnboardingState.AWAITING_OTP.value,
                    "message": "Failed to resend OTP",
                    "response_text": "Sorry, I couldn't send a new verification code. Please try again later."
                }
                
        except Exception as e:
            logger.error(f"Error resending OTP: {str(e)}")
            return {
                "success": False,
                "state": OnboardingState.AWAITING_OTP.value,
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
    
    async def _send_otp(self, phone_number: str) -> Dict[str, Any]:
        """
        Send OTP via Supabase Auth API
        
        Args:
            phone_number: Phone number to send OTP to
            
        Returns:
            Dict with success status and any error info
        """
        try:
            # Use Supabase Auth API to send OTP
            response = self.auth_user_service.supabase.auth.sign_in_with_otp({
                "phone": phone_number
            })
            
            return {
                "success": True,
                "message": "OTP sent successfully"
            }
            
        except Exception as e:
            logger.error(f"Error sending OTP to {phone_number}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _verify_otp_code(self, phone_number: str, otp_code: str) -> Dict[str, Any]:
        """
        Verify OTP code with Supabase Auth
        
        Args:
            phone_number: Phone number that received the OTP
            otp_code: The OTP code to verify
            
        Returns:
            Dict with verification result
        """
        try:
            # Use Supabase Auth API to verify OTP
            response = self.auth_user_service.supabase.auth.verify_otp({
                "phone": phone_number,
                "token": otp_code,
                "type": "sms"
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
            logger.error(f"Error verifying OTP for {phone_number}: {str(e)}")
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
