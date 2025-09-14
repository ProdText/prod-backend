import logging
from models.auth_user import AuthUserWithProfile

logger = logging.getLogger(__name__)

class OnboardingHandlers:

    async def _handle_state_not_started(self, user: AuthUserWithProfile) -> str:
        await self._update_onboarding_state(user.profile.id, 'awaiting_email')
        return (
            "👋 Welcome! To get started, I need to verify your email address.\n\n"
            "Please reply with your email address."
        )

    async def _handle_state_awaiting_email(self, user: AuthUserWithProfile, message_text: str) -> str:
        if not self._is_valid_email(message_text):
            return "❌ Please provide a valid email address. Example: your.email@example.com"

        try:
            # This is the first time we have an email, so create the auth user.
            auth_user = await self.auth_user_service.create_auth_user_for_profile(user.profile, message_text)
            
            # Send OTP
            otp_result = await self._send_email_otp(auth_user.email)
            if not otp_result["success"]:
                return "❌ Sorry, I couldn't send the verification email. Please try again later."

            # Update state
            await self._update_onboarding_state(user.profile.id, 'awaiting_email_otp')

            return (
                f"📧 Perfect! I've sent a verification code to {auth_user.email}.\n\n"
                "Please check your email and reply with the 6-digit code you received."
            )
        except Exception as e:
            logger.error(f"Error creating auth user or sending OTP: {e}")
            return "❌ Sorry, there was an error processing your email. Please try again."

    async def _handle_state_awaiting_otp(self, user: AuthUserWithProfile, message_text: str) -> str:
        if not self._is_valid_otp_code(message_text):
            return "❌ Please enter the 6-digit verification code from your email. Example: 123456"

        try:
            user_email = user.auth_user.email
            if not user_email:
                # This case should be rare, but we handle it by resetting.
                logger.error(f"User {user.profile.id} in state awaiting_otp has no email.")
                return await self._handle_state_not_started(user)

            verification_result = await self._verify_otp_code(user_email, message_text)
            if not verification_result["success"]:
                return "❌ Invalid verification code. Please check your email and try again."

            # Verification successful
            await self._mark_email_verified(user.profile.id)
            await self._update_onboarding_state(user.profile.id, 'completed')
            
            return (
                "✅ Email verified successfully! Your account is now active.\n\n"
                "🔗 Access your integrations dashboard: https://dashboard.example.com\n\n"
                "Complete your setup there to start using the service."
            )
        except Exception as e:
            logger.error(f"Error verifying OTP for user {user.profile.id}: {e}")
            return "❌ Sorry, there was an error verifying your code. Please try again."

    async def _handle_state_completed(self, user: AuthUserWithProfile) -> str:
        return (
            "🔗 You're all set! Access your integrations dashboard here:\n\n"
            "https://dashboard.example.com"
        )
