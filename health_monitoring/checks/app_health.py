"""Application health check implementation."""

import time
import logging
from datetime import datetime
from typing import Dict, Any

from .base_check import BaseHealthCheck
from ..models import HealthResult, HealthStatus

logger = logging.getLogger(__name__)


class ApplicationHealthCheck(BaseHealthCheck):
    """Check application-specific health."""
    
    def __init__(self, config, agents_dict=None):
        """Initialize application health check.
        
        Args:
            config: Application configuration object
            agents_dict: Dictionary of active agents (for session monitoring)
        """
        super().__init__("application", timeout=1.0)
        self.config = config
        self.agents_dict = agents_dict or {}
    
    async def check(self) -> HealthResult:
        """Check application health."""
        start_time = time.time()
        details = {}
        
        try:
            # Check session store health
            session_count = len(self.agents_dict)
            details['active_sessions'] = session_count
            details['max_sessions'] = self.config.max_sessions
            details['session_utilization'] = round(session_count / max(self.config.max_sessions, 1), 3)
            
            # Check memory usage if psutil is available
            try:
                import psutil
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                details['memory_usage_mb'] = round(memory_mb, 2)
                details['memory_limit_mb'] = 512  # Configurable limit
                details['memory_utilization'] = round(memory_mb / 512, 3)
            except ImportError:
                details['memory_usage_mb'] = 'unavailable'
                details['memory_limit_mb'] = 'unavailable'
                details['memory_utilization'] = 'unavailable'
            
            # Check for recent errors from logs
            error_count = self._get_recent_error_count()
            details['recent_errors'] = error_count
            details['error_threshold'] = 10
            
            # Check configuration health
            missing_keys = self.config.validate_required_keys()
            details['missing_config_keys'] = missing_keys
            details['config_complete'] = len(missing_keys) == 0
            
            # Determine status
            status = HealthStatus.HEALTHY
            message = "Application healthy"
            
            if isinstance(details.get('memory_usage_mb'), (int, float)) and details['memory_usage_mb'] > 512:
                status = HealthStatus.DEGRADED
                message = f"High memory usage: {details['memory_usage_mb']}MB"
            elif error_count > 10:
                status = HealthStatus.DEGRADED
                message = f"Elevated error rate: {error_count} errors"
            elif session_count >= self.config.max_sessions * 0.9:
                status = HealthStatus.DEGRADED
                message = f"Session capacity nearly full: {session_count}/{self.config.max_sessions}"
            elif missing_keys:
                status = HealthStatus.DEGRADED
                message = f"Missing configuration keys: {', '.join(missing_keys[:3])}"
                
            return HealthResult(
                name=self.name,
                status=status,
                message=message,
                details=details,
                duration_ms=round((time.time() - start_time) * 1000, 2),
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Application health check failed: {e}")
            return HealthResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                details={'error': str(e), 'error_type': type(e).__name__},
                duration_ms=round((time.time() - start_time) * 1000, 2),
                timestamp=datetime.now()
            )
    
    def _get_recent_error_count(self) -> int:
        """Get count of recent errors from logs.
        
        This is a simplified implementation. In production, you might
        want to parse actual log files or use a logging aggregator.
        """
        try:
            # Check if there's a logging handler that tracks errors
            app_logger = logging.getLogger('app')
            error_count = 0
            
            # Simple heuristic: check if any handlers have recent error records
            # This is basic - in production you'd want more sophisticated error tracking
            for handler in app_logger.handlers:
                if hasattr(handler, 'error_count'):
                    error_count += getattr(handler, 'error_count', 0)
            
            return error_count
            
        except Exception:
            # If we can't check error count, assume it's okay
            return 0