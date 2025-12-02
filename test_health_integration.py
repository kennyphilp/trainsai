"""Simplified integration tests for health monitoring system."""

import pytest
from unittest.mock import Mock
from datetime import datetime
import time

# Test the health monitoring integration with the app
def test_health_monitoring_integration():
    """Test basic health monitoring integration."""
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    from health_monitoring.models import HealthStatus, HealthResult
    
    # Test HealthStatus enum
    assert HealthStatus.HEALTHY.value == "healthy"
    assert HealthStatus.DEGRADED.value == "degraded"
    assert HealthStatus.UNHEALTHY.value == "unhealthy"
    
    # Test HealthResult creation with all required parameters
    start_time = time.time()
    time.sleep(0.001)  # Small delay to ensure duration > 0
    end_time = time.time()
    
    result = HealthResult(
        name="test_check",
        status=HealthStatus.HEALTHY,
        message="All good",
        details={"key": "value"},
        duration_ms=(end_time - start_time) * 1000,
        timestamp=datetime.now()
    )
    
    assert result.name == "test_check"
    assert result.status == HealthStatus.HEALTHY
    assert result.message == "All good"
    assert result.details == {"key": "value"}
    assert result.is_healthy is True
    assert result.duration_ms > 0
    
    # Test serialization
    data = result.to_dict()
    assert data['status'] == 'healthy'
    assert 'timestamp' in data
    assert 'duration_ms' in data


def test_application_config_integration():
    """Test that our app config includes health monitoring settings."""
    from config import get_config
    
    config = get_config()
    
    # Check that our new health monitoring config attributes exist
    assert hasattr(config, 'health_cache_timeout')
    assert hasattr(config, 'max_memory_mb')
    assert hasattr(config, 'max_cpu_percent')
    assert hasattr(config, 'max_memory_percent')
    
    # Check default values
    assert config.health_cache_timeout == 30
    assert config.max_memory_mb == 500
    assert config.max_cpu_percent == 80.0
    assert config.max_memory_percent == 85.0


def test_health_routes_import():
    """Test that health routes can be imported."""
    try:
        from health_monitoring.health_routes import init_health_monitoring
        from health_integration import setup_health_monitoring
        assert callable(init_health_monitoring)
        assert callable(setup_health_monitoring)
    except ImportError as e:
        pytest.fail(f"Failed to import health monitoring routes: {e}")


if __name__ == '__main__':
    pytest.main([__file__, "-v"])