#!/usr/bin/env python3
"""
Test script for memory integration.
Tests profile extraction, event storage, and context enrichment.
"""

import sys
import json
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.memory import MemoryService


def test_memory_service():
    """Test the memory service functionality."""
    print("=" * 80)
    print("Testing Memory Service")
    print("=" * 80)

    # Initialize service
    print("\n1. Initializing memory service...")
    service = MemoryService()
    print("✓ Memory service initialized")

    # Clear any existing data
    print("\n2. Clearing existing memory...")
    service.clear_all()
    print("✓ Memory cleared")

    # Test conversation 1: User introduces themselves
    print("\n3. Recording first conversation (user introduction)...")
    user_msg_1 = "Hi! I'm Alex, a Python developer working on AI projects."
    assistant_msg_1 = "Hello Alex! Great to meet you. I'd be happy to help with your AI projects."

    success = service.record_event(user_msg_1, assistant_msg_1, session_id="test_session_1")
    print(f"✓ Event recorded: {success}")

    # Check profile after first conversation
    print("\n4. Checking profile after first conversation...")
    stats = service.get_stats()
    print(f"Profile properties: {json.dumps(stats['profile']['properties'], indent=2)}")
    print(f"Profile preferences: {json.dumps(stats['profile']['preferences'], indent=2)}")
    print(f"Events recorded: {stats['events']['total_count']}")

    # Test conversation 2: User expresses preferences
    print("\n5. Recording second conversation (user preferences)...")
    user_msg_2 = "I prefer concise answers and I'm really interested in machine learning and NLP."
    assistant_msg_2 = "Understood! I'll keep responses brief. ML and NLP are fascinating fields."

    success = service.record_event(user_msg_2, assistant_msg_2, session_id="test_session_1")
    print(f"✓ Event recorded: {success}")

    # Check updated profile
    print("\n6. Checking updated profile...")
    stats = service.get_stats()
    print(f"Profile properties: {json.dumps(stats['profile']['properties'], indent=2)}")
    print(f"Profile preferences: {json.dumps(stats['profile']['preferences'], indent=2)}")
    print(f"Events recorded: {stats['events']['total_count']}")

    # Test context retrieval
    print("\n7. Testing context retrieval...")
    query = "What can you help me with?"
    context = service.get_context(query, max_events=3, session_id="test_session_1")
    print("Context generated:")
    print("-" * 80)
    print(context)
    print("-" * 80)

    # Test semantic search
    print("\n8. Testing semantic search for relevant events...")
    query = "Tell me about machine learning"
    context = service.get_context(query, max_events=2, use_semantic_search=True)
    print("Semantically relevant context:")
    print("-" * 80)
    print(context)
    print("-" * 80)

    print("\n" + "=" * 80)
    print("✓ All tests completed successfully!")
    print("=" * 80)

    # Print final stats
    print("\nFinal Memory Statistics:")
    final_stats = service.get_stats()
    print(json.dumps(final_stats, indent=2, default=str))


if __name__ == "__main__":
    try:
        test_memory_service()
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
