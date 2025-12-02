"""Unit tests for health monitoring system."""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import tempfile
import os
import sys

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from health_monitoring.models import HealthStatus, HealthResult
from health_monitoring.checks.base_check import BaseHealthCheck
from health_monitoring.checks.app_health import ApplicationHealthCheck
from health_monitoring.checks.database_check import DatabaseHealthCheck
from health_monitoring.checks.system_check import SystemHealthCheck
from health_monitoring.health_manager import HealthCheckManager


class TestHealthResult:
    """Test HealthResult data class."""
    
    def test_creation(self):
        """Test HealthResult creation."""
        result = HealthResult(
            status=HealthStatus.HEALTHY,
            message="All good",
            details={"key": "value"}
        )
        
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "All good"
        assert result.details == {"key": "value"}
        assert result.is_healthy is True
        assert isinstance(result.timestamp, datetime)
        assert result.duration_ms >= 0
    
    def test_healthy_status(self):
        """Test is_healthy property for different statuses."""
        healthy = HealthResult(HealthStatus.HEALTHY, "OK")
        degraded = HealthResult(HealthStatus.DEGRADED, "Slow")
        unhealthy = HealthResult(HealthStatus.UNHEALTHY, "Error")
        
        assert healthy.is_healthy is True
        assert degraded.is_healthy is False
        assert unhealthy.is_healthy is False
    
    def test_to_dict(self):
        """Test dictionary serialization."""
        result = HealthResult(
            status=HealthStatus.HEALTHY,
            message="Test message",
            details={"count": 5}
        )
        
        data = result.to_dict()
        
        assert data['status'] == 'healthy'
        assert data['message'] == "Test message"
        assert data['details'] == {"count": 5}
        assert 'timestamp' in data
        assert 'duration_ms' in data


class TestBaseHealthCheck:
    """Test abstract BaseHealthCheck class."""
    
    def test_cannot_instantiate_abstract(self):
        """Test that abstract class cannot be instantiated."""
        with pytest.raises(TypeError):
            BaseHealthCheck()
    
    def test_concrete_implementation(self):
        """Test concrete implementation works."""
        
        class TestCheck(BaseHealthCheck):
            async def check(self):
                return HealthResult(HealthStatus.HEALTHY, "Test OK")
        
        check = TestCheck()
        assert check.name == "TestCheck"
    
    @pytest.mark.asyncio
    async def test_execute_with_timeout(self):
        """Test execute method with timeout."""
        
        class FastCheck(BaseHealthCheck):
            async def check(self):
                return HealthResult(HealthStatus.HEALTHY, "Fast")
        
        class SlowCheck(BaseHealthCheck):
            async def check(self):
                await asyncio.sleep(0.1)
                return HealthResult(HealthStatus.HEALTHY, "Slow")
        
        # Fast check should succeed
        fast_check = FastCheck()
        result = await fast_check.execute(timeout=1.0)
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "Fast"
        
        # Slow check should timeout
        slow_check = SlowCheck()
        result = await slow_check.execute(timeout=0.05)
        assert result.status == HealthStatus.UNHEALTHY
        assert "timeout" in result.message.lower()


class TestApplicationHealthCheck:
    """Test ApplicationHealthCheck implementation."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration."""
        config = Mock()
        config.max_memory_mb = 500
        return config
    
    @pytest.fixture
    def mock_agents(self):
        """Mock agents dictionary."""
        return {
            'agent1': Mock(session_count=5),
            'agent2': Mock(session_count=3)
        }
    
    def test_initialization(self, mock_config):
        """Test initialization."""
        check = ApplicationHealthCheck(mock_config)
        assert check.name == "ApplicationHealthCheck"
        assert check.config == mock_config
    
    @pytest.mark.asyncio
    async def test_healthy_check(self, mock_config, mock_agents):
        """Test healthy application state."""
        with patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.Process') as mock_process:
            
            # Mock memory usage under limit
            mock_memory.return_value = Mock(
                total=1024 * 1024 * 1024,  # 1GB
                used=200 * 1024 * 1024     # 200MB
            )
            
            mock_proc = Mock()
            mock_proc.memory_info.return_value = Mock(
                rss=100 * 1024 * 1024  # 100MB
            )
            mock_process.return_value = mock_proc
            
            check = ApplicationHealthCheck(mock_config, mock_agents)
            result = await check.check()
            
            assert result.status == HealthStatus.HEALTHY
            assert result.details['active_sessions'] == 8
            assert result.details['memory_usage_mb'] == 100
    
    @pytest.mark.asyncio
    async def test_degraded_memory(self, mock_config, mock_agents):
        """Test degraded state due to high memory usage."""
        with patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.Process') as mock_process:
            
            # Mock high memory usage
            mock_memory.return_value = Mock(
                total=1024 * 1024 * 1024,  # 1GB
                used=800 * 1024 * 1024     # 800MB
            )
            
            mock_proc = Mock()
            mock_proc.memory_info.return_value = Mock(
                rss=600 * 1024 * 1024  # 600MB (above 500MB limit)
            )
            mock_process.return_value = mock_proc
            
            check = ApplicationHealthCheck(mock_config, mock_agents)
            result = await check.check()
            
            assert result.status == HealthStatus.DEGRADED
            assert "memory usage high" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_no_agents(self, mock_config):
        """Test with no agents dictionary."""
        check = ApplicationHealthCheck(mock_config, None)
        
        with patch('psutil.virtual_memory'), \
             patch('psutil.Process'):
            
            result = await check.check()
            assert result.details['active_sessions'] == 0


