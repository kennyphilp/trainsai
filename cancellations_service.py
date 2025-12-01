"""
Cancellations service for managing Scottish train cancellations.

Provides thread-safe in-memory storage and retrieval of train cancellation data
received from the Train Movements feed.
"""

import logging
import threading
from collections import deque
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CancellationsService:
    """Service for managing train cancellation data."""
    
    def __init__(self, max_stored: int = 50):
        """
        Initialize the cancellations service.
        
        Args:
            max_stored: Maximum number of cancellations to store (ring buffer size)
        """
        self.max_stored = max_stored
        self._cancellations = deque(maxlen=max_stored)
        self._lock = threading.Lock()
        self._total_cancellations = 0
        
        logger.info(f"📋 Cancellations service initialized (max_stored={max_stored})")
    
    def add_cancellation(self, cancellation: Dict):
        """
        Add a new cancellation to storage.
        
        Thread-safe operation. Automatically evicts oldest cancellations when
        storage limit is reached.
        
        Args:
            cancellation: Cancellation data dictionary
        """
        with self._lock:
            # Add timestamp if not present
            if 'added_at' not in cancellation:
                cancellation['added_at'] = datetime.now().isoformat()
            
            # Add to deque (automatically evicts oldest if at max capacity)
            self._cancellations.append(cancellation)
            self._total_cancellations += 1
            
            logger.info(
                f"📥 Added cancellation: Train {cancellation.get('train_service_code', 'Unknown')} "
                f"(Total stored: {len(self._cancellations)}/{self.max_stored}, "
                f"Total received: {self._total_cancellations})"
            )
    
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
        Get service statistics.
        
        Thread-safe operation.
        
        Returns:
            Dictionary containing service stats
        """
        with self._lock:
            return {
                'stored_count': len(self._cancellations),
                'max_stored': self.max_stored,
                'total_received': self._total_cancellations,
                'oldest_cancellation': self._cancellations[0] if self._cancellations else None,
                'newest_cancellation': self._cancellations[-1] if self._cancellations else None
            }
    
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
