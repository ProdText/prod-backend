#!/usr/bin/env python3
"""
Debug script to test function parsing regex and imports
"""

import re
import json

def test_regex_pattern():
    """Test the regex pattern used for JSON function call parsing"""
    print("🔍 Testing regex pattern...")
    
    test_response = """hey, i'll draft that email for you right now

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

    # Test the exact regex pattern from the code
    json_match = re.search(r"```json\s*(\{.*?\})\s*```", test_response, re.DOTALL)
    
    if json_match:
        print("✅ Regex pattern matches!")
        json_content = json_match.group(1)
        print(f"   Extracted JSON: {json_content}")
        
        try:
            function_call = json.loads(json_content)
            print(f"   Parsed function: {function_call.get('function')}")
            print(f"   Parsed params: {function_call.get('params')}")
            return True
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing failed: {e}")
            return False
    else:
        print("❌ Regex pattern does not match!")
        
        # Try alternative patterns
        patterns = [
            r"```json\s*(\{.*?\})\s*```",
            r"```json\s*(\{[\s\S]*?\})\s*```",
            r"```json\s*(.*?)\s*```",
        ]
        
        for i, pattern in enumerate(patterns):
            match = re.search(pattern, test_response, re.DOTALL)
            if match:
                print(f"   Alternative pattern {i+1} matches: {match.group(1)[:50]}...")
        
        return False

def test_import():
    """Test if Google integration service can be imported"""
    print("\n🔍 Testing Google integration import...")
    
    try:
        from services.google_integration_service import GoogleIntegrationService
        print("✅ Google integration service imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def test_multiline_json():
    """Test with multiline JSON that might cause issues"""
    print("\n🔍 Testing multiline JSON parsing...")
    
    multiline_response = '''i'll create that draft for you

```json
{
  "function": "DRAFT_EMAIL",
  "params": {
    "to": ["test@example.com"],
    "subject": "Test Subject",
    "body": "Line 1\nLine 2\nLine 3"
  }
}
```

done!'''

    json_match = re.search(r"```json\s*(\{.*?\})\s*```", multiline_response, re.DOTALL)
    
    if json_match:
        print("✅ Multiline JSON matches!")
        try:
            function_call = json.loads(json_match.group(1))
            print(f"   Function: {function_call.get('function')}")
            return True
        except json.JSONDecodeError as e:
            print(f"❌ Multiline JSON parsing failed: {e}")
            return False
    else:
        print("❌ Multiline JSON does not match!")
        return False

if __name__ == "__main__":
    print("🚀 Debugging Function Parsing\n")
    
    tests = [
        ("Regex Pattern", test_regex_pattern),
        ("Import Test", test_import),
        ("Multiline JSON", test_multiline_json)
    ]
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} - {test_name}\n")
        except Exception as e:
            print(f"❌ FAIL - {test_name}: {str(e)}\n")
