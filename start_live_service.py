#!/usr/bin/env python3
"""
Production startup script for the Live Darwin Integration Service.

This script starts the integrated service that connects to the live Darwin feed
and provides enriched cancellation data.
"""

import os
import sys
import logging
from pathlib import Path

# Ensure we can import our modules
sys.path.append(str(Path(__file__).parent))

from live_integration import LiveIntegrationService

# Configure production logging
def setup_production_logging():
    """Set up production-grade logging."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # File handler for detailed logs
    file_handler = logging.FileHandler(log_dir / "darwin_integration.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    
    # Console handler for key events
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    
    # Add handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Reduce noise from specific loggers
    logging.getLogger('stomp.transport').setLevel(logging.WARNING)
    logging.getLogger('stomp.listener').setLevel(logging.WARNING)


def check_environment():
    """Check that the environment is properly configured."""
    logger = logging.getLogger(__name__)
    
    # Check for demo database (fallback) or configured database
    demo_db = Path("demo_detailed.db")
    configured_db = Path("darwin_schedules.db")
    
    if demo_db.exists():
        logger.info(f"✅ Demo database found: {demo_db}")
        return True
    elif configured_db.exists():
        logger.info(f"✅ Configured database found: {configured_db}")
        return True
    else:
        logger.warning("⚠️  No Darwin schedule database found")
        logger.warning("   Enrichment will not work until schedules are collected")
        return True  # Don't fail, just warn
    

def main():
    """Main startup function."""
    print("🚀 Starting Darwin Live Integration Service")
    
    # Setup logging
    setup_production_logging()
    logger = logging.getLogger(__name__)
    
    # Check environment
    if not check_environment():
        logger.error("❌ Environment check failed")
        sys.exit(1)
    
    # Create and start the service
    try:
        logger.info("🏗️  Initializing Live Darwin Integration Service...")
        service = LiveIntegrationService()
        
        logger.info("🚀 Starting service...")
        service.start()
        
        # Log startup success
        status = service.get_status()
        logger.info("✅ Service started successfully!")
        logger.info("📊 Configuration:")
        logger.info(f"   Darwin Database: {status['configuration']['darwin_db_path']}")
        logger.info(f"   Enrichment Enabled: {status['configuration']['enrichment_enabled']}")
        logger.info(f"   Max Stored Cancellations: {status['configuration']['max_stored']}")
        
        logger.info("📡 Now listening for live Darwin feed data...")
        logger.info("💡 Press Ctrl+C to stop the service")
        
        # Keep the service running
        import time
        while service.running:
            time.sleep(60)  # Log status every minute
            
            status = service.get_status()
            if status['processing_stats']['cancellations_detected'] > 0:
                logger.info(
                    f"📊 Status: "
                    f"Uptime={status['service_status']['uptime_formatted']}, "
                    f"Cancellations={status['processing_stats']['cancellations_detected']} "
                    f"({status['processing_stats']['enrichment_rate']}% enriched), "
                    f"Connected={status['darwin_feed'].get('connected', False)}"
                )
    
    except KeyboardInterrupt:
        logger.info("🛑 Received shutdown signal")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
    finally:
        if 'service' in locals():
            logger.info("🛑 Stopping service...")
            service.stop()
            logger.info("✅ Service stopped cleanly")


if __name__ == "__main__":
    main()