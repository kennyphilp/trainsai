"""Base health check class."""

import asyncio
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional

from ..models import HealthResult, HealthStatus


class BaseHealthCheck(ABC):
    """Abstract base class for health checks."""
    
    def __init__(self, name: str, timeout: float = 5.0):
        """Initialize the health check.
        
        Args:
            name: Name of the health check
            timeout: Maximum time allowed for the check in seconds
        """
        self.name = name
        self.timeout = timeout
        self.last_result: Optional[HealthResult] = None
        self.last_check_time: Optional[datetime] = None
    
    @abstractmethod
    async def check(self) -> HealthResult:
        """Perform the health check.
        
        Returns:
            HealthResult with status and details
        """
        pass
    
    def should_check(self, cache_ttl: timedelta) -> bool:
        """Determine if check should run based on cache TTL.
        
        Args:
            cache_ttl: Time to live for cached results
            
        Returns:
            True if check should run, False if cached result is still valid
        """
        if not self.last_check_time:
            return True
        return datetime.now() - self.last_check_time > cache_ttl
    
    def get_cached_result(self) -> Optional[HealthResult]:
        """Get the last cached result if available."""
        return self.last_result
    
    async def run_with_timeout(self) -> HealthResult:
        """Run the health check with timeout protection."""
        start_time = time.time()
        
        try:
            result = await asyncio.wait_for(self.check(), timeout=self.timeout)
            self.last_result = result
            self.last_check_time = datetime.now()
            return result
        except asyncio.TimeoutError:
            return HealthResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check timed out after {self.timeout}s",
                details={'error': 'timeout', 'timeout_seconds': self.timeout},
                duration_ms=self.timeout * 1000,
                timestamp=datetime.now()
            )
        except Exception as e:
            return HealthResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed with exception: {str(e)}",
                details={'error': str(e), 'error_type': type(e).__name__},
                duration_ms=round((time.time() - start_time) * 1000, 2),
                timestamp=datetime.now()
            )