-- Conversation History Schema
-- This table stores AI conversation messages with context management

-- Create conversation_history table
CREATE TABLE IF NOT EXISTS public.conversation_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.user_profiles(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    token_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Enable Row Level Security (RLS)
ALTER TABLE public.conversation_history ENABLE ROW LEVEL SECURITY;

-- Create policies for conversation_history
DROP POLICY IF EXISTS "service_role_full_access_conversation" ON public.conversation_history;
DROP POLICY IF EXISTS "users_own_conversation" ON public.conversation_history;
DROP POLICY IF EXISTS "deny_public_access_conversation" ON public.conversation_history;

-- Service role has full access
CREATE POLICY "service_role_full_access_conversation" ON public.conversation_history
    FOR ALL
    TO service_role
    USING (TRUE)
    WITH CHECK (TRUE);

-- Authenticated users can only access their own conversation history
CREATE POLICY "users_own_conversation" ON public.conversation_history
    FOR ALL
    TO authenticated
    USING (
        user_id IN (
            SELECT id FROM public.user_profiles WHERE id = auth.uid()
        )
    )
    WITH CHECK (
        user_id IN (
            SELECT id FROM public.user_profiles WHERE id = auth.uid()
        )
    );

-- Deny public access
CREATE POLICY "deny_public_access_conversation" ON public.conversation_history
    FOR ALL
    TO PUBLIC
    USING (FALSE)
    WITH CHECK (FALSE);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_conversation_history_user_id ON public.conversation_history (user_id);
CREATE INDEX IF NOT EXISTS idx_conversation_history_created_at ON public.conversation_history (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversation_history_user_created ON public.conversation_history (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversation_history_role ON public.conversation_history (role);

-- Create function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_conversation_history_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
CREATE TRIGGER update_conversation_history_updated_at_trigger
    BEFORE UPDATE ON public.conversation_history
    FOR EACH ROW 
    EXECUTE FUNCTION update_conversation_history_updated_at();

-- Add helpful comments
COMMENT ON TABLE public.conversation_history IS 'Stores AI conversation messages with token counting for context management';
COMMENT ON COLUMN public.conversation_history.role IS 'Message role: user, assistant, or system';
COMMENT ON COLUMN public.conversation_history.content IS 'The actual message content';
COMMENT ON COLUMN public.conversation_history.token_count IS 'Number of tokens in the message for context management';

-- Optional: Create a view for recent conversations
CREATE OR REPLACE VIEW public.recent_conversations AS
SELECT 
    ch.user_id,
    up.phone_number,
    up.email,
    ch.role,
    ch.content,
    ch.token_count,
    ch.created_at
FROM public.conversation_history ch
JOIN public.user_profiles up ON ch.user_id = up.id
WHERE ch.created_at >= NOW() - INTERVAL '7 days'
ORDER BY ch.user_id, ch.created_at DESC;

-- Grant access to the view
GRANT SELECT ON public.recent_conversations TO service_role;
