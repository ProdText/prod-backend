#!/usr/bin/env python3
"""
Test script for Memory Service integration
"""

import asyncio
import sys
import os
import uuid
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.memory_service import MemoryService


async def test_memory_integration():
    """Test the memory service integration"""
    print("🧪 Testing Memory Service Integration")
    print("=" * 60)
    
    memory_service = MemoryService()
    
    # Test data
    test_message_id = f"test-message-{uuid.uuid4()}"
    test_user_id = str(uuid.uuid4())
    test_message_body = "This is a test message for memory ingestion"
    
    print(f"📝 Test Message ID: {test_message_id}")
    print(f"👤 Test User ID: {test_user_id}")
    print(f"💬 Test Message: {test_message_body}")
    print(f"🔗 Memory Endpoint: {memory_service.memory_endpoint}")
    print()
    
    try:
        print("🚀 Sending message to memory endpoint...")
        success = await memory_service.ingest_message(
            message_id=test_message_id,
            message_body=test_message_body,
            user_id=test_user_id,
            source_description="imessage"
        )
        
        if success:
            print("✅ Memory ingestion successful!")
        else:
            print("❌ Memory ingestion failed!")
            
    except Exception as e:
        print(f"💥 Error during memory ingestion: {str(e)}")
        return False
    
    print()
    print("📊 Test Results Summary")
    print("=" * 60)
    if success:
        print("✅ Memory service integration working correctly")
        return True
    else:
        print("❌ Memory service integration failed")
        return False


if __name__ == "__main__":
    result = asyncio.run(test_memory_integration())
    sys.exit(0 if result else 1)
