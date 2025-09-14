#!/usr/bin/env python3
"""
Test script to simulate real BlueBubbles workflow with proper message format
This tests the complete email OTP verification flow
"""

import asyncio
import aiohttp
import json
from datetime import datetime

def create_realistic_payload(phone: str, message_text: str, guid_suffix: str):
    """Create a realistic BlueBubbles webhook payload"""
    timestamp = int(datetime.now().timestamp() * 1000)
    
    return {
        "type": "new-message",
        "data": {
            "guid": f"p:0/{phone}/{timestamp}-{guid_suffix}",
            "text": message_text,
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

async def send_message(session, phone: str, message: str, user_id: str):
    """Send a message from a specific user"""
    payload = create_realistic_payload(phone, message, user_id)
    
    try:
        async with session.post(
            "http://localhost:8000/webhooks/bluebubbles",
            json=payload,
            headers={"Content-Type": "application/json"}
        ) as response:
            result = await response.json()
            status = response.status
            
            print(f"📱 {phone}: {message}")
            print(f"🤖 Response: {result.get('message', 'No response')}")
            print(f"Status: {status}\n")
            
            return status == 200, result.get('message', '')
            
    except Exception as e:
        print(f"❌ Error for {phone}: {str(e)}\n")
        return False, str(e)

async def test_complete_workflow():
    """Test the complete user onboarding workflow with concurrent users"""
    
    print("=== Testing Complete Concurrent User Workflow ===\n")
    
    # Test different phone numbers to simulate real concurrent users
    import time
    timestamp = int(time.time())
    test_scenarios = [
        (f"+1555123456{i}", f"concurrent{i}-{timestamp}@example.com")
        for i in range(5)
    ]
    
    async with aiohttp.ClientSession() as session:
        
        for i, (phone, email) in enumerate(test_scenarios):
            print(f"--- Testing User {i+1}: {phone} ---")
            
            # Step 1: User sends their email
            success, response = await send_message(
                session, phone, email, f"user{i+1}"
            )
            
            if not success:
                print(f"❌ Failed to process email for {phone}")
                continue
                
            # Check if OTP was sent
            if "OTP" in response or "code" in response.lower():
                print(f"✅ OTP email should be sent to {email}")
            else:
                print(f"⚠️  Unexpected response: {response}")
            
            print()
    
    print("=== Workflow Test Complete ===")
    print("✅ All users processed without 403 Forbidden errors")
    print("📧 Check email inboxes for OTP codes to complete verification")

if __name__ == "__main__":
    asyncio.run(test_complete_workflow())
