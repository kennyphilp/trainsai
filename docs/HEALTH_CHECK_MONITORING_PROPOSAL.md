# Health Check Monitoring Integration Proposal

**Date:** 2 December 2025  
**Branch:** app_review  
**Target:** Phase II Implementation  
**Priority:** High (Priority 1 - Enhanced Monitoring)

---

## Overview

This proposal outlines the implementation of comprehensive health check monitoring integration for the ScotRail Train Travel Advisor application. The current basic health endpoint will be enhanced into a production-grade monitoring system supporting multiple check types, external dependencies, and integration with monitoring platforms.

---

## Current State Analysis

### Existing Health Check (`/api/health`)
```python
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'ScotRail Train Travel Advisor',
        'active_sessions': len(agents)
    })
```

**Limitations:**
- Only checks if Flask app is responding
- No validation of external dependencies
- No detailed component status
- No integration with monitoring systems
- No alerting capabilities

---

## Proposed Implementation

### 1. Enhanced Health Check Architecture

#### Core Components
```
┌─────────────────────────────────────────┐
│           Health Check Router           │
├─────────────────────────────────────────┤
│  /api/health/live    (Liveness Probe)   │
│  /api/health/ready   (Readiness Probe)  │
│  /api/health/deep    (Deep Check)       │
│  /api/health/metrics (Metrics Export)   │
└─────────────────────────────────────────┘
                      │
┌─────────────────────────────────────────┐
│          Health Check Manager           │
├─────────────────────────────────────────┤
│ • Orchestrates all health checks        │
│ • Caches results with TTL              │
│ • Manages check timeouts               │
│ • Handles parallel execution           │
└─────────────────────────────────────────┘
                      │
┌─────────────────────────────────────────┐
│         Individual Health Checks        │
├─────────────────────────────────────────┤
│ • Application Health                   │
│ • Database Connectivity               │
│ • External API Health                 │
│ • System Resource Check               │
│ • Session Store Health                │
│ • OpenAI API Connectivity             │
└─────────────────────────────────────────┘
```

### 2. Implementation Structure

#### A. Health Check Types

**Liveness Probe** (`/api/health/live`)
- Basic application responsiveness
- Memory usage within limits
- No critical errors in last 5 minutes
- Response time: <100ms

**Readiness Probe** (`/api/health/ready`)
- All external dependencies available
- Database connectivity confirmed
- API keys validated
- Configuration loaded correctly
- Response time: <1000ms

**Deep Health Check** (`/api/health/deep`)
- Comprehensive dependency validation
- Performance metrics collection
- Resource utilization analysis
- Business logic validation
- Response time: <5000ms

#### B. File Structure
```
health_monitoring/
├── __init__.py
├── health_manager.py      # Core orchestration
├── checks/
│   ├── __init__.py
│   ├── base_check.py      # Abstract base class
│   ├── app_health.py      # Application health
│   ├── database_check.py  # Database connectivity
│   ├── api_health.py      # External API health
│   ├── openai_check.py    # OpenAI connectivity
│   └── system_check.py    # System resources
├── models.py              # Health check data models
├── metrics.py             # Metrics collection
└── alerting.py            # Alert notifications
```

### 3. Detailed Implementation

#### A. Base Health Check Class
```python
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

@dataclass
class HealthResult:
    """Result of a health check."""
    name: str
    status: HealthStatus
    message: str
    details: Dict[str, Any]
    duration_ms: float
    timestamp: datetime
    
class BaseHealthCheck(ABC):
    """Abstract base class for health checks."""
    
    def __init__(self, name: str, timeout: float = 5.0):
        self.name = name
        self.timeout = timeout
        self.last_result: Optional[HealthResult] = None
        self.last_check_time: Optional[datetime] = None
    
    @abstractmethod
    async def check(self) -> HealthResult:
        """Perform the health check."""
        pass
    
    def should_check(self, cache_ttl: timedelta) -> bool:
        """Determine if check should run based on cache TTL."""
        if not self.last_check_time:
            return True
        return datetime.now() - self.last_check_time > cache_ttl
```

