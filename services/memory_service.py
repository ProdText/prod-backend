import logging
import httpx
import os
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class MemoryService:
    """Service for posting message data to the memory ingestion endpoint"""
    
    def __init__(self):
        self.memory_endpoint = "https://memory.tryamygdala.tech/api/ingest/episode"
    
    async def ingest_message(
        self,
        message_id: str,
        message_body: str,
        user_id: str,
        source_description: str = "imessage"
    ) -> bool:
        """
        Post message data to memory endpoint for onboarded users
        
        Args:
            message_id: Unique message identifier
            message_body: The actual message content
            user_id: User UUID from database
            source_description: Source of the message (default: imessage)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            payload = {
                "name": message_id,
                "episode_body": message_body,
                "source_description": source_description,
                "reference_time": datetime.now().isoformat() + "Z",
                "group_id": user_id
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.memory_endpoint,
                    json=payload,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    logger.info(f"Successfully ingested message {message_id} for user {user_id}")
                    return True
                else:
                    logger.error(f"Failed to ingest message {message_id}: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error ingesting message {message_id} for user {user_id}: {str(e)}")
            return False
