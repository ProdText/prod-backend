#!/usr/bin/env python3
"""
Test script for email drafting functionality end-to-end
Tests the complete flow from AI response parsing to Google integration
"""

import asyncio
import json
import re
import os
from unittest.mock import AsyncMock, MagicMock, patch
from services.ai_conversation_service import AIConversationService
from services.google_integration_service import GoogleIntegrationService

# Mock Supabase client
class MockSupabaseClient:
    def __init__(self):
        self.table_data = {
            'user_profiles': [
                {
                    'id': 'test-user-123',
                    'phone_number': '+1234567890',
                    'conversation_history': ''
                }
            ],
            'google_accounts': [
                {
                    'id': 'google-account-123',
                    'user_id': 'test-user-123',
                    'email': 'test@example.com'
                }
            ]
        }
    
    def table(self, table_name):
        return MockTable(self.table_data.get(table_name, []))

class MockTable:
    def __init__(self, data):
        self.data = data
        self._filters = {}
    
    def select(self, columns):
        return self
    
    def eq(self, column, value):
        self._filters[column] = value
        return self
    
    def single(self):
        return self
    
    def execute(self):
        # Filter data based on applied filters
        filtered_data = self.data
        for item in filtered_data:
            match = True
            for key, value in self._filters.items():
                if item.get(key) != value:
                    match = False
                    break
            if match:
                return MagicMock(data=item)
        return MagicMock(data=None)
    
    def update(self, data):
        return self
    
    def insert(self, data):
        return self

async def test_function_parsing():
    """Test that AI responses with JSON function calls are properly parsed"""
    print("🧪 Testing function call parsing...")
    
    # Mock AI response with email draft function call
    ai_response = """hey, i'll draft that email for you right now

```json
{
  "function": "DRAFT_EMAIL",
  "params": {
    "to": ["professor@university.edu"],
    "subject": "Question about Assignment 3",
    "body": "Hi Professor,\n\nI have a quick question about Assignment 3. Could we schedule office hours this week?\n\nThanks,\nStudent"
  }
}
```

let me know if you want to make any changes"""

    # Create AI service with mock Supabase
    mock_supabase = MockSupabaseClient()
    ai_service = AIConversationService(mock_supabase)
    
    # Test function parsing
    function_result = await ai_service._parse_and_execute_function(
        ai_response, 'test-user-123', '+1234567890'
    )
    
    if function_result:
        print("✅ Function call detected and parsed successfully")
        print(f"   Result: {function_result}")
        
        # Test JSON block removal
        cleaned_response = re.sub(r"```json\s*\{.*?\}\s*```", "", ai_response, flags=re.DOTALL)
        cleaned_response = cleaned_response.strip()
        print(f"✅ JSON block removed, remaining text: '{cleaned_response}'")
        
        return True
    else:
        print("❌ Function call not detected or parsed")
        return False

async def test_google_integration_mock():
    """Test Google integration service with mocked HTTP calls"""
    print("\n🧪 Testing Google integration service...")
    
    mock_supabase = MockSupabaseClient()
    google_service = GoogleIntegrationService(mock_supabase, '+1234567890')
    
    # Mock the HTTP client response
    with patch('httpx.AsyncClient') as mock_client:
        # Mock successful draft creation
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'id': 'draft-123',
            'message': {'id': 'msg-456'}
        }
        
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        
        # Test draft email
        result = await google_service.draft_email(
            to=['test@example.com'],
            subject='Test Subject',
            body='Test body content'
        )
        
        if result['success']:
            print("✅ Google integration service working correctly")
            print(f"   Result: {result['message']}")
            return True
        else:
            print(f"❌ Google integration failed: {result['error']}")
            return False

async def test_complete_flow():
    """Test the complete AI conversation flow with function calls"""
    print("\n🧪 Testing complete AI conversation flow...")
    
    # Mock AI response that should trigger email drafting
    test_ai_response = """i'll help you draft that email to your professor

```json
{
  "function": "DRAFT_EMAIL",
  "params": {
    "to": ["prof.smith@university.edu"],
    "subject": "Office Hours Request",
    "body": "Dear Professor Smith,\n\nI hope this email finds you well. I was wondering if you have any available office hours this week to discuss Assignment 3.\n\nBest regards,\nYour Student"
  }
}
```

the draft is ready for you to review"""

    mock_supabase = MockSupabaseClient()
    ai_service = AIConversationService(mock_supabase)
    
    # Mock the Google integration HTTP calls
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'id': 'draft-789'}
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        
        # Test function parsing and execution
        function_result = await ai_service._parse_and_execute_function(
            test_ai_response, 'test-user-123', '+1234567890'
        )
        
        if function_result and "created the email draft" in function_result:
            print("✅ Complete flow working correctly")
            
            # Test response cleaning
            cleaned_response = re.sub(r"```json\s*\{.*?\}\s*```", "", test_ai_response, flags=re.DOTALL)
            cleaned_response = cleaned_response.strip()
            
            if cleaned_response:
                final_response = [cleaned_response, function_result]
            else:
                final_response = [function_result]
            
            print(f"   Final user response: {'. '.join(final_response)}")
            return True
        else:
            print(f"❌ Complete flow failed: {function_result}")
            return False

async def test_error_handling():
    """Test error handling when Google integration fails"""
    print("\n🧪 Testing error handling...")
    
    test_ai_response = """let me draft that email

```json
{
  "function": "DRAFT_EMAIL",
  "params": {
    "to": ["invalid@email"],
    "subject": "Test",
    "body": "Test body"
  }
}
```

should be ready soon"""

    mock_supabase = MockSupabaseClient()
    ai_service = AIConversationService(mock_supabase)
    
    # Mock failed HTTP response
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Invalid email address"
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        
        function_result = await ai_service._parse_and_execute_function(
            test_ai_response, 'test-user-123', '+1234567890'
        )
        
        if function_result and "Failed to create draft" in function_result:
            print("✅ Error handling working correctly")
            print(f"   Error message: {function_result}")
            return True
        else:
            print(f"❌ Error handling failed: {function_result}")
            return False

async def main():
    """Run all tests"""
    print("🚀 Starting Email Drafting End-to-End Tests\n")
    
    tests = [
        ("Function Parsing", test_function_parsing),
        ("Google Integration Mock", test_google_integration_mock),
        ("Complete Flow", test_complete_flow),
        ("Error Handling", test_error_handling)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {str(e)}")
            results.append((test_name, False))
    
    print("\n📊 Test Results Summary:")
    print("=" * 50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! Email drafting functionality is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")

if __name__ == "__main__":
    asyncio.run(main())
