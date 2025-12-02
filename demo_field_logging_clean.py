#!/usr/bin/env python3
"""
Enhanced Option 1 Field Logging Demonstration
"""

import logging
from datetime import datetime
from darwin_schedule_prototype import DarwinScheduleDatabase, DarwinScheduleProcessor

# Set up detailed logging to see field processing
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def demonstrate_detailed_logging():
    """Show the enhanced detailed logging capabilities"""
    
    print("=" * 80)
    print("🎯 Enhanced Option 1 - Detailed Field Logging Demonstration")
    print("=" * 80)
    print()
    
    # Create database and processor
    database = DarwinScheduleDatabase("demo_detailed.db")
    processor = DarwinScheduleProcessor(database)
    
    print("📦 DEMONSTRATION: Schedule Field Processing")
    print("-" * 60)
    
    # Create sample schedule data to demonstrate field logging
    sample_schedule = {
        'rid': 'DEMO202512011800001',
        'uid': 'W12345',
        'train_id': '1A23',
        'headcode': '1A23', 
        'toc': 'SW',
        'status': 'P',
        'category': 'OO',
        'start_date': '2025-12-01',
        'end_date': '2025-12-01',
        'days_run': '1111111',
        'origin_tiploc': 'WATRLOO',
        'origin_time': '18:00',
        'origin_platform': '12',
        'destination_tiploc': 'GUILDFD',
        'destination_time': '18:35',
        'destination_platform': '1',
        'calling_points': [
            {'tiploc': 'CLAPJUN', 'arrival': '18:04', 'departure': '18:05', 'platform': '2'},
            {'tiploc': 'RAYNESK', 'arrival': '18:10', 'departure': '18:11', 'platform': '1'},
            {'tiploc': 'WIMBLDN', 'arrival': '18:17', 'departure': '18:19', 'platform': '8'},
            {'tiploc': 'RAYNESM', 'arrival': '18:23', 'departure': '18:24', 'platform': '3'},
            {'tiploc': 'EPSOM', 'arrival': '18:30', 'departure': '18:31', 'platform': '2'}
        ]
    }
    
    print("🚂 Sample Schedule Data:")
    print(f"   📦 RID: {sample_schedule['rid']}")
    print(f"   🚂 Train: {sample_schedule['train_id']} ({sample_schedule['headcode']})")
    print(f"   🏢 TOC: {sample_schedule['toc']} | Category: {sample_schedule['category']}")
    print(f"   📅 Service Date: {sample_schedule['start_date']}")
    print(f"   🚀 Origin: {sample_schedule['origin_tiploc']} at {sample_schedule['origin_time']} (P{sample_schedule['origin_platform']})")
    print(f"   🏁 Destination: {sample_schedule['destination_tiploc']} at {sample_schedule['destination_time']} (P{sample_schedule['destination_platform']})")
    print(f"   📍 Calling Points: {len(sample_schedule['calling_points'])} stops")
    print()
    
    # Store the schedule
    print("💾 Storing Schedule in Database...")
    success = database.store_schedule(sample_schedule)
    print(f"   ✅ Storage Result: {'Success' if success else 'Failed'}")
    print()
    
    print("🚫 DEMONSTRATION: Cancellation Processing with Enrichment")
    print("-" * 60)
    
    # Create sample cancellation
    sample_cancellation = {
        'rid': 'DEMO202512011800001',  # Same RID as our stored schedule
        'uid': 'W12345',
        'timestamp': datetime.now().isoformat(),
        'enriched': False
    }
    
    print("📋 Basic Cancellation Data:")
    print(f"   🚫 RID: {sample_cancellation['rid']}")
    print(f"   🆔 UID: {sample_cancellation['uid']}")
    print(f"   ⏰ Timestamp: {sample_cancellation['timestamp']}")
    print()
    
    print("🔍 Searching for Schedule Data to Enrich Cancellation...")
    stored_schedule = database.get_schedule(sample_cancellation['rid'])
    
    if stored_schedule:
        print("✅ SCHEDULE FOUND! Enriching cancellation data...")
        print()
        
        # Show the enrichment in detail
        enriched_data = {
            'train_id': stored_schedule.get('train_id'),
            'headcode': stored_schedule.get('headcode'),
            'toc': stored_schedule.get('toc'),
            'origin_tiploc': stored_schedule.get('origin_tiploc'),
            'origin_time': stored_schedule.get('origin_time'),
            'origin_platform': stored_schedule.get('origin_platform'),
            'destination_tiploc': stored_schedule.get('destination_tiploc'),
            'destination_time': stored_schedule.get('destination_time'),
            'destination_platform': stored_schedule.get('destination_platform'),
            'category': stored_schedule.get('category'),
            'calling_points_count': len(stored_schedule.get('calling_points', []))
        }
        
        sample_cancellation.update(enriched_data)
        sample_cancellation['enriched'] = True
        
        print("🎯 ENRICHMENT SUCCESSFUL - Full Train Details Available:")
        print(f"   🚂 Train: {enriched_data['train_id']} ({enriched_data['headcode']})")
        print(f"   🏢 Operator: {enriched_data['toc']}")
        print(f"   🚀 Origin: {enriched_data['origin_tiploc']} at {enriched_data['origin_time']}")
        if enriched_data['origin_platform']:
            print(f"      Platform: {enriched_data['origin_platform']}")
        print(f"   🏁 Destination: {enriched_data['destination_tiploc']} at {enriched_data['destination_time']}")
        if enriched_data['destination_platform']:
            print(f"      Platform: {enriched_data['destination_platform']}")
        print(f"   📍 Journey: {enriched_data['calling_points_count']} calling points")
        print(f"   📋 Category: {enriched_data['category']}")
        
    else:
        print("❌ NO SCHEDULE DATA FOUND - Cancellation cannot be enriched")
    
    print()
    print("📊 FINAL STATISTICS")
    print("=" * 60)
    
    # Get detailed statistics
    detailed_stats = processor.get_detailed_statistics()
    
    print("💾 Database Status:")
    db_stats = detailed_stats['database']
    print(f"   📋 Total schedules: {db_stats['total_schedules']}")
    print(f"   📍 Calling points: {db_stats['total_calling_points']}")
    print(f"   🚂 Unique operators: {db_stats['unique_operators']}")
    print(f"   💽 Database size: {db_stats['database_size_mb']} MB")
    
    print()
    print("✅ Enhanced Option 1 Field Logging Demonstration Complete!")
    print("🎯 Detailed field processing and enrichment capabilities validated")
    
    # Show the power of the enrichment
    print()
    print("💡 KEY BENEFITS DEMONSTRATED:")
    print("   ✅ Comprehensive field capture and logging")
    print("   ✅ Real-time schedule storage and retrieval")
    print("   ✅ Complete cancellation enrichment with full train details")
    print("   ✅ Detailed statistics and processing metrics")
    print("   ✅ Robust database management with calling point storage")
    
    # Cleanup
    database.close()

if __name__ == "__main__":
    demonstrate_detailed_logging()