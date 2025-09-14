#!/usr/bin/env python3
"""
Test script to simulate multiple concurrent users signing up
This will verify the 403 Forbidden fix works under load
"""

import asyncio
import aiohttp
import json
from datetime import datetime

# Test webhook payload template
def create_test_payload(email: str, phone: str, message_text: str):
    return {
        "type": "new-message",
        "data": {
            "guid": f"test-{email.split('@')[0]}-{datetime.now().timestamp()}",
            "text": message_text,
            "dateCreated": int(datetime.now().timestamp() * 1000),
            "chatGuid": f"SMS;-;+1{phone}",
            "isFromMe": False,
            "handle": {
                "address": f"+1{phone}",
                "country": "us"
            }
        }
    }

async def send_webhook(session, email: str, phone: str, message_text: str):
    """Send a webhook request for a test user"""
    payload = create_test_payload(email, phone, message_text)
    
    try:
        async with session.post(
            "http://localhost:8000/webhooks/bluebubbles",
            json=payload,
            headers={"Content-Type": "application/json"}
        ) as response:
            result = await response.json()
            status = response.status
            
            print(f"User {email}: Status {status} - {result.get('message', 'No message')}")
            return status == 200
            
    except Exception as e:
        print(f"User {email}: ERROR - {str(e)}")
        return False

async def test_concurrent_signups():
    """Test multiple users signing up concurrently"""
    
    # Test users with different emails and phone numbers
    test_users = [
        ("user1@test.com", "5551234567", "user1@test.com"),
        ("user2@test.com", "5551234568", "user2@test.com"), 
        ("user3@test.com", "5551234569", "user3@test.com"),
        ("user4@test.com", "5551234570", "user4@test.com"),
        ("user5@test.com", "5551234571", "user5@test.com")
    ]
    
    print("=== Testing Concurrent User Signups ===")
    print(f"Testing {len(test_users)} users simultaneously...")
    
    async with aiohttp.ClientSession() as session:
        # Send all requests concurrently
        tasks = [
            send_webhook(session, email, phone, message_text)
            for email, phone, message_text in test_users
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successes
        successes = sum(1 for result in results if result is True)
        failures = len(results) - successes
        
        print(f"\n=== Results ===")
        print(f"✅ Successful: {successes}/{len(test_users)}")
        print(f"❌ Failed: {failures}/{len(test_users)}")
        
        if failures == 0:
            print("🎉 All users processed successfully - 403 Forbidden errors are FIXED!")
        else:
            print("⚠️  Some users failed - may need further investigation")

if __name__ == "__main__":
    asyncio.run(test_concurrent_signups())
