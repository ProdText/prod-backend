-- Fix the root cause: Remove conflicting database trigger
-- This trigger auto-creates user profiles, conflicting with our application logic

-- Drop the conflicting trigger and function
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
DROP FUNCTION IF EXISTS public.handle_new_user();

-- Verify triggers are removed
SELECT 
    trigger_name, 
    event_manipulation, 
    event_object_table,
    event_object_schema
FROM information_schema.triggers 
WHERE (event_object_schema = 'auth' AND event_object_table = 'users')
   OR (event_object_schema = 'public' AND event_object_table = 'user_profiles');

-- Add comment explaining the fix
COMMENT ON TABLE public.user_profiles IS 'User profiles managed by application code only - no database triggers';
