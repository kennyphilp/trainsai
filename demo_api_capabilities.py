#!/usr/bin/env python3
"""
Demo script showing the enhanced API capabilities with enriched cancellation data.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Add current directory to path
sys.path.append('.')

from live_integration import LiveIntegrationService


def demo_enhanced_api():
    """Demonstrate the enhanced API capabilities."""
    print("🚀 Enhanced Cancellations API Demo")
    print("=" * 50)
    
    try:
        # Initialize the live service
        print("\n📋 Initializing service...")
        service = LiveIntegrationService()
        print("✅ Service initialized successfully")
        
        # Add test cancellations
        print("\n📝 Adding demo cancellation data...")
        test_cancellations = [
            {
                'rid': 'DEMO202512011800001',  # This will be enriched
                'train_id': '1A23',
                'uid': '1A23',
                'cancellation_reason': '104',
                'cancellation_type': 'Full',
                'cancellation_datetime': datetime.now().isoformat(),
                'origin_tiploc': 'WATRLOO',
                'destination_tiploc': 'GUILDFD',
                'toc_id': 'SW',
                'received_at': datetime.now().isoformat()
            },
            {
                'rid': 'UNKNOWN_RID_001',  # This won't be enriched
                'train_id': '2B45',
                'uid': '2B45', 
                'cancellation_reason': '105',
                'cancellation_type': 'Partial',
                'cancellation_datetime': datetime.now().isoformat(),
                'origin_tiploc': 'GLASGOW',
                'destination_tiploc': 'EDINBUR',
                'toc_id': 'SR',
                'received_at': datetime.now().isoformat()
            },
            {
                'rid': 'UNKNOWN_RID_002',  # This won't be enriched
                'train_id': '3C67',
                'uid': '3C67',
                'cancellation_reason': '106', 
                'cancellation_type': 'Full',
                'cancellation_datetime': datetime.now().isoformat(),
                'origin_tiploc': 'ABERDEEN',
                'destination_tiploc': 'INVERNESS',
                'toc_id': 'SR',
                'received_at': datetime.now().isoformat()
            }
        ]
        
        for i, cancellation in enumerate(test_cancellations, 1):
            service._handle_cancellation(cancellation)
            print(f"   ✅ Added cancellation {i}: Train {cancellation['train_id']}")
        
        print(f"\n📊 Added {len(test_cancellations)} test cancellations")
        
        # Demonstrate API endpoint responses
        print("\n🔗 API Endpoint Demonstrations:")
        print("-" * 40)
        
        # 1. GET /cancellations
        print("\n1️⃣  GET /cancellations (All recent cancellations)")
        cancellations = service.get_recent_enriched_cancellations(10)
        
        response = {
            'status': 'success',
            'count': len(cancellations),
            'cancellations': cancellations,
            'enrichment_summary': get_enrichment_summary(cancellations)
        }
        
        print("   📋 Response preview:")
        print(f"     Total cancellations: {response['count']}")
        print(f"     Enriched: {response['enrichment_summary']['enriched']}")
        print(f"     Enrichment rate: {response['enrichment_summary']['enrichment_rate']}%")
        
        # 2. GET /cancellations/enriched
        print("\n2️⃣  GET /cancellations/enriched (Only enriched cancellations)")
        enriched_only = [c for c in cancellations if c.get('darwin_enriched', False)]
        
        print("   📋 Enriched cancellations found:")
        for c in enriched_only:
            print(f"     🎯 Train {c['train_service_code']}: {c.get('origin_tiploc_darwin')} → {c.get('destination_tiploc_darwin')}")
            print(f"        Platform: {c.get('origin_platform_darwin')} → {c.get('destination_platform_darwin')}")
            print(f"        Time: {c.get('origin_time_darwin')} → {c.get('destination_time_darwin')}")
            print(f"        TOC: {c.get('toc_darwin')}")
        
        # 3. GET /cancellations/stats
        print("\n3️⃣  GET /cancellations/stats (Service statistics)")
        status = service.get_status()
        
        print("   📊 Service Statistics:")
        print(f"     Enrichment enabled: {status['configuration']['enrichment_enabled']}")
        print(f"     Total detected: {status['processing_stats']['cancellations_detected']}")
        print(f"     Total enriched: {status['processing_stats']['cancellations_enriched']}")
        print(f"     Success rate: {status['processing_stats']['enrichment_rate']}%")
        
        # 4. GET /cancellations/by-route
        print("\n4️⃣  GET /cancellations/by-route (Route analysis)")
        routes = {}
        for c in cancellations:
            if c.get('darwin_enriched'):
                origin = c.get('origin_tiploc_darwin', 'Unknown')
                destination = c.get('destination_tiploc_darwin', 'Unknown')
                route = f"{origin} → {destination}"
                
                if route not in routes:
                    routes[route] = {'count': 0, 'cancellations': []}
                
                routes[route]['count'] += 1
                routes[route]['cancellations'].append({
                    'train': c.get('train_service_code'),
                    'reason': c.get('reason_text'),
                    'platform_origin': c.get('origin_platform_darwin'),
                    'platform_destination': c.get('destination_platform_darwin')
                })
        
        print("   📈 Route Analysis:")
        if routes:
            for route, data in routes.items():
                print(f"     {route}: {data['count']} cancellation(s)")
                for cancel in data['cancellations']:
                    print(f"       - Train {cancel['train']}: {cancel['reason']}")
        else:
            print("     No enriched route data available")
        
        # 5. Dashboard data structure
        print("\n5️⃣  Dashboard Data Structure")
        print("   🎯 Dashboard would display:")
        print(f"     - Total Cancellations: {status['processing_stats']['cancellations_detected']}")
        print(f"     - Enriched Cancellations: {status['processing_stats']['cancellations_enriched']}")
        print(f"     - Enrichment Rate: {status['processing_stats']['enrichment_rate']}%")
        print(f"     - Service Status: Running")
        
        print("\n✅ API Demo completed successfully!")
        print("\nTo start the full API server:")
        print("   python enhanced_api.py")
        print("\nAPI endpoints available:")
        print("   🌐 http://localhost:5001/cancellations/dashboard")
        print("   🔗 http://localhost:5001/cancellations")
        print("   📊 http://localhost:5001/cancellations/stats")
        print("   📈 http://localhost:5001/cancellations/by-route")
        
        return True
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_enrichment_summary(cancellations):
    """Generate enrichment summary for a list of cancellations."""
    total = len(cancellations)
    if total == 0:
        return {'total': 0, 'enriched': 0, 'basic': 0, 'enrichment_rate': 0}
    
    enriched = sum(1 for c in cancellations if c.get('darwin_enriched', False))
    basic = total - enriched
    rate = round((enriched / total) * 100, 1) if total > 0 else 0
    
    return {
        'total': total,
        'enriched': enriched,
        'basic': basic,
        'enrichment_rate': rate
    }


if __name__ == "__main__":
    demo_enhanced_api()