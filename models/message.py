from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class BlueBubblesHandle(BaseModel):
    """BlueBubbles handle/contact information"""
    address: str
    country: Optional[str] = None
    uncanonicalizedId: Optional[str] = None


class BlueBubblesChat(BaseModel):
    """BlueBubbles chat information"""
    guid: str
    style: Optional[int] = None
    chatIdentifier: Optional[str] = None
    isArchived: Optional[bool] = False
    isFiltered: Optional[bool] = False
    participants: Optional[List[BlueBubblesHandle]] = []


class BlueBubblesMessage(BaseModel):
    """BlueBubbles message data structure"""
    guid: Optional[str] = None  # Make optional for read receipts
    text: Optional[str] = None
    handle: Optional[BlueBubblesHandle] = None
    hasAttachments: Optional[bool] = False
    dateSent: Optional[int] = None
    dateDelivered: Optional[int] = None
    dateRead: Optional[int] = None
    isFromMe: Optional[bool] = False
    isDelayed: Optional[bool] = False
    isAutoReply: Optional[bool] = False
    isSystemMessage: Optional[bool] = False
    isServiceMessage: Optional[bool] = False
    chats: Optional[List[BlueBubblesChat]] = []
    # Additional fields for read receipts and other events
    chatGuid: Optional[str] = None
    read: Optional[bool] = None


class WebhookPayload(BaseModel):
    """Complete webhook payload from BlueBubbles"""
    type: str
    data: BlueBubblesMessage


class MessageResponse(BaseModel):
    """Response model for message processing"""
    success: bool
    user_guid: str
    message: str
    sent_response: Optional[bool] = False
