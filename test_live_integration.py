#!/usr/bin/env python3
"""
Test script to verify the live Darwin integration service.
"""

import sys
import time
import logging
from datetime import datetime

# Add current directory to path for imports
sys.path.append('.')

from live_integration import LiveIntegrationService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_live_integration():
    """Test the live Darwin integration service."""
    logger.info("🧪 Testing Live Darwin Integration Service")
    
    try:
        # Initialize the service
        service = LiveIntegrationService()
        
        logger.info("✅ Service initialized successfully")
        logger.info("💡 Note: This will connect to the live Darwin feed")
        
        # Get initial status
        status = service.get_status()
        logger.info("📊 Initial Status:")
        print(f"   Enrichment Enabled: {status['configuration']['enrichment_enabled']}")
        print(f"   Darwin Database: {status['configuration']['darwin_db_path']}")
        print(f"   Max Stored: {status['configuration']['max_stored']}")
        
        # Start the service (this connects to live feed)
        logger.info("🚀 Starting live service (connects to Darwin feed)...")
        service.start()
        
        # Monitor for a short time
        logger.info("📡 Monitoring for 60 seconds...")
        start_time = time.time()
        last_stats_time = start_time
        
        while time.time() - start_time < 60:  # Run for 60 seconds
            time.sleep(5)
            
            # Log status every 20 seconds
            if time.time() - last_stats_time >= 20:
                status = service.get_status()
                logger.info(
                    f"📊 Status: "
                    f"Connected={status['darwin_feed'].get('connected', False)}, "
                    f"Messages={status['darwin_feed'].get('messages_processed', 0)}, "
                    f"Cancellations={status['processing_stats']['cancellations_detected']}"
                )
                last_stats_time = time.time()
        
        # Stop the service
        logger.info("🛑 Stopping service...")
        service.stop()
        
        # Final status
        final_status = service.get_status()
        logger.info("📊 Final Results:")
        print(f"   Messages Processed: {final_status['darwin_feed'].get('messages_processed', 0)}")
        print(f"   Cancellations Detected: {final_status['processing_stats']['cancellations_detected']}")
        print(f"   Cancellations Enriched: {final_status['processing_stats']['cancellations_enriched']}")
        print(f"   Enrichment Rate: {final_status['processing_stats']['enrichment_rate']}%")
        
        # Show recent cancellations
        recent = service.get_recent_enriched_cancellations(5)
        if recent:
            logger.info(f"📋 Recent Cancellations ({len(recent)} found):")
            for i, cancellation in enumerate(recent, 1):
                print(f"\n=== Cancellation {i} ===")
                print(f"RID: {cancellation.get('rid')}")
                print(f"Train: {cancellation.get('train_service_code')}")
                print(f"Reason: {cancellation.get('reason_text')}")
                print(f"Source: {cancellation.get('source')}")
                
                if cancellation.get('darwin_enriched'):
                    print("🎯 DARWIN ENRICHMENT:")
                    print(f"  Train ID: {cancellation.get('train_id_darwin')}")
                    print(f"  TOC: {cancellation.get('toc_darwin')}")
                    print(f"  Origin: {cancellation.get('origin_tiploc_darwin')} at {cancellation.get('origin_time_darwin')}")
                    print(f"  Destination: {cancellation.get('destination_tiploc_darwin')} at {cancellation.get('destination_time_darwin')}")
                else:
                    print("⚪ No Darwin enrichment available")
        else:
            logger.info("📋 No cancellations detected during test period")
        
        logger.info("✅ Live integration test completed successfully!")
        return True
        
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        if 'service' in locals():
            service.stop()
        return False
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        if 'service' in locals():
            try:
                service.stop()
            except:
                pass
        return False


def test_dry_run():
    """Test service initialization without connecting to live feed."""
    logger.info("🧪 Testing Service Initialization (Dry Run)")
    
    try:
        # Initialize the service
        service = LiveIntegrationService()
        
        logger.info("✅ Service components initialized successfully")
        
        # Test with mock cancellation data
        mock_cancellation = {
            'rid': 'DEMO202512011800001',  # Use demo RID
            'train_id': '1A23',
            'uid': '1A23',
            'cancellation_reason': '104',
            'cancellation_type': 'Full',
            'cancellation_datetime': datetime.now().isoformat(),
            'origin_tiploc': 'WATRLOO',
            'toc_id': 'SW',
            'received_at': datetime.now().isoformat()
        }
        
        logger.info("📝 Testing with mock cancellation data...")
        service._handle_cancellation(mock_cancellation)
        
        # Get status
        status = service.get_status()
        logger.info("📊 Results:")
        print(f"   Cancellations Processed: {status['processing_stats']['cancellations_detected']}")
        print(f"   Cancellations Enriched: {status['processing_stats']['cancellations_enriched']}")
        print(f"   Enrichment Rate: {status['processing_stats']['enrichment_rate']}%")
        
        # Show the processed cancellation
        recent = service.get_recent_enriched_cancellations(1)
        if recent:
            cancellation = recent[0]
            logger.info("📋 Processed Cancellation:")
            print(f"   RID: {cancellation.get('rid')}")
            print(f"   Train: {cancellation.get('train_service_code')}")
            print(f"   Enriched: {cancellation.get('darwin_enriched', False)}")
            
            if cancellation.get('darwin_enriched'):
                print(f"   Origin: {cancellation.get('origin_tiploc_darwin')} at {cancellation.get('origin_time_darwin')}")
                print(f"   Destination: {cancellation.get('destination_tiploc_darwin')} at {cancellation.get('destination_time_darwin')}")
        
        logger.info("✅ Dry run test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Dry run test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    logger.info("🚀 Live Darwin Integration Tests")
    
    # First run dry run test
    dry_run_success = test_dry_run()
    
    print("\n" + "="*60 + "\n")
    
    if dry_run_success:
        # Ask user if they want to test live connection
        try:
            response = input("🔴 Do you want to test live Darwin feed connection? (y/N): ").strip().lower()
            if response in ['y', 'yes']:
                live_success = test_live_integration()
                if live_success:
                    logger.info("🎉 All tests passed!")
                else:
                    logger.error("❌ Live test failed")
                    sys.exit(1)
            else:
                logger.info("✅ Dry run test passed. Skipping live test.")
        except (KeyboardInterrupt, EOFError):
            logger.info("Skipping live test.")
    else:
        logger.error("❌ Dry run test failed. Not proceeding with live test.")
        sys.exit(1)