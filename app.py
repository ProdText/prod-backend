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
from dotenv import load_dotenv

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

supabase: Client = create_client(supabase_url, supabase_service_role_key)

# Optional webhook shared secret for validation
WEBHOOK_SHARED_SECRET = os.getenv("WEBHOOK_SHARED_SECRET")


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    service: str


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


async def insert_webhook_event(
    event_id: str,
    event_type: str,
    headers: Dict[str, Any],
    payload: Dict[str, Any]
) -> bool:
    """
    Insert webhook event into Supabase with graceful idempotency handling.
    Returns True if successful, False if duplicate (idempotent).
    """
    try:
        # Prepare the event data
        event_data = {
            "id": event_id,
            "source": "bluebubbles",
            "event_type": event_type,
            "headers": headers,
            "payload": payload
        }
        
        # Insert with upsert to handle duplicates gracefully
        result = supabase.table("bb_events").upsert(
            event_data,
            on_conflict="id"
        ).execute()
        
        logger.info(f"Successfully processed event {event_id} (type: {event_type})")
        return True
        
    except Exception as e:
        logger.error(f"Failed to insert event {event_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/healthz", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        service="bluebubbles-webhook-receiver"
    )


@app.post("/webhooks/bluebubbles", response_model=WebhookResponse)
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
    4. Generates event ID by hashing raw body
    5. Stores event in Supabase with idempotency
    """
    
    # Read raw body for hashing
    raw_body = await request.body()
    
    if not raw_body:
        raise HTTPException(status_code=400, detail="Empty request body")
    
    # Validate shared secret if configured
    if not validate_shared_secret(x_shared_secret):
        logger.warning("Invalid or missing X-Shared-Secret header")
        raise HTTPException(status_code=401, detail="Invalid or missing X-Shared-Secret")
    
    # Parse JSON payload
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in request body: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    
    # Generate event ID from raw body hash
    event_id = generate_event_id(raw_body)
    
    # Extract event type from payload
    event_type = payload.get("type", "unknown")
    
    # Convert headers to dict for storage
    headers_dict = dict(request.headers)
    
    # Log the incoming webhook
    logger.info(f"Received BlueBubbles webhook - Event ID: {event_id}, Type: {event_type}")
    
    # Insert event into database
    await insert_webhook_event(
        event_id=event_id,
        event_type=event_type,
        headers=headers_dict,
        payload=payload
    )
    
    return WebhookResponse(
        success=True,
        event_id=event_id,
        message=f"Successfully processed {event_type} event"
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
