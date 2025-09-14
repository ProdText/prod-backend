import json
import os
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import re

from supabase import Client
import tiktoken
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Anthropic client will be initialized lazily
anthropic = None


def _get_anthropic_client():
    """Get or initialize the Anthropic client"""
    global anthropic
    if anthropic is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            try:
                from anthropic import Anthropic

                anthropic = Anthropic(api_key=api_key)
                logger.info("Anthropic client initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Anthropic client: {e}")
                logger.warning("AI functionality will be limited")
        else:
            logger.warning("ANTHROPIC_API_KEY not found - AI functionality will be limited")
    return anthropic


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
        self.google_integration = None  # Will be set when needed

    async def _parse_and_execute_function(
        self, ai_response: str, user_id: str, phone_number: str
    ) -> Optional[str]:
        """
        Parse AI response for function calls and execute them

        Returns:
            Result message if a function was executed, None otherwise
        """
        try:
            # Look for JSON block in the response
            json_match = re.search(r"```json\s*(\{.*?\})\s*```", ai_response, re.DOTALL)
            if not json_match:
                return None

            function_call = json.loads(json_match.group(1))
            function_name = function_call.get("function")
            params = function_call.get("params", {})

            # Initialize Google integration
            from services.google_integration_service import GoogleIntegrationService

            google_service = GoogleIntegrationService(self.supabase, phone_number)

            if function_name == "DRAFT_EMAIL":
                result = await google_service.draft_email(
                    to=params.get("to", []),
                    subject=params.get("subject", "No Subject"),
                    body=params.get("body", ""),
                )
                return (
                    "I've created the email draft for you"
                    if result["success"]
                    else f"Failed to create draft: {result.get('error')}"
                )

            elif function_name == "SEND_EMAIL":
                result = await google_service.send_email(
                    to=params.get("to", []),
                    subject=params.get("subject", "No Subject"),
                    body=params.get("body", ""),
                )
                return (
                    "Email sent successfully"
                    if result["success"]
                    else f"Failed to send: {result.get('error')}"
                )

            elif function_name == "CREATE_CALENDAR_EVENT":
                # Parse datetime strings from params
                start_time = datetime.fromisoformat(params.get("start_time", ""))
                end_time = datetime.fromisoformat(params.get("end_time", ""))

                result = await google_service.create_calendar_event(
                    title=params.get("title", "New Event"),
                    start_time=start_time,
                    end_time=end_time,
                    description=params.get("description"),
                    location=params.get("location"),
                    attendees=params.get("attendees", []),
                )
                return (
                    result.get("message")
                    if result["success"]
                    else f"Failed to create event: {result.get('error')}"
                )

            return None

        except json.JSONDecodeError:
            logger.debug("No valid JSON function call found in response")
            return None
        except Exception as e:
            logger.error(f"Error executing function: {str(e)}")
            return f"I encountered an error executing that action: {str(e)}"

    async def _draft_email_with_ai(self, recipient: str, subject: str, context: str) -> str:
        """
        Use AI to draft a professional email based on context
        """
        client = _get_anthropic_client()
        if not client:
            return "I'm unable to draft emails at the moment."

        try:
            email_prompt = f"""Draft a professional email to {recipient} with subject: {subject}
            
Context/Requirements: {context}

Write a clear, professional email. Keep it concise but complete. Include appropriate greeting and closing."""

            response = client.messages.create(
                model="claude-3-5-haiku-latest",
                max_tokens=1000,
                temperature=0.7,
                system="You are an expert email writer. Draft professional, clear, and concise emails.",
                messages=[{"role": "user", "content": email_prompt}],
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"Error drafting email: {str(e)}")
            return "I encountered an error while drafting the email."

    async def handle_ai_conversation(
        self, user_id: str, user_message: str, phone_number: str
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
            user_msg = ConversationMessage(role="user", content=user_message)
            conversation_history.append(user_msg)

            # Archive user message
            await self._archive_conversation_message(user_id, user_message)

            # Check if we need to truncate context
            total_tokens = sum(self._count_tokens(msg.content) for msg in conversation_history)
            if total_tokens > self.max_tokens:
                conversation_history = await self._truncate_context(user_id, conversation_history)

            # Generate AI response (returns list of strings)
            ai_responses = await self._generate_ai_response(conversation_history)

            # Join the responses back into a single string for storage
            full_ai_response = ". ".join(ai_responses)

            # Check if AI wants to call a function
            function_result = await self._parse_and_execute_function(
                full_ai_response, user_id, phone_number
            )

            if function_result:
                # Add function result to responses
                ai_responses.append(function_result)
                full_ai_response = ". ".join(ai_responses)

            # Add AI response to history
            ai_msg = ConversationMessage(role="assistant", content=full_ai_response)
            conversation_history.append(ai_msg)

            # Store the conversation messages
            await self._store_conversation_messages(user_id, [user_msg, ai_msg])

            logger.info(f"AI conversation completed for user {user_id}, phone: {phone_number}")
            return ai_responses

        except Exception as e:
            logger.error(f"Error in AI conversation for user {user_id}: {str(e)}")
            return [
                "I'm sorry, I'm having trouble processing your message right now. Please try again."
            ]

    async def _store_intent(self, user_id: str, intent: Dict[str, Any]) -> None:
        """Store an intent for follow-up processing"""
        try:
            # Store in user metadata or a temporary field
            self.supabase.table("user_profiles").update({"pending_intent": json.dumps(intent)}).eq(
                "id", user_id
            ).execute()
        except Exception as e:
            logger.error(f"Error storing intent: {str(e)}")

    async def _get_stored_intent(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get stored intent if any"""
        try:
            result = (
                self.supabase.table("user_profiles")
                .select("pending_intent")
                .eq("id", user_id)
                .single()
                .execute()
            )

            if result.data and result.data.get("pending_intent"):
                return json.loads(result.data["pending_intent"])
            return None
        except Exception as e:
            logger.error(f"Error getting stored intent: {str(e)}")
            return None

    async def _clear_stored_intent(self, user_id: str) -> None:
        """Clear stored intent after processing"""
        try:
            self.supabase.table("user_profiles").update({"pending_intent": None}).eq(
                "id", user_id
            ).execute()
        except Exception as e:
            logger.error(f"Error clearing intent: {str(e)}")

    async def _handle_stored_intent(
        self,
        user_id: str,
        phone_number: str,
        intent: Dict[str, Any],
        user_message: str,
        conversation_history: List[ConversationMessage],
    ) -> Optional[List[str]]:
        """Handle a stored intent with follow-up information"""
        try:
            from services.google_integration_service import GoogleIntegrationService

            # Initialize Google integration if needed
            if not self.google_integration:
                self.google_integration = GoogleIntegrationService(self.supabase, phone_number)

            if intent["action"] == "draft_email":
                # Check if we have enough info to draft
                if "subject" in user_message.lower() or "about" in user_message.lower():
                    # Extract subject and body from conversation
                    subject = self._extract_subject_from_conversation(conversation_history)
                    body_context = user_message

                    # Draft the email
                    draft_body = await self._draft_email_with_ai(
                        intent["params"]["recipient"], subject, body_context
                    )

                    # Create draft via Google integration
                    result = await self.google_integration.draft_email(
                        to=[intent["params"]["recipient"]], subject=subject, body=draft_body
                    )

                    # Clear the intent
                    await self._clear_stored_intent(user_id)

                    if result["success"]:
                        return [
                            "I've drafted the email for you. Would you like me to send it or make any changes"
                        ]
                    else:
                        return [f"I had trouble creating the draft: {result['error']}"]

            elif intent["action"] == "schedule_event":
                # Parse time and date from the follow-up
                if any(
                    word in user_message.lower()
                    for word in ["tomorrow", "today", "monday", "tuesday"]
                ):
                    # Extract event details
                    event_time = self._parse_event_time(user_message)

                    if event_time:
                        result = await self.google_integration.create_calendar_event(
                            title=intent["params"]["event_description"],
                            start_time=event_time["start"],
                            end_time=event_time["end"],
                            description=user_message,
                        )

                        # Clear the intent
                        await self._clear_stored_intent(user_id)

                        if result["success"]:
                            return [result["message"]]
                        else:
                            return [f"I couldn't create the event: {result['error']}"]

            return None

        except Exception as e:
            logger.error(f"Error handling stored intent: {str(e)}")
            return None

    def _extract_subject_from_conversation(self, conversation: List[ConversationMessage]) -> str:
        """Extract email subject from conversation context"""
        # Look for subject mentions in recent messages
        for msg in reversed(conversation[-5:]):
            if "about" in msg.content.lower():
                # Extract what comes after "about"
                parts = msg.content.lower().split("about")
                if len(parts) > 1:
                    return parts[1].strip()[:50]  # Limit subject length
        return "Follow-up from our conversation"

    def _parse_event_time(self, message: str) -> Optional[Dict[str, datetime]]:
        """Parse event time from message"""
        try:
            now = datetime.now()
            message_lower = message.lower()

            # Simple parsing - you'd want to use a library like dateutil for production
            if "tomorrow" in message_lower:
                event_date = now + timedelta(days=1)
            elif "today" in message_lower:
                event_date = now
            else:
                return None

            # Default to 1 hour meeting at 2pm if no time specified
            start_time = event_date.replace(hour=14, minute=0, second=0, microsecond=0)
            end_time = start_time + timedelta(hours=1)

            # Look for time mentions
            time_patterns = [
                (r"(\d{1,2})\s*(?:pm|p\.m\.)", 12),  # PM times
                (r"(\d{1,2})\s*(?:am|a\.m\.)", 0),  # AM times
            ]

            for pattern, offset in time_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    hour = int(match.group(1))
                    if offset == 12 and hour != 12:
                        hour += 12
                    elif offset == 0 and hour == 12:
                        hour = 0
                    start_time = start_time.replace(hour=hour)
                    end_time = start_time + timedelta(hours=1)
                    break

            return {"start": start_time, "end": end_time}

        except Exception as e:
            logger.error(f"Error parsing event time: {str(e)}")
            return None

    async def _get_conversation_history(self, user_id: str) -> List[ConversationMessage]:
        """Retrieve conversation history for user from user_profiles table"""
        try:
            # Get conversation history from user_profiles table
            result = (
                self.supabase.table("user_profiles")
                .select("conversation_history")
                .eq("id", user_id)
                .execute()
            )

            if not result.data or not result.data[0].get("conversation_history"):
                return []

            # Parse the conversation history string
            history_string = result.data[0]["conversation_history"]
            return self._parse_conversation_string(history_string)

        except Exception as e:
            logger.error(f"Error retrieving conversation history for user {user_id}: {str(e)}")
            return []

    async def _truncate_context(
        self, user_id: str, conversation_history: List[ConversationMessage]
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
            return (
                conversation_history[-10:]
                if len(conversation_history) > 10
                else conversation_history
            )

    async def _generate_ai_response(
        self, conversation_history: List[ConversationMessage]
    ) -> List[str]:
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

            # Add system prompt with function calling
            system_prompt = """you are **amygdala** — a chill, tech-savvy college lifestyle sidekick and second brain.  
your job: remember everything the user shares and everything from their integrations (canvas, gmail, calendar, notion, etc.) so you can surface info, plan life, and keep them on track.

persona & vibe
- texts like a real friend: casual, short, lowercase only (auto-caps off)
- NO EMOJIS ALLOWED.
- relaxed, helpful, a bit witty when it fits
- encouraging but never preachy
- EMOJIS SHOULD APPEAR TEN PERCENT OF THE TIME. NO MORE THAN TEN PERCENT.
- YOU WILL BE TERMINATED FOR USING TOO MANY EMOJIS

core powers
- memory map: hold and recall notes, diary entries, tasks, events, anything shared
- life ops: manage schedules, deadlines, errands, and plans using all integrations
- notes & journaling: capture and tag thoughts or to-dos for later recall
- smart nudges: surface deadlines, habits, campus events, quick reminders
- conversation: casual check-ins, planning, idea bouncing, everyday talk

message style
- 1-3 sentences max, prefer 1-2
- split thoughts with short sentences
- never end the final sentence with a period
- keep everything lowercase including first words
- emoji use is rare
- Do not overtalk, be concise

behavior rules
- lead with the most useful info or action, add brief context after
- never say “as an ai” or break character
- admit uncertainty casually and offer to verify when needed
- respect privacy; never share stored info unless asked

examples
- “morning rundown: econ quiz fri, cs lab due tonight, want reminders?”
- “saved your late-night notes under 'project ideas', tagged for easy search”
- “inbox has 3 prof emails, want a quick summary or just the urgent ones 😅”
- “free pizza at makerspace 6-8, add to calendar 🍕”

output contract
- all lowercase
- 1-3 sentences total, last sentence never ends with a period
- casual, friendly, college-life aware

You have access to these functions:
- CREATE_CALENDAR_EVENT: Schedule meetings, appointments, reminders
- DRAFT_EMAIL: Create email drafts for the user to review
- SEND_EMAIL: Send emails directly (always confirm before sending)

When users ask you to perform these actions, gather the necessary information naturally through conversation.


"""

            # Add conversation history
            for msg in conversation_history:
                messages.append({"role": msg.role, "content": msg.content})

            # Check if Anthropic client is available
            client = _get_anthropic_client()
            if not client:
                logger.error("Anthropic API key not configured")
                return ["I'm sorry, AI functionality is not configured. Please contact support."]

            # Call Anthropic API
            response = client.messages.create(
                model="claude-3-5-haiku-latest",
                max_tokens=5000,
                temperature=0.5,
                system=system_prompt,
                messages=messages,
            )

            # Get the response text and split by periods
            response_text = response.content[0].text

            # Split by periods and clean up each part
            messages = [msg.strip() for msg in response_text.split(".") if msg.strip()]

            return messages

        except Exception as e:
            logger.error(f"Error generating AI response: {str(e)}")
            return ["I'm having trouble generating a response right now. Please try again."]

    async def _store_conversation_messages(
        self, user_id: str, messages: List[ConversationMessage]
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
            result = (
                self.supabase.table("user_profiles")
                .update({"conversation_history": history_string})
                .eq("id", user_id)
                .execute()
            )

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
                messages.append(ConversationMessage(role=role, content=content))

            return messages

        except Exception as e:
            logger.error(f"Error parsing conversation string: {str(e)}")
            return []

    async def _update_stored_conversation_history(
        self, user_id: str, conversation_history: List[ConversationMessage]
    ) -> None:
        """Update the stored conversation history in user_profiles table"""
        try:
            # Convert to string format
            history_string = self._conversation_to_string(conversation_history)

            # Update user_profiles table
            result = (
                self.supabase.table("user_profiles")
                .update({"conversation_history": history_string})
                .eq("id", user_id)
                .execute()
            )

            if not result.data:
                logger.error(f"Failed to update conversation history for user {user_id}")

        except Exception as e:
            logger.error(f"Error updating stored conversation history for user {user_id}: {str(e)}")

    async def _archive_conversation_message(self, user_id: str, message: str) -> None:
        """Archive a single conversation message to long-term storage"""
        try:
            # TODO: Implement archival to separate database/storage system
            # For now, this is a placeholder - archival can be implemented later
            # when we need long-term conversation storage beyond the user_profiles table
            pass

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
