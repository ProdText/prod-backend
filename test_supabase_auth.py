#!/usr/bin/env python3
"""
Diagnostic script to test Supabase service role authentication
This will help identify the root cause of 403 Forbidden errors
"""

import os
from dotenv import load_dotenv
from supabase import create_client

def test_supabase_auth():
    """Test Supabase service role authentication and permissions"""
    
    # Load environment variables
    load_dotenv()
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    print("=== Supabase Authentication Diagnostic ===")
    print(f"URL: {url}")
    print(f"Service Role Key: {key[:20]}...{key[-10:] if key else 'None'}")
    
    if not url or not key:
        print("❌ CRITICAL: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
        return False
    
    try:
        # Create client
        client = create_client(url, key)
        print("✅ Client created successfully")
        
        # Test 1: Basic table access
        try:
            result = client.table("user_profiles").select("count", count="exact").execute()
            print(f"✅ Table access works - user_profiles count: {result.count}")
        except Exception as e:
            print(f"❌ Table access failed: {str(e)}")
        
        # Test 2: Admin auth access
        try:
            admin_auth = client.auth.admin
            users = admin_auth.list_users(page=1, per_page=1)
            print(f"✅ Admin auth works - can list users")
        except Exception as e:
            print(f"❌ Admin auth failed: {str(e)}")
            print("This is likely the root cause of 403 Forbidden errors")
            
        # Test 3: Try creating a test user
        try:
            from gotrue import AdminUserAttributes
            
            test_attrs = AdminUserAttributes(
                email="test-diagnostic@example.com",
                email_confirm=True,
                user_metadata={"test": True}
            )
            
            # This should work with proper service role
            response = admin_auth.create_user(test_attrs)
            if response.user:
                print("✅ User creation works")
                # Clean up test user
                admin_auth.delete_user(response.user.id)
                print("✅ Test user cleaned up")
            else:
                print("❌ User creation returned no user")
                
        except Exception as e:
            error_msg = str(e)
            print(f"❌ User creation failed: {error_msg}")
            
            if "User not allowed" in error_msg or "403" in error_msg:
                print("\n🔍 DIAGNOSIS:")
                print("1. Service role key may be invalid or expired")
                print("2. Admin API may be disabled in Supabase project")
                print("3. Check Supabase dashboard > Settings > API")
                print("4. Verify service_role key has admin permissions")
                
        return True
        
    except Exception as e:
        print(f"❌ Failed to create Supabase client: {str(e)}")
        return False

if __name__ == "__main__":
    test_supabase_auth()
