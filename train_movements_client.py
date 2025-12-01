"""
STOMP client for Darwin Push Port feed.

Connects to the Darwin Push Port STOMP feed, receives real-time train schedule
messages (including cancellations), filters for Scottish trains, and forwards them 
to the cancellations service.
"""

import gzip
import logging
import time
import threading
import xml.etree.ElementTree as ET
from typing import Optional, Callable
from datetime import datetime

import stomp

from config import TrainMovementsConfig

logger = logging.getLogger(__name__)


class DarwinPushPortListener(stomp.ConnectionListener):
    """STOMP listener for Darwin Push Port messages."""
    
    def __init__(self, config: TrainMovementsConfig, on_cancellation: Callable):
        """
        Initialize the listener.
        
        Args:
            config: Darwin Push Port configuration
            on_cancellation: Callback function for cancellation messages
        """
        self.config = config
        self.on_cancellation = on_cancellation
        self.message_count = 0
        self.cancellation_count = 0
        self.connected = False
    
    def on_connected(self, frame):
        """Called when successfully connected to STOMP server."""
        self.connected = True
        logger.info("✅ Connected to Darwin Push Port feed")
    
    def on_disconnected(self):
        """Called when disconnected from STOMP server."""
        self.connected = False
        logger.warning("⚠️  Disconnected from Darwin Push Port feed")
    
    def on_error(self, frame):
        """Called when an error frame is received."""
        error_msg = frame.body if hasattr(frame, 'body') else str(frame)
        error_headers = frame.headers if hasattr(frame, 'headers') else {}
        logger.error(f"❌ STOMP error: {error_msg}")
        logger.error(f"   Error headers: {error_headers}")
    
    def on_message(self, frame):
        """
        Called when a message is received.
        
        Args:
            frame: STOMP frame containing the message
        """
        try:
            self.message_count += 1
            
            # Darwin messages are gzip-compressed
            # With auto_decode=False, frame.body should be bytes
            body = frame.body
            
            decompressed = gzip.decompress(body)
            
            # Parse XML
            root = ET.fromstring(decompressed)
            
            # Process the message
            self._process_darwin_message(root)
            
            # Log progress every 100 messages
            if self.message_count % 100 == 0:
                logger.info(
                    f"📊 Processed {self.message_count} messages "
                    f"({self.cancellation_count} Scottish cancellations)"
                )
        
        except gzip.BadGzipFile as e:
            logger.error(f"Failed to decompress gzipped message: {e}")
        except ET.ParseError as e:
            logger.error(f"Failed to parse XML: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
    
    def _process_darwin_message(self, root: ET.Element):
        """
        Process a Darwin XML message.
        
        Args:
            root: Root XML element
        """
        try:
            # Darwin messages have namespace
            ns = {'ns': 'http://www.thalesgroup.com/rtti/PushPort/v16'}
            
            # Look for schedule updates (uR element contains updates)
            for ur in root.findall('.//ns:uR', ns):
                # Process schedule elements
                for schedule in ur.findall('.//ns:schedule', ns):
                    self._process_schedule(schedule, ns)
                
                # Process deactivated schedules (explicit cancellations)
                for deactivated in ur.findall('.//ns:deactivated', ns):
                    self._process_deactivated_schedule(deactivated, ns)
        
        except Exception as e:
            logger.error(f"Error processing Darwin message: {e}", exc_info=True)
    
    def _process_schedule(self, schedule: ET.Element, ns: dict):
        """
        Process a schedule element looking for cancellations.
        
        Args:
            schedule: Schedule XML element
            ns: XML namespace dict
        """
        try:
            # Get TOC (train operating company)
            toc = schedule.get('toc', '')
            
            # Filter for Scottish trains
            if toc not in self.config.scottish_toc_codes:
                return
            
            # Check if schedule contains cancelled locations
            # Look for locations with isCancelled="true" attribute
            cancelled_locations = []
            for location in schedule.findall('.//*[@isCancelled]', ns):
                if location.get('isCancelled') == 'true':
                    cancelled_locations.append(location)
            
            # If entire schedule has cancelled attribute or has cancelled locations
            if schedule.get('cancelReason') or cancelled_locations:
                self.cancellation_count += 1
                
                # Extract cancellation data
                cancellation_data = self._extract_cancellation_from_schedule(schedule, cancelled_locations, ns)
                
                logger.info(
                    f"🚫 Scottish train cancellation detected: "
                    f"RID={cancellation_data.get('rid')}, "
                    f"UID={cancellation_data.get('uid')}, "
                    f"TOC={toc}"
                )
                
                # Forward to cancellations service
                self.on_cancellation(cancellation_data)
        
        except Exception as e:
            logger.error(f"Error processing schedule: {e}", exc_info=True)
    
    def _process_deactivated_schedule(self, deactivated: ET.Element, ns: dict):
        """
        Process a deactivated (cancelled) schedule.
        
        Args:
            deactivated: Deactivated schedule XML element
            ns: XML namespace dict
        """
        try:
            rid = deactivated.get('rid', '')
            
            # These are explicit cancellations - always process them
            self.cancellation_count += 1
            
            cancellation_data = {
                'rid': rid,
                'cancellation_type': 'Deactivated',
                'cancellation_datetime': datetime.now().isoformat(),
                'received_at': datetime.now().isoformat()
            }
            
            logger.info(f"🚫 Schedule deactivated (cancelled): RID={rid}")
            
            # Forward to cancellations service
            self.on_cancellation(cancellation_data)
        
        except Exception as e:
            logger.error(f"Error processing deactivated schedule: {e}", exc_info=True)
    
    def _extract_cancellation_from_schedule(self, schedule: ET.Element, cancelled_locations: list, ns: dict) -> dict:
        """
        Extract cancellation data from a schedule.
        
        Args:
            schedule: Schedule XML element
            cancelled_locations: List of cancelled location elements
            ns: XML namespace dict
        
        Returns:
            Dictionary containing cancellation data
        """
        # Extract schedule attributes
        rid = schedule.get('rid', '')
        uid = schedule.get('uid', '')
        train_id = schedule.get('trainId', '')
        ssd = schedule.get('ssd', '')  # Scheduled start date
        toc = schedule.get('toc', '')
        cancel_reason = schedule.get('cancelReason', '')
        
        # Get origin and destination
        origin_elem = schedule.find('.//ns:OR', ns)
        dest_elem = schedule.find('.//ns:DT', ns)
        
        origin_tpl = origin_elem.get('tpl', '') if origin_elem is not None else ''
        dest_tpl = dest_elem.get('tpl', '') if dest_elem is not None else ''
        
        # Get origin departure time
        origin_ptd = origin_elem.get('ptd', '') if origin_elem is not None else ''
        origin_wtd = origin_elem.get('wtd', '') if origin_elem is not None else ''
        
        return {
            'rid': rid,
            'uid': uid,
            'train_id': train_id,
            'toc_id': toc,
            'scheduled_start_date': ssd,
            'cancellation_reason': cancel_reason,
            'cancellation_type': 'Partial' if cancelled_locations else 'Full',
            'cancellation_datetime': datetime.now().isoformat(),
            'origin_tiploc': origin_tpl,
            'destination_tiploc': dest_tpl,
            'origin_departure_scheduled': origin_ptd,
            'origin_departure_working': origin_wtd,
            'cancelled_location_count': len(cancelled_locations),
            'received_at': datetime.now().isoformat()
        }


class TrainMovementsClient:
    """Client for Darwin Push Port STOMP feed."""
    
    def __init__(self, config: TrainMovementsConfig, on_cancellation: Callable):
        """
        Initialize the Darwin Push Port client.
        
        Args:
            config: Darwin Push Port configuration
            on_cancellation: Callback function for cancellation messages
        """
        self.config = config
        self.on_cancellation = on_cancellation
        self.listener = DarwinPushPortListener(config, on_cancellation)
        self.connection: Optional[stomp.Connection] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.reconnect_delay = config.reconnect_base_delay
    
    def start(self):
        """Start the STOMP client in a background thread."""
        if self.running:
            logger.warning("Darwin Push Port client is already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True, name="DarwinPushPortClient")
        self.thread.start()
        logger.info("🚀 Darwin Push Port client started in background thread")
    
    def stop(self):
        """Stop the STOMP client."""
        logger.info("Stopping Darwin Push Port client...")
        self.running = False
        
        if self.connection and self.connection.is_connected():
            try:
                self.connection.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")
        
        if self.thread:
            self.thread.join(timeout=5)
        
        logger.info("✅ Darwin Push Port client stopped")
    
    def _run(self):
        """Main client loop with reconnection logic."""
        while self.running:
            try:
                self._connect_and_subscribe()
                
                # Keep alive while connected
                while self.running and self.listener.connected:
                    time.sleep(1)
                
                # If we get here and still running, we disconnected unexpectedly
                if self.running:
                    logger.warning(
                        f"Connection lost. Reconnecting in {self.reconnect_delay} seconds..."
                    )
                    time.sleep(self.reconnect_delay)
                    
                    # Exponential backoff
                    self.reconnect_delay = min(
                        self.reconnect_delay * 2,
                        self.config.reconnect_max_delay
                    )
            
            except Exception as e:
                logger.error(f"Error in client loop: {e}", exc_info=True)
                if self.running:
                    logger.info(f"Retrying in {self.reconnect_delay} seconds...")
                    time.sleep(self.reconnect_delay)
                    
                    # Exponential backoff
                    self.reconnect_delay = min(
                        self.reconnect_delay * 2,
                        self.config.reconnect_max_delay
                    )
    
    def _connect_and_subscribe(self):
        """Connect to STOMP server and subscribe to queue."""
        logger.info(f"Connecting to {self.config.host}:{self.config.port}...")
        
        # Create connection with heartbeats and disable auto-decode to preserve binary gzip data
        self.connection = stomp.Connection(
            [(self.config.host, self.config.port)],
            heartbeats=(
                self.config.heartbeat_send_interval,
                self.config.heartbeat_receive_interval
            ),
            auto_decode=False  # Keep message bodies as bytes for gzip decompression
        )
        
        # Set listener
        self.connection.set_listener('', self.listener)
        
        # Connect with credentials and client-id for durable subscription
        # Darwin requires client-id to start with username
        self.connection.connect(
            username=self.config.username,
            passcode=self.config.password,
            wait=True,
            headers={'client-id': self.config.client_id}
        )
        
        # Subscribe to queue (Darwin uses queue, not topic)
        self.connection.subscribe(
            destination=self.config.queue,
            id=1,
            ack='auto',
            headers={'activemq.subscriptionName': self.config.subscription_name}
        )
        
        logger.info(f"✅ Subscribed to {self.config.queue} with durable subscription")
        
        # Reset reconnect delay on successful connection
        self.reconnect_delay = self.config.reconnect_base_delay
    
    def get_stats(self) -> dict:
        """
        Get client statistics.
        
        Returns:
            Dictionary containing client stats
        """
        return {
            'connected': self.listener.connected,
            'running': self.running,
            'messages_processed': self.listener.message_count,
            'cancellations_detected': self.listener.cancellation_count
        }
