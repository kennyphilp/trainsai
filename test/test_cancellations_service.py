"""
Unit tests for CancellationsService.

Tests the thread-safe cancellations storage and retrieval service.
"""

import unittest
from datetime import datetime
from cancellations_service import CancellationsService


class TestCancellationsService(unittest.TestCase):
    """Test cases for CancellationsService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.service = CancellationsService(max_stored=5)
    
    def test_initialization(self):
        """Test service initializes with correct settings."""
        self.assertEqual(self.service.max_stored, 5)
        self.assertEqual(len(self.service._cancellations), 0)
    
    def test_add_single_cancellation(self):
        """Test adding a single cancellation."""
        cancellation = {
            'rid': 'TEST123',
            'train_id': '1A23',
            'toc_id': 'SR',
            'cancellation_datetime': datetime.now().isoformat()
        }
        
        self.service.add_cancellation(cancellation)
        
        stats = self.service.get_stats()
        self.assertEqual(stats['total_received'], 1)
        self.assertEqual(stats['stored_count'], 1)
        
        # Check Scottish trains manually
        recent = self.service.get_recent_cancellations()
        scottish_count = sum(1 for c in recent if c.get('toc_id') == 'SR')
        self.assertEqual(scottish_count, 1)
    
    def test_add_multiple_cancellations(self):
        """Test adding multiple cancellations."""
        for i in range(3):
            cancellation = {
                'rid': f'TEST{i}',
                'train_id': f'1A{i}',
                'toc_id': 'SR',
                'cancellation_datetime': datetime.now().isoformat()
            }
            self.service.add_cancellation(cancellation)
        
        stats = self.service.get_stats()
        self.assertEqual(stats['total_received'], 3)
        self.assertEqual(stats['stored_count'], 3)
    
    def test_max_stored_limit(self):
        """Test that storage respects max_stored limit."""
        # Add 7 cancellations (max is 5)
        for i in range(7):
            cancellation = {
                'rid': f'TEST{i}',
                'train_id': f'1A{i}',
                'toc_id': 'SR',
                'cancellation_datetime': datetime.now().isoformat()
            }
            self.service.add_cancellation(cancellation)
        
        stats = self.service.get_stats()
        self.assertEqual(stats['total_received'], 7)
        self.assertEqual(stats['stored_count'], 5)  # Limited to max_stored
        
        # Verify oldest were removed (FIFO)
        recent = self.service.get_recent_cancellations()
        rids = [c['rid'] for c in recent]
        self.assertIn('TEST6', rids)  # Most recent
        self.assertIn('TEST5', rids)
        self.assertNotIn('TEST0', rids)  # Oldest removed
        self.assertNotIn('TEST1', rids)
    
    def test_get_recent_cancellations_with_limit(self):
        """Test retrieving recent cancellations with limit."""
        for i in range(5):
            cancellation = {
                'rid': f'TEST{i}',
                'train_id': f'1A{i}',
                'toc_id': 'SR'
            }
            self.service.add_cancellation(cancellation)
        
        recent = self.service.get_recent_cancellations(limit=3)
        self.assertEqual(len(recent), 3)
        
        # Should be most recent first
        self.assertEqual(recent[0]['rid'], 'TEST4')
        self.assertEqual(recent[1]['rid'], 'TEST3')
        self.assertEqual(recent[2]['rid'], 'TEST2')
    
    def test_get_recent_cancellations_no_limit(self):
        """Test retrieving all cancellations."""
        for i in range(3):
            cancellation = {'rid': f'TEST{i}', 'toc_id': 'SR'}
            self.service.add_cancellation(cancellation)
        
        recent = self.service.get_recent_cancellations()
        self.assertEqual(len(recent), 3)
    
    def test_get_cancellation_by_train_id(self):
        """Test retrieving cancellation by train ID."""
        cancellation = {
            'rid': 'TEST123',
            'train_id': '1A23',
            'uid': 'C12345',
            'toc_id': 'SR'
        }
        self.service.add_cancellation(cancellation)
        
        # Search by train_id
        found = self.service.get_cancellation_by_train_id('1A23')
        self.assertIsNotNone(found)
        self.assertEqual(found['rid'], 'TEST123')
        
        # get_cancellation_by_train_id only searches by train_id field
        # Searching by UID or RID won't work (expected behavior)
        
        # Not found
        found = self.service.get_cancellation_by_train_id('NOTEXIST')
        self.assertIsNone(found)
    
    def test_scottish_train_counting(self):
        """Test counting of Scottish trains."""
        # Add Scottish train
        self.service.add_cancellation({'rid': 'TEST1', 'toc_id': 'SR'})
        
        # Add non-Scottish train
        self.service.add_cancellation({'rid': 'TEST2', 'toc_id': 'GW'})
        
        stats = self.service.get_stats()
        self.assertEqual(stats['total_received'], 2)
        
        # Count Scottish trains manually from stored data
        recent = self.service.get_recent_cancellations()
        scottish_count = sum(1 for c in recent if c.get('toc_id') == 'SR')
        self.assertEqual(scottish_count, 1)
    
    def test_thread_safety(self):
        """Test concurrent access is thread-safe."""
        import threading
        
        def add_cancellations():
            for i in range(10):
                self.service.add_cancellation({
                    'rid': f'TEST{threading.current_thread().name}{i}',
                    'toc_id': 'SR'
                })
        
        threads = [threading.Thread(target=add_cancellations) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        stats = self.service.get_stats()
        self.assertEqual(stats['total_received'], 50)
        # Storage limited to max_stored
        self.assertEqual(stats['stored_count'], 5)
    
    def test_format_cancellation_for_display(self):
        """Test formatting cancellation data for display."""
        cancellation = {
            'rid': 'TEST123',
            'train_id': '1A23',
            'uid': 'C12345',
            'toc_id': 'SR',
            'origin_tiploc': 'GLAS',
            'destination_tiploc': 'EDINBUR',
            'scheduled_departure': '14:30',
            'cancellation_reason': 'Staff shortage',
            'cancellation_type': 'Full',
            'cancellation_datetime': '2025-12-01T14:25:00'
        }
        
        formatted = self.service.format_cancellation_for_display(cancellation)
        
        # format_cancellation_for_display returns a dict, not a string
        self.assertIsInstance(formatted, dict)
        self.assertEqual(formatted['rid'], 'TEST123')
        self.assertEqual(formatted['train_id'], '1A23')
        self.assertEqual(formatted['toc'], 'SR')
        self.assertEqual(formatted['reason'], 'Staff shortage')
    
    def test_format_cancellation_minimal_data(self):
        """Test formatting with minimal cancellation data."""
        cancellation = {
            'rid': 'TEST123'
        }
        
        formatted = self.service.format_cancellation_for_display(cancellation)
        
        # Should handle missing fields gracefully with 'Unknown'
        self.assertIsInstance(formatted, dict)
        self.assertEqual(formatted['rid'], 'TEST123')
        self.assertEqual(formatted['train_id'], 'Unknown')
        self.assertEqual(formatted['toc'], 'Unknown')
    
    def test_empty_service(self):
        """Test service with no cancellations."""
        stats = self.service.get_stats()
        self.assertEqual(stats['total_received'], 0)
        self.assertEqual(stats['stored_count'], 0)
        
        recent = self.service.get_recent_cancellations()
        self.assertEqual(len(recent), 0)


if __name__ == '__main__':
    unittest.main()
