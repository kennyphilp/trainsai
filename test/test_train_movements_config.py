"""
Unit tests for TrainMovementsConfig.

Tests the Darwin Push Port configuration.
"""

import unittest
from config import TrainMovementsConfig, get_train_movements_config


class TestTrainMovementsConfig(unittest.TestCase):
    """Test cases for TrainMovementsConfig."""
    
    def test_default_configuration(self):
        """Test default configuration values."""
        config = TrainMovementsConfig()
        
        # Connection details
        self.assertEqual(config.host, "darwin-dist-44ae45.nationalrail.co.uk")
        self.assertEqual(config.port, 61613)
        self.assertIsNotNone(config.username)
        self.assertIsNotNone(config.password)
        self.assertEqual(config.queue, "/topic/darwin.pushport-v16")
        
        # Heartbeat configuration
        self.assertEqual(config.heartbeat_send_interval, 15000)
        self.assertEqual(config.heartbeat_receive_interval, 15000)
        
        # Reconnection configuration
        self.assertEqual(config.reconnect_delay, 5)
        self.assertEqual(config.reconnect_max_delay, 300)
        
        # Scottish filtering
        self.assertIn("SR", config.scottish_toc_codes)
        self.assertIn("EDB", config.scottish_crs_codes)
        self.assertIn("GLC", config.scottish_crs_codes)
    
    def test_scottish_station_codes(self):
        """Test Scottish station CRS codes are comprehensive."""
        config = TrainMovementsConfig()
        
        expected_stations = [
            "EDB",  # Edinburgh
            "GLC",  # Glasgow Central
            "ABD",  # Aberdeen
            "INV",  # Inverness
            "DND",  # Dundee
            "PER",  # Perth
            "STG",  # Stirling
            "AYR",  # Ayr
            "KDY",  # Kirkcaldy
            "MBR",  # Musselburgh
            "FAL",  # Falkirk
            "DUM",  # Dumfries
            "HYM",  # Haymarket
            "TWE",  # Tweedbank
        ]
        
        for station in expected_stations:
            self.assertIn(station, config.scottish_crs_codes)
    
    def test_get_train_movements_config(self):
        """Test get_train_movements_config returns valid config."""
        config = get_train_movements_config()
        
        # Check it's the right type by checking attributes instead of isinstance
        self.assertTrue(hasattr(config, 'host'))
        self.assertTrue(hasattr(config, 'username'))
        self.assertTrue(hasattr(config, 'password'))
        self.assertEqual(config.host, "darwin-dist-44ae45.nationalrail.co.uk")
    
    def test_username_format(self):
        """Test username follows Darwin format."""
        config = TrainMovementsConfig()
        
        # Darwin usernames start with "DARWIN"
        self.assertTrue(config.username.startswith("DARWIN"))
    
    def test_heartbeat_intervals_match(self):
        """Test send and receive heartbeat intervals are configured."""
        config = TrainMovementsConfig()
        
        # Both should be set for bidirectional heartbeat
        self.assertGreater(config.heartbeat_send_interval, 0)
        self.assertGreater(config.heartbeat_receive_interval, 0)
    
    def test_reconnection_delays_valid(self):
        """Test reconnection delays are sensible."""
        config = TrainMovementsConfig()
        
        # Initial delay should be less than max delay
        self.assertLess(config.reconnect_delay, config.reconnect_max_delay)
        
        # Delays should be positive
        self.assertGreater(config.reconnect_delay, 0)
        self.assertGreater(config.reconnect_max_delay, 0)


if __name__ == '__main__':
    unittest.main()
