import os
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions

def get_supabase_client() -> Client:
    """FastAPI dependency to create and yield a Supabase client."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise ValueError("Supabase URL and service key must be set.")
    
    # Create a fresh client instance for each request to prevent session conflicts
    # This ensures concurrent requests don't interfere with each other
    client = create_client(url, key)
    
    return client