#### B. Application Health Check
```python
class ApplicationHealthCheck(BaseHealthCheck):
    """Check application-specific health."""
    
    def __init__(self, app_instance, config):
        super().__init__("application", timeout=1.0)
        self.app = app_instance
        self.config = config
    
    async def check(self) -> HealthResult:
        """Check application health."""
        start_time = time.time()
        details = {}
        
        try:
            # Check session store health
            session_count = len(agents) if 'agents' in globals() else 0
            details['active_sessions'] = session_count
            details['max_sessions'] = self.config.max_sessions
            details['session_utilization'] = session_count / self.config.max_sessions
            
            # Check memory usage
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            details['memory_usage_mb'] = round(memory_mb, 2)
            details['memory_limit_mb'] = 512  # Configurable
            
            # Check for recent errors
            error_count = self._get_recent_error_count()
            details['recent_errors'] = error_count
            details['error_threshold'] = 10
            
            # Determine status
            status = HealthStatus.HEALTHY
            message = "Application healthy"
            
            if memory_mb > 512:
                status = HealthStatus.DEGRADED
                message = "High memory usage"
            elif error_count > 10:
                status = HealthStatus.DEGRADED
                message = "Elevated error rate"
            elif session_count >= self.config.max_sessions * 0.9:
                status = HealthStatus.DEGRADED
                message = "Session capacity nearly full"
                
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
                message=f"Health check failed: {str(e)}",
                details={'error': str(e)},
                duration_ms=round((time.time() - start_time) * 1000, 2),
                timestamp=datetime.now()
            )
```

#### C. External API Health Checks
```python
class OpenAIHealthCheck(BaseHealthCheck):
    """Check OpenAI API connectivity."""
    
    def __init__(self, openai_client):
        super().__init__("openai_api", timeout=10.0)
        self.client = openai_client
    
    async def check(self) -> HealthResult:
        """Check OpenAI API health."""
        start_time = time.time()
        
        try:
            # Simple API test
            response = await asyncio.wait_for(
                self._test_openai_connection(),
                timeout=self.timeout
            )
            
            details = {
                'api_responsive': True,
                'model_available': response.get('model_available', False),
                'rate_limit_remaining': response.get('rate_limit_remaining', 'unknown')
            }
            
            status = HealthStatus.HEALTHY if response['success'] else HealthStatus.DEGRADED
            message = response['message']
            
        except asyncio.TimeoutError:
            status = HealthStatus.UNHEALTHY
            message = "OpenAI API timeout"
            details = {'error': 'Connection timeout'}
        except Exception as e:
            status = HealthStatus.UNHEALTHY
            message = f"OpenAI API error: {str(e)}"
            details = {'error': str(e)}
            
        return HealthResult(
            name=self.name,
            status=status,
            message=message,
            details=details,
            duration_ms=round((time.time() - start_time) * 1000, 2),
            timestamp=datetime.now()
        )

class TrainAPIHealthCheck(BaseHealthCheck):
    """Check National Rail API health."""
    
    def __init__(self, train_tools):
        super().__init__("train_apis", timeout=15.0)
        self.train_tools = train_tools
    
    async def check(self) -> HealthResult:
        """Check train API health."""
        start_time = time.time()
        details = {}
        
        try:
            # Test LDBWS API
            ldbws_result = await self._test_ldbws_api()
            details['ldbws'] = ldbws_result
            
            # Test Disruptions API
            disruptions_result = await self._test_disruptions_api()
            details['disruptions'] = disruptions_result
            
            # Test Service Details API
            service_details_result = await self._test_service_details_api()
            details['service_details'] = service_details_result
            
            # Determine overall status
            healthy_apis = sum(1 for result in [ldbws_result, disruptions_result, service_details_result] 
                             if result['status'] == 'healthy')
            
            if healthy_apis == 3:
                status = HealthStatus.HEALTHY
                message = "All train APIs healthy"
            elif healthy_apis >= 2:
                status = HealthStatus.DEGRADED
                message = f"{healthy_apis}/3 train APIs healthy"
            else:
                status = HealthStatus.UNHEALTHY
                message = f"Only {healthy_apis}/3 train APIs healthy"
                
        except Exception as e:
            status = HealthStatus.UNHEALTHY
            message = f"Train API health check failed: {str(e)}"
            details = {'error': str(e)}
            
        return HealthResult(
            name=self.name,
            status=status,
            message=message,
            details=details,
            duration_ms=round((time.time() - start_time) * 1000, 2),
            timestamp=datetime.now()
        )
```

