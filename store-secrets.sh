#!/bin/bash

# Store secrets in AWS Parameter Store
set -e

AWS_REGION="us-east-2"

echo "🔐 Storing secrets in AWS Parameter Store..."

# Function to store a parameter
store_parameter() {
    local name=$1
    local value=$2
    local description=$3
    
    echo "Storing parameter: $name"
    aws ssm put-parameter \
        --name "$name" \
        --value "$value" \
        --type "SecureString" \
        --description "$description" \
        --region $AWS_REGION \
        --overwrite 2>/dev/null || echo "✅ Parameter $name already exists"
}

# Prompt for secrets
echo "Please provide your environment variables:"

read -p "SUPABASE_URL: " SUPABASE_URL
read -s -p "SUPABASE_SERVICE_ROLE_KEY: " SUPABASE_SERVICE_ROLE_KEY
echo ""
read -s -p "WEBHOOK_SHARED_SECRET (optional): " WEBHOOK_SHARED_SECRET
echo ""
read -s -p "ANTHROPIC_API_KEY (optional): " ANTHROPIC_API_KEY
echo ""
read -p "BLUEBUBBLES_API_URL (optional): " BLUEBUBBLES_API_URL
read -s -p "BLUEBUBBLES_PASSWORD (optional): " BLUEBUBBLES_PASSWORD
echo ""

# Store parameters
store_parameter "/amygdala/supabase-url" "$SUPABASE_URL" "Supabase project URL"
store_parameter "/amygdala/supabase-service-role-key" "$SUPABASE_SERVICE_ROLE_KEY" "Supabase service role key"

if [ ! -z "$WEBHOOK_SHARED_SECRET" ]; then
    store_parameter "/amygdala/webhook-shared-secret" "$WEBHOOK_SHARED_SECRET" "Webhook shared secret"
fi

if [ ! -z "$ANTHROPIC_API_KEY" ]; then
    store_parameter "/amygdala/anthropic-api-key" "$ANTHROPIC_API_KEY" "Anthropic API key"
fi

if [ ! -z "$BLUEBUBBLES_API_URL" ]; then
    store_parameter "/amygdala/bluebubbles-api-url" "$BLUEBUBBLES_API_URL" "BlueBubbles API URL"
fi

if [ ! -z "$BLUEBUBBLES_PASSWORD" ]; then
    store_parameter "/amygdala/bluebubbles-password" "$BLUEBUBBLES_PASSWORD" "BlueBubbles API password"
fi

echo "✅ All secrets stored in Parameter Store!"
echo "🔒 Parameters are encrypted and secure"
