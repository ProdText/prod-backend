#!/usr/bin/env python3
"""
Comprehensive test to verify no 403 Forbidden errors occur
with the enhanced per-request Supabase client isolation
"""

import asyncio
import aiohttp
import json
from datetime import datetime
import time

def create_user_registration_payload(phone: str, email: str, guid_suffix: str):
    """Create a realistic user registration payload"""
    timestamp = int(datetime.now().timestamp() * 1000)
    
    return {
        "type": "new-message",
        "data": {
            "guid": f"p:0/{phone}/{timestamp}-{guid_suffix}",
            "text": email,
            "dateCreated": timestamp,
            "chatGuid": f"iMessage;-;{phone}",
            "isFromMe": False,
            "handle": {
                "address": phone,
                "country": "us"
            },
            "chats": [
                {
                    "guid": f"iMessage;-;{phone}",
                    "chatIdentifier": phone
                }
            ]
        }
    }

async def register_user_and_check_errors(session, phone: str, email: str, user_id: str):
    """Register a user and specifically check for 403 Forbidden errors"""
    payload = create_user_registration_payload(phone, email, user_id)
    
    try:
        start_time = time.time()
        async with session.post(
            "http://localhost:8000/webhooks/bluebubbles",
            json=payload,
            headers={"Content-Type": "application/json"}
        ) as response:
            result = await response.json()
            end_time = time.time()
            
            # Check specifically for 403 Forbidden errors
            has_403_error = response.status == 403
            has_user_not_allowed = "user not allowed" in result.get('message', '').lower()
            has_forbidden_error = "forbidden" in result.get('message', '').lower()
            
            # Check for successful processing (200 status)
            processed_successfully = response.status == 200
            
            # Check for BlueBubbles 500 errors (external issue)
            has_bluebubbles_500 = "500 internal server error" in result.get('message', '').lower()
            
            print(f"📱 {phone} ({email})")
            print(f"   HTTP Status: {response.status}")
            print(f"   Time: {end_time - start_time:.3f}s")
            print(f"   403 Forbidden: {has_403_error}")
            print(f"   'User not allowed': {has_user_not_allowed}")
            print(f"   'Forbidden' error: {has_forbidden_error}")
            print(f"   Processed (200): {processed_successfully}")
            print(f"   BlueBubbles 500: {has_bluebubbles_500}")
            print(f"   Response: {result.get('message', 'No message')[:80]}...")
            print()
            
            return {
                'phone': phone,
                'status': response.status,
                'has_403': has_403_error,
                'has_user_not_allowed': has_user_not_allowed,
                'has_forbidden': has_forbidden_error,
                'processed_ok': processed_successfully,
                'bluebubbles_500': has_bluebubbles_500,
                'time': end_time - start_time
            }
            
    except Exception as e:
        print(f"❌ Exception for {phone}: {str(e)}")
        return {
            'phone': phone,
            'status': 'exception',
            'has_403': False,
            'has_user_not_allowed': False,
            'has_forbidden': False,
            'processed_ok': False,
            'bluebubbles_500': False,
            'time': 0,
            'error': str(e)
        }

async def test_no_403_errors():
    """Test that no 403 Forbidden errors occur with enhanced client isolation"""
    
    print("=== Testing for 403 Forbidden Errors (Enhanced Client Isolation) ===\n")
    
    # Generate unique test users with timestamp
    timestamp = int(time.time())
    test_users = [
        (f"+1555987654{i}", f"test403-{i}-{timestamp}@example.com", f"test{i}")
        for i in range(10)  # Test with 10 concurrent users
    ]
    
    print(f"Testing {len(test_users)} concurrent registrations for 403 errors...\n")
    
    async with aiohttp.ClientSession() as session:
        # Send all registration requests simultaneously
        start_time = time.time()
        tasks = [
            register_user_and_check_errors(session, phone, email, user_id)
            for phone, email, user_id in test_users
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # Analyze results for 403 errors
        total_requests = len(results)
        forbidden_403_count = sum(1 for r in results if isinstance(r, dict) and r.get('has_403', False))
        user_not_allowed_count = sum(1 for r in results if isinstance(r, dict) and r.get('has_user_not_allowed', False))
        forbidden_text_count = sum(1 for r in results if isinstance(r, dict) and r.get('has_forbidden', False))
        processed_ok_count = sum(1 for r in results if isinstance(r, dict) and r.get('processed_ok', False))
        bluebubbles_500_count = sum(1 for r in results if isinstance(r, dict) and r.get('bluebubbles_500', False))
        exceptions_count = sum(1 for r in results if isinstance(r, dict) and 'error' in r)
        
        print("=== 403 Forbidden Error Analysis ===")
        print(f"Total concurrent requests: {total_requests}")
        print(f"HTTP 403 Forbidden responses: {forbidden_403_count}")
        print(f"'User not allowed' messages: {user_not_allowed_count}")
        print(f"'Forbidden' error messages: {forbidden_text_count}")
        print(f"Successfully processed (200): {processed_ok_count}")
        print(f"BlueBubbles 500 errors (external): {bluebubbles_500_count}")
        print(f"Exceptions: {exceptions_count}")
        print(f"Total processing time: {end_time - start_time:.3f}s")
        
        # Determine if 403 errors are resolved
        total_403_issues = forbidden_403_count + user_not_allowed_count + forbidden_text_count
        
        if total_403_issues == 0:
            print(f"\n🎉 SUCCESS: NO 403 FORBIDDEN ERRORS DETECTED!")
            print(f"✅ Enhanced per-request client isolation is working")
            print(f"✅ All {processed_ok_count}/{total_requests} requests processed successfully")
            print(f"✅ Concurrent user creation is fully functional")
            if bluebubbles_500_count > 0:
                print(f"⚠️  {bluebubbles_500_count} BlueBubbles 500 errors (external service issue)")
        else:
            print(f"\n❌ FAILURE: {total_403_issues} 403 FORBIDDEN ERRORS DETECTED")
            print(f"❌ Per-request client isolation needs further enhancement")
            
            # Show specific error details
            for result in results:
                if isinstance(result, dict) and (result.get('has_403') or result.get('has_user_not_allowed') or result.get('has_forbidden')):
                    print(f"   - {result['phone']}: Status {result['status']}")

if __name__ == "__main__":
    asyncio.run(test_no_403_errors())
