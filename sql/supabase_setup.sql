-- Consolidated Supabase Setup for BlueBubbles Backend
-- This file sets up the complete database schema with concurrency-safe constraints
-- Run this file in your Supabase SQL editor or via psql

-- =============================================================================
-- CLEANUP: Drop existing tables and policies
-- =============================================================================

-- Drop existing policies first
DROP POLICY IF EXISTS "service_role_full_access_profiles" ON public.user_profiles;
DROP POLICY IF EXISTS "users_own_profile" ON public.user_profiles;
DROP POLICY IF EXISTS "deny_public_access_profiles" ON public.user_profiles;

-- Drop existing tables
DROP TABLE IF EXISTS public.user_profiles;
DROP TABLE IF EXISTS public.users;

-- Drop existing functions
DROP FUNCTION IF EXISTS update_user_profiles_updated_at();

-- =============================================================================
-- MAIN SCHEMA: User Profiles with Supabase Auth Integration
-- =============================================================================

-- Create user profiles table that links to auth.users
CREATE TABLE public.user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    bluebubbles_guid TEXT UNIQUE NOT NULL,  -- BlueBubbles message/chat GUID
    phone_number TEXT UNIQUE,               -- Phone number from BlueBubbles handle (UNIQUE for concurrency)
    email TEXT UNIQUE,                      -- Email address (UNIQUE for concurrency)
    chat_identifier TEXT,                   -- BlueBubbles chat identifier for responses
    onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE,
    onboarding_state TEXT NOT NULL DEFAULT 'not_started',
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    verified_at TIMESTAMPTZ,
    first_interaction_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_interaction_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    interaction_count INTEGER NOT NULL DEFAULT 1,
    metadata JSONB DEFAULT '{}',            -- Additional user metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- SECURITY: Row Level Security (RLS) Policies
-- =============================================================================

-- Enable Row Level Security
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;

-- Service role has full access (for backend operations)
CREATE POLICY "service_role_full_access_profiles" ON public.user_profiles
    FOR ALL
    TO service_role
    USING (TRUE)
    WITH CHECK (TRUE);

-- Authenticated users can only access their own profile
CREATE POLICY "users_own_profile" ON public.user_profiles
    FOR ALL
    TO authenticated
    USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id);

-- Deny public access
CREATE POLICY "deny_public_access_profiles" ON public.user_profiles
    FOR ALL
    TO PUBLIC
    USING (FALSE)
    WITH CHECK (FALSE);

-- =============================================================================
-- PERFORMANCE: Indexes for fast lookups and concurrency
-- =============================================================================

CREATE INDEX idx_user_profiles_bluebubbles_guid ON public.user_profiles (bluebubbles_guid);
CREATE INDEX idx_user_profiles_phone_number ON public.user_profiles (phone_number);
CREATE INDEX idx_user_profiles_email ON public.user_profiles (email);
CREATE INDEX idx_user_profiles_last_interaction ON public.user_profiles (last_interaction_at DESC);
CREATE INDEX idx_user_profiles_onboarding ON public.user_profiles (onboarding_completed);
CREATE INDEX idx_user_profiles_onboarding_state ON public.user_profiles (onboarding_state);
CREATE INDEX idx_user_profiles_email_verified ON public.user_profiles (email_verified);

-- =============================================================================
-- TRIGGERS: Automatic timestamp updates
-- =============================================================================

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_user_profiles_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to automatically update updated_at on row changes
CREATE TRIGGER update_user_profiles_updated_at_trigger
    BEFORE UPDATE ON public.user_profiles
    FOR EACH ROW 
    EXECUTE FUNCTION update_user_profiles_updated_at();

-- =============================================================================
-- COMMENTS: Documentation for future reference
-- =============================================================================

COMMENT ON TABLE public.user_profiles IS 'User profiles linked to Supabase auth.users with BlueBubbles integration';
COMMENT ON COLUMN public.user_profiles.bluebubbles_guid IS 'Unique BlueBubbles message/chat GUID for identification';
COMMENT ON COLUMN public.user_profiles.phone_number IS 'Phone number from BlueBubbles handle (unique constraint for concurrency)';
COMMENT ON COLUMN public.user_profiles.email IS 'Email address for OTP verification (unique constraint for concurrency)';
COMMENT ON COLUMN public.user_profiles.onboarding_state IS 'Current onboarding state: not_started, awaiting_email, awaiting_email_otp, awaiting_integrations, completed';
COMMENT ON COLUMN public.user_profiles.email_verified IS 'Whether the users email has been verified via OTP';
COMMENT ON COLUMN public.user_profiles.verified_at IS 'Timestamp when email verification was completed';

-- =============================================================================
-- VALIDATION: Check constraints for data integrity
-- =============================================================================

-- Ensure onboarding_state has valid values
ALTER TABLE public.user_profiles 
ADD CONSTRAINT check_onboarding_state 
CHECK (onboarding_state IN ('not_started', 'awaiting_email', 'awaiting_email_otp', 'awaiting_integrations', 'completed'));

-- Ensure email format is valid (basic check)
ALTER TABLE public.user_profiles 
ADD CONSTRAINT check_email_format 
CHECK (email IS NULL OR email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$');

-- Ensure phone number format (basic E.164 check)
ALTER TABLE public.user_profiles 
ADD CONSTRAINT check_phone_format 
CHECK (phone_number IS NULL OR phone_number ~* '^\+[1-9]\d{1,14}$');

-- =============================================================================
-- COMPLETION MESSAGE
-- =============================================================================

-- Log successful setup
DO $$
BEGIN
    RAISE NOTICE 'BlueBubbles Supabase setup completed successfully!';
    RAISE NOTICE 'Tables created: user_profiles';
    RAISE NOTICE 'Policies enabled: RLS with service_role access';
    RAISE NOTICE 'Indexes created: 7 performance indexes';
    RAISE NOTICE 'Constraints added: Unique constraints for concurrency safety';
    RAISE NOTICE 'Ready for production use with concurrent user support';
END $$;
