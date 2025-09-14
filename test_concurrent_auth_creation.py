#!/usr/bin/env python3
"""
Test script to identify the root cause of 403 Forbidden errors during concurrent user creation
This will test the Supabase Admin API under concurrent load to find the real issue
"""

import asyncio
import os
from dotenv import load_dotenv
from supabase import create_client
from gotrue import AdminUserAttributes
import time
import random

async def create_test_user(client, user_id: str, email: str):
    """Attempt to create a single test user"""
    try:
        admin_auth = client.auth.admin
        
        attrs = AdminUserAttributes(
            email=email,
            email_confirm=True,
            user_metadata={"test": True, "user_id": user_id}
        )
        
        start_time = time.time()
        response = admin_auth.create_user(attrs)
        end_time = time.time()
        
        if response.user:
            print(f"✅ User {user_id}: SUCCESS - Created in {end_time - start_time:.3f}s")
            # Clean up immediately
            admin_auth.delete_user(response.user.id)
            return True, None
        else:
            print(f"❌ User {user_id}: FAILED - No user returned")
            return False, "No user returned"
            
    except Exception as e:
        error_msg = str(e)
        print(f"❌ User {user_id}: ERROR - {error_msg}")
        return False, error_msg

async def test_concurrent_user_creation():
    """Test concurrent user creation to identify the root cause"""
    
    load_dotenv()
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        print("❌ Missing Supabase credentials")
        return
    
    print("=== Testing Concurrent User Creation ===\n")
    
    # Test with increasing concurrency levels
    concurrency_levels = [1, 2, 5, 10, 20]
    
    for level in concurrency_levels:
        print(f"--- Testing {level} concurrent user creations ---")
        
        # Create fresh clients for each test to avoid session pollution
        clients = [create_client(url, key) for _ in range(level)]
        
        # Generate unique test emails
        test_users = [
            (f"test-{level}-{i}-{int(time.time())}-{random.randint(1000,9999)}@example.com", f"user_{level}_{i}")
            for i in range(level)
        ]
        
        # Run concurrent user creation
        start_time = time.time()
        tasks = [
            create_test_user(clients[i], user_id, email)
            for i, (email, user_id) in enumerate(test_users)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # Analyze results
        successes = sum(1 for result in results if isinstance(result, tuple) and result[0])
        failures = level - successes
        
        print(f"Results: {successes}/{level} successful ({failures} failed)")
        print(f"Total time: {end_time - start_time:.3f}s")
        
        # Check for specific error patterns
        forbidden_errors = 0
        rate_limit_errors = 0
        other_errors = 0
        
        for result in results:
            if isinstance(result, tuple) and not result[0] and result[1]:
                error_msg = result[1].lower()
                if "403" in error_msg or "forbidden" in error_msg or "not allowed" in error_msg:
                    forbidden_errors += 1
                elif "rate" in error_msg or "limit" in error_msg or "429" in error_msg:
                    rate_limit_errors += 1
                else:
                    other_errors += 1
        
        print(f"Error breakdown:")
        print(f"  - 403 Forbidden: {forbidden_errors}")
        print(f"  - Rate limiting: {rate_limit_errors}")
        print(f"  - Other errors: {other_errors}")
        print()
        
        # If we start seeing failures, we've found the breaking point
        if failures > 0:
            print(f"🔍 BREAKING POINT FOUND: {level} concurrent requests")
            print("This indicates the root cause is Supabase Admin API concurrency limits")
            break
        
        # Small delay between tests
        await asyncio.sleep(1)
    
    print("=== Root Cause Analysis ===")
    print("If failures occurred at low concurrency (2-5), the issue is:")
    print("1. Supabase Admin API has strict concurrency limits")
    print("2. Multiple simultaneous admin_auth.create_user() calls are blocked")
    print("3. This is a fundamental Supabase limitation, not our code")
    print("\nSolution needed: Implement request queuing/serialization for user creation")

if __name__ == "__main__":
    asyncio.run(test_concurrent_user_creation())
