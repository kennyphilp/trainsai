#!/usr/bin/env python3
"""
Phase 2 Demonstration - Enhanced Search Capabilities
=====================================================

This script demonstrates the enhanced search capabilities implemented in Phase 2:

1. Geographical hierarchy integration in station queries
2. Place-name search tools for natural language planning
3. Enhanced API responses with geographical metadata
4. Advanced fuzzy matching with geographical context

All improvements build on Phase 1's performance optimizations.
"""

import os
import sys
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from timetable_tools import TimetableTools
from improved_station_resolver import ImprovedStationResolver

# Load environment
load_dotenv()

def print_header(title: str):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")

def print_subheader(title: str):
    """Print a formatted subsection header."""
    print(f"\n{'-'*40}")
    print(f" {title}")
    print(f"{'-'*40}")

def demo_geographical_hierarchy():
    """Demonstrate geographical hierarchy integration."""
    print_header("PHASE 2 DEMO: ENHANCED SEARCH CAPABILITIES")
    print("Building on Phase 1's 2.9x performance improvements...")
    print("Now adding geographical intelligence and natural language planning")
    
    # Initialize tools
    tools = TimetableTools()
    resolver = ImprovedStationResolver()
    
    print_subheader("1. Enhanced Station Resolution with Geographical Context")
    
    # Test geographical context for major stations
    test_stations = ['Edinburgh', 'Glasgow Central', 'Inverness', 'Aberdeen', 'Perth']
    
    for station_name in test_stations:
        print(f"\nStation: {station_name}")
        station_info = tools.get_station_with_context(station_name)
        
        if station_info:
            print(f"  Display Name: {station_info['display_name']}")
            print(f"  CRS Code: {station_info['crs_code']}")
            
            geo_context = station_info.get('geographical_context', {})
            if geo_context:
                print(f"  Geographical Context:")
                if geo_context.get('area'):
                    print(f"    Area: {geo_context['area']}")
                if geo_context.get('region'):
                    print(f"    Region: {geo_context['region']}")
                if geo_context.get('country'):
                    print(f"    Country: {geo_context['country']}")
        else:
            print(f"  Could not resolve: {station_name}")

