import os
import json
import hashlib
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions
from dotenv import load_dotenv

# Import our new services and models
from models.message import WebhookPayload, MessageResponse
from services.auth_user_service import AuthUserService
from services.message_processor import MessageProcessor
from services.bluebubbles_client import get_bluebubbles_client

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="BlueBubbles Webhook Receiver",
    description="FastAPI webhook receiver for BlueBubbles events",
    version="1.0.0"
)

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not supabase_url or not supabase_service_role_key:
    raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment variables")

supabase_client = create_client(
    supabase_url, 
    supabase_service_role_key,
    options=ClientOptions(
        auto_refresh_token=False,
        persist_session=False
    )
)

# Initialize services with auth integration
auth_user_service = AuthUserService(supabase_client)
bluebubbles_client = get_bluebubbles_client()
message_processor = MessageProcessor(auth_user_service, bluebubbles_client)

# Optional webhook shared secret for validation
WEBHOOK_SHARED_SECRET = os.getenv("WEBHOOK_SHARED_SECRET")


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    service: str


# Legacy response model for backwards compatibility
class WebhookResponse(BaseModel):
    success: bool
    event_id: str
    message: str


def generate_event_id(raw_body: bytes) -> str:
    """Generate a unique event ID by hashing the raw request body."""
    return hashlib.sha256(raw_body).hexdigest()


def validate_shared_secret(x_shared_secret: Optional[str]) -> bool:
    """Validate the X-Shared-Secret header if configured."""
    if not WEBHOOK_SHARED_SECRET:
        return True  # No validation required if secret not configured
    return x_shared_secret == WEBHOOK_SHARED_SECRET




@app.get("/healthz", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        service="bluebubbles-webhook-receiver"
    )


@app.post("/webhooks/bluebubbles", response_model=MessageResponse)
async def receive_bluebubbles_webhook(
    request: Request,
    x_shared_secret: Optional[str] = Header(None, alias="X-Shared-Secret")
):
    """
    Receive and process BlueBubbles webhook events.
    
    This endpoint:
    1. Reads the raw request body
    2. Validates JSON format
    3. Optionally checks X-Shared-Secret header
    4. Processes message and manages user state
    5. Sends response back to BlueBubbles if applicable
    """
    
    # Read raw body
    raw_body = await request.body()
    
    if not raw_body:
        raise HTTPException(status_code=400, detail="Empty request body")
    
    # Validate shared secret if configured
    if not validate_shared_secret(x_shared_secret):
        logger.warning("Invalid or missing X-Shared-Secret header")
        raise HTTPException(status_code=401, detail="Invalid or missing X-Shared-Secret")
    
    # Parse JSON payload
    try:
        payload_dict = json.loads(raw_body)
        webhook_payload = WebhookPayload(**payload_dict)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in request body: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        logger.error(f"Invalid webhook payload structure: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid payload: {str(e)}")
    
    # Generate event ID for logging
    event_id = generate_event_id(raw_body)
    event_type = webhook_payload.type
    
    # Log the incoming webhook
    logger.info(f"Received BlueBubbles webhook - Event ID: {event_id}, Type: {event_type}")
    
    # Process the message
    try:
        result = await message_processor.process_webhook_message(webhook_payload)
        
        logger.info(f"Processed webhook {event_id}: {result.message}")
        return result
        
    except Exception as e:
        logger.error(f"Error processing webhook {event_id}: {str(e)}")
        return MessageResponse(
            success=False,
            user_guid="unknown",
            message=f"Processing error: {str(e)}"
        )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
