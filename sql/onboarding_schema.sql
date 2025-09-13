-- Add onboarding state column to user_profiles table
ALTER TABLE user_profiles 
ADD COLUMN IF NOT EXISTS onboarding_state TEXT DEFAULT 'not_started',
ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ;

-- Create index for onboarding state queries
CREATE INDEX IF NOT EXISTS idx_user_profiles_onboarding_state 
ON user_profiles(onboarding_state);

-- Update RLS policies to include new columns
-- (Existing policies should already cover these columns)

-- Add comment for documentation
COMMENT ON COLUMN user_profiles.onboarding_state IS 'Current onboarding state: not_started, awaiting_otp, completed';
COMMENT ON COLUMN user_profiles.phone_verified IS 'Whether the users phone number has been verified via OTP';
COMMENT ON COLUMN user_profiles.verified_at IS 'Timestamp when phone verification was completed';
