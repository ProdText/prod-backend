#!/usr/bin/env python3
"""
Test script for Google integration with AI assistant
"""
import asyncio
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client
from services.ai_conversation_service import AIConversationService
from services.google_integration_service import GoogleIntegrationService

# Load environment variables
load_dotenv()

async def test_ai_conversation():
    """Test the AI conversation with Google integration"""
    
    # Initialize Supabase client
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Missing Supabase credentials in .env")
        return
    
    supabase = create_client(supabase_url, supabase_key)
    
    # Get a test user (you'll need to replace with actual phone/user_id)
    print("\n🔍 Enter your phone number (format: +1234567890): ", end="")
    phone_number = input().strip()
    
    # Get user profile
    result = supabase.table('user_profiles').select('*').eq('phone_number', phone_number).single().execute()
    if not result.data:
        print(f"❌ No user found with phone number {phone_number}")
        return
    
    user_id = result.data['id']
    print(f"✅ Found user: {user_id}")
    
    # Initialize AI conversation service
    ai_service = AIConversationService(supabase)
    
    print("\n📝 Test scenarios:")
    print("1. Schedule a calendar event")
    print("2. Draft an email")
    print("3. Send an email (with confirmation)")
    print("4. Natural conversation")
    print("5. Exit")
    
    test_messages = {
        "1": "Schedule a meeting with John tomorrow at 2pm about the quarterly review",
        "2": "Draft an email to test@example.com about following up on our project discussion",
        "3": "Send an email to test@example.com saying thanks for the meeting today",
        "4": "How's the weather today?",
    }
    
    while True:
        print("\n🔢 Select test scenario (1-5): ", end="")
        choice = input().strip()
        
        if choice == "5":
            print("👋 Exiting test")
            break
        
        if choice in test_messages:
            message = test_messages[choice]
            print(f"\n📤 Sending: {message}")
            
            try:
                # Call the AI conversation handler
                responses = await ai_service.handle_ai_conversation(
                    user_id=user_id,
                    user_message=message,
                    phone_number=phone_number
                )
                
                print("\n📥 AI Response:")
                for response in responses:
                    print(f"  - {response}")
                    
            except Exception as e:
                print(f"❌ Error: {str(e)}")
        else:
            print("❌ Invalid choice")

async def test_direct_google_integration():
    """Test Google integration directly"""
    
    # Initialize Supabase client
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Missing Supabase credentials in .env")
        return
    
    supabase = create_client(supabase_url, supabase_key)
    
    print("\n🔍 Enter your phone number (format: +1234567890): ", end="")
    phone_number = input().strip()
    
    # Initialize Google integration service
    google_service = GoogleIntegrationService(supabase, phone_number)
    
    # Check if Google account is linked
    account = await google_service.get_google_account()
    if not account:
        print("❌ No Google account linked. Please connect your Google account first.")
        return
    
    print(f"✅ Google account found: {account['email']}")
    
    print("\n📝 Direct Google integration tests:")
    print("1. Create calendar event")
    print("2. Draft email")
    print("3. Get upcoming events")
    print("4. Exit")
    
    while True:
        print("\n🔢 Select test (1-4): ", end="")
        choice = input().strip()
        
        if choice == "4":
            print("👋 Exiting test")
            break
        
        if choice == "1":
            # Test calendar event creation
            print("\n📅 Creating test calendar event...")
            start_time = datetime.now() + timedelta(days=1, hours=14)  # Tomorrow at 2pm
            end_time = start_time + timedelta(hours=1)
            
            result = await google_service.create_calendar_event(
                title="Test Meeting",
                start_time=start_time,
                end_time=end_time,
                description="This is a test event created by the integration",
                location="Conference Room A"
            )
            
            if result['success']:
                print(f"✅ {result['message']}")
            else:
                print(f"❌ {result['error']}")
                
        elif choice == "2":
            # Test email draft
            print("\n📧 Creating test email draft...")
            result = await google_service.draft_email(
                to=["test@example.com"],
                subject="Test Email from Integration",
                body="This is a test email created by the Google integration."
            )
            
            if result['success']:
                print(f"✅ {result['message']}")
            else:
                print(f"❌ {result['error']}")
                
        elif choice == "3":
            # Get upcoming events
            print("\n📅 Getting upcoming events...")
            result = await google_service.get_upcoming_events(days_ahead=7)
            
            if result['success']:
                print(f"✅ {result['message']}")
                for event in result['events']:
                    print(f"  - {event['title']} at {event['start']}")
            else:
                print(f"❌ {result['error']}")

async def main():
    """Main test function"""
    print("🚀 Google Integration Test Suite")
    print("================================")
    
    print("\n📋 Select test mode:")
    print("1. Test AI conversation with Google integration")
    print("2. Test Google integration directly")
    print("3. Exit")
    
    print("\n🔢 Select mode (1-3): ", end="")
    choice = input().strip()
    
    if choice == "1":
        await test_ai_conversation()
    elif choice == "2":
        await test_direct_google_integration()
    elif choice == "3":
        print("👋 Goodbye!")
    else:
        print("❌ Invalid choice")

if __name__ == "__main__":
    asyncio.run(main())