#### D. Health Check Manager
```python
class HealthCheckManager:
    """Manages all health checks."""
    
    def __init__(self, config):
        self.config = config
        self.checks: List[BaseHealthCheck] = []
        self.cache_ttl = timedelta(seconds=30)
        self._setup_checks()
    
    def _setup_checks(self):
        """Initialize all health checks."""
        from dependencies import get_container
        container = get_container()
        
        # Application health
        self.checks.append(ApplicationHealthCheck(
            app_instance=app,
            config=self.config
        ))
        
        # Database health
        self.checks.append(DatabaseHealthCheck(
            db_path=self.config.timetable_db_path
        ))
        
        # External API health
        self.checks.append(OpenAIHealthCheck(
            openai_client=container.get_openai_client()
        ))
        
        self.checks.append(TrainAPIHealthCheck(
            train_tools=container.get_train_tools()
        ))
        
        # System health
        self.checks.append(SystemHealthCheck())
    
    async def run_checks(self, check_types: List[str] = None) -> Dict[str, HealthResult]:
        """Run health checks."""
        if check_types is None:
            checks_to_run = self.checks
        else:
            checks_to_run = [c for c in self.checks if c.name in check_types]
        
        # Run checks in parallel
        tasks = []
        for check in checks_to_run:
            if check.should_check(self.cache_ttl):
                tasks.append(self._run_single_check(check))
            else:
                # Use cached result
                tasks.append(asyncio.create_task(self._get_cached_result(check)))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            check.name: result if not isinstance(result, Exception) else self._error_result(check.name, result)
            for check, result in zip(checks_to_run, results)
        }
    
    async def _run_single_check(self, check: BaseHealthCheck) -> HealthResult:
        """Run a single health check with timeout."""
        try:
            result = await asyncio.wait_for(check.check(), timeout=check.timeout)
            check.last_result = result
            check.last_check_time = datetime.now()
            return result
        except asyncio.TimeoutError:
            return HealthResult(
                name=check.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check timed out after {check.timeout}s",
                details={'error': 'timeout'},
                duration_ms=check.timeout * 1000,
                timestamp=datetime.now()
            )
```

