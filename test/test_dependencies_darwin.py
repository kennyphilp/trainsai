"""
Unit tests for Darwin Push Port integration in dependencies container.

Tests the dependency injection of cancellations service and train movements client.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from dependencies import ServiceContainer, get_container


class TestDarwinDependencies(unittest.TestCase):
    """Test cases for Darwin Push Port dependencies."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.container = ServiceContainer()
    
    def tearDown(self):
        """Clean up after tests."""
        self.container.reset()
    
    def test_get_cancellations_service(self):
        """Test getting cancellations service from container."""
        service = self.container.get_cancellations_service()
        
        self.assertIsNotNone(service)
        self.assertEqual(service.max_stored, 50)
    
    def test_cancellations_service_singleton(self):
        """Test cancellations service is singleton."""
        service1 = self.container.get_cancellations_service()
        service2 = self.container.get_cancellations_service()
        
        self.assertIs(service1, service2)
    
    @patch('dependencies.TrainMovementsClient')
    def test_get_train_movements_client(self, mock_client_class):
        """Test getting train movements client from container."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        client = self.container.get_train_movements_client()
        
        self.assertIsNotNone(client)
        mock_client.start.assert_called_once()
    
    @patch('dependencies.TrainMovementsClient')
    def test_train_movements_client_singleton(self, mock_client_class):
        """Test train movements client is singleton."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        client1 = self.container.get_train_movements_client()
        client2 = self.container.get_train_movements_client()
        
        self.assertIs(client1, client2)
        # Should only be started once
        self.assertEqual(mock_client.start.call_count, 1)
    
    @patch('dependencies.TrainMovementsClient')
    def test_train_movements_client_uses_cancellations_service(self, mock_client_class):
        """Test train movements client uses cancellations service."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Get cancellations service first
        cancellations_service = self.container.get_cancellations_service()
        
        # Get client - should use same cancellations service
        self.container.get_train_movements_client()
        
        # Verify client was created with config and callback
        mock_client_class.assert_called_once()
        args, kwargs = mock_client_class.call_args
        
        # First arg is config
        self.assertIsNotNone(args[0])
        
        # Second arg is callback
        callback = args[1]
        self.assertIsNotNone(callback)
        
        # Test callback adds to cancellations service
        test_cancellation = {'rid': 'TEST123', 'toc_id': 'SR'}
        callback(test_cancellation)
        
        stats = cancellations_service.get_stats()
        self.assertEqual(stats['total_received'], 1)
    
    @patch('dependencies.TrainMovementsClient')
    def test_reset_stops_train_movements_client(self, mock_client_class):
        """Test reset stops train movements client."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Get client (starts it)
        self.container.get_train_movements_client()
        
        # Reset container
        self.container.reset()
        
        # Verify client was stopped
        mock_client.stop.assert_called_once()
    
    @patch('dependencies.TrainMovementsClient')
    def test_reset_handles_client_stop_error(self, mock_client_class):
        """Test reset handles errors when stopping client."""
        mock_client = Mock()
        mock_client.stop.side_effect = Exception("Stop failed")
        mock_client_class.return_value = mock_client
        
        # Get client
        self.container.get_train_movements_client()
        
        # Reset should not raise exception
        try:
            self.container.reset()
        except Exception as e:
            self.fail(f"Reset raised exception: {e}")
    
    @patch('dependencies.TrainMovementsClient')
    def test_reset_clears_all_darwin_services(self, mock_client_class):
        """Test reset clears cancellations service and client."""
        mock_client1 = Mock()
        mock_client2 = Mock()
        mock_client_class.side_effect = [mock_client1, mock_client2]
        
        # Get services
        service1 = self.container.get_cancellations_service()
        client1 = self.container.get_train_movements_client()
        
        # Reset
        self.container.reset()
        
        # Get again - should be new instances
        service2 = self.container.get_cancellations_service()
        client2 = self.container.get_train_movements_client()
        
        self.assertIsNot(service1, service2)
        self.assertIsNot(client1, client2)
    
    def test_get_container_returns_singleton(self):
        """Test get_container returns global singleton."""
        container1 = get_container()
        container2 = get_container()
        
        self.assertIs(container1, container2)
    
    @patch('dependencies.TrainMovementsClient')
    def test_cancellation_callback_integration(self, mock_client_class):
        """Test end-to-end cancellation callback integration."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Get client - this sets up the callback
        client = self.container.get_train_movements_client()
        
        # Extract the callback that was passed to the client
        args, kwargs = mock_client_class.call_args
        callback = args[1]
        
        # Simulate Darwin sending cancellations
        cancellations = [
            {'rid': 'TEST1', 'train_id': '1A01', 'toc_id': 'SR'},
            {'rid': 'TEST2', 'train_id': '1A02', 'toc_id': 'SR'},
            {'rid': 'TEST3', 'train_id': '1A03', 'toc_id': 'GW'},
        ]
        
        for cancellation in cancellations:
            callback(cancellation)
        
        # Verify they're stored in cancellations service
        service = self.container.get_cancellations_service()
        stats = service.get_stats()
        
        self.assertEqual(stats['total_received'], 3)
        self.assertEqual(stats['stored_count'], 3)
        
        # Count Scottish trains manually (service doesn't track this separately)
        recent = service.get_recent_cancellations()
        scottish_count = sum(1 for c in recent if c.get('toc_id') == 'SR')
        self.assertEqual(scottish_count, 2)
        
        # Verify we can retrieve them
        self.assertEqual(len(recent), 3)
        
        rids = [c['rid'] for c in recent]
        self.assertIn('TEST1', rids)
        self.assertIn('TEST2', rids)
        self.assertIn('TEST3', rids)


if __name__ == '__main__':
    unittest.main()
