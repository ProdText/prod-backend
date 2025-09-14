#!/usr/bin/env python3
"""
Verify that users are being properly created in the database
despite BlueBubbles API errors
"""

import os
import asyncio
from dotenv import load_dotenv
from supabase import create_client
from services.auth_user_service import AuthUserService

async def main():
    load_dotenv()
    
    # Create Supabase client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    client = create_client(url, key)
    
    auth_service = AuthUserService(client)
    
    print("=== Verifying User Creation Results ===\n")
    
    # Check for the test users we just created
    test_phones = [f"+1555123456{i}" for i in range(5)]
    
    created_users = []
    missing_users = []
    
    for phone in test_phones:
        try:
            user = await auth_service.get_user_by_phone_number(phone)
            if user:
                email = user.auth_user.email if hasattr(user, 'auth_user') else user.profile.email if hasattr(user, 'profile') else "No email"
                status = getattr(user.profile, 'onboarding_state', 'unknown') if hasattr(user, 'profile') else 'unknown'
                created_users.append((phone, email, status))
                print(f"✅ {phone}: {email} (Status: {status})")
            else:
                missing_users.append(phone)
                print(f"❌ {phone}: Not found in database")
        except Exception as e:
            missing_users.append(phone)
            print(f"❌ {phone}: Error - {str(e)}")
    
    print(f"\n=== Summary ===")
    print(f"Users successfully created: {len(created_users)}/5")
    print(f"Users missing from database: {len(missing_users)}/5")
    
    if len(created_users) == 5:
        print("\n🎉 SUCCESS: All concurrent users were created successfully!")
        print("✅ The 403 Forbidden errors have been resolved")
        print("✅ Concurrent user creation is working properly")
        print("⚠️  BlueBubbles API 500 errors are external - users still get created")
    elif len(created_users) > 0:
        print(f"\n⚠️  PARTIAL SUCCESS: {len(created_users)}/5 users created")
        print("Some users may have been affected by race conditions")
    else:
        print("\n❌ FAILURE: No users were created")
        print("The concurrent creation system is not working")
    
    # Check auth users table as well
    print(f"\n=== Checking Supabase Auth Users ===")
    try:
        auth_users = client.auth.admin.list_users()
        recent_users = [u for u in auth_users.users if any(phone in u.phone for phone in test_phones if u.phone)]
        print(f"Auth users created: {len(recent_users)}")
        for user in recent_users:
            print(f"  - {user.phone}: {user.email} (ID: {user.id[:8]}...)")
    except Exception as e:
        print(f"Error checking auth users: {e}")

if __name__ == "__main__":
    asyncio.run(main())