#### E. Flask Integration
```python
# health_routes.py
from flask import Blueprint, jsonify, request
from health_monitoring import HealthCheckManager

health_bp = Blueprint('health', __name__, url_prefix='/api/health')
health_manager = None

def init_health_monitoring(app, config):
    """Initialize health monitoring."""
    global health_manager
    health_manager = HealthCheckManager(config)
    app.register_blueprint(health_bp)

@health_bp.route('/live')
async def liveness_probe():
    """Kubernetes liveness probe."""
    results = await health_manager.run_checks(['application'])
    app_health = results['application']
    
    if app_health.status == HealthStatus.UNHEALTHY:
        return jsonify({
            'status': 'unhealthy',
            'message': app_health.message
        }), 503
    
    return jsonify({
        'status': 'healthy',
        'timestamp': app_health.timestamp.isoformat()
    })

@health_bp.route('/ready')
async def readiness_probe():
    """Kubernetes readiness probe."""
    critical_checks = ['application', 'openai_api', 'train_apis']
    results = await health_manager.run_checks(critical_checks)
    
    unhealthy_checks = [
        name for name, result in results.items() 
        if result.status == HealthStatus.UNHEALTHY
    ]
    
    if unhealthy_checks:
        return jsonify({
            'status': 'not_ready',
            'failed_checks': unhealthy_checks,
            'details': {name: result.message for name, result in results.items()}
        }), 503
    
    degraded_checks = [
        name for name, result in results.items() 
        if result.status == HealthStatus.DEGRADED
    ]
    
    return jsonify({
        'status': 'ready' if not degraded_checks else 'ready_degraded',
        'degraded_checks': degraded_checks,
        'timestamp': datetime.now().isoformat()
    })

@health_bp.route('/deep')
async def deep_health_check():
    """Comprehensive health check."""
    results = await health_manager.run_checks()
    
    overall_status = 'healthy'
    if any(r.status == HealthStatus.UNHEALTHY for r in results.values()):
        overall_status = 'unhealthy'
    elif any(r.status == HealthStatus.DEGRADED for r in results.values()):
        overall_status = 'degraded'
    
    return jsonify({
        'status': overall_status,
        'timestamp': datetime.now().isoformat(),
        'checks': {
            name: {
                'status': result.status.value,
                'message': result.message,
                'duration_ms': result.duration_ms,
                'details': result.details
            }
            for name, result in results.items()
        }
    })

@health_bp.route('/metrics')
async def health_metrics():
    """Prometheus-style metrics."""
    results = await health_manager.run_checks()
    
    metrics = []
    for name, result in results.items():
        # Health status metric (1=healthy, 0.5=degraded, 0=unhealthy)
        status_value = {
            HealthStatus.HEALTHY: 1.0,
            HealthStatus.DEGRADED: 0.5,
            HealthStatus.UNHEALTHY: 0.0
        }[result.status]
        
        metrics.append(f'health_check_status{{check="{name}"}} {status_value}')
        metrics.append(f'health_check_duration_ms{{check="{name}"}} {result.duration_ms}')
    
    return '\n'.join(metrics), 200, {'Content-Type': 'text/plain'}
```

### 4. Monitoring Integration

#### A. Prometheus Integration
```python
# Add to requirements.txt
prometheus-client==0.21.1

# metrics.py
from prometheus_client import Gauge, Histogram, Counter

# Health check metrics
health_check_status = Gauge(
    'health_check_status', 
    'Health check status (1=healthy, 0.5=degraded, 0=unhealthy)',
    ['check_name']
)

health_check_duration = Histogram(
    'health_check_duration_seconds',
    'Health check duration',
    ['check_name']
)

health_check_total = Counter(
    'health_checks_total',
    'Total health checks performed',
    ['check_name', 'status']
)
```

#### B. Alerting Integration
```python
# alerting.py
import requests
from typing import List, Dict

class AlertManager:
    """Manages health check alerts."""
    
    def __init__(self, config):
        self.webhook_url = config.get('alert_webhook_url')
        self.slack_webhook = config.get('slack_webhook_url')
        self.alert_thresholds = {
            'consecutive_failures': 3,
            'degraded_duration_minutes': 10
        }
    
    async def check_alert_conditions(self, results: Dict[str, HealthResult]):
        """Check if any alert conditions are met."""
        for name, result in results.items():
            if result.status == HealthStatus.UNHEALTHY:
                await self.send_unhealthy_alert(name, result)
            elif result.status == HealthStatus.DEGRADED:
                await self.check_degraded_duration(name, result)
    
    async def send_unhealthy_alert(self, check_name: str, result: HealthResult):
        """Send alert for unhealthy check."""
        message = {
            'text': f'🚨 Health Check Alert: {check_name}',
            'attachments': [{
                'color': 'danger',
                'fields': [
                    {'title': 'Status', 'value': 'UNHEALTHY', 'short': True},
                    {'title': 'Message', 'value': result.message, 'short': True},
                    {'title': 'Duration', 'value': f'{result.duration_ms}ms', 'short': True},
                    {'title': 'Timestamp', 'value': result.timestamp.isoformat(), 'short': True}
                ]
            }]
        }
        
        if self.slack_webhook:
            await self._send_slack_alert(message)
```

---

## Implementation Timeline

### Phase 1 (Week 1): Foundation
- [ ] Create health monitoring module structure
- [ ] Implement base health check class
- [ ] Create application health check
- [ ] Add basic Flask route integration
- [ ] Write unit tests

