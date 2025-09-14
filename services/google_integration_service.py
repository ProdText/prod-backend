import logging
import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import httpx
from supabase import Client

logger = logging.getLogger(__name__)


class GoogleIntegrationService:
    """Service to handle Google Calendar and Gmail operations for the AI assistant"""
    
    def __init__(self, supabase_client: Client, user_guid: str):
        self.supabase = supabase_client
        self.user_guid = user_guid
        self.prod_web_url = os.getenv("PROD_WEB_URL", "http://localhost:3000")
        self._google_account = None
    
    async def get_google_account(self) -> Optional[Dict[str, Any]]:
        """Get the Google account for the current user"""
        if self._google_account:
            return self._google_account
            
        try:
            # Get user profile
            result = self.supabase.table('user_profiles').select('*').eq('phone_number', self.user_guid).single().execute()
            if not result.data:
                logger.warning(f"No user profile found for {self.user_guid}")
                return None
            
            user_id = result.data['id']
            
            # Get Google account
            result = self.supabase.table('google_accounts').select('*').eq('user_id', user_id).single().execute()
            if not result.data:
                logger.warning(f"No Google account linked for user {user_id}")
                return None
            
            self._google_account = result.data
            return self._google_account
            
        except Exception as e:
            logger.error(f"Error getting Google account: {str(e)}")
            return None
    
    async def create_calendar_event(
        self,
        title: str,
        start_time: datetime,
        end_time: datetime,
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        reminder_minutes: Optional[int] = 10
    ) -> Dict[str, Any]:
        """
        Create a calendar event for the user
        
        Args:
            title: Event title
            start_time: Event start time
            end_time: Event end time
            description: Optional event description
            location: Optional location
            attendees: Optional list of attendee emails
            reminder_minutes: Minutes before event to send reminder
        
        Returns:
            Created event details or error
        """
        try:
            account = await self.get_google_account()
            if not account:
                return {
                    "success": False,
                    "error": "No Google account linked. Please connect your Google account first."
                }
            
            # Call the prod-web API to create the event
            async with httpx.AsyncClient() as client:
                payload = {
                    "accountId": account['id'],
                    "title": title,
                    "startTime": start_time.isoformat(),
                    "endTime": end_time.isoformat(),
                    "description": description,
                    "location": location,
                    "attendees": attendees or [],
                    "reminders": [{"method": "popup", "minutes": reminder_minutes}] if reminder_minutes else []
                }
                
                response = await client.post(
                    f"{self.prod_web_url}/api/google/calendar/create-event",
                    json=payload,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    event_data = response.json()
                    return {
                        "success": True,
                        "event": event_data,
                        "message": f"Calendar event '{title}' created successfully for {start_time.strftime('%B %d at %I:%M %p')}"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to create event: {response.text}"
                    }
                    
        except Exception as e:
            logger.error(f"Error creating calendar event: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to create calendar event: {str(e)}"
            }
    
    async def draft_email(
        self,
        to: List[str],
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a draft email for the user
        
        Args:
            to: List of recipient emails
            subject: Email subject
            body: Email body
            cc: Optional CC recipients
            bcc: Optional BCC recipients
        
        Returns:
            Draft details or error
        """
        try:
            account = await self.get_google_account()
            if not account:
                return {
                    "success": False,
                    "error": "No Google account linked. Please connect your Google account first."
                }
            
            # Call the prod-web API to create the draft
            async with httpx.AsyncClient() as client:
                payload = {
                    "accountId": account['id'],
                    "to": to,
                    "subject": subject,
                    "body": body,
                    "cc": cc or [],
                    "bcc": bcc or []
                }
                
                response = await client.post(
                    f"{self.prod_web_url}/api/google/gmail/create-draft",
                    json=payload,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    draft_data = response.json()
                    return {
                        "success": True,
                        "draft": draft_data,
                        "message": f"Email draft created to {', '.join(to)} with subject '{subject}'"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to create draft: {response.text}"
                    }
                    
        except Exception as e:
            logger.error(f"Error creating email draft: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to create email draft: {str(e)}"
            }
    
    async def send_email(
        self,
        to: List[str],
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Send an email directly for the user
        
        Args:
            to: List of recipient emails
            subject: Email subject
            body: Email body
            cc: Optional CC recipients
            bcc: Optional BCC recipients
        
        Returns:
            Send result or error
        """
        try:
            account = await self.get_google_account()
            if not account:
                return {
                    "success": False,
                    "error": "No Google account linked. Please connect your Google account first."
                }
            
            # Call the prod-web API to send the email
            async with httpx.AsyncClient() as client:
                payload = {
                    "accountId": account['id'],
                    "to": to,
                    "subject": subject,
                    "body": body,
                    "cc": cc or [],
                    "bcc": bcc or []
                }
                
                response = await client.post(
                    f"{self.prod_web_url}/api/google/gmail/send-email",
                    json=payload,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    return {
                        "success": True,
                        "message": f"Email sent to {', '.join(to)} with subject '{subject}'"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to send email: {response.text}"
                    }
                    
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to send email: {str(e)}"
            }
    
    async def get_upcoming_events(self, days_ahead: int = 7) -> Dict[str, Any]:
        """
        Get upcoming calendar events for the user
        
        Args:
            days_ahead: Number of days to look ahead
        
        Returns:
            List of upcoming events or error
        """
        try:
            account = await self.get_google_account()
            if not account:
                return {
                    "success": False,
                    "error": "No Google account linked. Please connect your Google account first."
                }
            
            # Get events from database
            time_min = datetime.now()
            time_max = time_min + timedelta(days=days_ahead)
            
            result = self.supabase.table('calendar_events').select('*').eq(
                'account_id', account['id']
            ).gte('start_time', time_min.isoformat()).lte('start_time', time_max.isoformat()).order(
                'start_time'
            ).execute()
            
            events = result.data if result.data else []
            
            # Format events for response
            formatted_events = []
            for event in events:
                formatted_events.append({
                    'title': event['title'],
                    'start': event['start_time'],
                    'end': event['end_time'],
                    'location': event['location'],
                    'description': event['description']
                })
            
            return {
                "success": True,
                "events": formatted_events,
                "count": len(formatted_events),
                "message": f"Found {len(formatted_events)} upcoming events in the next {days_ahead} days"
            }
            
        except Exception as e:
            logger.error(f"Error getting upcoming events: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to get upcoming events: {str(e)}"
            }
    
    async def search_emails(self, query: str, max_results: int = 10) -> Dict[str, Any]:
        """
        Search emails for the user
        
        Args:
            query: Search query
            max_results: Maximum number of results
        
        Returns:
            Search results or error
        """
        try:
            account = await self.get_google_account()
            if not account:
                return {
                    "success": False,
                    "error": "No Google account linked. Please connect your Google account first."
                }
            
            # Search emails in database
            # For now, do a simple subject/body search
            result = self.supabase.table('emails').select('*').eq(
                'account_id', account['id']
            ).or_(
                f"subject.ilike.%{query}%,body_text.ilike.%{query}%"
            ).order('internal_date', desc=True).limit(max_results).execute()
            
            emails = result.data if result.data else []
            
            # Format emails for response
            formatted_emails = []
            for email in emails:
                formatted_emails.append({
                    'subject': email['subject'],
                    'from': email['from_email'],
                    'date': email['internal_date'],
                    'snippet': email['snippet']
                })
            
            return {
                "success": True,
                "emails": formatted_emails,
                "count": len(formatted_emails),
                "message": f"Found {len(formatted_emails)} emails matching '{query}'"
            }
            
        except Exception as e:
            logger.error(f"Error searching emails: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to search emails: {str(e)}"
            }