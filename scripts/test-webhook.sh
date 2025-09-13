#!/bin/bash

# Load PORT from .env file if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Set default port if not specified
PORT=${PORT:-8000}

# Sample BlueBubbles webhook payload based on documentation
SAMPLE_PAYLOAD='{
  "type": "new-message",
  "data": {
    "guid": "sample-message-guid-12345",
    "text": "Hello, this is a test message from BlueBubbles!",
    "handle": {
      "address": "+1234567890",
      "country": "us",
      "uncanonicalizedId": "+1234567890"
    },
    "hasAttachments": false,
    "hasDdResults": false,
    "dateSent": 1640995200000,
    "dateDelivered": 1640995201000,
    "dateRead": null,
    "isFromMe": false,
    "isDelayed": false,
    "isAutoReply": false,
    "isSystemMessage": false,
    "isServiceMessage": false,
    "isForward": false,
    "isArchived": false,
    "cacheRoomnames": null,
    "isAudioMessage": false,
    "datePlayed": null,
    "itemType": 0,
    "otherHandle": null,
    "groupTitle": null,
    "groupActionType": 0,
    "isExpired": false,
    "balloonBundleId": null,
    "associatedMessageGuid": null,
    "associatedMessageType": null,
    "expressiveSendStyleId": null,
    "timeExpressiveSendStyleId": null,
    "chats": [
      {
        "guid": "SMS;-;+1234567890",
        "style": 45,
        "chatIdentifier": "+1234567890",
        "isArchived": false,
        "isFiltered": false,
        "participants": [
          {
            "address": "+1234567890",
            "country": "us",
            "uncanonicalizedId": "+1234567890"
          }
        ]
      }
    ]
  }
}'

echo "Testing BlueBubbles webhook endpoint..."
echo "URL: http://localhost:$PORT/webhooks/bluebubbles"
echo "Payload: $SAMPLE_PAYLOAD"
echo ""

# Make the POST request
response=$(curl -s -w "\nHTTP_CODE:%{http_code}\n" \
  -X POST \
  -H "Content-Type: application/json" \
  -H "X-Shared-Secret: ${WEBHOOK_SHARED_SECRET:-test-secret}" \
  -d "$SAMPLE_PAYLOAD" \
  "http://localhost:$PORT/webhooks/bluebubbles")

# Extract HTTP code and response body
http_code=$(echo "$response" | grep "HTTP_CODE:" | cut -d: -f2)
response_body=$(echo "$response" | sed '/HTTP_CODE:/d')

echo "Response (HTTP $http_code):"
echo "$response_body" | jq . 2>/dev/null || echo "$response_body"

# Check if request was successful
if [ "$http_code" = "200" ]; then
    echo ""
    echo "✅ Webhook test successful!"
else
    echo ""
    echo "❌ Webhook test failed with HTTP code: $http_code"
    exit 1
fi
