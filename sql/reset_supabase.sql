-- =====================================================
-- SUPABASE COMPLETE RESET SCRIPT
-- =====================================================
-- This script will completely reset your Supabase database
-- WARNING: This will delete ALL data and users!
-- =====================================================

-- Step 1: Delete all auth users (this cascades to user_profiles)
-- Note: This requires service_role permissions
DELETE FROM auth.users;

-- Step 2: Drop existing tables and related objects
DROP TABLE IF EXISTS public.bb_events CASCADE;
DROP TABLE IF EXISTS public.user_profiles CASCADE;

-- Step 3: Drop any existing functions
DROP FUNCTION IF EXISTS public.handle_new_user() CASCADE;

-- Step 4: Recreate bb_events table
CREATE TABLE public.bb_events (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL DEFAULT 'bluebubbles',
    event_type TEXT NOT NULL,
    received_at TIMESTAMPTZ DEFAULT NOW(),
    headers JSONB,
    payload JSONB NOT NULL
);

-- Step 5: Recreate user_profiles table with onboarding support
CREATE TABLE public.user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    bluebubbles_guid TEXT UNIQUE NOT NULL,
    phone_number TEXT,
    original_phone TEXT,
    chat_identifier TEXT,
    onboarding_completed BOOLEAN DEFAULT FALSE,
    onboarding_state TEXT DEFAULT 'not_started',
    phone_verified BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMPTZ,
    interaction_count INTEGER DEFAULT 0,
    last_interaction_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Step 6: Create indexes for performance
CREATE INDEX idx_user_profiles_bluebubbles_guid ON public.user_profiles(bluebubbles_guid);
CREATE INDEX idx_user_profiles_phone_number ON public.user_profiles(phone_number);
CREATE INDEX idx_user_profiles_onboarding_state ON public.user_profiles(onboarding_state);
CREATE INDEX idx_bb_events_event_type ON public.bb_events(event_type);
CREATE INDEX idx_bb_events_received_at ON public.bb_events(received_at);

-- Step 7: Enable Row Level Security
ALTER TABLE public.bb_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;

-- Step 8: Create RLS Policies for bb_events
-- Deny all access to bb_events (service role only)
CREATE POLICY "Deny all access to bb_events" ON public.bb_events
    FOR ALL USING (false);

-- Step 9: Create RLS Policies for user_profiles
-- Service role has full access
CREATE POLICY "Service role full access" ON public.user_profiles
    FOR ALL TO service_role USING (true);

-- Authenticated users can only access their own profile
CREATE POLICY "Users can access own profile" ON public.user_profiles
    FOR ALL TO authenticated USING (auth.uid() = id);

-- Deny public access
CREATE POLICY "Deny public access" ON public.user_profiles
    FOR ALL TO public USING (false);

-- Step 10: Create trigger function for auto-updating timestamps
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Step 11: Create trigger for user_profiles updated_at
CREATE TRIGGER update_user_profiles_updated_at
    BEFORE UPDATE ON public.user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

-- Step 12: Create function to handle new auth users
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    -- Only create profile if user has bluebubbles_guid in metadata
    IF NEW.raw_user_meta_data ? 'bluebubbles_guid' THEN
        INSERT INTO public.user_profiles (
            id,
            bluebubbles_guid,
            phone_number,
            onboarding_completed,
            onboarding_state,
            phone_verified
        ) VALUES (
            NEW.id,
            NEW.raw_user_meta_data->>'bluebubbles_guid',
            NEW.raw_user_meta_data->>'original_phone',
            false,
            'not_started',
            false
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Step 13: Create trigger for auto-creating user profiles
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();

-- Step 14: Add helpful comments
COMMENT ON TABLE public.bb_events IS 'BlueBubbles webhook events storage';
COMMENT ON TABLE public.user_profiles IS 'User profiles linked to auth.users with BlueBubbles-specific data';
COMMENT ON COLUMN public.user_profiles.onboarding_state IS 'Current onboarding state: not_started, awaiting_otp, completed';
COMMENT ON COLUMN public.user_profiles.phone_verified IS 'Whether the users phone number has been verified via OTP';
COMMENT ON COLUMN public.user_profiles.verified_at IS 'Timestamp when phone verification was completed';

-- =====================================================
-- RESET COMPLETE
-- =====================================================
-- Your Supabase database has been completely reset with:
-- ✅ All auth users deleted
-- ✅ All tables recreated with latest schema
-- ✅ RLS policies configured
-- ✅ Triggers and functions set up
-- ✅ Indexes created for performance
-- ✅ Onboarding support enabled
-- =====================================================
