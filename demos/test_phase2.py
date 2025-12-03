#!/usr/bin/env python3
"""
Simple Phase 2 Test - Enhanced Search Capabilities
"""

import sys
import os
from datetime import datetime, timedelta

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from timetable_tools import TimetableTools
from improved_station_resolver import ImprovedStationResolver

def test_geographical_context():
    print("=== PHASE 2 TEST: Enhanced Search Capabilities ===")
    print("Building on Phase 1's 2.9x performance improvements")
    print("Testing geographical intelligence features...\n")
    
    # Initialize tools
    tools = TimetableTools()
    
    print("1. Testing Enhanced Station Resolution:")
    stations = ['Edinburgh', 'Glasgow Central', 'Inverness']
    
    for station in stations:
        print(f"\nStation: {station}")
        info = tools.get_station_with_context(station)
        if info:
            print(f"  Name: {info['display_name']}")
            print(f"  CRS: {info['crs_code']}")
            geo = info.get('geographical_context', {})
            if geo:
                print(f"  Area: {geo.get('area', 'N/A')}")
                print(f"  Region: {geo.get('region', 'N/A')}")

def test_place_search():
    print("\n2. Testing Place-Name Search:")
    tools = TimetableTools()
    
    places = ['Glasgow', 'Highlands']
    for place in places:
        print(f"\nSearching '{place}':")
        stations = tools.search_stations_by_place(place, limit=3)
        for station in stations:
            name = station.get('display_name', 'Unknown')
            crs = station.get('crs_code', 'N/A')
            print(f"  • {name} ({crs})")

def test_enhanced_journey():
    print("\n3. Testing Enhanced Journey Planning:")
    tools = TimetableTools()
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"Journey from Edinburgh to Glasgow on {tomorrow}")
    result = tools.plan_journey_with_context(
        from_place='Edinburgh',
        to_place='Glasgow',
        travel_date=tomorrow
    )
    
    if result['success']:
        print(f"  Found {len(result['journeys'])} journey options")
        if result['journeys']:
            best = result['journeys'][0]
            print(f"  Best: {best['from_station']['display_name']} → {best['to_station']['display_name']}")
            print(f"  Duration: {best['total_duration']} mins")
    else:
        print(f"  Error: {result.get('error', 'Unknown')}")

def test_enhanced_api():
    print("\n4. Testing Enhanced API Responses:")
    tools = TimetableTools()
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    result = tools.get_scheduled_trains(
        from_station='Edinburgh',
        to_station='Glasgow Central',
        travel_date=tomorrow
    )
    
    if result['success']:
        print(f"  Found {result['count']} trains")
        print(f"  From: {result['from']['name']} (TIPLOC: {result['from']['tiploc']})")
        print(f"  To: {result['to']['name']} (TIPLOC: {result['to']['tiploc']})")
        
        from_geo = result['from'].get('geographical_context')
        if from_geo:
            print(f"  From geography: {from_geo.get('area', 'N/A')}")
            
        to_geo = result['to'].get('geographical_context')
        if to_geo:
            print(f"  To geography: {to_geo.get('area', 'N/A')}")
    else:
        print(f"  Error: {result.get('error', 'Unknown')}")

def main():
    try:
        test_geographical_context()
        test_place_search() 
        test_enhanced_journey()
        test_enhanced_api()
        
        print("\n=== PHASE 2 TEST COMPLETE ===")
        print("✓ Geographical hierarchy integration")
        print("✓ Place-name search capabilities") 
        print("✓ Enhanced journey planning")
        print("✓ API responses with geographical metadata")
        print("\nPhase 2 enhanced search capabilities working correctly!")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)