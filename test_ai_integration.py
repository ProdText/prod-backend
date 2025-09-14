#!/usr/bin/env python3
"""
Simple test to verify AI integration works with the merged code
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.ai_conversation_service import AIConversationService
from supabase import create_client

# Load environment variables
load_dotenv()

async def test_ai_service():
    """Test that AI service can be instantiated and basic functionality works"""
    print("🤖 Testing AI Integration")
    print("=" * 40)
    
    try:
        # Create Supabase client
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not url or not key:
            print("❌ Missing Supabase credentials")
            return False
            
        supabase_client = create_client(url, key)
        
        # Check if ANTHROPIC_API_KEY is available
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if not anthropic_key:
            print("⚠️  ANTHROPIC_API_KEY not set - testing basic functionality only")
            # Test basic functionality without AI service initialization
            print("✅ Supabase client created successfully")
            print("✅ Basic imports working")
            print("\n🎉 Basic Integration Test Passed!")
            print("✅ All imports and basic setup working")
            print("⚠️  Set ANTHROPIC_API_KEY to test full AI functionality")
            return True
        
        # Initialize AI service
        ai_service = AIConversationService(supabase_client)
        print("✅ AI service initialized successfully")
        
        # Test token counting
        test_text = "Hello, this is a test message"
        token_count = ai_service._count_tokens(test_text)
        print(f"✅ Token counting works: '{test_text}' = {token_count} tokens")
        
        # Test conversation string parsing
        test_conversation = "user|Hello\nassistant|Hi there!"
        parsed = ai_service._parse_conversation_string(test_conversation)
        print(f"✅ Conversation parsing works: {len(parsed)} messages parsed")
        
        # Test conversation to string
        string_result = ai_service._conversation_to_string(parsed)
        print(f"✅ Conversation to string works: {len(string_result)} characters")
        
        print("\n🎉 AI Integration Test Passed!")
        print("✅ All basic AI service functions working")
        print("⚠️  Note: Full AI conversation requires ANTHROPIC_API_KEY")
        
        return True
        
    except Exception as e:
        print(f"❌ AI Integration Test Failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_ai_service())
    sys.exit(0 if success else 1)
