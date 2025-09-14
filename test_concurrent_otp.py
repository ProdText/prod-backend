#!/usr/bin/env python3
"""
Test script to simulate the exact concurrent OTP verification scenario
This tests the retry logic fix for user lookup failures
"""

import asyncio
import aiohttp
import json
from datetime import datetime

def create_otp_payload(phone: str, otp_code: str, guid_suffix: str):
    """Create a realistic OTP verification payload"""
    timestamp = int(datetime.now().timestamp() * 1000)
    
    return {
        "type": "new-message",
        "data": {
            "guid": f"p:0/{phone}/{timestamp}-{guid_suffix}",
            "text": otp_code,
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

async def send_otp_verification(session, phone: str, otp_code: str, user_id: str):
    """Send OTP verification for a user"""
    payload = create_otp_payload(phone, otp_code, user_id)
    
    try:
        async with session.post(
            "http://localhost:8000/webhooks/bluebubbles",
            json=payload,
            headers={"Content-Type": "application/json"}
        ) as response:
            result = await response.json()
            status = response.status
            
            print(f"📱 {phone}: OTP {otp_code}")
            print(f"🤖 Response: {result.get('message', 'No response')[:100]}...")
            print(f"Status: {status}")
            
            # Check if verification was successful
            success = "verified successfully" in result.get('message', '').lower()
            account_not_found = "couldn't find your account" in result.get('message', '').lower()
            
            print(f"✅ Verified: {success}")
            print(f"❌ Account Not Found: {account_not_found}")
            print()
            
            return success, account_not_found
            
    except Exception as e:
        print(f"❌ Error for {phone}: {str(e)}\n")
        return False, False

async def test_concurrent_otp_verification():
    """Test concurrent OTP verification with the retry logic"""
    
    print("=== Testing Concurrent OTP Verification ===\n")
    
    # Use the actual phone number from the logs that had issues
    test_phone = "+19197109288"
    
    # Simulate two users trying to verify at the same time
    # (In reality, these would be different users, but we're testing the lookup logic)
    test_scenarios = [
        (test_phone, "123456", "user1"),
        (test_phone, "654321", "user2")
    ]
    
    async with aiohttp.ClientSession() as session:
        print("Sending concurrent OTP verification requests...\n")
        
        # Send both OTP verifications simultaneously
        tasks = [
            send_otp_verification(session, phone, otp, user_id)
            for phone, otp, user_id in test_scenarios
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze results
        successful_verifications = sum(1 for result in results if isinstance(result, tuple) and result[0])
        account_not_found_errors = sum(1 for result in results if isinstance(result, tuple) and result[1])
        
        print("=== Test Results ===")
        print(f"Successful verifications: {successful_verifications}")
        print(f"Account not found errors: {account_not_found_errors}")
        
        if account_not_found_errors == 0:
            print("🎉 SUCCESS: No 'account not found' errors with retry logic!")
        else:
            print("⚠️  Still experiencing account lookup issues")

if __name__ == "__main__":
    asyncio.run(test_concurrent_otp_verification())
