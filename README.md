ProdText# BlueBubbles Webhook Receiver

A production-ready Python FastAPI webhook receiver for BlueBubbles events with Supabase integration.

## Features

- **FastAPI-based webhook receiver** for BlueBubbles events
- **Supabase integration** for event storage with RLS security
- **Event deduplication** using SHA-256 hashing of raw request body
- **Optional webhook authentication** via X-Shared-Secret header
- **Health check endpoint** for monitoring
- **Docker support** with multi-stage builds
- **Comprehensive logging** and error handling
- **Graceful idempotency** handling for duplicate events

## Quick Start

### 1. Environment Setup

```bash
# Clone and navigate to the project
git clone <repository-url>
cd prod-backend

# Copy environment template
cp .env.example .env

# Edit .env with your actual values
nano .env
```

### 2. Supabase Database Setup

Run the bootstrap SQL to create the required table and security policies:

```sql
-- Execute the contents of sql/bootstrap.sql in your Supabase SQL editor
-- This creates the bb_events table with RLS enabled
```

### 3. Install Dependencies

```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Run the Server

```bash
# Development mode
python app.py

# Or with uvicorn directly
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
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
PORT=8000
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
WEBHOOK_SHARED_SECRET=your-secure-secret-here
```

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

## BlueBubbles Webhook Registration

1. Open BlueBubbles Server on your Mac
2. Go to **Server Settings** → **Webhooks**
3. Add a new webhook with your tunnel URL:
   ```
   https://your-tunnel-url.ngrok.io/webhooks/bluebubbles
   ```
4. Select the events you want to receive:
   - New Messages
   - Message Updates
   - Message Errors
   - Group Changes
   - Typing Indicators
   - etc.

5. If using shared secret authentication, add it in the webhook configuration

## Testing

### Manual Testing

Use the provided test script:

```bash
# Make sure your server is running
python app.py

# Run the test script
./scripts/test-webhook.sh
```

### Manual cURL Test

```bash
curl -X POST http://localhost:8000/webhooks/bluebubbles \
  -H "Content-Type: application/json" \
  -H "X-Shared-Secret: your-secret" \
  -d '{
    "type": "new-message",
    "data": {
      "guid": "test-message-123",
      "text": "Hello from BlueBubbles!",
      "isFromMe": false,
      "chats": [{"guid": "SMS;-;+1234567890"}]
    }
  }'
```

Expected response:
```json
{
  "success": true,
  "event_id": "a1b2c3d4e5f6...",
  "message": "Successfully processed new-message event"
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

## Development

### Project Structure

```
prod-backend/
├── app.py                 # Main FastAPI application
├── requirements.txt       # Python dependencies
├── .env.example          # Environment template
├── Dockerfile            # Container configuration
├── .dockerignore         # Docker ignore patterns
├── README.md             # This file
├── sql/
│   └── bootstrap.sql     # Database schema
└── scripts/
    └── test-webhook.sh   # Test script
```

### Adding New Features

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Update documentation
6. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
- Check the [BlueBubbles Documentation](https://docs.bluebubbles.app/)
- Review application logs
- Open an issue in this repository