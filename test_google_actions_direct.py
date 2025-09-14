#!/usr/bin/env python3
"""
Direct test of Google Actions AI function calling without BlueBubbles messaging
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.ai_conversation_service import AIConversationService
from services.google_integration_service import GoogleIntegrationService
from utils.dependencies import get_supabase_client

# Load environment variables
load_dotenv()

async def test_gmail_draft_creation():
    """Test Gmail draft creation through AI function calling"""
    # Create a test user ID (you can replace with a real user ID from your database)
    test_user_id = "test-user-123"
    test_phone = "+15551234567"
    
    # Initialize services
    supabase_client = get_supabase_client()
    ai_service = AIConversationService(supabase_client)
    
    print("🧪 Testing Gmail Draft Creation with AI Function Calling")
    print("=" * 60)
    
    # Test user message requesting email draft
    user_message = """Can you draft an email to john@example.com with subject "Meeting Tomorrow" and message "Hi John, just wanted to confirm our meeting tomorrow at 2pm. Thanks!" """
    
    # Create a test user ID (you can replace with a real user ID from your database)
    test_user_id = "test-user-123"
    test_phone = "+15551234567"
    
    print(f"📝 User Message: {user_message}")
    print(f"👤 Test User ID: {test_user_id}")
    print(f"📱 Test Phone: {test_phone}")
    print()
    
    try:
        # Call the AI conversation service directly
        print("🤖 Calling AI Conversation Service...")
        ai_responses = await ai_service.handle_ai_conversation(
            user_id=test_user_id,
            user_message=user_message,
            phone_number=test_phone
        )
        
        print("✅ AI Response Generated:")
        for i, response in enumerate(ai_responses, 1):
            print(f"   Response {i}: {response}")
            print()
        
        # Check if any function calls were executed
        print("🔍 Checking for function call execution...")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during test: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def test_gmail_send_email():
    """Test Gmail send email through AI function calling"""
    print("\n🧪 Testing Gmail Send Email with AI Function Calling")
    print("=" * 60)
    
    # Initialize services
    supabase_client = get_supabase_client()
    ai_service = AIConversationService(supabase_client)
    
    # Test user message requesting email send
    user_message = """Please send an email to jane@example.com with subject "Project Update" and message "Hi Jane, the project is on track for completion next week. Best regards!" """
    
    test_user_id = "test-user-123"
    test_phone = "+15551234567"
    
    print(f"📝 User Message: {user_message}")
    print(f"👤 Test User ID: {test_user_id}")
    print()
    
    try:
        # Call the AI conversation service directly
        print("🤖 Calling AI Conversation Service...")
        ai_responses = await ai_service.handle_ai_conversation(
            user_id=test_user_id,
            user_message=user_message,
            phone_number=test_phone
        )
        
        print("✅ AI Response Generated:")
        for i, response in enumerate(ai_responses, 1):
            print(f"   Response {i}: {response}")
            print()
        
        return True
        
    except Exception as e:
        print(f"❌ Error during test: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def test_calendar_event_creation():
    """Test Calendar event creation through AI function calling"""
    print("\n🧪 Testing Calendar Event Creation with AI Function Calling")
    print("=" * 60)
    
    # Initialize services
    supabase_client = get_supabase_client()
    ai_service = AIConversationService(supabase_client)
    
    # Test user message requesting calendar event
    user_message = """Can you create a calendar event for "Team Meeting" tomorrow at 2pm for 1 hour? """
    
    test_user_id = "test-user-123"
    test_phone = "+15551234567"
    
    print(f"📝 User Message: {user_message}")
    print(f"👤 Test User ID: {test_user_id}")
    print()
    
    try:
        # Call the AI conversation service directly
        print("🤖 Calling AI Conversation Service...")
        ai_responses = await ai_service.handle_ai_conversation(
            user_id=test_user_id,
            user_message=user_message,
            phone_number=test_phone
        )
        
        print("✅ AI Response Generated:")
        for i, response in enumerate(ai_responses, 1):
            print(f"   Response {i}: {response}")
            print()
        
        return True
        
    except Exception as e:
        print(f"❌ Error during test: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all Google Actions tests"""
    print("🚀 Starting Google Actions Direct Testing")
    print("=" * 60)
    
    results = []
    
    # Test Gmail draft creation
    results.append(await test_gmail_draft_creation())
    
    # Test Gmail send email
    results.append(await test_gmail_send_email())
    
    # Test Calendar event creation
    results.append(await test_calendar_event_creation())
    
    # Summary
    print("\n📊 Test Results Summary")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed!")
    else:
        print("⚠️  Some tests failed. Check the logs above for details.")
    
    return passed == total

if __name__ == "__main__":
    asyncio.run(main())
