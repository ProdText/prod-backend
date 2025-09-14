import logging
from typing import Optional, Dict, Any, List
from models.message import WebhookPayload, BlueBubblesMessage, MessageResponse
from models.auth_user import AuthUserWithProfile, UserProfile
from services.auth_user_service import AuthUserService
from services.bluebubbles_client import BlueBubblesClient
from services.onboarding_service import OnboardingService, OnboardingState
from services.ai_conversation_service import AIConversationService

logger = logging.getLogger(__name__)


class MessageProcessor:
    """Service for processing incoming BlueBubbles messages"""
    
    def __init__(self, auth_user_service: AuthUserService, bluebubbles_client: BlueBubblesClient):
        self.auth_user_service = auth_user_service
        self.bluebubbles_client = bluebubbles_client
        self.onboarding_service = OnboardingService(auth_user_service)
        self.ai_conversation_service = AIConversationService(auth_user_service.supabase)
    
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
            
            # Initialize response variables
            response_text = None
            response_texts = None
            
            if existing_user:
                # Check if user has completed BOTH email verification AND onboarding
                if existing_user.profile.email_verified and existing_user.profile.onboarding_completed:
                    # Fully verified existing user - handle AI conversation
                    response_texts = await self._handle_ai_conversation(
                        existing_user, message_data.text, phone_number
                    )
                elif existing_user.profile.email_verified and not existing_user.profile.onboarding_completed:
                    # Email verified but onboarding not completed - check integrations and potentially complete
                    from services.integration_service import IntegrationService
                    integration_service = IntegrationService(self.auth_user_service.supabase)
                    
                    # Check if integrations are complete and auto-complete onboarding if so
                    onboarding_completed = await integration_service.check_and_complete_onboarding(existing_user.profile.id)
                    
                    if onboarding_completed:
                        # Onboarding was just completed - handle AI conversation
                        response_texts = await self._handle_ai_conversation(
                            existing_user, message_data.text, phone_number
                        )
                    else:
                        # Still need integrations - prompt for dashboard
                        dashboard_url = f"https://www.tryamygdala.tech/{existing_user.profile.id}"
                        response_text = (
                            "🔗 Complete your setup to start using the service:\n"
                            f"{dashboard_url}\n\n"
                            "Once you've set up your integrations, you'll be able to chat with me!"
                        )
                else:
                    # Existing user but email not verified - continue onboarding workflow
                    response_text = await self._handle_existing_user_workflow(message_data, existing_user, phone_number, chat_identifier)
            else:
                # New user - handle onboarding workflow
                response_text = await self._handle_new_user_workflow(message_data, user_guid, phone_number, chat_identifier)
            
            # Handle responses (could be single string or list of strings)
            responses_to_send = []
            if isinstance(response_texts, list):
                responses_to_send = response_texts
            elif response_text:
                responses_to_send = [response_text]
            
            if responses_to_send:
                # Send responses via BlueBubbles
                chat_identifier = self._extract_chat_identifier(message_data)
                if chat_identifier:
                    try:
                        for response in responses_to_send:
                            await self.bluebubbles_client.send_text_message(
                                chat_guid=chat_identifier,
                                text=response
                            )
                        logger.info(f"Sent {len(responses_to_send)} response(s) to user {user_guid}")
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
            
            # Check for restart command first
            if message_text.lower() == "restart":
                return await self._restart_verification_process(existing_user)
            
            # PRIORITY 1: Always check for OTP code first, regardless of state
            
            # Check if user provided email in their message first
            extracted_email = self._extract_email_from_text(message_text)
            if extracted_email:
                # User provided email - process it regardless of current state
                logger.info(f"DEBUG: User provided email {extracted_email} in message, processing directly")
                return await self._handle_email_provided_existing(existing_user, extracted_email)
            
            # Check if email already exists in profile and current state
            if existing_user.profile.email and existing_user.profile.onboarding_state != "awaiting_email_otp":
                # Email exists but not yet waiting for OTP - send OTP (only if it's not a temp email)
                if not existing_user.profile.email.startswith("temp_"):
                    await self._update_onboarding_state(existing_user.profile.id, "awaiting_email_otp")
                    
                    otp_result = await self._send_email_otp(existing_user.profile.email)
                    if otp_result["success"]:
                        return (
                            f"📧 I've sent a verification code to {existing_user.profile.email}.\n\n"
                            "Please check your email and reply with the 6-digit code you received.\n\n"
                            "💡 Type 'restart' at any time to restart the verification process with a new email."
                        )
                    else:
                        return "❌ Sorry, I couldn't send the verification email. Please try again later."
            
            # Check current onboarding state for users without email
            if existing_user.profile.onboarding_state == "not_started":
                # User exists but hasn't started onboarding - check if they provided email in this message
                extracted_email = self._extract_email_from_text(message_text)
                logger.info(f"DEBUG: not_started state - Text: '{message_text}', Extracted email: '{extracted_email}'")
                if extracted_email:
                    # User provided email in their message - process it directly
                    logger.info(f"DEBUG: Processing extracted email {extracted_email} for existing user")
                    return await self._handle_email_provided_existing(existing_user, extracted_email)
                else:
                    # No email found - prompt for email
                    logger.info(f"DEBUG: No email found, updating state to awaiting_email")
                    await self._update_onboarding_state(existing_user.profile.id, "awaiting_email")
                    return (
                        "👋 Welcome back! To get started, I need to verify your email address.\n\n"
                        "Please reply with your email address.\n\n"
                        "💡 Type 'restart' at any time to restart the verification process."
                    )
            elif existing_user.profile.onboarding_state == "awaiting_email":
                # User should provide email - try to extract email from natural language
                extracted_email = self._extract_email_from_text(message_text)
                if extracted_email:
                    return await self._handle_email_provided_existing(existing_user, extracted_email)
                else:
                    return (
                        "❌ I couldn't find a valid email address in your message.\n\n"
                        "Please provide your email address (e.g., your.email@example.com)\n\n"
                        "💡 Type 'restart' to start over."
                    )
            elif existing_user.profile.onboarding_state == "awaiting_email_otp":
                # User should provide OTP code, but also check if they provided a new email
                otp_code = self._extract_otp_from_text(message_text)
                extracted_email = self._extract_email_from_text(message_text)
                
                logger.info(f"Email extraction debug - Text: '{message_text}', Extracted email: '{extracted_email}', OTP: '{otp_code}'")
                
                if otp_code:
                    return await self._handle_otp_verification_existing(existing_user, otp_code)
                elif extracted_email:
                    # User provided a new email - update and send new OTP
                    logger.info(f"Processing email {extracted_email} for existing user")
                    return await self._handle_email_provided_existing(existing_user, extracted_email)
                else:
                    return (
                        "Please enter the 6-digit verification code from your email.\n\n"
                        "Example: 123456\n\n"
                        "💡 Type 'restart' to restart the verification process with a new email."
                    )
            else:
                # Unknown state - restart onboarding
                return await self._restart_verification_process(existing_user)
                
        except Exception as e:
            logger.error(f"Error in existing user workflow: {str(e)}")
            return "❌ Sorry, there was an error processing your message. Please try again or type 'restart' to start over."

    def _extract_email_from_text(self, text: str) -> Optional[str]:
        """Extract email address from natural language text using RegEx"""
        import re
        
        # Skip email extraction if this looks like an AI function call request
        ai_function_keywords = [
            "draft", "send", "email", "compose", "write", "create", "schedule", "calendar", "meeting"
        ]
        
        text_lower = text.lower()
        if any(keyword in text_lower for keyword in ai_function_keywords):
            # This looks like an AI function call, don't extract emails for onboarding
            return None
        
        # Email regex pattern - matches most common email formats
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        matches = re.findall(email_pattern, text)
        
        if matches:
            # Return the first valid email found
            return matches[0]
        return None
    
    def _extract_otp_from_text(self, text: str) -> Optional[str]:
        """Extract 6-digit OTP code from text"""
        import re
        # Look for 6 consecutive digits
        otp_pattern = r'\b\d{6}\b'
        matches = re.findall(otp_pattern, text)
        
        if matches:
            return matches[0]
        return None
    
    async def _restart_verification_process(self, existing_user: AuthUserWithProfile) -> str:
        """Restart the verification process from the beginning"""
        try:
            # Reset user state to awaiting_email and clear existing email
            await self._update_onboarding_state(existing_user.profile.id, "awaiting_email")
            
            # Clear email from profile
            result = self.auth_user_service.supabase.table("user_profiles").update({
                "email": None
            }).eq("id", existing_user.profile.id).execute()
            
            if not result.data:
                logger.error(f"Failed to clear email for user {existing_user.profile.id}")
            
            logger.info(f"Restarted verification process for user {existing_user.profile.id}")
            
            return (
                "🔄 Verification process restarted!\n\n"
                "Please provide your email address to begin verification.\n\n"
                "💡 Type 'restart' at any time to restart the process again."
            )
            
        except Exception as e:
            logger.error(f"Error restarting verification process: {str(e)}")
            return "❌ Sorry, there was an error restarting the verification process. Please try again."

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
                dashboard_url = f"https://www.tryamygdala.tech/{existing_user.profile.id}"
                return (
                    "✅ Email verified successfully! Your account is now active.\n\n"
                    f"🔗 Access your integrations dashboard: {dashboard_url}\n\n"
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
        """
        try:
            message_text = getattr(message, 'text', '').strip()
            
            # Check for restart command
            if message_text.lower() == "restart":
                return (
                    "🔄 Starting fresh verification process!\n\n"
                    "Please provide your email address to begin verification.\n\n"
                    "💡 Type 'restart' at any time to restart the process."
                )
            
            # Try to extract email from the message
            extracted_email = self._extract_email_from_text(message_text)
            
            if extracted_email:
                # Create new user with the provided email
                user_with_profile = await self.auth_user_service.create_authenticated_user(
                    bluebubbles_guid=user_guid,
                    phone_number=phone_number,
                    email=extracted_email,
                    chat_identifier=chat_identifier
                )
                
                # Store email in user_profiles table
                await self._store_email_in_profile(user_with_profile.profile.id, extracted_email)
                
                # Send OTP to the email using Supabase Auth
                otp_result = await self._send_email_otp(extracted_email)
                if otp_result["success"]:
                    logger.info(f"Email OTP sent to {extracted_email} for new user {user_with_profile.profile.id}")
                    return (
                        f"📧 Perfect! I've sent a verification code to {extracted_email}.\n\n"
                        "Please check your email and reply with the 6-digit code you received.\n\n"
                        "💡 Type 'restart' at any time to restart the verification process with a new email."
                    )
                else:
                    logger.error(f"Failed to send email OTP to {extracted_email} for new user")
                    return "❌ Sorry, I couldn't send the verification email. Please try again later."
            else:
                # No email found - prompt for email
                # Create user with temporary email first
                temp_email = f"temp_{phone_number.replace('+', '').replace('-', '')}@temp.example.com"
                
                user_with_profile = await self.auth_user_service.create_authenticated_user(
                    bluebubbles_guid=user_guid,
                    phone_number=phone_number,
                    email=temp_email,
                    chat_identifier=chat_identifier
                )
                
                return (
                    "👋 Welcome! To get started, I need to verify your email address.\n\n"
                    "Please reply with your email address.\n\n"
                    "💡 Type 'restart' at any time to restart the verification process."
                )
                
        except Exception as e:
            logger.error(f"Error in new user workflow: {str(e)}")
            return "❌ Sorry, there was an error setting up your account. Please try again or type 'restart' to start over."
    
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
                dashboard_url = f"https://www.tryamygdala.tech/{user_with_profile.profile.id}"
                return (
                    "✅ Email verified successfully! Your account is now active.\n\n"
                    f"🔗 Access your integrations dashboard: {dashboard_url}\n\n"
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

    async def _handle_ai_conversation(
        self, 
        user_with_profile: AuthUserWithProfile, 
        user_message: str, 
        phone_number: str
    ) -> List[str]:
        """
        Handle AI conversation for fully verified users
        
        Args:
            user_with_profile: Authenticated user with profile
            user_message: The user's message text
            phone_number: User's phone number for logging
            
        Returns:
            List of AI response strings
        """
        try:
            logger.info(f"Handling AI conversation for user {user_with_profile.profile.id}")
            
            # Check for dashboard keywords first
            dashboard_keywords = ["dashboard", "integrations", "dashboard link", "integrations link", "dashabord"]
            if any(keyword in user_message.lower() for keyword in dashboard_keywords):
                dashboard_url = f"https://www.tryamygdala.tech/{user_with_profile.profile.id}"
                return [
                    "here's your integrations dashboard:",
                    dashboard_url,
                    "you can manage all your connected services there"
                ]
            
            # Use the AI conversation service to generate response with context
            ai_response = await self.ai_conversation_service.handle_ai_conversation(
                user_id=user_with_profile.profile.id,
                user_message=user_message,
                phone_number=phone_number
            )
            
            return ai_response
            
        except Exception as e:
            logger.error(f"Error in AI conversation for user {user_with_profile.profile.id}: {str(e)}")
            return ["I'm sorry, I'm having trouble processing your message right now. Please try again in a moment."]
