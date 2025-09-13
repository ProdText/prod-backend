import os
import logging
import uuid
from typing import Dict, Any, Optional
import httpx
from datetime import datetime

logger = logging.getLogger(__name__)


class BlueBubblesClient:
    """Client for interacting with BlueBubbles REST API"""
    
    def __init__(self, server_url: str, server_password: str):
        self.server_url = server_url.rstrip('/')
        self.server_password = server_password
        self.client = httpx.AsyncClient(timeout=30.0)
    
    def _generate_temp_guid(self) -> str:
        """Generate a unique temporary GUID for message requests"""
        return str(uuid.uuid4())
    
    async def send_text_message(
        self, 
        chat_guid: str, 
        text: str, 
        method: str = "private-api"
    ) -> Dict[str, Any]:
        """
        Send a text message to a BlueBubbles chat
        
        Args:
            chat_guid: The chat GUID to send the message to
            text: The message text to send
            method: Send method ('private-api' or 'apple-script')
            
        Returns:
            API response from BlueBubbles server
        """
        url = f"{self.server_url}/api/v1/message/text"
        
        params = {
            'password': self.server_password
        }
        
        payload = {
            'chatGuid': chat_guid,
            'tempGuid': self._generate_temp_guid(),
            'message': text,
            'method': method
        }
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        try:
            logger.info(f"Sending message to chat {chat_guid}: {text[:50]}...")
            
            response = await self.client.post(
                url,
                json=payload,
                params=params,
                headers=headers
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Message sent successfully to {chat_guid}")
            return result
            
        except httpx.HTTPStatusError as e:
            # Get response body for more detailed error info
            error_body = e.response.text
            logger.error(f"Failed to send message to {chat_guid}: {str(e)}")
            logger.error(f"Response status: {e.response.status_code}")
            logger.error(f"Response body: {error_body}")
            raise Exception(f"BlueBubbles API error: {str(e)}")
        except httpx.HTTPError as e:
            logger.error(f"HTTP error sending message to {chat_guid}: {str(e)}")
            raise Exception(f"BlueBubbles API error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error sending message: {str(e)}")
            raise
    
    async def get_server_info(self) -> Dict[str, Any]:
        """Get BlueBubbles server information"""
        url = f"{self.server_url}/api/v1/server/info"
        params = {'password': self.server_password}
        
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get server info: {str(e)}")
            raise
    
    async def ping_server(self) -> bool:
        """Ping the BlueBubbles server to check connectivity"""
        url = f"{self.server_url}/api/v1/ping"
        params = {'password': self.server_password}
        
        try:
            response = await self.client.get(url, params=params)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Server ping failed: {str(e)}")
            return False
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()


def get_bluebubbles_client() -> BlueBubblesClient:
    """Factory function to create BlueBubbles client from environment"""
    server_url = os.getenv("BLUEBUBBLES_SERVER_URL")
    server_password = os.getenv("BLUEBUBBLES_SERVER_PASSWORD")
    
    if not server_url or not server_password:
        raise ValueError(
            "BLUEBUBBLES_SERVER_URL and BLUEBUBBLES_SERVER_PASSWORD must be set"
        )
    
    return BlueBubblesClient(server_url, server_password)