### Phase 2 (Week 2): External Dependencies
- [ ] Implement OpenAI health check
- [ ] Implement train API health checks
- [ ] Add database connectivity check
- [ ] Create system resource monitoring
- [ ] Add integration tests

### Phase 3 (Week 3): Advanced Features
- [ ] Implement health check manager
- [ ] Add caching and parallel execution
- [ ] Create Prometheus metrics integration
- [ ] Add alerting framework
- [ ] Performance optimization

### Phase 4 (Week 4): Monitoring Integration
- [ ] Kubernetes probe configuration
- [ ] Grafana dashboard creation
- [ ] Slack/webhook alerting setup
- [ ] Documentation and deployment guides
- [ ] Load testing and validation

---

## Configuration Updates

### Environment Variables
```bash
# Health Check Configuration
HEALTH_CHECK_CACHE_TTL=30
HEALTH_CHECK_TIMEOUT=10
HEALTH_CHECK_ENABLED=true

# Alerting Configuration
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
ALERT_WEBHOOK_URL=https://monitoring.company.com/webhooks/alerts

# Monitoring Integration
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=8001
```

### Config Class Updates
```python
# config.py additions
class AppConfig(BaseSettings):
    # Health Check Configuration
    health_check_enabled: bool = Field(default=True)
    health_check_cache_ttl: int = Field(default=30)
    health_check_timeout: int = Field(default=10)
    
    # Monitoring Configuration
    prometheus_enabled: bool = Field(default=False)
    prometheus_port: int = Field(default=8001)
    
    # Alerting Configuration
    slack_webhook_url: Optional[str] = Field(default=None)
    alert_webhook_url: Optional[str] = Field(default=None)
```

---

## Benefits

### 1. Operational Excellence
- **Proactive Monitoring:** Early detection of issues before user impact
- **Automated Alerting:** Immediate notification of critical problems
- **Detailed Diagnostics:** Rich information for troubleshooting
- **Performance Insights:** Health check duration and success rate tracking

### 2. DevOps Integration
- **Kubernetes Ready:** Standard liveness/readiness probes
- **CI/CD Pipeline:** Health checks in deployment validation
- **Load Balancer Integration:** Automatic traffic routing based on health
- **Container Orchestration:** Proper health check configuration

### 3. Business Value
- **Improved Reliability:** Reduced downtime through early detection
- **Better User Experience:** Proactive issue resolution
- **Operational Insights:** Understanding of system behavior
- **Cost Optimization:** Efficient resource utilization monitoring

---

## Testing Strategy

### Unit Tests
- Individual health check components
- Health check manager functionality
- Alert condition logic
- Metrics collection accuracy

### Integration Tests
- End-to-end health check flows
- External API connectivity validation
- Alert delivery verification
- Prometheus metrics export

### Load Tests
- Health check performance under load
- Concurrent health check execution
- Cache effectiveness validation
- Resource usage optimization

---

## Success Metrics

### Technical Metrics
- Health check execution time < 5 seconds (deep check)
- Health check availability > 99.9%
- Alert delivery time < 30 seconds
- False positive rate < 1%

### Business Metrics
- Mean time to detection (MTTD) < 2 minutes
- Mean time to recovery (MTTR) reduction by 50%
- Unplanned downtime reduction by 75%
- Operational overhead reduction by 40%

---

## Conclusion

This health check monitoring integration proposal provides a comprehensive foundation for production-grade monitoring of the ScotRail Train Travel Advisor application. The implementation will significantly improve operational visibility, reduce downtime, and enable proactive issue resolution.

**Recommended Next Steps:**
1. Review and approve proposal
2. Begin Phase 1 implementation
3. Set up monitoring infrastructure
4. Plan deployment strategy

**Estimated Effort:** 4 weeks (1 developer)  
**Priority:** High (Critical for production readiness)  
**Dependencies:** None (can be implemented independently)

---

*Proposal prepared by GitHub Copilot*  
*Date: 2 December 2025*  
*Branch: app_review*