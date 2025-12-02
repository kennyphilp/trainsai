"""System resource health check implementation."""

import time
from datetime import datetime

from .base_check import BaseHealthCheck
from ..models import HealthResult, HealthStatus


class SystemHealthCheck(BaseHealthCheck):
    """Check system resource health."""
    
    def __init__(self):
        """Initialize system health check."""
        super().__init__("system", timeout=2.0)
    
    async def check(self) -> HealthResult:
        """Check system health."""
        start_time = time.time()
        details = {}
        
        try:
            # Try to import psutil for system monitoring
            try:
                import psutil
                
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=0.1)
                details['cpu_percent'] = round(cpu_percent, 1)
                details['cpu_count'] = psutil.cpu_count()
                
                # Memory usage
                memory = psutil.virtual_memory()
                details['memory_total_gb'] = round(memory.total / (1024**3), 2)
                details['memory_available_gb'] = round(memory.available / (1024**3), 2)
                details['memory_percent_used'] = round(memory.percent, 1)
                
                # Disk usage for current directory
                disk = psutil.disk_usage('.')
                details['disk_total_gb'] = round(disk.total / (1024**3), 2)
                details['disk_free_gb'] = round(disk.free / (1024**3), 2)
                details['disk_percent_used'] = round((1 - disk.free / disk.total) * 100, 1)
                
                # Load average (Unix-like systems only)
                try:
                    load_avg = psutil.getloadavg()
                    details['load_average'] = {
                        '1min': round(load_avg[0], 2),
                        '5min': round(load_avg[1], 2),
                        '15min': round(load_avg[2], 2)
                    }
                except (AttributeError, OSError):
                    details['load_average'] = 'unavailable'
                
                # Process information
                process = psutil.Process()
                details['process_memory_mb'] = round(process.memory_info().rss / (1024**2), 2)
                details['process_cpu_percent'] = round(process.cpu_percent(), 1)
                
                # Determine status based on thresholds
                status = HealthStatus.HEALTHY
                message = "System resources healthy"
                
                if cpu_percent > 80:
                    status = HealthStatus.DEGRADED
                    message = f"High CPU usage: {cpu_percent}%"
                elif memory.percent > 85:
                    status = HealthStatus.DEGRADED
                    message = f"High memory usage: {memory.percent}%"
                elif details['disk_percent_used'] > 90:
                    status = HealthStatus.DEGRADED
                    message = f"Low disk space: {details['disk_percent_used']}% used"
                elif isinstance(details.get('load_average'), dict):
                    load_1min = details['load_average']['1min']
                    if load_1min > details['cpu_count'] * 2:
                        status = HealthStatus.DEGRADED
                        message = f"High system load: {load_1min}"
                
            except ImportError:
                # psutil not available, provide basic info
                details['psutil_available'] = False
                details['message'] = 'System monitoring unavailable (psutil not installed)'
                status = HealthStatus.DEGRADED
                message = "Limited system monitoring available"
            
            return HealthResult(
                name=self.name,
                status=status,
                message=message,
                details=details,
                duration_ms=round((time.time() - start_time) * 1000, 2),
                timestamp=datetime.now()
            )
            
        except Exception as e:
            return HealthResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"System health check failed: {str(e)}",
                details={'error': str(e), 'error_type': type(e).__name__},
                duration_ms=round((time.time() - start_time) * 1000, 2),
                timestamp=datetime.now()
            )