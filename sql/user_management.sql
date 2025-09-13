-- User management schema for BlueBubbles integration
-- This replaces the bb_events table with a focus on user tracking

-- Drop the old bb_events table if it exists
DROP TABLE IF EXISTS public.bb_events;

-- Create users table for tracking BlueBubbles users
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guid TEXT UNIQUE NOT NULL,  -- BlueBubbles message/chat GUID for user identification
    phone_number TEXT,          -- Optional: extracted from handle
    chat_identifier TEXT,       -- BlueBubbles chat identifier
    onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE,
    first_interaction_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_interaction_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    interaction_count INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Enable Row Level Security (RLS)
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

-- Create a policy that allows service-role full access
CREATE POLICY "service_role_full_access" ON public.users
    FOR ALL
    TO service_role
    USING (TRUE)
    WITH CHECK (TRUE);

-- Create a deny-all policy for public access
CREATE POLICY "deny_public_access" ON public.users
    FOR ALL
    TO PUBLIC
    USING (FALSE)
    WITH CHECK (FALSE);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_guid ON public.users (guid);
CREATE INDEX IF NOT EXISTS idx_users_phone_number ON public.users (phone_number);
CREATE INDEX IF NOT EXISTS idx_users_last_interaction ON public.users (last_interaction_at DESC);
CREATE INDEX IF NOT EXISTS idx_users_onboarding ON public.users (onboarding_completed);

-- Create function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON public.users
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();
