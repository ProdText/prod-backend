#!/usr/bin/env python3
"""
Test concurrent user creation with clean database
This will verify if the fixes work properly with fresh users
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

async def register_user(session, phone: str, email: str, user_id: str):
    """Register a new user by sending their email"""
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
            
            success = response.status == 200
            has_error = "error" in result.get('message', '').lower()
            otp_sent = "otp" in result.get('message', '').lower() or "code" in result.get('message', '').lower()
            
            print(f"📱 {phone} ({email})")
            print(f"   Status: {response.status}")
            print(f"   Time: {end_time - start_time:.3f}s")
            print(f"   Response: {result.get('message', 'No message')[:80]}...")
            print(f"   Success: {success and not has_error}")
            print(f"   OTP Sent: {otp_sent}")
            print()
            
            return success and not has_error, otp_sent
            
    except Exception as e:
        print(f"❌ Error for {phone}: {str(e)}")
        return False, False

async def test_concurrent_user_creation():
    """Test concurrent user creation with clean database"""
    
    print("=== Testing Concurrent User Creation (Clean Database) ===\n")
    
    # Generate unique test users
    timestamp = int(time.time())
    test_users = [
        (f"+1555123456{i}", f"testuser{i}-{timestamp}@example.com", f"user{i}")
        for i in range(5)
    ]
    
    print(f"Testing {len(test_users)} concurrent user registrations...\n")
    
    async with aiohttp.ClientSession() as session:
        # Send all registration requests simultaneously
        start_time = time.time()
        tasks = [
            register_user(session, phone, email, user_id)
            for phone, email, user_id in test_users
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # Analyze results
        successful_registrations = sum(1 for result in results if isinstance(result, tuple) and result[0])
        otp_sent_count = sum(1 for result in results if isinstance(result, tuple) and result[1])
        errors = sum(1 for result in results if isinstance(result, Exception))
        
        print("=== Results ===")
        print(f"Total time: {end_time - start_time:.3f}s")
        print(f"Successful registrations: {successful_registrations}/{len(test_users)}")
        print(f"OTP emails sent: {otp_sent_count}/{len(test_users)}")
        print(f"Errors: {errors}")
        
        if successful_registrations == len(test_users) and otp_sent_count == len(test_users):
            print("\n🎉 CONCURRENT USER CREATION SUCCESSFUL!")
            print("✅ All users registered without conflicts")
            print("✅ All OTP emails sent successfully")
            print("✅ System handles concurrent load properly")
        elif successful_registrations > 0:
            print(f"\n⚠️  PARTIAL SUCCESS: {successful_registrations}/{len(test_users)} users created")
            print("Some users may have encountered issues")
        else:
            print("\n❌ CONCURRENT CREATION FAILED")
            print("System cannot handle concurrent user registrations")

if __name__ == "__main__":
    asyncio.run(test_concurrent_user_creation())
