#!/bin/bash

# =====================================================
# SUPABASE RESET SCRIPT
# =====================================================
# This script will completely reset your Supabase database
# WARNING: This will delete ALL data and users!
# =====================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SUPABASE_URL="${SUPABASE_URL}"
SUPABASE_SERVICE_ROLE_KEY="${SUPABASE_SERVICE_ROLE_KEY}"
SQL_FILE="sql/reset_supabase.sql"

echo -e "${BLUE}=====================================================${NC}"
echo -e "${BLUE}SUPABASE DATABASE RESET SCRIPT${NC}"
echo -e "${BLUE}=====================================================${NC}"

# Check if environment variables are set
if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_SERVICE_ROLE_KEY" ]; then
    echo -e "${RED}❌ Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set${NC}"
    echo -e "${YELLOW}💡 Make sure your .env file is loaded or export these variables${NC}"
    exit 1
fi

# Check if SQL file exists
if [ ! -f "$SQL_FILE" ]; then
    echo -e "${RED}❌ Error: SQL file not found: $SQL_FILE${NC}"
    exit 1
fi

echo -e "${YELLOW}⚠️  WARNING: This will DELETE ALL DATA in your Supabase database!${NC}"
echo -e "${YELLOW}   - All auth users will be deleted${NC}"
echo -e "${YELLOW}   - All tables will be dropped and recreated${NC}"
echo -e "${YELLOW}   - All webhook events will be lost${NC}"
echo ""
read -p "Are you sure you want to continue? (type 'YES' to confirm): " confirm

if [ "$confirm" != "YES" ]; then
    echo -e "${BLUE}❌ Reset cancelled${NC}"
    exit 0
fi

echo ""
echo -e "${BLUE}🚀 Starting Supabase reset...${NC}"

# Extract project ID from URL
PROJECT_ID=$(echo "$SUPABASE_URL" | sed -n 's/.*https:\/\/\([^.]*\)\.supabase\.co.*/\1/p')
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}❌ Error: Could not extract project ID from SUPABASE_URL${NC}"
    exit 1
fi

echo -e "${BLUE}📊 Project ID: $PROJECT_ID${NC}"

# Function to execute SQL
execute_sql() {
    local sql_content="$1"
    local description="$2"
    
    echo -e "${BLUE}🔄 $description...${NC}"
    
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -X POST \
        "$SUPABASE_URL/rest/v1/rpc/exec_sql" \
        -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
        -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"sql\": $(echo "$sql_content" | jq -Rs .)}")
    
    http_code=$(echo "$response" | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
    body=$(echo "$response" | sed -e 's/HTTPSTATUS\:.*//g')
    
    if [ "$http_code" -eq 200 ] || [ "$http_code" -eq 201 ]; then
        echo -e "${GREEN}✅ $description completed${NC}"
    else
        echo -e "${RED}❌ $description failed (HTTP $http_code)${NC}"
        echo -e "${RED}Response: $body${NC}"
        return 1
    fi
}

# Alternative method using psql if available
execute_sql_psql() {
    echo -e "${BLUE}🔄 Executing SQL script via direct connection...${NC}"
    
    # Extract connection details
    DB_HOST="db.${PROJECT_ID}.supabase.co"
    DB_PORT="5432"
    DB_NAME="postgres"
    DB_USER="postgres"
    
    echo -e "${YELLOW}💡 You'll need to enter your database password${NC}"
    echo -e "${YELLOW}   (This is your project's database password, not the service role key)${NC}"
    
    PGPASSWORD="" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$SQL_FILE"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ SQL script executed successfully${NC}"
    else
        echo -e "${RED}❌ SQL script execution failed${NC}"
        return 1
    fi
}

# Try to execute the SQL file
echo -e "${BLUE}📄 Reading SQL file: $SQL_FILE${NC}"
sql_content=$(cat "$SQL_FILE")

# Method 1: Try REST API (may not work for all operations)
echo -e "${BLUE}🔄 Attempting reset via REST API...${NC}"
if execute_sql "$sql_content" "Database reset"; then
    echo -e "${GREEN}🎉 Database reset completed successfully via REST API!${NC}"
else
    echo -e "${YELLOW}⚠️  REST API method failed, trying direct connection...${NC}"
    
    # Method 2: Use psql if available
    if command -v psql &> /dev/null; then
        if execute_sql_psql; then
            echo -e "${GREEN}🎉 Database reset completed successfully via psql!${NC}"
        else
            echo -e "${RED}❌ Both methods failed. Please run the SQL manually in Supabase SQL Editor${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}❌ psql not available. Please install PostgreSQL client or run SQL manually${NC}"
        echo -e "${BLUE}📋 Manual steps:${NC}"
        echo -e "${BLUE}   1. Go to your Supabase Dashboard${NC}"
        echo -e "${BLUE}   2. Navigate to SQL Editor${NC}"
        echo -e "${BLUE}   3. Copy and paste the contents of: $SQL_FILE${NC}"
        echo -e "${BLUE}   4. Execute the script${NC}"
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}=====================================================${NC}"
echo -e "${GREEN}✅ SUPABASE RESET COMPLETE!${NC}"
echo -e "${GREEN}=====================================================${NC}"
echo -e "${GREEN}Your database has been completely reset with:${NC}"
echo -e "${GREEN}✅ All auth users deleted${NC}"
echo -e "${GREEN}✅ All tables recreated with latest schema${NC}"
echo -e "${GREEN}✅ RLS policies configured${NC}"
echo -e "${GREEN}✅ Triggers and functions set up${NC}"
echo -e "${GREEN}✅ Indexes created for performance${NC}"
echo -e "${GREEN}✅ Onboarding support enabled${NC}"
echo ""
echo -e "${BLUE}🚀 Your webhook system is ready for fresh testing!${NC}"
