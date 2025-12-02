#!/usr/bin/env python3
"""
Live Darwin Feed Service with Integrated Schedule Storage and Cancellation Enrichment.

This service connects to the live Darwin Push Port feed to:
1. Collect and store train schedules for enrichment
2. Detect cancellations and enrich them with schedule data
3. Forward enriched cancellations to the cancellation service
"""

import logging
import threading
import time
import signal
import sys
import gzip
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, Any

# Import existing components
from train_movements_client import DarwinPushPortListener, TrainMovementsClient
from cancellations_service import CancellationsService
from darwin_schedule_prototype import DarwinScheduleDatabase, DarwinScheduleProcessor
from config import get_config, get_train_movements_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('live_darwin_service.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class EnhancedDarwinListener(DarwinPushPortListener):
    """Enhanced Darwin listener that handles both schedules and cancellations."""
    
    def __init__(self, config, on_cancellation, on_schedule):
        """
        Initialize the enhanced listener.
        
        Args:
            config: Darwin Push Port configuration
            on_cancellation: Callback function for cancellation messages
            on_schedule: Callback function for schedule messages
        """
        super().__init__(config, on_cancellation)
        self.on_schedule = on_schedule
        self.schedule_count = 0
    
    def on_message(self, frame):
        """
        Process Darwin messages for both schedules and cancellations.
        
        Args:
            frame: STOMP frame containing the message
        """
        try:
            self.message_count += 1
            
            # Darwin messages are gzip-compressed
            body = frame.body
            decompressed = gzip.decompress(body)
            
            # Parse XML
            root = ET.fromstring(decompressed)
            
            # Process the message for both schedules and cancellations
            self._process_darwin_message_enhanced(root)
            
            # Log progress every 100 messages
            if self.message_count % 100 == 0:
                logger.info(
                    f"📊 Processed {self.message_count} messages "
                    f"({self.schedule_count} schedules, {self.cancellation_count} cancellations)"
                )
        
        except gzip.BadGzipFile as e:
            logger.error(f"Failed to decompress gzipped message: {e}")
        except ET.ParseError as e:
            logger.error(f"Failed to parse XML: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
    
    def _process_darwin_message_enhanced(self, root: ET.Element):
        """
        Enhanced processing for both schedules and cancellations.
        
        Args:
            root: Root XML element
        """
        try:
            # Darwin messages have namespace
            ns = {'ns': 'http://www.thalesgroup.com/rtti/PushPort/v16'}
            
            # Process schedule messages for storage (for enrichment database)
            for schedule_msg in root.findall('.//ns:schedule', ns):
                self._process_schedule_for_storage(schedule_msg, ns)
            
            # Look for schedule updates (uR element contains updates)
            for ur in root.findall('.//ns:uR', ns):
                # Process schedule elements for cancellations
                for schedule in ur.findall('.//ns:schedule', ns):
                    self._process_schedule(schedule, ns)
                
                # Process deactivated schedules (explicit cancellations)
                for deactivated in ur.findall('.//ns:deactivated', ns):
                    self._process_deactivated_schedule(deactivated, ns)
        
        except Exception as e:
            logger.error(f"Error processing Darwin message: {e}", exc_info=True)
    
    def _process_schedule_for_storage(self, schedule: ET.Element, ns: dict):
        """
        Process a schedule element for storage in enrichment database.
        
        Args:
            schedule: Schedule XML element
            ns: XML namespace dict
        """
        try:
            # Extract schedule data for storage
            rid = schedule.get('rid', '')
            toc = schedule.get('toc', '')
            
            # Filter for Scottish trains for storage
            if toc in self.config.scottish_toc_codes:
                self.schedule_count += 1
                
                # Convert XML to dictionary format for schedule processor
                schedule_data = self._extract_schedule_data(schedule, ns)
                
                # Forward to schedule storage
                if schedule_data:
                    self.on_schedule(schedule_data)
        
        except Exception as e:
            logger.error(f"Error processing schedule for storage: {e}", exc_info=True)
    
    def _extract_schedule_data(self, schedule: ET.Element, ns: dict) -> Dict[str, Any]:
        """
        Extract schedule data for storage.
        
        Args:
            schedule: Schedule XML element
            ns: XML namespace dict
            
        Returns:
            Dictionary containing schedule data
        """
        try:
            # Basic schedule attributes
            rid = schedule.get('rid', '')
            uid = schedule.get('uid', '')
            train_id = schedule.get('trainId', '')
            ssd = schedule.get('ssd', '')  # Scheduled start date
            toc = schedule.get('toc', '')
            category = schedule.get('trainCat', '')
            
            # Get origin and destination
            origin_elem = schedule.find('.//ns:OR', ns)
            dest_elem = schedule.find('.//ns:DT', ns)
            
            origin_data = self._extract_location_data(origin_elem) if origin_elem is not None else {}
            dest_data = self._extract_location_data(dest_elem) if dest_elem is not None else {}
            
            # Get calling points
            calling_points = []
            for ip_elem in schedule.findall('.//ns:IP', ns):
                cp_data = self._extract_location_data(ip_elem)
                if cp_data:
                    calling_points.append(cp_data)
            
            return {
                'rid': rid,
                'uid': uid,
                'train_id': train_id,
                'headcode': train_id,  # Use train_id as headcode
                'toc': toc,
                'category': category,
                'start_date': ssd,
                'origin_tiploc': origin_data.get('tiploc', ''),
                'origin_time': origin_data.get('departure_time', ''),
                'origin_platform': origin_data.get('platform', ''),
                'destination_tiploc': dest_data.get('tiploc', ''),
                'destination_time': dest_data.get('arrival_time', ''),
                'destination_platform': dest_data.get('platform', ''),
                'calling_points': calling_points
            }
            
        except Exception as e:
            logger.error(f"Error extracting schedule data: {e}", exc_info=True)
            return {}
    
    def _extract_location_data(self, location_elem: ET.Element) -> Dict[str, Any]:
        """
        Extract location data from a location element.
        
        Args:
            location_elem: XML location element
            
        Returns:
            Dictionary containing location data
        """
        if location_elem is None:
            return {}
        
        return {
            'tiploc': location_elem.get('tpl', ''),
            'platform': location_elem.get('plat', ''),
            'arrival_time': location_elem.get('pta', location_elem.get('wta', '')),
            'departure_time': location_elem.get('ptd', location_elem.get('wtd', '')),
            'pass_time': location_elem.get('wtp', '')
        }


class LiveDarwinService:
    """Integrated Darwin service for live schedule collection and cancellation enrichment."""
    
    def __init__(self):
        """Initialize the live Darwin service."""
        self.config = get_config()
        self.movements_config = get_train_movements_config()
        
        # Initialize components
        self.schedule_database = None
        self.schedule_processor = None
        self.cancellations_service = None
        self.movements_client = None
        
        # Service state
        self.running = False
        self.stats = {
            'start_time': None,
            'schedules_processed': 0,
            'cancellations_detected': 0,
            'cancellations_enriched': 0,
            'last_schedule_update': None,
            'last_cancellation': None
        }
        
        # Cleanup thread
        self.cleanup_thread = None
        
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize all service components."""
        try:
            # Initialize Darwin schedule storage
            logger.info("🗄️  Initializing Darwin schedule database...")
            self.schedule_database = DarwinScheduleDatabase(self.config.darwin_db_path)
            self.schedule_processor = DarwinScheduleProcessor(self.schedule_database)
            logger.info("✅ Darwin schedule storage initialized")
            
            # Initialize enhanced cancellations service
            logger.info("📋 Initializing enhanced cancellations service...")
            self.cancellations_service = CancellationsService(
                max_stored=self.config.cancellation_max_stored,
                darwin_db_path=self.config.darwin_db_path,
                enable_enrichment=self.config.darwin_enrichment_enabled
            )
            logger.info("✅ Enhanced cancellations service initialized")
            
            # Initialize Darwin feed client
            logger.info("📡 Initializing Darwin feed client...")
            self.movements_client = TrainMovementsClient(
                config=self.movements_config,
                on_cancellation=self._handle_cancellation
            )
            logger.info("✅ Darwin feed client initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize components: {e}")
            raise
    
    def _handle_cancellation(self, cancellation_data: Dict[str, Any]):
        """
        Handle a detected cancellation from the Darwin feed.
        
        Args:
            cancellation_data: Cancellation data from train movements client
        """
        try:
            self.stats['cancellations_detected'] += 1
            self.stats['last_cancellation'] = datetime.now().isoformat()
            
            logger.info(
                f"🚫 Processing cancellation: RID={cancellation_data.get('rid')}, "
                f"Train={cancellation_data.get('train_id', cancellation_data.get('uid'))}"
            )
            
            # Convert train movements format to cancellations service format
            service_cancellation = {
                'rid': cancellation_data.get('rid'),
                'train_service_code': cancellation_data.get('train_id', cancellation_data.get('uid')),
                'train_id': cancellation_data.get('train_id', cancellation_data.get('uid')),
                'reason_code': cancellation_data.get('cancellation_reason', 'Unknown'),
                'reason_text': self._format_cancellation_reason(cancellation_data),
                'location': cancellation_data.get('origin_tiploc', 'Unknown'),
                'toc': cancellation_data.get('toc_id', 'Unknown'),
                'cancellation_type': cancellation_data.get('cancellation_type', 'Full'),
                'cancelled_at': cancellation_data.get('cancellation_datetime'),
                'received_at': cancellation_data.get('received_at'),
                'source': 'darwin_live_feed'
            }
            
            # Add to enhanced cancellations service (will automatically enrich if RID available)
            self.cancellations_service.add_cancellation(service_cancellation)
            
            # Check if it was enriched
            recent_cancellations = self.cancellations_service.get_recent_cancellations(limit=1)
            if recent_cancellations and recent_cancellations[0].get('darwin_enriched'):
                self.stats['cancellations_enriched'] += 1
                logger.info("✅ Cancellation successfully enriched with Darwin schedule data")
            else:
                logger.info("⚪ Cancellation processed without enrichment (no schedule data available)")
                
        except Exception as e:
            logger.error(f"❌ Error processing cancellation: {e}", exc_info=True)
    
    def _format_cancellation_reason(self, cancellation_data: Dict[str, Any]) -> str:
        """
        Format a human-readable cancellation reason.
        
        Args:
            cancellation_data: Raw cancellation data
            
        Returns:
            Formatted reason text
        """
        reason_code = cancellation_data.get('cancellation_reason', '')
        cancellation_type = cancellation_data.get('cancellation_type', 'Full')
        
        if reason_code:
            return f"{cancellation_type} cancellation - Reason code: {reason_code}"
        else:
            return f"{cancellation_type} cancellation detected"
    
    def start(self):
        """Start the live Darwin service."""
        if self.running:
            logger.warning("Service is already running")
            return
        
        logger.info("🚀 Starting Live Darwin Service")
        
        self.running = True
        self.stats['start_time'] = datetime.now().isoformat()
        
        # Start Darwin feed client
        try:
            self.movements_client.start()
            logger.info("✅ Darwin feed client started")
        except Exception as e:
            logger.error(f"❌ Failed to start Darwin feed client: {e}")
            self.running = False
            raise
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True, name="CleanupThread")
        self.cleanup_thread.start()
        logger.info("✅ Cleanup thread started")
        
        logger.info("🎉 Live Darwin Service is now running")
        logger.info("📡 Listening for train schedules and cancellations...")
        
        # Log configuration
        logger.info(f"📋 Configuration:")
        logger.info(f"   Darwin Database: {self.config.darwin_db_path}")
        logger.info(f"   Enrichment Enabled: {self.config.darwin_enrichment_enabled}")
        logger.info(f"   Max Cancellations Stored: {self.config.cancellation_max_stored}")
        logger.info(f"   Schedule Retention: {self.config.darwin_schedule_retention_days} days")
    
    def stop(self):
        """Stop the live Darwin service."""
        if not self.running:
            logger.info("Service is not running")
            return
        
        logger.info("🛑 Stopping Live Darwin Service...")
        
        self.running = False
        
        # Stop Darwin feed client
        if self.movements_client:
            self.movements_client.stop()
        
        # Wait for cleanup thread
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=5)
        
        logger.info("✅ Live Darwin Service stopped")
        
        # Log final statistics
        self._log_final_stats()
    
    def _cleanup_loop(self):
        """Background cleanup loop."""
        while self.running:
            try:
                # Sleep for 1 hour between cleanup cycles
                for _ in range(3600):
                    if not self.running:
                        return
                    time.sleep(1)
                
                logger.info("🧹 Starting periodic cleanup...")
                
                # Cleanup old schedules
                if self.schedule_database:
                    retention_date = datetime.now() - timedelta(days=self.config.darwin_schedule_retention_days)
                    
                    # Delete old schedules
                    with self.schedule_database.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "DELETE FROM schedules WHERE start_date < ?",
                            (retention_date.strftime('%Y-%m-%d'),)
                        )
                        deleted_schedules = cursor.rowcount
                        
                        cursor.execute(
                            "DELETE FROM calling_points WHERE rid NOT IN (SELECT rid FROM schedules)"
                        )
                        deleted_calling_points = cursor.rowcount
                        
                        conn.commit()
                    
                    if deleted_schedules > 0 or deleted_calling_points > 0:
                        logger.info(
                            f"🧹 Cleanup completed: Removed {deleted_schedules} old schedules "
                            f"and {deleted_calling_points} orphaned calling points"
                        )
                
                # VACUUM database to reclaim space
                with self.schedule_database.get_connection() as conn:
                    conn.execute("VACUUM")
                    logger.info("🗜️  Database vacuumed")
                
            except Exception as e:
                logger.error(f"❌ Error in cleanup loop: {e}", exc_info=True)
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive service status.
        
        Returns:
            Dictionary containing service status and statistics
        """
        # Get component statistics
        movements_stats = self.movements_client.get_stats() if self.movements_client else {}
        cancellations_stats = self.cancellations_service.get_stats() if self.cancellations_service else {}
        database_stats = self.schedule_database.get_statistics() if self.schedule_database else {}
        
        # Calculate enrichment rate
        enrichment_rate = 0
        if self.stats['cancellations_detected'] > 0:
            enrichment_rate = (self.stats['cancellations_enriched'] / self.stats['cancellations_detected']) * 100
        
        # Calculate uptime
        uptime_seconds = 0
        if self.stats['start_time']:
            start_time = datetime.fromisoformat(self.stats['start_time'])
            uptime_seconds = (datetime.now() - start_time).total_seconds()
        
        return {
            'service_status': {
                'running': self.running,
                'uptime_seconds': uptime_seconds,
                'uptime_formatted': str(timedelta(seconds=int(uptime_seconds))),
                'start_time': self.stats['start_time']
            },
            'processing_stats': {
                'schedules_processed': self.stats['schedules_processed'],
                'cancellations_detected': self.stats['cancellations_detected'],
                'cancellations_enriched': self.stats['cancellations_enriched'],
                'enrichment_rate': round(enrichment_rate, 1),
                'last_schedule_update': self.stats['last_schedule_update'],
                'last_cancellation': self.stats['last_cancellation']
            },
            'darwin_feed': movements_stats,
            'cancellations_service': cancellations_stats,
            'schedule_database': database_stats,
            'configuration': {
                'darwin_db_path': self.config.darwin_db_path,
                'enrichment_enabled': self.config.darwin_enrichment_enabled,
                'max_stored': self.config.cancellation_max_stored,
                'retention_days': self.config.darwin_schedule_retention_days
            }
        }
    
    def _log_final_stats(self):
        """Log final service statistics."""
        status = self.get_status()
        logger.info("📊 Final Service Statistics:")
        logger.info(f"   Uptime: {status['service_status']['uptime_formatted']}")
        logger.info(f"   Schedules Processed: {status['processing_stats']['schedules_processed']}")
        logger.info(f"   Cancellations Detected: {status['processing_stats']['cancellations_detected']}")
        logger.info(f"   Cancellations Enriched: {status['processing_stats']['cancellations_enriched']}")
        logger.info(f"   Enrichment Rate: {status['processing_stats']['enrichment_rate']}%")


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {sig}, shutting down...")
    if 'service' in globals():
        service.stop()
    sys.exit(0)


def main():
    """Main entry point."""
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and start service
    global service
    service = LiveDarwinService()
    
    try:
        service.start()
        
        # Keep the main thread alive and log status periodically
        while service.running:
            time.sleep(300)  # Log status every 5 minutes
            
            status = service.get_status()
            logger.info(
                f"📊 Status Update - "
                f"Uptime: {status['service_status']['uptime_formatted']}, "
                f"Cancellations: {status['processing_stats']['cancellations_detected']} "
                f"({status['processing_stats']['enrichment_rate']}% enriched), "
                f"Feed Connected: {status['darwin_feed'].get('connected', False)}"
            )
    
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        service.stop()


if __name__ == "__main__":
    main()