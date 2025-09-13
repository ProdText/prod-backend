-- Create the bb_events table for storing BlueBubbles webhook events
CREATE TABLE IF NOT EXISTS public.bb_events (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL DEFAULT 'bluebubbles',
    event_type TEXT NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    headers JSONB,
    payload JSONB
);

-- Enable Row Level Security (RLS)
ALTER TABLE public.bb_events ENABLE ROW LEVEL SECURITY;

-- Create a deny-all policy (no public access by default)
-- This ensures that only service-role or authenticated users with proper permissions can access the data
CREATE POLICY "deny_all_bb_events" ON public.bb_events
    FOR ALL
    TO PUBLIC
    USING (FALSE)
    WITH CHECK (FALSE);

-- Optional: Create an index on received_at for better query performance
CREATE INDEX IF NOT EXISTS idx_bb_events_received_at ON public.bb_events (received_at DESC);

-- Optional: Create an index on event_type for filtering by event type
CREATE INDEX IF NOT EXISTS idx_bb_events_event_type ON public.bb_events (event_type);

-- Optional: Create an index on source for filtering by source
CREATE INDEX IF NOT EXISTS idx_bb_events_source ON public.bb_events (source);
