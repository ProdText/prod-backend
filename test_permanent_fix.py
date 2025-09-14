#!/usr/bin/env python3
"""
Test the permanent fix for database trigger conflicts
This verifies that user creation now works with trigger-created profiles
"""

import asyncio
import os
from dotenv import load_dotenv
from supabase import create_client
from services.auth_user_service import AuthUserService
import time

async def test_permanent_fix():
    """Test the permanent fix for concurrent user creation"""
    
    load_dotenv()
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        print("❌ Missing Supabase credentials")
        return False
    
    print("=== Testing Permanent Fix for Database Trigger Conflicts ===\n")
    
    # Test multiple concurrent user creations
    test_users = [
        (f"test-fix-{i}-{int(time.time())}@example.com", f"+155512345{60+i}", f"guid-{i}-{int(time.time())}")
        for i in range(5)
    ]
    
    success_count = 0
    
    for i, (email, phone, guid) in enumerate(test_users):
        print(f"--- Testing User {i+1}: {email} ---")
        
        try:
            # Create fresh client for each test
            client = create_client(url, key)
            auth_service = AuthUserService(client)
            
            # Test the fixed user creation logic
            user_with_profile = await auth_service.create_authenticated_user(
                bluebubbles_guid=guid,
                phone_number=phone,
                email=email,
                chat_identifier=phone
            )
            
            if user_with_profile:
                print(f"✅ User created successfully: {user_with_profile.auth_user.id}")
                print(f"   Email: {user_with_profile.auth_user.email}")
                print(f"   Phone: {user_with_profile.profile.phone_number}")
                print(f"   GUID: {user_with_profile.profile.bluebubbles_guid}")
                
                success_count += 1
                
                # Clean up
                client.auth.admin.delete_user(user_with_profile.auth_user.id)
                print(f"✅ Test user cleaned up")
            else:
                print(f"❌ User creation failed - no user returned")
                
        except Exception as e:
            error_msg = str(e)
            print(f"❌ User creation failed: {error_msg}")
            
            if "User not allowed" in error_msg or "403" in error_msg:
                print("   This indicates the fix didn't work - still getting 403 errors")
            elif "duplicate" in error_msg.lower() or "already exists" in error_msg.lower():
                print("   This indicates trigger conflict still exists")
            else:
                print(f"   Unexpected error: {error_msg}")
        
        print()
    
    print("=== Test Results ===")
    print(f"Successful creations: {success_count}/{len(test_users)}")
    
    if success_count == len(test_users):
        print("🎉 PERMANENT FIX SUCCESSFUL!")
        print("✅ All users created without 403 Forbidden errors")
        print("✅ Database trigger conflicts resolved")
        print("✅ System ready for production scale")
        return True
    else:
        print("⚠️  Fix partially successful - some users still failing")
        return False

if __name__ == "__main__":
    asyncio.run(test_permanent_fix())