class TestDatabaseHealthCheck:
    """Test DatabaseHealthCheck implementation."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary SQLite database."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        os.unlink(path)
    
    @pytest.fixture
    def mock_config(self, temp_db):
        """Mock configuration with temp database."""
        config = Mock()
        config.database_url = f"sqlite:///{temp_db}"
        return config
    
    @pytest.mark.asyncio
    async def test_healthy_database(self, mock_config):
        """Test healthy database connection."""
        check = DatabaseHealthCheck(mock_config)
        result = await check.check()
        
        assert result.status == HealthStatus.HEALTHY
        assert "successfully" in result.message.lower()
        assert result.details['database_type'] == 'sqlite'
    
    @pytest.mark.asyncio
    async def test_invalid_database(self):
        """Test invalid database configuration."""
        config = Mock()
        config.database_url = "sqlite:///nonexistent/path/db.sqlite"
        
        check = DatabaseHealthCheck(config)
        result = await check.check()
        
        assert result.status == HealthStatus.UNHEALTHY
        assert "failed" in result.message.lower()


class TestSystemHealthCheck:
    """Test SystemHealthCheck implementation."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration."""
        config = Mock()
        config.max_cpu_percent = 80.0
        config.max_memory_percent = 85.0
        return config
    
    @pytest.mark.asyncio
    async def test_healthy_system(self, mock_config):
        """Test healthy system state."""
        with patch('psutil.cpu_percent', return_value=50.0), \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk:
            
            mock_memory.return_value = Mock(percent=60.0)
            mock_disk.return_value = Mock(percent=40.0)
            
            check = SystemHealthCheck(mock_config)
            result = await check.check()
            
            assert result.status == HealthStatus.HEALTHY
            assert result.details['cpu_percent'] == 50.0
            assert result.details['memory_percent'] == 60.0
            assert result.details['disk_percent'] == 40.0
    
    @pytest.mark.asyncio
    async def test_high_cpu(self, mock_config):
        """Test degraded state due to high CPU."""
        with patch('psutil.cpu_percent', return_value=90.0), \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk:
            
            mock_memory.return_value = Mock(percent=60.0)
            mock_disk.return_value = Mock(percent=40.0)
            
            check = SystemHealthCheck(mock_config)
            result = await check.check()
            
            assert result.status == HealthStatus.DEGRADED
            assert "high cpu" in result.message.lower()


class TestHealthCheckManager:
    """Test HealthCheckManager orchestration."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration."""
        config = Mock()
        config.health_cache_timeout = 30
        config.max_memory_mb = 500
        config.max_cpu_percent = 80.0
        config.max_memory_percent = 85.0
        config.database_url = "sqlite:///:memory:"
        return config
    
    @pytest.fixture
    def mock_agents(self):
        """Mock agents dictionary."""
        return {'agent1': Mock(session_count=2)}
    
    def test_initialization(self, mock_config, mock_agents):
        """Test manager initialization."""
        manager = HealthCheckManager(mock_config, mock_agents)
        
        assert len(manager.checks) == 3  # app, database, system
        assert 'application' in manager.checks
        assert 'database' in manager.checks
        assert 'system' in manager.checks
    
    @pytest.mark.asyncio
    async def test_run_all_checks(self, mock_config, mock_agents):
        """Test running all health checks."""
        manager = HealthCheckManager(mock_config, mock_agents)
        
        with patch.object(ApplicationHealthCheck, 'execute') as mock_app, \
             patch.object(DatabaseHealthCheck, 'execute') as mock_db, \
             patch.object(SystemHealthCheck, 'execute') as mock_sys:
            
            # Mock successful results
            mock_app.return_value = HealthResult(HealthStatus.HEALTHY, "App OK")
            mock_db.return_value = HealthResult(HealthStatus.HEALTHY, "DB OK")
            mock_sys.return_value = HealthResult(HealthStatus.HEALTHY, "System OK")
            
            results = await manager.run_checks()
            
            assert len(results) == 3
            assert all(result.status == HealthStatus.HEALTHY for result in results.values())
    
    @pytest.mark.asyncio
    async def test_run_specific_checks(self, mock_config, mock_agents):
        """Test running specific health checks."""
        manager = HealthCheckManager(mock_config, mock_agents)
        
        with patch.object(ApplicationHealthCheck, 'execute') as mock_app:
            mock_app.return_value = HealthResult(HealthStatus.HEALTHY, "App OK")
            
            results = await manager.run_checks(['application'])
            
            assert len(results) == 1
            assert 'application' in results
    
    def test_update_agents(self, mock_config, mock_agents):
        """Test updating agents dictionary."""
        manager = HealthCheckManager(mock_config, mock_agents)
        
        new_agents = {'agent2': Mock(session_count=5)}
        manager.update_agents_dict(new_agents)
        
        # Check that application health check has new agents
        app_check = manager.checks['application']
        assert app_check.agents_dict == new_agents
    
    def test_get_overall_status(self, mock_config):
        """Test overall status calculation."""
        manager = HealthCheckManager(mock_config)
        
        # All healthy
        results = {
            'app': HealthResult(HealthStatus.HEALTHY, "OK"),
            'db': HealthResult(HealthStatus.HEALTHY, "OK")
        }
        assert manager.get_overall_status(results) == HealthStatus.HEALTHY
        
        # One degraded
        results['db'] = HealthResult(HealthStatus.DEGRADED, "Slow")
        assert manager.get_overall_status(results) == HealthStatus.DEGRADED
        
        # One unhealthy
        results['app'] = HealthResult(HealthStatus.UNHEALTHY, "Error")
        assert manager.get_overall_status(results) == HealthStatus.UNHEALTHY


if __name__ == '__main__':
    pytest.main([__file__])