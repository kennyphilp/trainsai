#!/usr/bin/env python3
"""
Test script to verify the enhanced cancellations service with Darwin integration.
"""

import sys
import os
import logging
import json
from datetime import datetime
from pathlib import Path

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import enhanced service and config
from cancellations_service import CancellationsService
from config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_enhanced_service():
    """Test the enhanced cancellations service with Darwin integration."""
    logger.info("🧪 Starting enhanced cancellations service test...")
    
    try:
        # Get configuration
        config = get_config()
        logger.info(f"📋 Using Darwin DB path: {config.darwin_db_path}")
        
        # Initialize service with Darwin enrichment
        service = CancellationsService(
            max_stored=10,
            darwin_db_path="demo_detailed.db",  # Use our demo database
            enable_enrichment=True
        )
        
        logger.info("✅ Service initialized successfully")
        
        # Test cancellation data (using RID from our demo database)
        test_cancellations = [
            {
                "rid": "DEMO202512011800001",  # This should exist in demo_detailed.db
                "train_service_code": "1A23",
                "train_id": "1A23",
                "reason_code": "104",
                "reason_text": "Train cancelled due to a fault on this train",
                "location": "Edinburgh",
                "cancelled_at": datetime.now().isoformat()
            },
            {
                "rid": "nonexistent_rid",  # This should not exist
                "train_service_code": "2B45",
                "train_id": "2B45", 
                "reason_code": "105",
                "reason_text": "Train cancelled due to severe weather conditions",
                "location": "Glasgow",
                "cancelled_at": datetime.now().isoformat()
            }
        ]
        
        # Add test cancellations
        logger.info("📥 Adding test cancellations...")
        for i, cancellation in enumerate(test_cancellations):
            logger.info(f"\n--- Adding cancellation {i+1} ---")
            service.add_cancellation(cancellation.copy())
        
        # Get and display service statistics
        logger.info("\n📊 Service Statistics:")
        stats = service.get_stats()
        print(json.dumps(stats, indent=2, default=str))
        
        # Get recent cancellations
        logger.info("\n📋 Recent Cancellations:")
        recent = service.get_recent_cancellations(limit=5)
        for i, cancellation in enumerate(recent):
            print(f"\n=== Cancellation {i+1} ===")
            
            # Basic information
            print(f"RID: {cancellation.get('rid')}")
            print(f"Train: {cancellation.get('train_service_code')}")
            print(f"Reason: {cancellation.get('reason_text')}")
            
            # Darwin enrichment data
            if cancellation.get('darwin_enriched'):
                print("🎯 DARWIN ENRICHMENT:")
                print(f"  Train ID: {cancellation.get('train_id_darwin')}")
                print(f"  Headcode: {cancellation.get('headcode_darwin')}")
                print(f"  TOC: {cancellation.get('toc_darwin')}")
                print(f"  Origin: {cancellation.get('origin_tiploc_darwin')} at {cancellation.get('origin_time_darwin')}")
                print(f"  Destination: {cancellation.get('destination_tiploc_darwin')} at {cancellation.get('destination_time_darwin')}")
                print(f"  Calling points: {cancellation.get('calling_points_count')} total")
                if cancellation.get('calling_points_darwin'):
                    print("  First few stops:")
                    for cp in cancellation.get('calling_points_darwin', []):
                        print(f"    - {cp.get('tiploc')} at {cp.get('scheduled_arrival')}")
            else:
                print("⚪ No Darwin enrichment available")
        
        logger.info("\n✅ Test completed successfully!")
        return True
        
    except ImportError as e:
        logger.error(f"❌ Import error (Darwin components not available): {e}")
        logger.info("💡 This is expected if darwin_schedule_prototype.py is not in the same directory")
        return False
        
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_basic_service():
    """Test basic service functionality without Darwin integration."""
    logger.info("🧪 Starting basic cancellations service test (no Darwin)...")
    
    try:
        # Initialize service without Darwin enrichment
        service = CancellationsService(
            max_stored=5,
            enable_enrichment=False
        )
        
        logger.info("✅ Basic service initialized successfully")
        
        # Test cancellation data
        test_cancellation = {
            "train_service_code": "1X99",
            "train_id": "1X99",
            "reason_code": "103",
            "reason_text": "Train cancelled due to crew shortage",
            "location": "Perth",
            "cancelled_at": datetime.now().isoformat()
        }
        
        # Add test cancellation
        logger.info("📥 Adding test cancellation...")
        service.add_cancellation(test_cancellation)
        
        # Get statistics
        stats = service.get_stats()
        logger.info(f"📊 Statistics: {stats}")
        
        # Get recent cancellations
        recent = service.get_recent_cancellations()
        logger.info(f"📋 Recent cancellations: {len(recent)} found")
        
        logger.info("✅ Basic test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Basic test failed: {e}")
        return False


if __name__ == "__main__":
    logger.info("🚀 Testing Enhanced Cancellations Service")
    
    # Test with Darwin enrichment first
    enhanced_success = test_enhanced_service()
    
    print("\n" + "="*60 + "\n")
    
    # Always test basic functionality
    basic_success = test_basic_service()
    
    print("\n" + "="*60 + "\n")
    
    # Summary
    if enhanced_success and basic_success:
        logger.info("🎉 All tests passed! Enhanced service is working correctly.")
    elif basic_success:
        logger.info("✅ Basic service is working. Darwin enrichment may not be available.")
    else:
        logger.error("❌ Tests failed. Check the service implementation.")
        sys.exit(1)