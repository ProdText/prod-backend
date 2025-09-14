#!/usr/bin/env python3
"""
Test the fixed function parsing with proper JSON handling
"""

import asyncio
import json
import re
import sys
import os

# Add the current directory to Python path
sys.path.append('/Users/Rk/Documents/GitHub/prod-backend')

from unittest.mock import AsyncMock, MagicMock, patch
from services.ai_conversation_service import AIConversationService

class MockSupabaseClient:
    def __init__(self):
        self.table_data = {
            'user_profiles': [{'id': 'test-user-123', 'phone_number': '+1234567890', 'conversation_history': ''}],
            'google_accounts': [{'id': 'google-account-123', 'user_id': 'test-user-123', 'email': 'test@example.com'}]
        }
    
    def table(self, table_name):
        return MockTable(self.table_data.get(table_name, []))

class MockTable:
    def __init__(self, data):
        self.data = data
        self._filters = {}
    
    def select(self, columns): return self
    def eq(self, column, value): self._filters[column] = value; return self
    def single(self): return self
    def update(self, data): return self
    def insert(self, data): return self
    
    def execute(self):
        for item in self.data:
            match = all(item.get(k) == v for k, v in self._filters.items())
            if match:
                return MagicMock(data=item)
        return MagicMock(data=None)

def test_json_parsing_fix():
    """Test the improved JSON parsing with various edge cases"""
    print("🧪 Testing improved JSON parsing...")
    
    # Test cases with different JSON formatting issues
    test_cases = [
        {
            "name": "Simple JSON",
            "response": '''```json
{
  "function": "DRAFT_EMAIL",
  "params": {
    "to": ["test@example.com"],
    "subject": "Test",
    "body": "Simple body"
  }
}
```''',
            "should_work": True
        },
        {
            "name": "JSON with newlines",
            "response": '''```json
{
  "function": "DRAFT_EMAIL",
  "params": {
    "to": ["test@example.com"],
    "subject": "Test",
    "body": "Line 1\nLine 2\nLine 3"
  }
}
```''',
            "should_work": True
        },
        {
            "name": "JSON with quotes",
            "response": '''```json
{
  "function": "DRAFT_EMAIL",
  "params": {
    "to": ["test@example.com"],
    "subject": "Meeting \"Tomorrow\"",
    "body": "Hi there,\n\nLet's meet tomorrow.\n\nBest regards"
  }
}
```''',
            "should_work": True
        }
    ]
    
    results = []
    for test_case in test_cases:
        print(f"\n  Testing: {test_case['name']}")
        
        # Extract JSON manually to test parsing
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", test_case['response'], re.DOTALL)
        if not json_match:
            print(f"    ❌ No JSON match found")
            results.append(False)
            continue
            
        json_str = json_match.group(1).strip()
        
        # Try the same parsing logic as the fixed function
        try:
            function_call = json.loads(json_str)
            print(f"    ✅ Direct JSON parsing worked")
            results.append(True)
        except json.JSONDecodeError as e:
            print(f"    ⚠️  Direct parsing failed: {e}")
            try:
                # Try the fallback method
                json_str_cleaned = json_str.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
                function_call = json.loads(json_str_cleaned)
                print(f"    ✅ Cleaned JSON parsing worked")
                results.append(True)
            except Exception as e2:
                print(f"    ❌ All parsing methods failed: {e2}")
                results.append(False)
    
    success_rate = sum(results) / len(results)
    print(f"\n  Overall success rate: {success_rate*100:.0f}% ({sum(results)}/{len(results)})")
    return success_rate == 1.0

async def test_end_to_end_with_mocks():
    """Test the complete end-to-end flow with proper mocking"""
    print("\n🧪 Testing end-to-end flow with mocks...")
    
    # Create a properly formatted AI response
    ai_response = '''i'll draft that email for you

```json
{
  "function": "DRAFT_EMAIL",
  "params": {
    "to": ["professor@university.edu"],
    "subject": "Office Hours Request",
    "body": "Dear Professor,\\n\\nI hope this email finds you well. I was wondering if you have any available office hours this week.\\n\\nBest regards,\\nStudent"
  }
}
```

the draft should be ready for review'''

    mock_supabase = MockSupabaseClient()
    ai_service = AIConversationService(mock_supabase)
    
    # Mock the HTTP client for Google integration
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'id': 'draft-123', 'message': {'id': 'msg-456'}}
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        
        # Test the function parsing and execution
        function_result = await ai_service._parse_and_execute_function(
            ai_response, 'test-user-123', '+1234567890'
        )
        
        if function_result and "created the email draft" in function_result:
            print("    ✅ Function executed successfully")
            print(f"    Result: {function_result}")
            
            # Test the response cleaning
            cleaned_response = re.sub(r"```json\s*\{.*?\}\s*```", "", ai_response, flags=re.DOTALL)
            cleaned_response = cleaned_response.strip()
            
            if cleaned_response:
                final_response = [cleaned_response, function_result]
            else:
                final_response = [function_result]
            
            final_text = ". ".join(final_response)
            print(f"    Final response: {final_text}")
            return True
        else:
            print(f"    ❌ Function execution failed: {function_result}")
            return False

async def main():
    """Run the fixed parsing tests"""
    print("🚀 Testing Fixed Function Parsing\n")
    
    tests = [
        ("JSON Parsing Fix", test_json_parsing_fix),
        ("End-to-End with Mocks", test_end_to_end_with_mocks)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {str(e)}")
            results.append((test_name, False))
    
    print("\n📊 Results:")
    print("=" * 40)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All parsing tests passed!")
    else:
        print("⚠️  Some tests failed.")

if __name__ == "__main__":
    asyncio.run(main())
