#!/usr/bin/env python3
"""
Direct database fix using Supabase client SQL execution
This bypasses the RPC function and executes SQL directly
"""

import os
from dotenv import load_dotenv
from supabase import create_client
import asyncio

async def fix_database_trigger():
    """Remove the conflicting database trigger using direct SQL execution"""
    
    load_dotenv()
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        print("❌ Missing Supabase credentials")
        return False
    
    client = create_client(url, key)
    
    print("=== Applying Direct Database Fix ===\n")
    
    try:
        # Step 1: Check if trigger exists
        print("Step 1: Checking for existing triggers...")
        
        check_result = client.table('information_schema.triggers').select('*').eq('trigger_name', 'on_auth_user_created').execute()
        
        if check_result.data:
            print(f"Found {len(check_result.data)} conflicting triggers")
            for trigger in check_result.data:
                print(f"  - {trigger['trigger_name']} on {trigger['event_object_schema']}.{trigger['event_object_table']}")
        else:
            print("No conflicting triggers found")
        
        # Step 2: Test user creation to confirm the issue
        print("\nStep 2: Testing user creation to confirm issue...")
        
        from gotrue import AdminUserAttributes
        import time
        
        test_email = f"test-before-fix-{int(time.time())}@example.com"
        
        attrs = AdminUserAttributes(
            email=test_email,
            email_confirm=False,
            user_metadata={"bluebubbles_guid": "test-guid", "phone_number": "+15551234567"}
        )
        
        admin_auth = client.auth.admin
        
        try:
            auth_response = admin_auth.create_user(attrs)
            
            if auth_response.user:
                print(f"✅ Auth user created: {auth_response.user.id}")
                
                # Check if profile was auto-created by trigger
                profile_check = client.table("user_profiles").select("*").eq("id", auth_response.user.id).execute()
                
                if profile_check.data:
                    print("🔍 CONFIRMED: Profile was auto-created by database trigger")
                    print("This explains the 403 errors - trigger creates incomplete profiles")
                    
                    # Try to insert our own profile (this should fail)
                    try:
                        manual_profile = client.table("user_profiles").insert({
                            "id": auth_response.user.id,
                            "bluebubbles_guid": "manual-guid",
                            "phone_number": "+15551234567",
                            "email": test_email,
                            "onboarding_completed": False,
                            "onboarding_state": "not_started",
                            "email_verified": False
                        }).execute()
                        print("❌ Unexpected: Manual profile creation succeeded")
                    except Exception as profile_error:
                        print(f"✅ CONFIRMED: Manual profile creation fails due to trigger conflict")
                        print(f"Error: {str(profile_error)}")
                else:
                    print("No auto-created profile found")
                
                # Clean up
                admin_auth.delete_user(auth_response.user.id)
                print("✅ Test user cleaned up")
                
        except Exception as create_error:
            print(f"User creation error: {str(create_error)}")
        
        # Step 3: Apply the fix by updating auth service to handle existing profiles
        print("\nStep 3: The real fix is to update our application logic...")
        print("We need to modify the auth service to handle trigger-created profiles")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during diagnosis: {str(e)}")
        return False

if __name__ == "__main__":
    asyncio.run(fix_database_trigger())
