#!/usr/bin/env python3
"""
Debug script to check user lookup by phone number
This will help identify why users are getting "account not found" errors
"""

import os
import asyncio
from dotenv import load_dotenv
from supabase import create_client
from services.auth_user_service import AuthUserService

async def debug_user_lookup():
    """Debug user lookup for the problematic phone number"""
    
    load_dotenv()
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        print("❌ Missing Supabase credentials")
        return
    
    client = create_client(url, key)
    auth_service = AuthUserService(client)
    
    # Check the problematic phone number
    phone = "+19197109288"
    
    print(f"=== Debugging User Lookup for {phone} ===\n")
    
    try:
        # 1. Check if user profile exists
        profile_result = client.table("user_profiles").select("*").eq(
            "phone_number", phone
        ).execute()
        
        print(f"Profile lookup result: {len(profile_result.data)} records found")
        if profile_result.data:
            for profile in profile_result.data:
                print(f"Profile ID: {profile['id']}")
                print(f"Email: {profile.get('email', 'No email')}")
                print(f"Phone: {profile.get('phone_number', 'No phone')}")
                print(f"Onboarding State: {profile.get('onboarding_state', 'No state')}")
                print(f"Email Verified: {profile.get('email_verified', 'Unknown')}")
                print()
        
        # 2. Try the auth service method
        user_with_profile = await auth_service.get_user_by_phone_number(phone)
        
        if user_with_profile:
            print("✅ Auth service found user:")
            print(f"Auth User ID: {user_with_profile.auth_user.id}")
            print(f"Auth User Email: {user_with_profile.auth_user.email}")
            print(f"Profile ID: {user_with_profile.profile.id}")
        else:
            print("❌ Auth service could not find user")
            
        # 3. Check all users with similar phone patterns
        all_profiles = client.table("user_profiles").select("phone_number, email, id").execute()
        print(f"\n=== All User Profiles ({len(all_profiles.data)} total) ===")
        for profile in all_profiles.data:
            if "919" in profile.get('phone_number', ''):
                print(f"Phone: {profile.get('phone_number')} | Email: {profile.get('email')} | ID: {profile.get('id')}")
                
    except Exception as e:
        print(f"❌ Error during lookup: {str(e)}")

if __name__ == "__main__":
    asyncio.run(debug_user_lookup())
