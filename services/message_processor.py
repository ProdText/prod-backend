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
            
            # Log all webhook events for debugging
            logger.info(f"Webhook event type: {payload.type}, GUID: {message_data.guid}")
            logger.info(f"Message text: {getattr(message_data, 'text', 'No text')}")
            logger.info(f"Is from me: {getattr(message_data, 'isFromMe', 'Unknown')}")
            
            # Skip non-message events (typing indicators, read receipts, etc.)
            if payload.type != "new-message":
                logger.info(f"Skipping non-message event: {payload.type}")
                return MessageResponse(
                    success=True,
                    user_guid=message_data.guid,
                    message=f"Skipped {payload.type} event"
                )
            
            # Extract user information
            user_guid = self._extract_user_guid(message_data)
            phone_number = self._extract_phone_number(message_data)
            chat_identifier = self._extract_chat_identifier(message_data)
            
            # Validate phone number is present for phone-only auth
            if not phone_number:
                logger.error(f"No phone number found in message {user_guid}")
                return MessageResponse(
                    success=False,
                    user_guid=user_guid,
                    message="Phone number required for authentication"
                )
            
            # Get or create authenticated user
            user_with_profile = await self.auth_user_service.get_or_create_user_by_guid(
                bluebubbles_guid=user_guid,
                phone_number=phone_number,
                chat_identifier=chat_identifier
            )
            
            # Process the message based on type and user state
            response_text = await self._generate_response(message_data, user_with_profile)
            
            # Send response back to BlueBubbles
            sent_response = False
            if response_text and chat_identifier:
                try:
                    await self.bluebubbles_client.send_text_message(
                        chat_guid=chat_identifier,
                        text=response_text
                    )
                    sent_response = True
                    logger.info(f"Sent response to user {user_guid}")
                except Exception as e:
                    logger.error(f"Failed to send response: {str(e)}")
            
            return MessageResponse(
                success=True,
                user_guid=user_guid,
                message="Message processed successfully",
                sent_response=sent_response
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
        # In the future, you might want to use handle address or chat participant info
        return message.guid
    
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
    
    async def _generate_response(self, message: BlueBubblesMessage, user_with_profile: AuthUserWithProfile) -> Optional[str]:
        """
        Generate response text based on message and user state
        
        This handles onboarding flow with OTP verification and regular conversation.
        """
        message_text = message.text or ""
        user_profile = user_with_profile.profile
        
        # Get original phone number from user metadata
        original_phone = self._extract_original_phone(message, user_with_profile)
        
        # Get current onboarding state
        onboarding_state = self.onboarding_service.get_onboarding_state(user_profile)
        
        # Handle onboarding flow based on state
        if onboarding_state == OnboardingState.NOT_STARTED:
            return await self._handle_onboarding_start(user_with_profile, original_phone)
        elif onboarding_state == OnboardingState.AWAITING_OTP:
            return await self._handle_otp_verification(user_with_profile, message_text, original_phone)
        elif onboarding_state == OnboardingState.COMPLETED:
            return await self._handle_conversation(message_text, user_profile)
        
        # Fallback
        return await self._handle_conversation(message_text, user_profile)
    
    def _extract_original_phone(self, message: BlueBubblesMessage, user_with_profile: AuthUserWithProfile) -> str:
        """Extract original phone number from user metadata or message"""
        # Try to get from user metadata first
        if hasattr(user_with_profile.auth_user, 'user_metadata'):
            metadata = user_with_profile.auth_user.user_metadata or {}
            if 'original_phone' in metadata:
                return metadata['original_phone']
        
        # Fallback to message handle
        return self._extract_phone_number(message) or ""
    
    async def _handle_onboarding_start(self, user_with_profile: AuthUserWithProfile, original_phone: str) -> str:
        """Start the onboarding process with OTP verification"""
        result = await self.onboarding_service.start_onboarding(user_with_profile, original_phone)
        return result.get("response_text", "Welcome! Let's get you set up.")
    
    async def _handle_otp_verification(self, user_with_profile: AuthUserWithProfile, message_text: str, original_phone: str) -> str:
        """Handle OTP verification during onboarding"""
        message_text = message_text.strip()
        
        # Check for resend request
        if message_text.upper() in ['RESEND', 'SEND AGAIN', 'NEW CODE']:
            result = await self.onboarding_service.resend_otp(user_with_profile, original_phone)
            return result.get("response_text", "I'll send you a new code.")
        
        # Check if message looks like an OTP code (6 digits)
        if message_text.isdigit() and len(message_text) == 6:
            result = await self.onboarding_service.verify_otp(user_with_profile, message_text, original_phone)
            return result.get("response_text", "Let me verify that code.")
        
        # Invalid format
        return (
            "Please reply with the 6-digit verification code I sent to your phone, "
            "or reply 'RESEND' to get a new code."
        )
    
    async def _handle_conversation(self, message_text: str, user_profile: UserProfile) -> str:
        """
        Handle regular conversation
        
        TODO: This is where you'll integrate:
        1. Query your graph database with message context
        2. Use graph nodes as context for LLM
        3. Generate intelligent responses
        """
        # Placeholder response - replace with your LLM integration
        if "hello" in message_text.lower() or "hi" in message_text.lower():
            return "Hello! How can I help you today?"
        elif "help" in message_text.lower():
            return "I'm here to assist you! Ask me anything and I'll do my best to help."
        else:
            return f"I received your message: '{message_text}'. I'm still learning how to respond better!"
