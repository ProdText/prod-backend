-- Supabase Auth Integration Schema
-- This replaces the custom users table with Supabase Auth integration

-- Drop the custom users table since we'll use auth.users
DROP TABLE IF EXISTS public.users;

-- Create user profiles table that links to auth.users
CREATE TABLE IF NOT EXISTS public.user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    bluebubbles_guid TEXT UNIQUE NOT NULL,  -- BlueBubbles message/chat GUID
    phone_number TEXT,                      -- Phone number from BlueBubbles handle
    chat_identifier TEXT,                   -- BlueBubbles chat identifier for responses
    onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE,
    first_interaction_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_interaction_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    interaction_count INTEGER NOT NULL DEFAULT 1,
    metadata JSONB DEFAULT '{}',            -- Additional user metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Enable Row Level Security (RLS)
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;

-- Create policies for user_profiles (drop existing first to avoid conflicts)
DROP POLICY IF EXISTS "service_role_full_access_profiles" ON public.user_profiles;
DROP POLICY IF EXISTS "users_own_profile" ON public.user_profiles;
DROP POLICY IF EXISTS "deny_public_access_profiles" ON public.user_profiles;

-- Service role has full access
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

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_profiles_bluebubbles_guid ON public.user_profiles (bluebubbles_guid);
CREATE INDEX IF NOT EXISTS idx_user_profiles_phone_number ON public.user_profiles (phone_number);
CREATE INDEX IF NOT EXISTS idx_user_profiles_last_interaction ON public.user_profiles (last_interaction_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_profiles_onboarding ON public.user_profiles (onboarding_completed);

-- Create function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_user_profiles_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
CREATE TRIGGER update_user_profiles_updated_at_trigger
    BEFORE UPDATE ON public.user_profiles
    FOR EACH ROW 
    EXECUTE FUNCTION update_user_profiles_updated_at();

-- Removed auto-trigger for user profile creation
-- This was causing conflicts with manual profile creation in the service layer
-- User profiles will be created explicitly by the AuthUserService
