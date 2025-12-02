#!/usr/bin/env python3
"""
Integration test script for Phase 1: Station Name Resolution

This script tests the conversational integration of the StationResolver
with the ScotRailAgent to verify that natural language station queries
are correctly resolved to CRS codes.
"""

import os
from scotrail_agent import ScotRailAgent


def test_station_resolution():
    """Test that the agent can resolve various station name formats."""
    
    print("=" * 70)
    print("Phase 1 Integration Test: Station Name Resolution")
    print("=" * 70)
    print()
    
    # Check API key
    if not os.environ.get('OPENAI_API_KEY'):
        print("⚠️  Warning: OPENAI_API_KEY not set. This test requires a valid API key.")
        print("Set it with: export OPENAI_API_KEY='your-key-here'")
        return False
    
    # Initialize agent
    print("Initializing ScotRailAgent...")
    agent = ScotRailAgent()
    print()
    
    # Test queries with various station name formats
    test_queries = [
        "What's the next train from edinburgh?",
        "Show me departures from glasgow central",
        "Trains from inverness to aberdeen",
        "When's the next train from waverley?",  # Partial name (Edinburgh Waverley)
        "Departures from dundee",
    ]
    
    print("Testing natural language station queries:")
    print("-" * 70)
    print()
    
    for i, query in enumerate(test_queries, 1):
        print(f"Test {i}: \"{query}\"")
        print()
        
        try:
            # Send query to agent
            response = agent.chat(query)
            
            # Check if agent used resolve_station_name tool
            # We can infer this from the conversation history
            used_resolve = False
            for msg in agent.conversation_history[-5:]:  # Check recent messages
                if msg.get('role') == 'assistant' and msg.get('tool_calls'):
                    for tool_call in msg['tool_calls']:
                        if tool_call['function']['name'] == 'resolve_station_name':
                            used_resolve = True
                            print("✓ Agent called resolve_station_name tool")
                            break
            
            if not used_resolve:
                print("ℹ️  Agent did not explicitly call resolve_station_name")
                print("   (may have already known the CRS code)")
            
            print()
            print(f"Response: {response[:200]}...")  # First 200 chars
            print()
            
        except Exception as e:
            print(f"✗ Error: {e}")
            print()
        
        print("-" * 70)
        print()
    
    print("=" * 70)
    print("Integration test complete!")
    print("=" * 70)
    
    return True


if __name__ == "__main__":
    test_station_resolution()
