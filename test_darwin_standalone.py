#!/usr/bin/env python3
"""
Standalone test for Darwin Push Port client.
Tests connection and message reception without dependencies.
"""

import logging
import time
import signal
import sys
import gzip
import xml.etree.ElementTree as ET

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    """Run standalone Darwin Push Port test."""
    print("=" * 80)
    print("🚂 Darwin Push Port Standalone Test")
    print("=" * 80)
    print("Connecting to Darwin Push Port STOMP feed...")
    print("This will display messages as they arrive.")
    print("Press Ctrl+C to stop.")
    print()
    
    # Import stomp
    try:
        import stomp
    except ImportError:
        logger.error("stomp.py not installed. Run: pip install stomp.py")
        return 1
    
    # Darwin configuration
    host = "darwin-dist-44ae45.nationalrail.co.uk"
    port = 61613
    username = "DARWINc7af8eb3-ad92-4869-8682-af701f2ce953"
    password = "022d5ca4-c7b3-4190-a64e-a679c211f3eb"
    topic = "/topic/darwin.pushport-v16"
    
    # Stats tracking
    message_count = 0
    cancellation_count = 0
    error_count = 0
    
    # STOMP Listener
    class TestListener(stomp.ConnectionListener):
        def on_connected(self, frame):
            logger.info("✅ Connected to Darwin Push Port feed")
        
        def on_disconnected(self):
            logger.warning("⚠️  Disconnected from Darwin Push Port feed")
        
        def on_error(self, frame):
            nonlocal error_count
            error_count += 1
            logger.error(f"STOMP error: {frame.body}")
        
        def on_message(self, frame):
            nonlocal message_count, cancellation_count
            
            try:
                message_count += 1
                
                # Decompress gzipped message
                body = frame.body
                decompressed = gzip.decompress(body)
                
                # Parse XML
                root = ET.fromstring(decompressed)
                
                # Look for cancellations (deactivated schedules)
                ns = {'ns': 'http://www.thalesgroup.com/rtti/PushPort/v16'}
                deactivated = root.findall('.//ns:deactivated', ns)
                
                if deactivated:
                    for d in deactivated:
                        cancellation_count += 1
                        rid = d.get('rid', 'UNKNOWN')
                        logger.info(f"🚫 Cancellation detected: RID={rid}")
                
                # Show progress every 100 messages
                if message_count % 100 == 0:
                    logger.info(f"📊 Processed {message_count} messages ({cancellation_count} cancellations)")
            
            except Exception as e:
                nonlocal error_count
                error_count += 1
                if error_count <= 3:  # Only show first 3 errors
                    logger.error(f"Error processing message: {e}")
    
    # Create connection
    listener = TestListener()
    
    # Client ID MUST start with username for Darwin
    client_id = f"{username}-standalone-{int(time.time())}"
    
    conn = stomp.Connection(
        [(host, port)],
        heartbeats=(15000, 15000),
        auto_decode=False  # Keep binary data as bytes
    )
    conn.set_listener('darwin', listener)
    
    # Setup signal handler
    def signal_handler(sig, frame):
        print("\n\n🧹 Shutting down...")
        if conn.is_connected():
            conn.disconnect()
        
        print(f"\n📊 Final Statistics:")
        print(f"   - Messages processed: {message_count}")
        print(f"   - Cancellations detected: {cancellation_count}")
        print(f"   - Errors: {error_count}")
        print("\n✅ Shutdown complete. Goodbye!")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Connect and subscribe
    try:
        logger.info(f"Connecting to {host}:{port}...")
        conn.connect(
            username,
            password,
            wait=True,
            headers={'client-id': client_id}
        )
        
        # Subscribe to topic with durable subscription
        conn.subscribe(
            destination=topic,
            id=1,
            ack='auto',
            headers={'activemq.subscriptionName': client_id}
        )
        
        logger.info(f"✅ Subscribed to {topic}")
        
        # Keep running
        start_time = time.time()
        while True:
            time.sleep(10)
            elapsed = int(time.time() - start_time)
            rate = message_count / elapsed if elapsed > 0 else 0
            print(f"\n⏱️  Running for {elapsed}s - {message_count} messages ({rate:.1f}/s), {cancellation_count} cancellations")
    
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1
    finally:
        if conn.is_connected():
            conn.disconnect()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
