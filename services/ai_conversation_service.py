import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from supabase import Client
import tiktoken
from anthropic import Anthropic
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Get API key and setup Anthropic client
api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    raise ValueError("ANTHROPIC_API_KEY not found in environment variables or .env file.")

anthropic = Anthropic(api_key=api_key)


@dataclass
class ConversationMessage:
    """Represents a single message in the conversation"""
    role: str  # 'user' or 'assistant'
    content: str


class AIConversationService:
    """Service for managing AI conversations with context and token management"""
    
    def __init__(self, supabase_client: Client, max_tokens: int = 5000):
        self.supabase = supabase_client
        self.max_tokens = max_tokens
        self.encoding = tiktoken.get_encoding("cl100k_base")  # GPT-4 encoding
        
    async def handle_ai_conversation(
        self, 
        user_id: str, 
        user_message: str,
        phone_number: str
    ) -> List[str]:
        """
        Handle AI conversation with context management
        
        Args:
            user_id: User's ID from user_profiles
            user_message: The user's message text
            phone_number: User's phone number for logging
            
        Returns:
            List of AI response strings split by periods
        """
        try:
            # Get conversation history
            conversation_history = await self._get_conversation_history(user_id)
            
            # Add user message to history
            user_msg = ConversationMessage(
                role="user",
                content=user_message
            )
            conversation_history.append(user_msg)

            # Archive user message
            await self._archive_conversation_message(user_id, user_message)
            
            # Check if we need to truncate context
            total_tokens = sum(self._count_tokens(msg.content) for msg in conversation_history)
            if total_tokens > self.max_tokens:
                conversation_history = await self._truncate_context(
                    user_id, conversation_history
                )
            
            # Generate AI response (returns list of strings)
            ai_responses = await self._generate_ai_response(conversation_history)
            
            # Join the responses back into a single string for storage and return
            full_ai_response = ". ".join(ai_responses)
            
            # Add AI response to history
            ai_msg = ConversationMessage(
                role="assistant",
                content=full_ai_response
            )
            conversation_history.append(ai_msg)
            
            # Store the conversation messages
            await self._store_conversation_messages(user_id, [user_msg, ai_msg])
            
            logger.info(f"AI conversation completed for user {user_id}, phone: {phone_number}")
            return ai_responses
            
        except Exception as e:
            logger.error(f"Error in AI conversation for user {user_id}: {str(e)}")
            return ["I'm sorry, I'm having trouble processing your message right now. Please try again."]
    
    async def _get_conversation_history(self, user_id: str) -> List[ConversationMessage]:
        """Retrieve conversation history for user from user_profiles table"""
        try:
            # Get conversation history from user_profiles table
            result = self.supabase.table("user_profiles").select(
                "conversation_history"
            ).eq("id", user_id).execute()
            
            if not result.data or not result.data[0].get("conversation_history"):
                return []
            
            # Parse the conversation history string
            history_string = result.data[0]["conversation_history"]
            return self._parse_conversation_string(history_string)
            
        except Exception as e:
            logger.error(f"Error retrieving conversation history for user {user_id}: {str(e)}")
            return []
    
    async def _truncate_context(
        self, 
        user_id: str, 
        conversation_history: List[ConversationMessage]
    ) -> List[ConversationMessage]:
        """
        Truncate conversation context when token limit is exceeded
        
        Args:
            user_id: User's ID
            conversation_history: Current conversation history
            
        Returns:
            Truncated conversation history
        """
        try:
            logger.info(f"Truncating conversation context for user {user_id}")
            
            # Calculate how many messages to remove (remove oldest first)
            total_tokens = sum(self._count_tokens(msg.content) for msg in conversation_history)
            remaining_messages = conversation_history.copy()
            
            while total_tokens > self.max_tokens * 0.7:  # Keep 70% of max tokens
                if len(remaining_messages) <= 2:  # Keep at least 2 messages
                    break
                    
                oldest_msg = remaining_messages.pop(0)
                total_tokens -= self._count_tokens(oldest_msg.content)
            
            # Update the stored conversation history with truncated version
            await self._update_stored_conversation_history(user_id, remaining_messages)
            
            logger.info(f"Truncated conversation history for user {user_id}")
            return remaining_messages
            
        except Exception as e:
            logger.error(f"Error truncating context for user {user_id}: {str(e)}")
            # Return last few messages as fallback
            return conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
    
    async def _generate_ai_response(self, conversation_history: List[ConversationMessage]) -> List[str]:
        """
        Generate AI response using conversation context
        
        Args:
            conversation_history: List of conversation messages
            
        Returns:
            List of AI generated response strings split by periods
        """
        try:
            # Prepare messages for AI API
            messages = []
            
            # Add system prompt
            system_prompt = """You are a helpful AI assistant that is conversational and responds like a human that is texting someone. 
You can help users with questions, provide information, and have natural conversations.
Keep your responses concise and friendly, suitable for text messaging.
If users ask about technical integrations or account features, direct them to their dashboard.
If you want to send multiple text messages to shorten up a message, use a period. In the very last sentence do not use a period. Only generate 3 sentences MAX.
Normally there should be one or two messages."""
                        
            # Add conversation history
            for msg in conversation_history:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            # Call Anthropic API
            response = anthropic.messages.create(
                model="claude-3-5-haiku-latest",
                max_tokens=5000,
                temperature=0.5,
                system=system_prompt,
                messages=messages
            )

            # Get the response text and split by periods
            response_text = response.content[0].text
            
            # Split by periods and clean up each part
            messages = [msg.strip() for msg in response_text.split('.') if msg.strip()]
            
            return messages
            
        except Exception as e:
            logger.error(f"Error generating AI response: {str(e)}")
            return ["I'm having trouble generating a response right now. Please try again."]
    
    async def _store_conversation_messages(
        self, 
        user_id: str, 
        messages: List[ConversationMessage]
    ) -> None:
        """Store conversation messages as a single string in user_profiles table"""
        try:
            # Get current conversation history
            current_history = await self._get_conversation_history(user_id)
            
            # Add new messages to history
            current_history.extend(messages)
            
            # Convert to string format
            history_string = self._conversation_to_string(current_history)
            
            # Update user_profiles table
            result = self.supabase.table("user_profiles").update({
                "conversation_history": history_string
            }).eq("id", user_id).execute()
            
            if not result.data:
                logger.error(f"Failed to store conversation history for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error storing conversation messages for user {user_id}: {str(e)}")
    
    def _conversation_to_string(self, conversation_history: List[ConversationMessage]) -> str:
        """Convert conversation history to a single string format"""
        try:
            conversation_parts = []
            for msg in conversation_history:
                # Format: ROLE|CONTENT
                part = f"{msg.role}|{msg.content}"
                conversation_parts.append(part)
            
            # Join with newlines
            return "\n".join(conversation_parts)
            
        except Exception as e:
            logger.error(f"Error converting conversation to string: {str(e)}")
            return ""
    
    def _parse_conversation_string(self, history_string: str) -> List[ConversationMessage]:
        """Parse conversation history string back to ConversationMessage objects"""
        try:
            if not history_string.strip():
                return []
            
            messages = []
            lines = history_string.strip().split("\n")
            
            for line in lines:
                if not line.strip():
                    continue
                    
                parts = line.split("|", 1)  # Split into max 2 parts
                if len(parts) != 2:
                    continue
                    
                role, content = parts
                
                # Create message with role and content only
                messages.append(ConversationMessage(
                    role=role,
                    content=content
                ))
            
            return messages
            
        except Exception as e:
            logger.error(f"Error parsing conversation string: {str(e)}")
            return []
    
    async def _update_stored_conversation_history(
        self, 
        user_id: str, 
        conversation_history: List[ConversationMessage]
    ) -> None:
        """Update the stored conversation history in user_profiles table"""
        try:
            # Convert to string format
            history_string = self._conversation_to_string(conversation_history)
            
            # Update user_profiles table
            result = self.supabase.table("user_profiles").update({
                "conversation_history": history_string
            }).eq("id", user_id).execute()
            
            if not result.data:
                logger.error(f"Failed to update conversation history for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error updating stored conversation history for user {user_id}: {str(e)}")
    
    async def _archive_conversation_message(
        self, 
        user_id: str, 
        message: ConversationMessage
    ) -> None:
        """Archive a single conversation message to long-term storage"""
        try:
            # TODO: Implement archival to separate database/storage system










            
        except Exception as e:
            logger.error(f"Error archiving conversation messages for user {user_id}: {str(e)}")
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken"""
        try:
            return len(self.encoding.encode(text))
        except Exception as e:
            logger.error(f"Error counting tokens: {str(e)}")
            # Fallback: rough estimate (1 token ≈ 4 characters)
            return len(text) // 4

