#!/usr/bin/env python3
"""
Test script for Darwin Push Port STOMP client.

This script connects to the Darwin Push Port feed and prints
Scottish train cancellations as they arrive. Useful for verifying the
connection and data flow.

Usage:
    python test_train_movements.py
    
Press Ctrl+C to stop.
"""

import logging
import time
import sys
from datetime import datetime

from dependencies import get_container

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def print_cancellation(cancellation):
    """Print a formatted cancellation message."""
    print("\n" + "="*80)
    print("🚫 SCOTTISH TRAIN CANCELLATION DETECTED")
    print("="*80)
    print(f"RID:               {cancellation.get('rid')}")
    print(f"UID:               {cancellation.get('uid')}")
    print(f"Train ID:          {cancellation.get('train_id')}")
    print(f"TOC:               {cancellation.get('toc_id')}")
    print(f"Start Date:        {cancellation.get('scheduled_start_date')}")
    print(f"Cancellation Type: {cancellation.get('cancellation_type')}")
    print(f"Cancel Reason:     {cancellation.get('cancellation_reason')}")
    print(f"Origin TIPLOC:     {cancellation.get('origin_tiploc')}")
    print(f"Dest TIPLOC:       {cancellation.get('destination_tiploc')}")
    print(f"Scheduled Dep:     {cancellation.get('origin_departure_scheduled')}")
    print(f"Working Dep:       {cancellation.get('origin_departure_working')}")
    if cancellation.get('cancelled_location_count'):
        print(f"Cancelled Locs:    {cancellation.get('cancelled_location_count')}")
    print("="*80)


def main():
    """Main test function."""
    print("\n" + "="*80)
    print("🚂 ScotRail Darwin Push Port Test Client")
    print("="*80)
    print("Connecting to Darwin Push Port STOMP feed...")
    print("This will display Scottish train cancellations as they arrive.")
    print("Press Ctrl+C to stop.\n")
    
    try:
        # Get the container and services
        container = get_container()
        cancellations_service = container.get_cancellations_service()
        train_movements_client = container.get_train_movements_client()
        
        print("✅ Services initialized successfully")
        print(f"   - CancellationsService: max_stored={cancellations_service.max_stored}")
        print(f"   - TrainMovementsClient: Starting...\n")
        
        # Wait for connection
        time.sleep(2)
        
        # Print initial status
        client_stats = train_movements_client.get_stats()
        service_stats = cancellations_service.get_stats()
        
        print("📊 Initial Status:")
        print(f"   - Client connected: {client_stats['connected']}")
        print(f"   - Client running: {client_stats['running']}")
        print(f"   - Messages processed: {client_stats['messages_processed']}")
        print(f"   - Cancellations detected: {client_stats['cancellations_detected']}")
        print(f"   - Stored cancellations: {service_stats['stored_count']}/{service_stats['max_stored']}")
        print("\n⏳ Waiting for cancellation messages...\n")
        
        # Keep track of last count to detect new cancellations
        last_count = 0
        
        # Main loop - print stats and new cancellations
        while True:
            time.sleep(5)  # Check every 5 seconds
            
            # Get current stats
            client_stats = train_movements_client.get_stats()
            service_stats = cancellations_service.get_stats()
            
            # Print periodic status
            print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                  f"Messages: {client_stats['messages_processed']}, "
                  f"Cancellations: {client_stats['cancellations_detected']}, "
                  f"Stored: {service_stats['stored_count']}")
            
            # Check for new cancellations
            current_count = service_stats['stored_count']
            if current_count > last_count:
                # Print the newest cancellations
                recent = cancellations_service.get_recent_cancellations(limit=1)
                if recent:
                    print_cancellation(recent[0])
                last_count = current_count
    
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopping...")
    except Exception as e:
        logger.error(f"Error in test client: {e}", exc_info=True)
        return 1
    finally:
        # Cleanup
        print("\n🧹 Cleaning up...")
        container = get_container()
        
        # Get final stats
        if hasattr(container, '_train_movements_client') and container._train_movements_client:
            client_stats = container._train_movements_client.get_stats()
            print("\n📊 Final Statistics:")
            print(f"   - Total messages processed: {client_stats['messages_processed']}")
            print(f"   - Total cancellations detected: {client_stats['cancellations_detected']}")
        
        if hasattr(container, '_cancellations_service') and container._cancellations_service:
            service_stats = container._cancellations_service.get_stats()
            print(f"   - Cancellations stored: {service_stats['stored_count']}")
            print(f"   - Total received: {service_stats['total_received']}")
        
        # Stop the client
        container.reset()
        print("\n✅ Cleanup complete. Goodbye!\n")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
