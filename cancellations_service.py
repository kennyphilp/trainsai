"""
Cancellations service for managing Scottish train cancellations.

Provides thread-safe in-memory storage and retrieval of train cancellation data
received from the Train Movements feed, with Darwin schedule-based enrichment.
"""

import logging
import threading
import sqlite3
import os
from pathlib import Path
from collections import deque
from typing import List, Dict, Optional
from datetime import datetime, timedelta

# Import Darwin schedule processing components
try:
    from darwin_schedule_prototype import DarwinScheduleDatabase, DarwinScheduleProcessor
    DARWIN_AVAILABLE = True
except ImportError:
    DARWIN_AVAILABLE = False
    logging.warning("Darwin schedule components not available - enrichment disabled")

logger = logging.getLogger(__name__)


class CancellationsService:
    """Service for managing train cancellation data with Darwin schedule enrichment."""
    
    def __init__(self, max_stored: int = 50, darwin_db_path: str = "darwin_schedules.db", enable_enrichment: bool = True):
        """
        Initialize the cancellations service.
        
        Args:
            max_stored: Maximum number of cancellations to store (ring buffer size)
            darwin_db_path: Path to Darwin schedules database
            enable_enrichment: Whether to enable Darwin schedule enrichment
        """
        self.max_stored = max_stored
        self.enable_enrichment = enable_enrichment and DARWIN_AVAILABLE
        self._cancellations = deque(maxlen=max_stored)
        self._lock = threading.Lock()
        self._total_cancellations = 0
        self._enriched_cancellations = 0
        
        # Initialize Darwin schedule processing if available
        self.darwin_database = None
        self.darwin_processor = None
        
        if self.enable_enrichment:
            try:
                self.darwin_database = DarwinScheduleDatabase(darwin_db_path)
                self.darwin_processor = DarwinScheduleProcessor(self.darwin_database)
                logger.info(f"✅ Darwin schedule enrichment enabled (DB: {darwin_db_path})")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Darwin enrichment: {e}")
                self.enable_enrichment = False
        
        logger.info(f"📋 Cancellations service initialized (max_stored={max_stored}, enrichment={'enabled' if self.enable_enrichment else 'disabled'})")
    
    def add_cancellation(self, cancellation: Dict):
        """
        Add a new cancellation to storage with optional Darwin enrichment.
        
        Thread-safe operation. Automatically evicts oldest cancellations when
        storage limit is reached. Attempts to enrich cancellation with Darwin
        schedule data if enrichment is enabled.
        
        Args:
            cancellation: Cancellation data dictionary
        """
        with self._lock:
            # Add timestamp if not present
            if 'added_at' not in cancellation:
                cancellation['added_at'] = datetime.now().isoformat()
            
            # Attempt Darwin enrichment
            enriched = False
            if self.enable_enrichment and 'rid' in cancellation:
                enriched = self._enrich_with_darwin_schedule(cancellation)
            
            # Add to deque (automatically evicts oldest if at max capacity)
            self._cancellations.append(cancellation)
            self._total_cancellations += 1
            
            if enriched:
                self._enriched_cancellations += 1
            
            enrichment_status = "✅ enriched" if enriched else "⚪ basic"
            logger.info(
                f"📥 Added cancellation ({enrichment_status}): Train {cancellation.get('train_service_code', cancellation.get('train_id', 'Unknown'))} "
                f"(Total stored: {len(self._cancellations)}/{self.max_stored}, "
                f"Total received: {self._total_cancellations}, Enriched: {self._enriched_cancellations})"
            )
    
    def _enrich_with_darwin_schedule(self, cancellation: Dict) -> bool:
        """
        Enrich cancellation with Darwin schedule data.
        
        Args:
            cancellation: Cancellation dictionary to enrich (modified in-place)
            
        Returns:
            True if enrichment was successful, False otherwise
        """
        try:
            rid = cancellation.get('rid')
            if not rid or not self.darwin_database:
                return False
            
            # Look up schedule data
            schedule = self.darwin_database.get_schedule(rid)
            if not schedule:
                logger.debug(f"🔍 No Darwin schedule found for RID: {rid}")
                return False
            
            # Enrich the cancellation with schedule data
            enrichment_data = {
                'darwin_enriched': True,
                'enriched_at': datetime.now().isoformat(),
                'train_id_darwin': schedule.get('train_id'),
                'headcode_darwin': schedule.get('headcode'),
                'toc_darwin': schedule.get('toc'),
                'category_darwin': schedule.get('category'),
                'origin_tiploc_darwin': schedule.get('origin_tiploc'),
                'origin_time_darwin': schedule.get('origin_time'),
                'origin_platform_darwin': schedule.get('origin_platform'),
                'destination_tiploc_darwin': schedule.get('destination_tiploc'),
                'destination_time_darwin': schedule.get('destination_time'),
                'destination_platform_darwin': schedule.get('destination_platform'),
                'service_date_darwin': schedule.get('start_date'),
                'calling_points_count': len(schedule.get('calling_points', [])),
                'calling_points_darwin': schedule.get('calling_points', [])[:5]  # First 5 for display
            }
            
            # Update the cancellation dictionary
            cancellation.update(enrichment_data)
            
            logger.info(
                f"🎯 ENRICHED cancellation RID {rid}: {enrichment_data['train_id_darwin']} "
                f"({enrichment_data['origin_tiploc_darwin']} → {enrichment_data['destination_tiploc_darwin']})"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error enriching cancellation with RID {cancellation.get('rid')}: {e}")
            return False
    
    def get_recent_cancellations(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Get recent cancellations, newest first.
        
        Thread-safe operation.
        
        Args:
            limit: Maximum number of cancellations to return (None = all)
        
        Returns:
            List of cancellation dictionaries, newest first
        """
        with self._lock:
            # Convert deque to list (newest last in deque)
            cancellations = list(self._cancellations)
            
            # Reverse to get newest first
            cancellations.reverse()
            
            # Apply limit if specified
            if limit is not None:
                cancellations = cancellations[:limit]
            
            return cancellations
    
    def get_cancellation_by_train_id(self, train_id: str) -> Optional[Dict]:
        """
        Get a specific cancellation by train ID.
        
        Thread-safe operation.
        
        Args:
            train_id: Train ID to search for
        
        Returns:
            Cancellation dictionary if found, None otherwise
        """
        with self._lock:
            for cancellation in reversed(self._cancellations):
                if cancellation.get('train_id') == train_id:
                    return cancellation
            
            return None
    
    def clear(self):
        """
        Clear all stored cancellations.
        
        Thread-safe operation. Useful for testing.
        """
        with self._lock:
            self._cancellations.clear()
            logger.info("🗑️  Cleared all stored cancellations")
    
    def get_stats(self) -> Dict:
        """
        Get service statistics including enrichment data.
        
        Thread-safe operation.
        
        Returns:
            Dictionary containing service stats
        """
        with self._lock:
            enrichment_rate = 0
            if self._total_cancellations > 0:
                enrichment_rate = (self._enriched_cancellations / self._total_cancellations) * 100
            
            stats = {
                'stored_count': len(self._cancellations),
                'max_stored': self.max_stored,
                'total_received': self._total_cancellations,
                'total_enriched': self._enriched_cancellations,
                'enrichment_rate': round(enrichment_rate, 1),
                'enrichment_enabled': self.enable_enrichment,
                'oldest_cancellation': self._cancellations[0] if self._cancellations else None,
                'newest_cancellation': self._cancellations[-1] if self._cancellations else None
            }
            
            # Add Darwin database stats if available
            if self.enable_enrichment and self.darwin_database:
                try:
                    db_stats = self.darwin_database.get_statistics()
                    stats['darwin_database'] = db_stats
                except Exception as e:
                    logger.error(f"Error getting Darwin database stats: {e}")
                    
            return stats
    
    def format_cancellation_for_display(self, cancellation: Dict) -> Dict:
        """
        Format cancellation data for frontend display.
        
        Args:
            cancellation: Raw cancellation data
        
        Returns:
            Formatted cancellation dictionary
        """
        # Get readable cancellation type
        canx_type = cancellation.get('cancellation_type', 'Unknown')
        
        # Format timestamps
        canx_datetime = cancellation.get('cancellation_datetime', '')
        if canx_datetime:
            try:
                dt = datetime.fromisoformat(canx_datetime)
                time_display = dt.strftime('%H:%M')
                date_display = dt.strftime('%d %b %Y')
            except ValueError:
                time_display = 'Unknown'
                date_display = 'Unknown'
        else:
            time_display = 'Unknown'
            date_display = 'Unknown'
        
        # Get origin departure time (Darwin uses scheduled departure)
        scheduled_dep = cancellation.get('origin_departure_scheduled', '')
        if not scheduled_dep:
            scheduled_dep = cancellation.get('origin_departure_working', '')
        
        return {
            'rid': cancellation.get('rid', 'Unknown'),
            'uid': cancellation.get('uid', 'Unknown'),
            'train_id': cancellation.get('train_id', 'Unknown'),
            'toc': cancellation.get('toc_id', 'Unknown'),
            'cancelled_at': time_display,
            'cancelled_date': date_display,
            'cancellation_type': canx_type,
            'reason': cancellation.get('cancellation_reason', 'Unknown'),
            'origin_tiploc': cancellation.get('origin_tiploc', 'Unknown'),
            'destination_tiploc': cancellation.get('destination_tiploc', 'Unknown'),
            'scheduled_departure': scheduled_dep,
            'scheduled_start_date': cancellation.get('scheduled_start_date', ''),
            'received_at': cancellation.get('received_at', '')
        }
