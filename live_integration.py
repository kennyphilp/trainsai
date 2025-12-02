#!/usr/bin/env python3
"""
Live Darwin Integration Service - Connects live feed to enhanced cancellation service.

This service integrates your existing train movements client with the enhanced
cancellation service to provide real-time enriched cancellation data.
"""

import logging
import threading
import time
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, Any

# Import existing components
from train_movements_client import TrainMovementsClient
from cancellations_service import CancellationsService
from config import get_config, get_train_movements_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('live_integration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class LiveIntegrationService:
    """Service to connect live Darwin feed with enhanced cancellation service."""
    
    def __init__(self):
        """Initialize the live integration service."""
        self.config = get_config()
        self.movements_config = get_train_movements_config()
        
        # Initialize components
        self.cancellations_service = None
        self.movements_client = None
        
        # Service state
        self.running = False
        self.stats = {
            'start_time': None,
            'cancellations_detected': 0,
            'cancellations_enriched': 0,
            'last_cancellation': None
        }
        
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize all service components."""
        try:
            # Initialize enhanced cancellations service
            logger.info("📋 Initializing enhanced cancellations service...")
            
            # Use demo database if it exists for testing, otherwise use configured path
            import os
            demo_db_path = "demo_detailed.db"
            darwin_db_path = demo_db_path if os.path.exists(demo_db_path) else self.config.darwin_db_path
            
            if os.path.exists(demo_db_path):
                logger.info(f"💡 Using demo database for testing: {demo_db_path}")
            
            self.cancellations_service = CancellationsService(
                max_stored=self.config.cancellation_max_stored,
                darwin_db_path=darwin_db_path,
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
        """Start the live integration service."""
        if self.running:
            logger.warning("Service is already running")
            return
        
        logger.info("🚀 Starting Live Darwin Integration Service")
        
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
        
        logger.info("🎉 Live Darwin Integration Service is now running")
        logger.info("📡 Listening for train cancellations...")
        
        # Log configuration
        logger.info(f"📋 Configuration:")
        logger.info(f"   Darwin Database: {self.config.darwin_db_path}")
        logger.info(f"   Enrichment Enabled: {self.config.darwin_enrichment_enabled}")
        logger.info(f"   Max Cancellations Stored: {self.config.cancellation_max_stored}")
    
    def stop(self):
        """Stop the live integration service."""
        if not self.running:
            logger.info("Service is not running")
            return
        
        logger.info("🛑 Stopping Live Darwin Integration Service...")
        
        self.running = False
        
        # Stop Darwin feed client
        if self.movements_client:
            self.movements_client.stop()
        
        logger.info("✅ Live Darwin Integration Service stopped")
        
        # Log final statistics
        self._log_final_stats()
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive service status.
        
        Returns:
            Dictionary containing service status and statistics
        """
        # Get component statistics
        movements_stats = self.movements_client.get_stats() if self.movements_client else {}
        cancellations_stats = self.cancellations_service.get_stats() if self.cancellations_service else {}
        
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
                'cancellations_detected': self.stats['cancellations_detected'],
                'cancellations_enriched': self.stats['cancellations_enriched'],
                'enrichment_rate': round(enrichment_rate, 1),
                'last_cancellation': self.stats['last_cancellation']
            },
            'darwin_feed': movements_stats,
            'cancellations_service': cancellations_stats,
            'configuration': {
                'darwin_db_path': self.config.darwin_db_path,
                'enrichment_enabled': self.config.darwin_enrichment_enabled,
                'max_stored': self.config.cancellation_max_stored
            }
        }
    
    def get_recent_enriched_cancellations(self, limit: int = 10):
        """Get recent cancellations from the enhanced service."""
        if self.cancellations_service:
            return self.cancellations_service.get_recent_cancellations(limit)
        return []
    
    def _log_final_stats(self):
        """Log final service statistics."""
        status = self.get_status()
        logger.info("📊 Final Service Statistics:")
        logger.info(f"   Uptime: {status['service_status']['uptime_formatted']}")
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
    service = LiveIntegrationService()
    
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