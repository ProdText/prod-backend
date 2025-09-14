#!/usr/bin/env python3
"""
Debug script to compare production user creation vs test user creation
This will identify why production fails but tests succeed
"""

import asyncio
import os
from dotenv import load_dotenv
from supabase import create_client
from services.auth_user_service import AuthUserService
from gotrue import AdminUserAttributes
import time

async def test_production_user_creation():
    """Test user creation exactly as production does it"""
    
    load_dotenv()
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        print("❌ Missing Supabase credentials")
        return
    
    print("=== Testing Production User Creation Flow ===\n")
    
    # Test the exact scenario from logs
    phone = "+13369881275"
    email = "arisingh8@gmail.com"
    guid = "905938CB-3853-42C3-8176-408E73282D21"
    
    # Create client exactly like production
    client = create_client(url, key)
    auth_service = AuthUserService(client)
    
    print(f"Testing user creation for:")
    print(f"Phone: {phone}")
    print(f"Email: {email}")
    print(f"GUID: {guid}\n")
    
    try:
        # Step 1: Check existing users (like production does)
        print("Step 1: Checking for existing users...")
        existing_by_phone = await auth_service.get_user_by_phone_number(phone)
        existing_by_email = await auth_service.get_user_by_email(email)
        
        print(f"Existing by phone: {'Yes' if existing_by_phone else 'No'}")
        print(f"Existing by email: {'Yes' if existing_by_email else 'No'}")
        
        if existing_by_phone or existing_by_email:
            print("⚠️  User already exists - this might be the issue!")
            if existing_by_phone:
                print(f"Phone user ID: {existing_by_phone.auth_user.id}")
                print(f"Phone user email: {existing_by_phone.auth_user.email}")
            if existing_by_email:
                print(f"Email user ID: {existing_by_email.auth_user.id}")
                print(f"Email user email: {existing_by_email.auth_user.email}")
            return
        
        # Step 2: Create auth user (like production does)
        print("\nStep 2: Creating auth user...")
        attrs = AdminUserAttributes(
            email=email,
            email_confirm=False,
            user_metadata={
                "bluebubbles_guid": guid,
                "phone_number": phone,
                "source": "bluebubbles_webhook"
            }
        )
        
        admin_auth = client.auth.admin
        auth_response = admin_auth.create_user(attrs)
        
        if auth_response.user:
            print(f"✅ Auth user created: {auth_response.user.id}")
            
            # Step 3: Create profile (like production does)
            print("\nStep 3: Creating user profile...")
            profile_result = client.table("user_profiles").insert({
                "id": auth_response.user.id,
                "bluebubbles_guid": guid,
                "phone_number": phone,
                "email": email,
                "chat_identifier": None,
                "interaction_count": 1,
                "onboarding_completed": False,
                "onboarding_state": "not_started",
                "email_verified": False
            }).execute()
            
            print(f"✅ Profile created successfully")
            
            # Clean up
            admin_auth.delete_user(auth_response.user.id)
            print("✅ Test user cleaned up")
            
        else:
            print("❌ Auth user creation failed - no user returned")
            
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error during production flow test: {error_msg}")
        
        # Analyze the specific error
        if "User not allowed" in error_msg or "403" in error_msg:
            print("\n🔍 ANALYSIS:")
            print("This is the exact same error as production!")
            print("Possible causes:")
            print("1. Email already exists in Supabase auth but not in our database")
            print("2. Phone number conflicts with existing users")
            print("3. Supabase project settings blocking certain emails")
            print("4. Rate limiting on specific email domains")
            
            # Check if user exists in Supabase auth
            print("\nChecking Supabase auth users...")
            try:
                auth_users = admin_auth.list_users()
                for user in auth_users:
                    if user.email == email:
                        print(f"🔍 FOUND: User {email} exists in auth.users with ID {user.id}")
                        print("This explains the 403 error - user already exists!")
                        break
                else:
                    print(f"User {email} not found in auth.users")
            except Exception as list_error:
                print(f"Error listing users: {list_error}")

if __name__ == "__main__":
    asyncio.run(test_production_user_creation())
