import logging
from typing import Optional, Dict, Any
from models.message import WebhookPayload, BlueBubblesMessage, MessageResponse
from models.auth_user import AuthUserWithProfile, UserProfile
from services.auth_user_service import AuthUserService
from services.bluebubbles_client import BlueBubblesClient
from services.onboarding_service import OnboardingService, OnboardingState

logger = logging.getLogger(__name__)


class MessageProcessor:
    """Service for processing incoming BlueBubbles messages"""
    
    def __init__(self, auth_user_service: AuthUserService, bluebubbles_client: BlueBubblesClient):
        self.auth_user_service = auth_user_service
        self.bluebubbles_client = bluebubbles_client
        self.onboarding_service = OnboardingService(auth_user_service)
    
    async def process_webhook_message(self, payload: WebhookPayload) -> MessageResponse:
        """
        Process incoming webhook message
        
        Args:
            payload: Webhook payload from BlueBubbles
            
        Returns:
            MessageResponse with processing results
        """
        try:
            message_data = payload.data
            
            # Skip messages from ourselves
            if message_data.isFromMe:
                logger.info(f"Skipping message from self: {message_data.guid}")
                return MessageResponse(
                    success=True,
                    user_guid=message_data.guid,
                    message="Skipped message from self"
                )
            
            # Extract user information first
            user_guid = self._extract_user_guid(message_data)
            phone_number = self._extract_phone_number(message_data)
            chat_identifier = self._extract_chat_identifier(message_data)
            
            # Log all webhook events for debugging
            logger.info(f"Webhook event type: {payload.type}, GUID: {message_data.guid}")
            logger.info(f"Message text: {getattr(message_data, 'text', 'No text')}")
            logger.info(f"Is from me: {getattr(message_data, 'isFromMe', 'Unknown')}")
            
            # Skip non-message events (typing indicators, read receipts, etc.)
            if payload.type != "new-message":
                logger.info(f"Skipping non-message event: {payload.type}")
                return MessageResponse(
                    success=True,
                    user_guid=user_guid,
                    message=f"Skipped {payload.type} event"
                )
            
            # Validate phone number is present for phone-only auth
            if not phone_number:
                logger.error(f"No phone number found in message {user_guid}")
                return MessageResponse(
                    success=False,
                    user_guid=user_guid,
                    message="Phone number required for authentication"
                )
            
            # Check if user already exists by phone number
            existing_user = await self.auth_user_service.get_user_by_phone_number(phone_number)
            
            if existing_user:
                # Check if user has verified email (regardless of onboarding_completed status)
                if existing_user.profile.email_verified:
                    # Email verified user - send dashboard link
                    response_text = (
                        "🔗 Access your integrations dashboard: https://dashboard.example.com\n\n"
                        "Complete your setup there to start using the service."
                    )
                else:
                    # Existing user but email not verified - continue onboarding workflow
                    response_text = await self._handle_existing_user_workflow(message_data, existing_user, phone_number, chat_identifier)
            else:
                # New user - handle onboarding workflow
                response_text = await self._handle_new_user_workflow(message_data, user_guid, phone_number, chat_identifier)
            
            if response_text:
                # Send response via BlueBubbles
                chat_identifier = self._extract_chat_identifier(message_data)
                if chat_identifier:
                    try:
                        await self.bluebubbles_client.send_text_message(
                            chat_guid=chat_identifier,
                            text=response_text
                        )
                        logger.info(f"Sent response to user {user_guid}")
                    except Exception as e:
                        logger.error(f"Failed to send response: {str(e)}")
                        raise Exception(f"Failed to send response: {str(e)}")
                else:
                    logger.error("No chat identifier found for response")
                    raise Exception("No chat identifier found for response")
            
            return MessageResponse(
                success=True,
                user_guid=user_guid,
                message="Message processed successfully"
            )
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return MessageResponse(
                success=False,
                user_guid="unknown",
                message=f"Processing error: {str(e)}"
            )
    
    def _extract_user_guid(self, message: BlueBubblesMessage) -> str:
        """Extract user GUID from message data"""
        # Use the message GUID as the primary identifier
        # For read receipts and other events without GUID, use chatGuid or handle
        if message.guid:
            return message.guid
        elif message.chatGuid:
            return f"chat_{message.chatGuid}"
        elif message.handle and message.handle.address:
            return f"handle_{message.handle.address}"
        else:
            return "unknown_guid"
    
    def _extract_phone_number(self, message: BlueBubblesMessage) -> Optional[str]:
        """Extract phone number from message handle"""
        if message.handle and message.handle.address:
            return message.handle.address
        return None
    
    def _extract_chat_identifier(self, message: BlueBubblesMessage) -> Optional[str]:
        """Extract chat identifier for sending responses"""
        if message.chats and len(message.chats) > 0:
            # Use chatIdentifier if available, fallback to guid
            chat = message.chats[0]
            chat_id = chat.chatIdentifier or chat.guid
            
            # Log for debugging
            logger.info(f"Extracted chat identifier: {chat_id}")
            
            # If chat identifier is already in proper BlueBubbles format, use it
            if chat_id and ('iMessage;-;' in chat_id or 'iMessage;+;' in chat_id):
                return chat_id
            
            # Otherwise, construct proper iMessage chat identifier from phone number
            phone = self._extract_phone_number(message)
            if phone:
                # Use iMessage;-; format for individual chats (not group chats)
                constructed_id = f"iMessage;-;{phone}"
                logger.info(f"Constructed chat ID from phone {phone}: {constructed_id}")
                return constructed_id
            
            # Fallback to original chat_id if no phone available
            return chat_id
        return None
    
    async def _handle_existing_user_workflow(self, message: BlueBubblesMessage, existing_user, phone_number: str, chat_identifier: str) -> str:
        """Handle workflow for existing user who hasn't completed verification"""
        try:
            message_text = getattr(message, 'text', '').strip()
            
            logger.info(f"Existing user workflow - State: {existing_user.profile.onboarding_state}, Message: '{message_text}'")
            
            # PRIORITY 1: Always check for OTP code first, regardless of state
            if self._is_valid_otp_code(message_text):
                logger.info(f"Valid OTP code detected: '{message_text}', proceeding to verification")
                return await self._handle_otp_verification_existing(existing_user, message_text)
            
            # PRIORITY 2: State-based logic only if not an OTP
            if existing_user.profile.onboarding_state == "awaiting_email_otp":
                # User is awaiting OTP but didn't provide valid one
                return (
                    "❌ Please enter the 6-digit verification code from your email.\n\n"
                    "Example: 123456"
                )
            
            # Check if email already exists in profile and user hasn't started OTP process
            if existing_user.profile.email and existing_user.profile.onboarding_state in ["not_started", "awaiting_email"]:
                # Email exists but not yet waiting for OTP - send OTP
                await self._update_onboarding_state(existing_user.profile.id, "awaiting_email_otp")
                
                # Send OTP to existing email
                otp_result = await self._send_email_otp(existing_user.profile.email)
                
                if otp_result["success"]:
                    return (
                        f"📧 I've sent a verification code to {existing_user.profile.email}.\n\n"
                        "Please check your email and reply with the 6-digit code you received."
                    )
                else:
                    return "❌ Sorry, I couldn't send the verification email. Please try again later."
            
            # Check current onboarding state for users without email
            if existing_user.profile.onboarding_state == "not_started":
                # User exists but hasn't started onboarding - prompt for email
                await self._update_onboarding_state(existing_user.profile.id, "awaiting_email")
                return (
                    "👋 Welcome back! To get started, I need to verify your email address.\n\n"
                    "Please reply with your email address."
                )
            elif existing_user.profile.onboarding_state == "awaiting_email":
                # User should provide email
                if self._is_valid_email(message_text):
                    return await self._handle_email_provided_existing(existing_user, message_text)
                else:
                    return (
                        "❌ Please provide a valid email address.\n\n"
                        "Example: your.email@example.com"
                    )
            else:
                # Unknown state - restart onboarding
                return (
                    "👋 Welcome! To get started, I need to verify your email address.\n\n"
                    "Please reply with your email address."
                )
                
        except Exception as e:
            logger.error(f"Error in existing user workflow: {str(e)}")
            return "❌ Sorry, there was an error processing your request. Please try again."

    async def _handle_email_provided_existing(self, existing_user, email: str) -> str:
        """Handle when existing user provides their email address"""
        try:
            # Update user's email in both auth and profile
            auth_user_id = existing_user.auth_user.id
            
            # Update email in auth.users
            self.auth_user_service.admin_auth.update_user_by_id(auth_user_id, {"email": email})
            
            # Store email in user_profiles table and update state
            await self._store_email_in_profile(auth_user_id, email)
            await self._update_onboarding_state(auth_user_id, "awaiting_email_otp")
            
            # Send OTP to the email using Supabase Auth
            otp_result = await self._send_email_otp(email)
            
            if otp_result["success"]:
                logger.info(f"Email OTP sent to {email} for existing user {auth_user_id}")
                return (
                    f"📧 Perfect! I've sent a verification code to {email}.\n\n"
                    "Please check your email and reply with the 6-digit code you received."
                )
            else:
                logger.error(f"Failed to send OTP to {email}: {otp_result.get('error')}")
                return (
                    "❌ Sorry, I couldn't send the verification email. Please try again later."
                )
                
        except Exception as e:
            logger.error(f"Error handling email for existing user: {str(e)}")
            return "❌ Sorry, there was an error processing your email. Please try again."

    async def _handle_otp_verification_existing(self, existing_user, otp_code: str) -> str:
        """Handle OTP verification for existing user"""
        try:
            # Get user's email from auth user or profile
            user_email = existing_user.auth_user.email or existing_user.profile.email
            
            if not user_email:
                return "❌ No email found for verification. Please start over."
            
            # Verify OTP with Supabase
            verification_result = await self._verify_otp_code(user_email, otp_code)
            
            if verification_result["success"]:
                # Mark email as verified but keep onboarding_completed as false
                # Dashboard will handle setting onboarding_completed to true
                await self._mark_email_verified(existing_user.profile.id)
                
                logger.info(f"Email verification completed for existing user {existing_user.profile.id}")
                return (
                    "✅ Email verified successfully! Your account is now active.\n\n"
                    "🔗 Access your integrations dashboard: https://dashboard.example.com\n\n"
                    "Complete your setup there to start using the service."
                )
            else:
                logger.error(f"OTP verification failed for existing user: {verification_result.get('error')}")
                return (
                    "❌ Invalid verification code. Please check your email and try again.\n\n"
                    "Make sure you're entering the 6-digit code exactly as received."
                )
                
        except Exception as e:
            logger.error(f"Error verifying OTP for existing user: {str(e)}")
            return "❌ Sorry, there was an error verifying your code. Please try again."

    async def _update_onboarding_state(self, user_id: str, state: str) -> None:
        """Update user's onboarding state with atomic operation"""
        try:
            # Use atomic update with WHERE clause to prevent race conditions
            result = self.auth_user_service.supabase.table("user_profiles").update({
                "onboarding_state": state,
                "updated_at": "NOW()"
            }).eq("id", user_id).execute()
            
            if not result.data:
                raise Exception("Failed to update onboarding state")
                
            logger.info(f"Updated onboarding state to {state} for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error updating onboarding state: {str(e)}")
            raise

    def _is_valid_otp_code(self, text: str) -> bool:
        """Check if text is a valid 6-digit OTP code"""
        if not text:
            return False
        text = text.strip()
        return len(text) == 6 and text.isdigit()

    def _is_valid_email(self, text: str) -> bool:
        """Check if text is a valid email address"""
        if not text:
            return False
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_pattern, text.strip()) is not None

    async def _handle_new_user_workflow(self, message: BlueBubblesMessage, user_guid: str, phone_number: str, chat_identifier: str) -> str:
        """
        Handle the complete new user onboarding workflow
        
        Steps:
        1. First message: Ask for email
        2. Email provided: Create user in Supabase and send OTP
        3. OTP provided: Verify and complete onboarding
        """
        message_text = (message.text or "").strip()
        
        # Check if this looks like an email address
        if "@" in message_text and "." in message_text.split("@")[-1]:
            # User provided email - create account and send OTP
            return await self._handle_email_provided(user_guid, phone_number, chat_identifier, message_text)
        
        # Check if this looks like an OTP code (6 digits)
        elif message_text.isdigit() and len(message_text) == 6:
            # User provided OTP - verify it
            return await self._handle_otp_provided(phone_number, message_text)
        
        # First message or invalid input - ask for email
        else:
            return (
                "👋 Welcome! To get started, I need to verify your email address.\n\n"
                "Please reply with your email address and I'll send you a verification code."
            )
    
    async def _handle_email_provided(self, user_guid: str, phone_number: str, chat_identifier: str, email: str) -> str:
        """Handle when user provides their email address"""
        try:
            # Create user in Supabase with the provided email
            user_with_profile = await self.auth_user_service.create_authenticated_user(
                bluebubbles_guid=user_guid,
                phone_number=phone_number,
                email=email,
                chat_identifier=chat_identifier
            )
            
            # Store email in user_profiles table and update state to awaiting_email_otp
            await self._store_email_in_profile(user_with_profile.profile.id, email)
            await self._update_onboarding_state(user_with_profile.profile.id, "awaiting_email_otp")
            
            # Send OTP to the email using Supabase Auth
            otp_result = await self._send_email_otp(email)
            
            if otp_result["success"]:
                logger.info(f"Email OTP sent to {email} for user {user_guid}")
                return (
                    f"📧 Perfect! I've sent a verification code to {email}.\n\n"
                    "Please check your email and reply with the 6-digit code you received."
                )
            else:
                logger.error(f"Failed to send email OTP to {email}: {otp_result.get('error')}")
                return "Sorry, I couldn't send the verification code. Please try again with a different email address."
                
        except Exception as e:
            logger.error(f"Error handling email provided: {str(e)}")
            return "Sorry, there was an error processing your email. Please try again."
    
    async def _handle_otp_provided(self, phone_number: str, otp_code: str) -> str:
        """Handle when user provides OTP code"""
        try:
            # Get user by phone number with retry logic for concurrent operations
            user_with_profile = await self._get_user_with_retry(phone_number)
            if not user_with_profile:
                logger.error(f"User lookup failed after retries for phone: {phone_number}")
                return "Sorry, I couldn't find your account. Please start over by texting me again."
            
            user_email = user_with_profile.auth_user.email
            
            # Verify OTP with Supabase Auth
            verification_result = await self._verify_otp_code(user_email, otp_code)
            
            if verification_result["success"]:
                # Mark email as verified but keep onboarding_completed as false
                # Dashboard will handle setting onboarding_completed to true
                await self._mark_email_verified(user_with_profile.profile.id)
                
                logger.info(f"Email OTP verified for user {user_with_profile.profile.id}")
                return (
                    "✅ Email verified successfully! Your account is now active.\n\n"
                    "🔗 Access your integrations dashboard: https://dashboard.example.com\n\n"
                    "Complete your setup there to start using the service."
                )
            else:
                logger.error(f"Email OTP verification failed for user {user_with_profile.profile.id}")
                return (
                    "❌ That code doesn't look right. Please check your email and try again.\n\n"
                    "Reply 'RESEND' if you need a new code."
                )
                
        except Exception as e:
            logger.error(f"Error verifying OTP: {str(e)}")
            return "Sorry, there was an error verifying your code. Please try again."
    
    async def _get_user_with_retry(self, phone_number: str, max_retries: int = 3):
        """Get user by phone number with retry logic for concurrent operations"""
        import asyncio
        
        for attempt in range(max_retries):
            try:
                logger.info(f"User lookup attempt {attempt + 1} for phone: {phone_number}")
                user_with_profile = await self.auth_user_service.get_user_by_phone_number(phone_number)
                
                if user_with_profile:
                    logger.info(f"User lookup successful on attempt {attempt + 1}")
                    return user_with_profile
                
                # If no user found, wait a bit before retry (except on last attempt)
                if attempt < max_retries - 1:
                    logger.warning(f"User not found on attempt {attempt + 1}, retrying...")
                    await asyncio.sleep(0.1 * (attempt + 1))  # Exponential backoff
                    
            except Exception as e:
                logger.error(f"User lookup error on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.1 * (attempt + 1))
                else:
                    raise e
        
        return None
    
    async def _send_email_otp(self, email: str) -> dict:
        """Send OTP to email using Supabase Auth"""
        try:
            logger.info(f"Sending OTP to email: {email}")
            
            # Use Supabase Auth client API to send OTP
            response = self.auth_user_service.supabase.auth.sign_in_with_otp({
                "email": email
            })
            
            logger.info(f"OTP send response: {response}")
            
            return {
                "success": True,
                "message": "OTP sent successfully"
            }
                
        except Exception as e:
            logger.error(f"Error sending OTP to {email}: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _verify_otp_code(self, email: str, otp_code: str) -> dict:
        """Verify OTP code with Supabase Auth"""
        try:
            logger.info(f"Attempting to verify OTP for email: {email}, code: {otp_code}")
            
            # Use Supabase Auth client API to verify OTP
            response = self.auth_user_service.supabase.auth.verify_otp({
                "email": email,
                "token": otp_code,
                "type": "email"
            })
            
            logger.info(f"OTP verification response: {response}")
            
            if response.user:
                logger.info(f"OTP verification successful for {email}")
                return {
                    "success": True,
                    "message": "OTP verified successfully"
                }
            else:
                logger.error(f"OTP verification failed - no user returned for {email}")
                return {
                    "success": False,
                    "error": "Invalid OTP code"
                }
                
        except Exception as e:
            logger.error(f"Error verifying OTP for {email}: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _store_email_in_profile(self, user_id: str, email: str) -> None:
        """Store email in user_profiles table"""
        try:
            result = self.auth_user_service.supabase.table("user_profiles").update({
                "email": email
            }).eq("id", user_id).execute()
            
            if not result.data:
                raise Exception("Failed to store email in profile")
                
            logger.info(f"Stored email {email} in profile for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error storing email in profile: {str(e)}")
            raise

    async def _mark_email_verified(self, user_id: str) -> None:
        """Mark email as verified and update onboarding state to awaiting_integrations - atomic operation"""
        try:
            from datetime import datetime
            
            # Atomic update to prevent race conditions during concurrent verifications
            update_data = {
                "email_verified": True,
                "verified_at": datetime.utcnow().isoformat(),
                "onboarding_state": "awaiting_integrations",
                "updated_at": "NOW()"
                # onboarding_completed remains false - dashboard will set this
            }
            
            # Use WHERE clause to ensure we only update if not already verified (prevents double processing)
            result = self.auth_user_service.supabase.table("user_profiles").update(update_data).eq("id", user_id).eq("email_verified", False).execute()
            
            if not result.data:
                # Check if already verified (not an error)
                existing = self.auth_user_service.supabase.table("user_profiles").select("email_verified").eq("id", user_id).execute()
                if existing.data and existing.data[0].get("email_verified"):
                    logger.info(f"User {user_id} already verified (concurrent verification)")
                    return
                else:
                    raise Exception("Failed to update email verification")
                
            logger.info(f"Marked email verified and updated state to awaiting_integrations for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error marking email verified: {str(e)}")
            raise

    async def _complete_onboarding(self, user_id: str) -> None:
        """Mark onboarding as completed for user"""
        try:
            from datetime import datetime
            
            update_data = {
                "onboarding_completed": True,
                "onboarding_state": "completed",
                "email_verified": True,
                "verified_at": datetime.utcnow().isoformat()
            }
            
            result = self.auth_user_service.supabase.table("user_profiles").update(update_data).eq("id", user_id).execute()
            
            if not result.data:
                raise Exception("Failed to update onboarding completion")
                
            logger.info(f"Completed onboarding for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error completing onboarding: {str(e)}")
            raise
