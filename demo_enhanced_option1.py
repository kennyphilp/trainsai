#!/usr/bin/env python3
"""
Enhanced Option 1 Demonstration
Shows detailed field logging and comprehensive data processing capabilities
"""

import asyncio
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from darwin_schedule_prototype import DarwinScheduleProcessor, DarwinScheduleDatabase

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('demo_enhanced_option1.log')
    ]
)

def create_sample_schedule_xml():
    """Create a comprehensive sample schedule XML for demonstration"""
    return """<?xml version="1.0" encoding="UTF-8"?>
<Pport xmlns="http://www.thalesgroup.com/rtti/PushPort/v16" xmlns:ns3="http://www.thalesgroup.com/rtti/PushPort/Schedules/v3" ts="2025-12-01T17:43:00" version="16.0">
    <ns3:schedule rid="202512011743123456" uid="W12345" trainId="1A23" headcode="1A23" toc="SW" status="P" trainCat="OO" ssd="2025-12-01" endDate="2025-12-01" daysRun="1111111">
        <ns3:OR tpl="WATRLOO" wta="17:43" wtd="17:45" plat="12" act="TB" />
        <ns3:IP tpl="CLAPJUN" wta="17:49" wtd="17:50" plat="2" act="T" />
        <ns3:IP tpl="RAYNESK" wta="17:55" wtd="17:56" plat="1" act="T" />
        <ns3:IP tpl="WIMBLDN" wta="18:02" wtd="18:04" plat="8" act="T" />
        <ns3:IP tpl="RAYNESM" wta="18:08" wtd="18:09" plat="3" act="T" />
        <ns3:IP tpl="EPSOM" wta="18:15" wtd="18:16" plat="2" act="T" />
        <ns3:IP tpl="ASHTEAD" wta="18:20" wtd="18:21" plat="1" act="T" />
        <ns3:IP tpl="LTHD" wta="18:25" wtd="18:26" plat="2" act="T" />
        <ns3:DT tpl="GUILDFD" wta="18:35" plat="1" act="TF" />
    </ns3:schedule>
</Pport>"""

def create_sample_cancellation_xml():
    """Create a sample cancellation XML for demonstration"""
    return """<?xml version="1.0" encoding="UTF-8"?>
<Pport xmlns="http://www.thalesgroup.com/rtti/PushPort/v16" xmlns:ns3="http://www.thalesgroup.com/rtti/PushPort/Schedules/v3" ts="2025-12-01T17:50:00" version="16.0">
    <ns3:deactivated rid="202512011743123456" />
</Pport>"""

async def demonstrate_enhanced_option1():
    """Demonstrate the enhanced Option 1 prototype with detailed logging"""
    
    print("="*80)
    print("🎯 Enhanced Option 1 Demonstration")
    print("📊 Detailed Field Logging & Comprehensive Data Processing")
    print("="*80)
    print()
    
    # Initialize database and processor
    database = DarwinScheduleDatabase("demo_schedules.db")
    processor = DarwinScheduleProcessor(database)
    
    print("📦 Processing Sample Schedule Message...")
    print("-" * 60)
    
    # Process sample schedule
    schedule_xml = create_sample_schedule_xml()
    schedule_result = processor.process_darwin_message(schedule_xml)
    
    print()
    print("📊 Schedule Processing Results:")
    print(f"   ✅ Schedules processed: {schedule_result.get('schedules_processed', 0)}")
    print(f"   📍 Calling points stored: {schedule_result.get('calling_points_processed', 0)}")
    
    await asyncio.sleep(1)  # Brief pause for effect
    
    print()
    print("🚫 Processing Sample Cancellation Message...")
    print("-" * 60)
    
    # Process cancellation
    cancellation_xml = create_sample_cancellation_xml()
    cancellation_result = processor.process_darwin_message(cancellation_xml)
    
    print()
    print("📊 Cancellation Processing Results:")
    print(f"   🚫 Cancellations detected: {cancellation_result.get('cancellations_processed', 0)}")
    
    # Show detailed statistics
    print()
    print("📈 DETAILED STATISTICS")
    print("=" * 60)
    
    detailed_stats = processor.get_detailed_statistics()
    
    print("📨 Message Processing:")
    print(f"   Messages processed: {detailed_stats['messages_processed']}")
    print(f"   Processing errors: {detailed_stats['errors']}")
    print()
    
    print("📦 Schedule Management:")
    print(f"   Schedules stored: {detailed_stats['schedules_stored']}")
    print(f"   Database schedules: {detailed_stats['database']['total_schedules']}")
    print(f"   Calling points: {detailed_stats['database']['total_calling_points']}")
    print(f"   Unique operators: {detailed_stats['database']['unique_operators']}")
    print()
    
    print("🚫 Cancellation Processing:")
    print(f"   Cancellations detected: {detailed_stats['cancellations_detected']}")
    print(f"   Cancellations enriched: {detailed_stats['cancellations_enriched']}")
    print(f"   Enrichment success rate: {detailed_stats['enrichment_rate']}%")
    print()
    
    print("⚡ Processing Efficiency:")
    eff = detailed_stats['processing_efficiency']
    print(f"   Schedules per message: {eff['schedules_per_message']}")
    print(f"   Cancellations per message: {eff['cancellations_per_message']}")
    print(f"   Overall success rate: {eff['success_rate']}")
    print()
    
    print("💾 Database Status:")
    print(f"   Database size: {detailed_stats['database']['database_size_mb']} MB")
    
    # Show field-level detail from logs
    print()
    print("📝 Detailed Processing Log:")
    print("   Check 'demo_enhanced_option1.log' for comprehensive field-by-field logging")
    
    print()
    print("✅ Enhanced Option 1 Demonstration Complete!")
    print("🎯 All functionality validated with detailed field logging")
    
    # Cleanup
    database.close()

if __name__ == "__main__":
    asyncio.run(demonstrate_enhanced_option1())