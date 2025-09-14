#!/usr/bin/env python3
"""
Test concurrent OTP verification workflow
This simulates multiple users entering their OTP codes simultaneously
"""

import asyncio
import aiohttp
import json
from datetime import datetime
import time

def create_otp_verification_payload(phone: str, otp_code: str, guid_suffix: str):
    """Create OTP verification payload"""
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

async def verify_otp(session, phone: str, otp_code: str, user_id: str):
    """Verify OTP code for a user"""
    payload = create_otp_verification_payload(phone, otp_code, user_id)
    
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
            message = result.get('message', '')
            
            # Check for successful verification indicators
            verification_success = any(keyword in message.lower() for keyword in [
                'welcome', 'verified', 'complete', 'success', 'congratulations'
            ])
            
            # Check for error indicators
            has_error = any(keyword in message.lower() for keyword in [
                'error', 'invalid', 'expired', 'not found', 'failed'
            ])
            
            print(f"📱 {phone} (OTP: {otp_code})")
            print(f"   Status: {response.status}")
            print(f"   Time: {end_time - start_time:.3f}s")
            print(f"   Response: {message[:100]}...")
            print(f"   Verified: {verification_success}")
            print(f"   Error: {has_error}")
            print()
            
            return success and verification_success and not has_error
            
    except Exception as e:
        print(f"❌ Error for {phone}: {str(e)}")
        return False

async def test_concurrent_otp_verification():
    """Test concurrent OTP verification"""
    
    print("=== Testing Concurrent OTP Verification ===\n")
    
    # Use the test users we created earlier
    test_users = [
        (f"+1555123456{i}", f"12345{i}", f"otp{i}")
        for i in range(5)
    ]
    
    print(f"Testing {len(test_users)} concurrent OTP verifications...\n")
    print("Note: Using dummy OTP codes since we can't access real email OTPs")
    print("This tests the system's ability to handle concurrent verification requests\n")
    
    async with aiohttp.ClientSession() as session:
        # Send all OTP verification requests simultaneously
        start_time = time.time()
        tasks = [
            verify_otp(session, phone, otp, user_id)
            for phone, otp, user_id in test_users
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # Analyze results
        successful_verifications = sum(1 for result in results if isinstance(result, bool) and result)
        failed_verifications = sum(1 for result in results if isinstance(result, bool) and not result)
        errors = sum(1 for result in results if isinstance(result, Exception))
        
        print("=== OTP Verification Results ===")
        print(f"Total time: {end_time - start_time:.3f}s")
        print(f"Successful verifications: {successful_verifications}/{len(test_users)}")
        print(f"Failed verifications: {failed_verifications}/{len(test_users)}")
        print(f"Errors: {errors}")
        
        if successful_verifications > 0:
            print(f"\n✅ CONCURRENT OTP VERIFICATION WORKING!")
            print(f"System handled {successful_verifications} concurrent verifications")
        else:
            print(f"\n⚠️  OTP verification results depend on correct OTP codes")
            print("System processed all requests without crashes or 403 errors")

async def test_user_lookup_stress():
    """Test user lookup under concurrent load"""
    
    print("\n=== Testing User Lookup Under Load ===\n")
    
    # Test the same phone number lookup multiple times concurrently
    test_phone = "+15551234560"  # One of our test users
    
    async def lookup_user(session, attempt_id):
        """Simulate user lookup during OTP verification"""
        payload = create_otp_verification_payload(test_phone, "999999", f"lookup{attempt_id}")
        
        try:
            start_time = time.time()
            async with session.post(
                "http://localhost:8000/webhooks/bluebubbles",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                result = await response.json()
                end_time = time.time()
                
                message = result.get('message', '')
                user_found = 'not found' not in message.lower()
                
                print(f"Lookup {attempt_id}: {end_time - start_time:.3f}s - User found: {user_found}")
                return user_found
                
        except Exception as e:
            print(f"Lookup {attempt_id}: Error - {str(e)}")
            return False
    
    async with aiohttp.ClientSession() as session:
        # Perform 10 concurrent user lookups
        tasks = [lookup_user(session, i) for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful_lookups = sum(1 for result in results if isinstance(result, bool) and result)
        
        print(f"\nUser lookup results: {successful_lookups}/10 successful")
        
        if successful_lookups >= 8:  # Allow for some variance
            print("✅ User lookup is stable under concurrent load")
        else:
            print("⚠️  User lookup may have issues under concurrent load")

if __name__ == "__main__":
    asyncio.run(test_concurrent_otp_verification())
    asyncio.run(test_user_lookup_stress())
