# Supabase Database Reset Guide

This guide provides scripts to completely reset your Supabase database and remove all test data.

## ⚠️ WARNING
**These scripts will DELETE ALL DATA in your Supabase database including:**
- All auth users
- All webhook events  
- All user profiles
- All tables will be dropped and recreated

## 🚀 Quick Reset

### Option 1: Automated Script (Recommended)
```bash
# Load environment variables
source .env

# Run the reset script
./scripts/reset_supabase.sh
```

### Option 2: Manual SQL Execution
1. Go to your Supabase Dashboard
2. Navigate to **SQL Editor**
3. Copy and paste the contents of `sql/reset_supabase.sql`
4. Execute the script

## 📋 What Gets Reset

### Deleted:
- ❌ All auth users (`auth.users`)
- ❌ All user profiles (`public.user_profiles`) 
- ❌ All webhook events (`public.bb_events`)
- ❌ All existing triggers and functions

### Recreated:
- ✅ `bb_events` table with proper schema
- ✅ `user_profiles` table with onboarding support
- ✅ RLS policies for security
- ✅ Indexes for performance
- ✅ Triggers for auto-updating timestamps
- ✅ Functions for handling new users

## 🔧 New Schema Features

The reset includes the latest schema with:
- **Onboarding States**: `not_started`, `awaiting_otp`, `completed`
- **Phone Verification**: OTP verification tracking
- **Performance Indexes**: Optimized queries
- **Proper RLS**: Security policies configured

## 📊 Tables After Reset

### `user_profiles`
```sql
- id (UUID, FK to auth.users)
- bluebubbles_guid (TEXT, UNIQUE)
- phone_number (TEXT)
- chat_identifier (TEXT)
- onboarding_completed (BOOLEAN)
- onboarding_state (TEXT) -- NEW
- phone_verified (BOOLEAN) -- NEW  
- verified_at (TIMESTAMPTZ) -- NEW
- interaction_count (INTEGER)
- last_interaction_at (TIMESTAMPTZ)
- created_at (TIMESTAMPTZ)
- updated_at (TIMESTAMPTZ)
```

### `bb_events`
```sql
- id (TEXT, PK)
- source (TEXT)
- event_type (TEXT)
- received_at (TIMESTAMPTZ)
- headers (JSONB)
- payload (JSONB)
```

## 🔐 Security Policies

- **Service Role**: Full access to all tables
- **Authenticated Users**: Can only access their own profile
- **Public**: Denied access to all tables
- **bb_events**: Service role only (webhook storage)

## 🚀 After Reset

1. **Configure Supabase Authentication:**
   - Enable phone authentication
   - Disable email authentication  
   - Add Twilio credentials

2. **Test the system:**
   - Send a test webhook
   - Verify user creation works
   - Test OTP onboarding flow

## 🛠️ Troubleshooting

### Script Fails
- Check environment variables are set
- Verify Supabase service role key has admin permissions
- Try manual SQL execution in Supabase Dashboard

### Permission Errors
- Ensure you're using the service role key (not anon key)
- Check RLS policies are properly configured

### Connection Issues
- Verify SUPABASE_URL format: `https://xxx.supabase.co`
- Check network connectivity to Supabase
