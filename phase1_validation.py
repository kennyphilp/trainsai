#!/usr/bin/env python3
"""
Phase 1 Validation Script
Validates that all live services are operational and performing correctly
"""

import requests
import json
import time
import sys
from datetime import datetime

def test_api_endpoint(url, description):
    """Test an API endpoint and return status"""
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print(f"✅ {description}: OK")
            return True, response.json()
        else:
            print(f"❌ {description}: HTTP {response.status_code}")
            return False, None
    except requests.exceptions.RequestException as e:
        print(f"❌ {description}: Connection failed - {e}")
        return False, None

def validate_phase1():
    """Validate Phase 1 operational launch"""
    
    print("🚀 PHASE 1 VALIDATION - OPERATIONAL LAUNCH")
    print("=" * 50)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    base_url = "http://localhost:8080"
    
    # Test API endpoints
    tests = [
        (f"{base_url}/cancellations/stats", "Service Statistics"),
        (f"{base_url}/cancellations", "Recent Cancellations"),
        (f"{base_url}/cancellations/by-route", "Route Analytics"),
    ]
    
    results = {}
    
    print("📡 Testing API Endpoints:")
    print("-" * 25)
    
    for url, description in tests:
        success, data = test_api_endpoint(url, description)
        results[description] = {"success": success, "data": data}
        time.sleep(0.5)
    
    print()
    
    # Analyze statistics if available
    if results["Service Statistics"]["success"]:
        stats = results["Service Statistics"]["data"]
        print("📊 Live Service Performance:")
        print("-" * 30)
        print(f"Total Cancellations Processed: {stats.get('total_cancellations', 'N/A')}")
        print(f"Enriched Cancellations: {stats.get('enriched_cancellations', 'N/A')}")
        print(f"Enrichment Success Rate: {stats.get('enrichment_rate', 'N/A')}%")
        print(f"Service Uptime: {stats.get('uptime_seconds', 'N/A')} seconds")
        
        # Check if we're processing live data
        total_cancellations = stats.get('total_cancellations', 0)
        if total_cancellations > 0:
            print("✅ Live data processing: ACTIVE")
        else:
            print("⚠️  Live data processing: No cancellations yet")
        
        print()
    
    # Test cancellations data
    if results["Recent Cancellations"]["success"]:
        cancellations = results["Recent Cancellations"]["data"]
        print("🚂 Recent Cancellations Sample:")
        print("-" * 30)
        if cancellations:
            latest = cancellations[0]
            print(f"Latest RID: {latest.get('rid', 'N/A')}")
            print(f"Enriched: {'Yes' if latest.get('darwin_enriched') else 'No'}")
            print(f"Timestamp: {latest.get('timestamp', 'N/A')}")
            
            # Count enriched vs non-enriched
            enriched_count = sum(1 for c in cancellations if c.get('darwin_enriched'))
            total_count = len(cancellations)
            live_enrichment_rate = (enriched_count / total_count * 100) if total_count > 0 else 0
            print(f"Live Enrichment Rate: {live_enrichment_rate:.1f}% ({enriched_count}/{total_count})")
        else:
            print("No cancellations data available yet")
        print()
    
    # Overall assessment
    successful_tests = sum(1 for test in results.values() if test["success"])
    total_tests = len(results)
    
    print("🎯 Phase 1 Assessment:")
    print("-" * 20)
    print(f"API Endpoint Tests: {successful_tests}/{total_tests} passed")
    
    if successful_tests == total_tests:
        print("✅ Phase 1 OPERATIONAL LAUNCH: SUCCESS")
        print("🎉 All live services are running and responding correctly!")
        return True
    else:
        print("❌ Phase 1 OPERATIONAL LAUNCH: ISSUES DETECTED")
        print("⚠️  Some services are not responding correctly")
        return False

def continuous_monitoring(duration_minutes=5):
    """Run continuous monitoring for specified duration"""
    print(f"\n🔄 Running continuous monitoring for {duration_minutes} minutes...")
    print("Press Ctrl+C to stop early")
    print()
    
    start_time = time.time()
    end_time = start_time + (duration_minutes * 60)
    
    try:
        while time.time() < end_time:
            success, stats = test_api_endpoint("http://localhost:8080/cancellations/stats", "Stats Check")
            if success:
                cancellations = stats.get('total_cancellations', 0)
                enriched = stats.get('enriched_cancellations', 0)
                rate = stats.get('enrichment_rate', 0)
                uptime = stats.get('uptime_seconds', 0)
                
                remaining = int((end_time - time.time()) / 60)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                      f"Cancellations: {cancellations}, Enriched: {enriched} ({rate}%), "
                      f"Uptime: {uptime}s, Remaining: {remaining}m")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Service check failed")
            
            time.sleep(30)  # Check every 30 seconds
            
    except KeyboardInterrupt:
        print("\n⏹️  Monitoring stopped by user")
    
    print("✅ Continuous monitoring completed")

if __name__ == "__main__":
    success = validate_phase1()
    
    if success and len(sys.argv) > 1 and sys.argv[1] == "--monitor":
        continuous_monitoring()
    
    sys.exit(0 if success else 1)