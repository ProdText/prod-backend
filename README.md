ProdText# BlueBubbles Webhook Receiver

A production-ready Python 3.11+ FastAPI webhook receiver for BlueBubbles events with Supabase integration.

## Table of Contents
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Endpoints](#api-endpoints)
- [Development Setup](#development-setup)
- [Testing](#testing)
- [Production Deployment](#production-deployment)
- [BlueBubbles Integration](#bluebubbles-integration)
- [Database Schema](#database-schema)
- [Security](#security-features)
- [Monitoring](#monitoring-and-logging)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## Features

- **FastAPI-based webhook receiver** for BlueBubbles events
- **Supabase integration** for event storage with RLS security
- **Event deduplication** using SHA-256 hashing of raw request body
- **Optional webhook authentication** via X-Shared-Secret header
- **Health check endpoint** for monitoring
- **Docker support** with multi-stage builds
- **Comprehensive logging** and error handling
- **Graceful idempotency** handling for duplicate events

## Prerequisites

- **Python 3.11+** (tested with 3.11 and 3.12)
- **Supabase account** with a project created
- **BlueBubbles Server** running on macOS
- **Git** for version control
- **ngrok** or **Cloudflare Tunnel** for public webhook access (development)

## Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/your-username/prod-backend.git
cd prod-backend

# Copy environment template
cp .env.example .env

# Edit .env with your actual Supabase credentials
nano .env  # or use your preferred editor
```

### 2. Supabase Database Setup

Run the bootstrap SQL to create the required table and security policies:

```sql
-- Execute the contents of sql/bootstrap.sql in your Supabase SQL editor
-- This creates the bb_events table with RLS enabled
```

### 3. Install Dependencies

```bash
# Create virtual environment (use python3 if python3.11 not available)
python3.11 -m venv venv
# or
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Run the Server

```bash
# Development mode with auto-reload
python app.py

# Or with uvicorn directly (more control)
uvicorn app:app --host 0.0.0.0 --port 8000 --reload --log-level info

# Production mode (no reload)
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
```

### 5. Verify Installation

```bash
# Test health endpoint
curl http://localhost:8000/healthz

# Expected response:
# {"status":"healthy","timestamp":"...","service":"bluebubbles-webhook-receiver"}
```

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `PORT` | No | Server port (default: 8000) |
| `SUPABASE_URL` | Yes | Your Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Supabase service role key |
| `WEBHOOK_SHARED_SECRET` | No | Optional webhook authentication secret |

### Example .env

```bash
# Server Configuration
PORT=8000

# Supabase Configuration (REQUIRED)
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Webhook Security (OPTIONAL - comment out if BlueBubbles doesn't support secrets)
# WEBHOOK_SHARED_SECRET=your-secure-secret-here
```

### Getting Supabase Credentials

1. Go to [Supabase Dashboard](https://supabase.com/dashboard)
2. Select your project
3. Navigate to **Settings** → **API**
4. Copy:
   - **Project URL** → `SUPABASE_URL`
   - **service_role secret** → `SUPABASE_SERVICE_ROLE_KEY` (⚠️ Keep this secret!)

## API Endpoints

### Health Check
```
GET /healthz
```

Returns server health status and timestamp.

### BlueBubbles Webhook
```
POST /webhooks/bluebubbles
Content-Type: application/json
X-Shared-Secret: your-secret (optional)
```

Receives and processes BlueBubbles webhook events.

## Development Setup

### Local Development Workflow

```bash
# 1. Start the webhook receiver
source venv/bin/activate
python app.py

# 2. In another terminal, start ngrok tunnel
ngrok http 8000

# 3. Copy the HTTPS URL from ngrok output
# Example: https://abc123.ngrok-free.app

# 4. Configure BlueBubbles with: https://abc123.ngrok-free.app/webhooks/bluebubbles
```

### Code Structure for Developers

```python
# app.py - Main application structure

# Key functions:
# - generate_event_id(raw_body) -> str
# - validate_shared_secret(header) -> bool  
# - insert_webhook_event(...) -> bool

# Key endpoints:
# - GET /healthz - Health check
# - POST /webhooks/bluebubbles - Main webhook receiver
```

## Tunneling for Development

### Using ngrok

```bash
# Install ngrok (if not already installed)
# https://ngrok.com/download

# Start your server
python app.py

# In another terminal, create tunnel
ngrok http 8000

# Use the HTTPS URL for webhook registration
# Example: https://abc123.ngrok.io/webhooks/bluebubbles
```

### Using Cloudflare Tunnel

```bash
# Install cloudflared
# https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/

# Start tunnel
cloudflared tunnel --url http://localhost:8000

# Use the provided URL for webhook registration
```

## BlueBubbles Integration

### Webhook Registration

1. **Open BlueBubbles Server** on your Mac
2. **Navigate to:** Server Settings → Webhooks
3. **Add New Webhook:**
   - **URL:** `https://your-tunnel-url.ngrok-free.app/webhooks/bluebubbles`
   - **Authentication:** Leave empty (most BB servers don't support secrets)
4. **Select Events** (recommended):
   - ✅ New Messages
   - ✅ Message Updates (delivered, read, etc)
   - ✅ Message Errors  
   - ✅ Group Name Changes
   - ✅ Participant Added/Removed/Left
   - ✅ Chat Read Status Changes
   - ✅ Typing Indicators
   - ✅ BB Server Update
   - ✅ BB Server URL Change

### Supported Event Types

The webhook receiver handles all BlueBubbles event types:

| Event Type | Description | Payload Fields |
|------------|-------------|----------------|
| `new-message` | New incoming/outgoing message | `guid`, `text`, `handle`, `chats` |
| `updated-message` | Message status updates | `guid`, `dateDelivered`, `dateRead` |
| `message-send-error` | Failed message delivery | `guid`, `error` |
| `group-name-change` | Group chat name changed | `chat`, `newName` |
| `participant-added` | User added to group | `chat`, `participant` |
| `participant-removed` | User removed from group | `chat`, `participant` |
| `typing-indicator` | Someone is typing | `chat`, `display` |

### Event Processing Flow

```
BlueBubbles Server → ngrok → FastAPI App → Supabase
                                ↓
                         1. Validate JSON
                         2. Generate event ID (SHA-256)
                         3. Check for duplicates
                         4. Store in database
```

## Testing

### Automated Testing

```bash
# Ensure server is running
python app.py &
SERVER_PID=$!

# Wait for server to start
sleep 2

# Run the comprehensive test script
./scripts/test-webhook.sh

# Stop server
kill $SERVER_PID
```

### Manual Testing

#### 1. Health Check
```bash
curl -s http://localhost:8000/healthz | jq .
# Expected: {"status":"healthy",...}
```

#### 2. Webhook Test (No Authentication)
```bash
curl -X POST http://localhost:8000/webhooks/bluebubbles \
  -H "Content-Type: application/json" \
  -d '{
    "type": "new-message",
    "data": {
      "guid": "test-message-123",
      "text": "Hello from BlueBubbles!",
      "isFromMe": false,
      "chats": [{"guid": "SMS;-;+1234567890"}]
    }
  }' | jq .
```

#### 3. Webhook Test (With Authentication)
```bash
# Only if WEBHOOK_SHARED_SECRET is set in .env
curl -X POST http://localhost:8000/webhooks/bluebubbles \
  -H "Content-Type: application/json" \
  -H "X-Shared-Secret: your-secret" \
  -d '{"type":"test","data":{"message":"auth test"}}' | jq .
```

#### 4. Test Event Deduplication
```bash
# Send the same payload twice - second should be idempotent
PAYLOAD='{"type":"duplicate-test","data":{"id":"same-payload"}}'
curl -X POST http://localhost:8000/webhooks/bluebubbles \
  -H "Content-Type: application/json" -d "$PAYLOAD"
  
# Send again - should get same event_id
curl -X POST http://localhost:8000/webhooks/bluebubbles \
  -H "Content-Type: application/json" -d "$PAYLOAD"
```

### Expected Responses

#### Success Response
```json
{
  "success": true,
  "event_id": "a1b2c3d4e5f6789...",
  "message": "Successfully processed new-message event"
}
```

#### Error Responses
```json
// Invalid JSON
{"detail": "Invalid JSON: Expecting value: line 1 column 1 (char 0)"}

// Missing shared secret (if required)
{"detail": "Invalid or missing X-Shared-Secret"}

// Database error
{"detail": "Database error: ..."}
```

### Load Testing

```bash
# Install apache bench
brew install httpd  # macOS

# Test with 100 requests, 10 concurrent
ab -n 100 -c 10 -H "Content-Type: application/json" \
   -p test-payload.json http://localhost:8000/webhooks/bluebubbles
```

## Production Deployment

### Environment Setup

```bash
# Production .env (no comments)
PORT=8000
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
# WEBHOOK_SHARED_SECRET=production-secret
```

### Systemd Service (Linux)

Create `/etc/systemd/system/bluebubbles-webhook.service`:

```ini
[Unit]
Description=BlueBubbles Webhook Receiver
After=network.target

[Service]
Type=simple
User=webhook
WorkingDirectory=/opt/bluebubbles-webhook
Environment=PATH=/opt/bluebubbles-webhook/venv/bin
ExecStart=/opt/bluebubbles-webhook/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable bluebubbles-webhook
sudo systemctl start bluebubbles-webhook
sudo systemctl status bluebubbles-webhook
```

### Reverse Proxy (Nginx)

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Docker Deployment

### Build and Run

```bash
# Build the image
docker build -t bluebubbles-webhook .

# Run with environment file
docker run -d \
  --name bluebubbles-webhook \
  --env-file .env \
  -p 8000:8000 \
  bluebubbles-webhook
```

### Docker Compose (Optional)

Create `docker-compose.yml`:

```yaml
version: '3.8'
services:
  webhook-receiver:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
```

Run with:
```bash
docker-compose up -d
```

## Database Schema

The `bb_events` table stores all webhook events:

```sql
CREATE TABLE public.bb_events (
    id TEXT PRIMARY KEY,              -- SHA-256 hash of raw request body
    source TEXT NOT NULL,             -- Always 'bluebubbles'
    event_type TEXT NOT NULL,         -- Event type from payload
    received_at TIMESTAMPTZ DEFAULT NOW(),
    headers JSONB,                    -- Request headers
    payload JSONB                     -- Full webhook payload
);
```

## Security Features

- **Row Level Security (RLS)** enabled on database table
- **Deny-all policy** by default (only service-role can access)
- **Optional webhook authentication** via shared secret
- **Request validation** and sanitization
- **Non-root Docker user** for container security

## Event Deduplication

The system uses SHA-256 hashing of the raw request body to generate unique event IDs. This ensures:

- **Idempotent processing** - duplicate webhooks are safely ignored
- **Reliable event tracking** - each unique payload gets a unique ID
- **Database integrity** - primary key constraint prevents duplicates

## Monitoring and Logging

- **Structured logging** with timestamps and levels
- **Health check endpoint** for uptime monitoring
- **Error tracking** with detailed exception information
- **Request/response logging** for debugging

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Verify `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`
   - Check network connectivity to Supabase

2. **Webhook Authentication Failed**
   - Verify `X-Shared-Secret` header matches `WEBHOOK_SHARED_SECRET`
   - Check BlueBubbles webhook configuration

3. **JSON Parsing Error**
   - Ensure BlueBubbles is sending valid JSON
   - Check request Content-Type header

4. **Port Already in Use**
   - Change `PORT` in .env file
   - Kill existing processes: `lsof -ti:8000 | xargs kill`

### Logs

Check application logs for detailed error information:

```bash
# If running directly
python app.py

# If running with Docker
docker logs bluebubbles-webhook
```

## Contributing

### Development Setup

```bash
# 1. Fork and clone the repository
git clone https://github.com/your-username/prod-backend.git
cd prod-backend

# 2. Create development branch
git checkout -b feature/your-feature-name

# 3. Setup development environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Setup pre-commit hooks (optional)
pip install pre-commit
pre-commit install
```

### Project Structure

```
prod-backend/
├── app.py                 # Main FastAPI application
├── requirements.txt       # Python dependencies  
├── .env.example          # Environment template
├── .gitignore            # Git ignore patterns
├── Dockerfile            # Container configuration
├── .dockerignore         # Docker ignore patterns
├── README.md             # This documentation
├── sql/
│   └── bootstrap.sql     # Database schema and policies
└── scripts/
    └── test-webhook.sh   # Automated test script
```

### Code Style Guidelines

- **Python:** Follow PEP 8, use type hints
- **Imports:** Group stdlib, third-party, local imports
- **Functions:** Document with docstrings
- **Variables:** Use descriptive names
- **Error Handling:** Use appropriate HTTP status codes

### Adding New Features

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/webhook-filtering`
3. **Implement** your changes with tests
4. **Update** documentation (README, docstrings)
5. **Test** thoroughly:
   ```bash
   # Run tests
   ./scripts/test-webhook.sh
   
   # Test with different event types
   # Test error conditions
   # Test edge cases
   ```
6. **Submit** a pull request with:
   - Clear description of changes
   - Test results
   - Updated documentation

### Common Development Tasks

#### Adding New Event Types
```python
# In app.py, update the webhook handler
@app.post("/webhooks/bluebubbles")
async def receive_webhook(request: Request):
    # Extract event type
    event_type = payload.get("type", "unknown")
    
    # Add custom processing for new event types
    if event_type == "new-event-type":
        # Custom processing logic
        pass
```

#### Adding Request Validation
```python
from pydantic import BaseModel

class WebhookPayload(BaseModel):
    type: str
    data: dict
    
# Use in endpoint
async def receive_webhook(payload: WebhookPayload):
    # Automatic validation
    pass
```

#### Adding Custom Headers
```python
# Check for custom headers
custom_header = request.headers.get("X-Custom-Header")
if custom_header:
    # Process custom header
    pass
```

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
- Check the [BlueBubbles Documentation](https://docs.bluebubbles.app/)
- Review application logs
- Open an issue in this repository