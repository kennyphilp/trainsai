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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('darwin_cancellations.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Run standalone Darwin Push Port test."""
    print("=" * 80)
    print("🚂 Darwin Push Port Standalone Test")
    print("=" * 80)
    print("Connecting to Darwin Push Port STOMP feed...")
    print("This will display messages as they arrive.")
    print("Cancellation details will be logged to 'darwin_cancellations.log'")
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
                
                # Debug: Print XML structure for messages with deactivated elements
                deactivated_elements = root.findall('.//ns:deactivated', ns)
                if deactivated_elements:
                    logger.info(f"Found {len(deactivated_elements)} deactivated elements in message {message_count}")
                    # Print a sample of the XML for debugging
                    xml_str = ET.tostring(root, encoding='unicode')
                    logger.info(f"Sample XML with cancellation: {xml_str[:500]}...")
                
                # Try different approaches to find journey structure
                all_elements = root.findall('.//*')
                journey_like_elements = [elem for elem in all_elements if 'rid' in elem.attrib or 'uid' in elem.attrib]
                
                if deactivated_elements:
                    logger.info(f"Found {len(journey_like_elements)} elements with rid/uid attributes")
                    for elem in journey_like_elements[:3]:  # Show first 3
                        logger.info(f"Element: {elem.tag}, attrib: {elem.attrib}")
                
                # Original logic - look for deactivated in journeys
                journeys = root.findall('.//ns:journey', ns)
                if deactivated_elements and not journeys:
                    logger.info("Found deactivated elements but no journey elements - checking alternative structures")
                    
                    # Try finding schedule elements instead
                    schedules = root.findall('.//ns:schedule', ns)
                    logger.info(f"Found {len(schedules)} schedule elements")
                    
                    # Try finding train status elements
                    ts_elements = root.findall('.//ns:TS', ns)
                    logger.info(f"Found {len(ts_elements)} TS (train status) elements")
                
                for journey in journeys:
                    deactivated = journey.findall('.//ns:deactivated', ns)
                    
                    if deactivated:
                        for d in deactivated:
                            cancellation_count += 1
                            rid = d.get('rid', 'UNKNOWN')
                            uid = d.get('uid', 'UNKNOWN')
                            
                            # Get journey details since we already have the parent
                            toc = journey.get('toc', 'UNKNOWN')
                            train_id = journey.get('trainId', 'UNKNOWN')
                            ssd = journey.get('ssd', 'UNKNOWN')
                            
                            # Try to find origin and destination
                            or_elem = journey.find('.//ns:OR', ns)
                            dt_elem = journey.find('.//ns:DT', ns)
                            
                            origin_tiploc = or_elem.get('tpl', 'UNKNOWN') if or_elem is not None else 'UNKNOWN'
                            dest_tiploc = dt_elem.get('tpl', 'UNKNOWN') if dt_elem is not None else 'UNKNOWN'
                            
                            # Get working departure time if available
                            wd = or_elem.get('wd', 'UNKNOWN') if or_elem is not None else 'UNKNOWN'
                            wtd = or_elem.get('wtd', 'UNKNOWN') if or_elem is not None else 'UNKNOWN'
                            
                            # Log comprehensive cancellation information
                            logger.info(f"CANCELLATION_DETECTED|{cancellation_count}|{rid}|{uid}|{train_id}|{toc}|{ssd}|{origin_tiploc}|{dest_tiploc}|{wd}|{wtd}|{time.strftime('%Y-%m-%d %H:%M:%S')}")
                            
                            # Also print to console for visibility
                            print(f"\n🚫 CANCELLATION #{cancellation_count}:")
                            print(f"   RID (Route Identifier): {rid}")
                            print(f"   UID (Unique Identifier): {uid}")
                            print(f"   Train ID (Service Identifier): {train_id}")
                            print(f"   TOC (Train Operating Company): {toc}")
                            print(f"   Start Date (Scheduled): {ssd}")
                            print(f"   Origin (TIPLOC): {origin_tiploc}")
                            print(f"   Destination (TIPLOC): {dest_tiploc}")
                            print(f"   Scheduled Departure: {wd}")
                            print(f"   Working Departure: {wtd}")
                            print(f"   Detection Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                            print("-" * 50)
                
                # Alternative approach: Look for deactivated elements directly and find their context
                if deactivated_elements and not any(journey.findall('.//ns:deactivated', ns) for journey in journeys):
                    logger.info(f"Processing {len(deactivated_elements)} deactivated elements outside journey structure")
                    
                    for d in deactivated_elements:
                        cancellation_count += 1
                        rid = d.get('rid', 'UNKNOWN')
                        uid = d.get('uid', 'UNKNOWN')
                        
                        # Try to find parent element with more details
                        # Since we can't use getparent(), look for elements with same rid/uid
                        matching_elements = []
                        for elem in all_elements:
                            if elem.attrib.get('rid') == rid or elem.attrib.get('uid') == uid:
                                matching_elements.append(elem)
                        
                        toc = 'UNKNOWN'
                        train_id = 'UNKNOWN'
                        ssd = 'UNKNOWN'
                        
                        # Extract info from matching elements
                        for elem in matching_elements:
                            if 'toc' in elem.attrib:
                                toc = elem.attrib['toc']
                            if 'trainId' in elem.attrib:
                                train_id = elem.attrib['trainId']
                            if 'ssd' in elem.attrib:
                                ssd = elem.attrib['ssd']
                        
                        # Log comprehensive cancellation information
                        logger.info(f"CANCELLATION_DETECTED|{cancellation_count}|{rid}|{uid}|{train_id}|{toc}|{ssd}|UNKNOWN|UNKNOWN|UNKNOWN|UNKNOWN|{time.strftime('%Y-%m-%d %H:%M:%S')}")
                        
                        # Also print to console for visibility
                        print(f"\n🚫 CANCELLATION #{cancellation_count} (Alternative Detection):")
                        print(f"   RID (Route Identifier): {rid}")
                        print(f"   UID (Unique Identifier): {uid}")
                        print(f"   Train ID (Service Identifier): {train_id}")
                        print(f"   TOC (Train Operating Company): {toc}")
                        print(f"   Start Date (Scheduled): {ssd}")
                        print(f"   Detection Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                        print("-" * 50)
                
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