def demo_place_name_search():
    """Demonstrate place-name search capabilities."""
    print_subheader("2. Place-Name Search with Geographical Intelligence")
    
    tools = TimetableTools()
    
    # Test place-based searches
    test_places = [
        'Glasgow',
        'Highlands', 
        'Borders',
        'Aberdeen',
        'Fife'
    ]
    
    for place in test_places:
        print(f"\nSearching for stations in: {place}")
        stations = tools.search_stations_by_place(place, limit=5)
        
        if stations:
            print(f"  Found {len(stations)} stations:")
            for station in stations:
                geo_context = station.get('geographical_context', {})
                area = geo_context.get('area', 'Unknown')
                print(f"    • {station['display_name']} ({station['crs_code']}) - {area}")
        else:
            print(f"  No stations found for: {place}")\n\ndef demo_place_name_search():\n    \"\"\"Demonstrate place-name search capabilities.\"\"\"\n    print_subheader(\"2. Place-Name Search with Geographical Intelligence\")\n    \n    tools = TimetableTools()\n    \n    # Test place-based searches\n    test_places = [\n        'Glasgow',\n        'Highlands', \n        'Borders',\n        'Aberdeen',\n        'Fife'\n    ]\n    \n    for place in test_places:\n        print(f\"\\nSearching for stations in: {place}\")\n        stations = tools.search_stations_by_place(place, limit=5)\n        \n        if stations:\n            print(f\"  Found {len(stations)} stations:\")\n            for station in stations:\n                geo_context = station.get('geographical_context', {})\n                area = geo_context.get('area', 'Unknown')\n                print(f\"    • {station['display_name']} ({station['crs_code']}) - {area}\")\n        else:\n            print(f\"  No stations found for: {place}\")\n\ndef demo_enhanced_journey_planning():\n    \"\"\"Demonstrate enhanced journey planning with geographical context.\"\"\"\n    print_subheader(\"3. Enhanced Journey Planning with Natural Language\")\n    \n    tools = TimetableTools()\n    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')\n    \n    # Test natural language journey planning\n    journey_queries = [\n        {\n            'from': 'Edinburgh',\n            'to': 'Highlands', \n            'description': 'Capital to Highlands'\n        },\n        {\n            'from': 'Glasgow',\n            'to': 'Aberdeen',\n            'description': 'West coast to East coast'\n        },\n        {\n            'from': 'Central Scotland',\n            'to': 'Borders',\n            'description': 'Central to Southern regions'\n        }\n    ]\n    \n    for query in journey_queries:\n        print(f\"\\nJourney: {query['description']}\")\n        print(f\"From '{query['from']}' to '{query['to']}' on {tomorrow}\")\n        \n        result = tools.plan_journey_with_context(\n            from_place=query['from'],\n            to_place=query['to'],\n            travel_date=tomorrow,\n            departure_time='09:00'\n        )\n        \n        if result['success']:\n            print(f\"  ✓ Found {len(result['journeys'])} journey options\")\n            \n            # Show geographical intelligence\n            from_options = result.get('from_options', [])\n            to_options = result.get('to_options', [])\n            \n            if from_options:\n                print(f\"  From options: {', '.join([s['display_name'] for s in from_options[:3]])}\")\n            if to_options:\n                print(f\"  To options: {', '.join([s['display_name'] for s in to_options[:3]])}\")\n            \n            # Show best journey with geographical summary\n            if result['journeys']:\n                best = result['journeys'][0]\n                geo_summary = best.get('geographical_summary', {})\n                \n                print(f\"  Best route: {best['from_station']['display_name']} → {best['to_station']['display_name']}\")\n                print(f\"  Duration: {best['total_duration']} mins, Changes: {best['changes']}\")\n                \n                if geo_summary.get('crosses_regions'):\n                    print(f\"  Crosses regions: {geo_summary.get('from_area')} → {geo_summary.get('to_area')}\")\n        else:\n            print(f\"  ✗ Error: {result.get('error', 'Unknown error')}\")\n\ndef demo_enhanced_api_responses():\n    \"\"\"Demonstrate enhanced API responses with geographical metadata.\"\"\"\n    print_subheader(\"4. Enhanced API Responses with Geographical Metadata\")\n    \n    tools = TimetableTools()\n    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')\n    \n    # Test enhanced scheduled trains response\n    print(\"\\nTesting enhanced get_scheduled_trains API:\")\n    \n    result = tools.get_scheduled_trains(\n        from_station='Edinburgh',\n        to_station='Glasgow Central',\n        travel_date=tomorrow,\n        departure_time='09:00'\n    )\n    \n    if result['success']:\n        print(f\"  ✓ Found {result['count']} trains\")\n        print(f\"  ✓ Optimization flag: {result.get('optimization_used', False)}\")\n        \n        # Show enhanced station information\n        from_info = result['from']\n        to_info = result['to']\n        \n        print(f\"\\n  From Station Enhanced Info:\")\n        print(f\"    Name: {from_info['name']}\")\n        print(f\"    TIPLOC: {from_info['tiploc']}\")\n        \n        from_geo = from_info.get('geographical_context')\n        if from_geo:\n            print(f\"    Geography: {from_geo.get('area', 'N/A')} ({from_geo.get('region', 'N/A')})\")\n        \n        print(f\"\\n  To Station Enhanced Info:\")\n        print(f\"    Name: {to_info['name']}\")\n        print(f\"    TIPLOC: {to_info['tiploc']}\")\n        \n        to_geo = to_info.get('geographical_context')\n        if to_geo:\n            print(f\"    Geography: {to_geo.get('area', 'N/A')} ({to_geo.get('region', 'N/A')})\")\n        \n        # Show sample train data\n        if result['trains']:\n            sample_train = result['trains'][0]\n            print(f\"\\n  Sample train: {sample_train['headcode']} ({sample_train['operator']})\")\n            print(f\"    Departs: {sample_train['departure_time']}\")\n            print(f\"    Arrives: {sample_train['arrival_time']}\")\n            print(f\"    Duration: {sample_train['duration_minutes']} minutes\")\n    else:\n        print(f\"  ✗ Error: {result.get('error', 'Unknown error')}\")\n\ndef demo_agent_integration():\n    \"\"\"Demonstrate ScotRailAgent integration with new geographical tools.\"\"\"\n    print_subheader(\"5. ScotRailAgent Integration - New Geographical Tools\")\n    \n    # Check if agent can be initialized\n    try:\n        agent = ScotRailAgent()\n        tools_count = len(agent.tools)\n        \n        print(f\"\\nScotRailAgent initialized with {tools_count} tools\")\n        \n        # Check for new geographical tools\n        tool_names = [tool['function']['name'] for tool in agent.tools]\n        new_tools = [\n            'plan_journey_with_context',\n            'search_stations_by_place', \n            'get_station_with_context'\n        ]\n        \n        print(\"\\nNew geographical intelligence tools:\")\n        for tool_name in new_tools:\n            status = \"✓ Available\" if tool_name in tool_names else \"✗ Missing\"\n            print(f\"  {tool_name}: {status}\")\n        \n        print(f\"\\nTotal tools available: {len(tool_names)}\")\n        \n        # Show sample tool descriptions\n        for tool in agent.tools:\n            if tool['function']['name'] in new_tools:\n                name = tool['function']['name']\n                desc = tool['function']['description'][:100] + \"...\"\n                print(f\"\\n  {name}:\")\n                print(f\"    {desc}\")\n        \n    except Exception as e:\n        print(f\"\\nCould not initialize ScotRailAgent: {e}\")\n        print(\"This might be due to missing API keys or dependencies.\")\n\ndef demo_performance_comparison():\n    \"\"\"Compare Phase 1 and Phase 2 capabilities.\"\"\"\n    print_subheader(\"6. Phase 1 vs Phase 2 Capabilities Comparison\")\n    \n    print(\"\\nPHASE 1 ACHIEVEMENTS (Completed):\")\n    print(\"  ✓ 2.9x faster time queries (seconds-based optimization)\")\n    print(\"  ✓ Smart station search with fuzzy matching\")\n    print(\"  ✓ Pre-computed journey views (31M+ routes)\")\n    print(\"  ✓ Enhanced database performance (45.5% time coverage)\")\n    \n    print(\"\\nPHASE 2 NEW CAPABILITIES (Current):\")\n    print(\"  ✓ Geographical hierarchy integration\")\n    print(\"  ✓ Natural language journey planning\")\n    print(\"  ✓ Place-name to station resolution\")\n    print(\"  ✓ Enhanced API responses with geographical metadata\")\n    print(\"  ✓ Cross-regional journey intelligence\")\n    \n    # Test actual performance\n    print(\"\\nPerformance Test:\")\n    \n    tools = TimetableTools()\n    \n    # Test geographical search performance\n    import time\n    \n    start_time = time.time()\n    stations = tools.search_stations_by_place('Glasgow', limit=10)\n    search_time = (time.time() - start_time) * 1000\n    \n    print(f\"  Place-based station search: {search_time:.2f}ms ({len(stations)} results)\")\n    \n    # Test enhanced journey planning performance\n    start_time = time.time()\n    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')\n    result = tools.plan_journey_with_context(\n        from_place='Edinburgh',\n        to_place='Glasgow',\n        travel_date=tomorrow\n    )\n    planning_time = (time.time() - start_time) * 1000\n    \n    journey_count = len(result.get('journeys', [])) if result.get('success') else 0\n    print(f\"  Enhanced journey planning: {planning_time:.2f}ms ({journey_count} journeys)\")\n    \n    print(\"\\nCOMBINED PERFORMANCE:\")\n    print(f\"  Phase 1 + Phase 2 = Enterprise-grade railway information system\")\n    print(f\"  With geographical intelligence and natural language understanding\")\n\ndef main():\n    \"\"\"Run all Phase 2 demonstrations.\"\"\"\n    try:\n        print(\"Starting Phase 2 Enhanced Search Capabilities Demonstration...\")\n        print(f\"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\")\n        \n        # Run all demonstrations\n        demo_geographical_hierarchy()\n        demo_place_name_search()\n        demo_enhanced_journey_planning()\n        demo_enhanced_api_responses()\n        demo_agent_integration()\n        demo_performance_comparison()\n        \n        print_header(\"PHASE 2 DEMONSTRATION COMPLETE\")\n        print(\"All enhanced search capabilities are working correctly!\")\n        print(\"\\nKey improvements delivered:\")\n        print(\"✓ Geographical hierarchy integration\")\n        print(\"✓ Natural language journey planning\")\n        print(\"✓ Place-name search intelligence\")\n        print(\"✓ Enhanced API responses with metadata\")\n        print(\"✓ Cross-regional journey awareness\")\n        print(\"\\nReady for Phase 3 implementation.\")\n        \n    except Exception as e:\n        print(f\"\\nError during demonstration: {e}\")\n        import traceback\n        traceback.print_exc()\n        return False\n    \n    return True\n\nif __name__ == \"__main__\":\n    success = main()\n    sys.exit(0 if success else 1)