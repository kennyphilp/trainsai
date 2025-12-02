"""Flask routes for health monitoring."""

import asyncio
from datetime import datetime
from flask import Blueprint, jsonify, current_app

from .health_manager import HealthCheckManager
from .models import HealthStatus

# Global health manager instance
health_manager = None

# Create blueprint
health_bp = Blueprint('health', __name__, url_prefix='/api/health')


def init_health_monitoring(app, config, agents_dict=None):
    """Initialize health monitoring.
    
    Args:
        app: Flask application instance
        config: Application configuration
        agents_dict: Dictionary of active agents (optional)
    """
    global health_manager
    
    try:
        health_manager = HealthCheckManager(config, agents_dict)
        app.register_blueprint(health_bp)
        
        # Store reference for updating agents
        app.health_manager = health_manager
        
        app.logger.info("Health monitoring initialized successfully")
    except Exception as e:
        app.logger.error(f"Failed to initialize health monitoring: {e}")
        # Don't fail app startup if health monitoring fails
        health_manager = None


def update_health_monitoring_agents(agents_dict):
    """Update the agents dictionary in health monitoring.
    
    Args:
        agents_dict: Updated agents dictionary
    """
    global health_manager
    if health_manager:
        health_manager.update_agents_dict(agents_dict)


@health_bp.route('/')
@health_bp.route('')
def basic_health():
    """Basic health check endpoint (maintains backward compatibility)."""
    if not health_manager:
        return jsonify({
            'status': 'degraded',
            'message': 'Health monitoring not available',
            'service': 'ScotRail Train Travel Advisor'
        }), 503
    
    try:
        # Run just the application health check for fast response
        results = asyncio.run(health_manager.run_checks(['application']))
        
        if 'application' in results:
            app_health = results['application']
            
            # Extract key metrics for backward compatibility
            details = app_health.details
            response_data = {
                'status': app_health.status.value,
                'message': app_health.message,
                'service': 'ScotRail Train Travel Advisor',
                'active_sessions': details.get('active_sessions', 0),
                'timestamp': app_health.timestamp.isoformat()
            }
            
            status_code = 200 if app_health.is_healthy else 503
            return jsonify(response_data), status_code
        else:
            return jsonify({
                'status': 'unhealthy',
                'message': 'Application health check failed',
                'service': 'ScotRail Train Travel Advisor'
            }), 503
            
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'message': f'Health check error: {str(e)}',
            'service': 'ScotRail Train Travel Advisor'
        }), 503


@health_bp.route('/live')
def liveness_probe():
    """Kubernetes liveness probe."""
    if not health_manager:
        return jsonify({
            'status': 'unhealthy',
            'message': 'Health monitoring not available'
        }), 503
    
    try:
        # Run critical checks for liveness
        results = asyncio.run(health_manager.run_checks(['application', 'system']))
        
        # Check if any critical component is unhealthy
        unhealthy_checks = [
            name for name, result in results.items() 
            if result.status == HealthStatus.UNHEALTHY
        ]
        
        if unhealthy_checks:
            return jsonify({
                'status': 'unhealthy',
                'failed_checks': unhealthy_checks,
                'timestamp': datetime.now().isoformat()
            }), 503
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'message': f'Liveness probe error: {str(e)}'
        }), 503


@health_bp.route('/ready')
def readiness_probe():
    """Kubernetes readiness probe."""
    if not health_manager:
        return jsonify({
            'status': 'not_ready',
            'message': 'Health monitoring not available'
        }), 503
    
    try:
        # Run all available checks for readiness
        results = asyncio.run(health_manager.run_checks())
        
        unhealthy_checks = [
            name for name, result in results.items() 
            if result.status == HealthStatus.UNHEALTHY
        ]
        
        degraded_checks = [
            name for name, result in results.items() 
            if result.status == HealthStatus.DEGRADED
        ]
        
        if unhealthy_checks:
            return jsonify({
                'status': 'not_ready',
                'failed_checks': unhealthy_checks,
                'degraded_checks': degraded_checks,
                'details': {name: result.message for name, result in results.items()},
                'timestamp': datetime.now().isoformat()
            }), 503
        
        status = 'ready' if not degraded_checks else 'ready_degraded'
        
        return jsonify({
            'status': status,
            'degraded_checks': degraded_checks,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'status': 'not_ready',
            'message': f'Readiness probe error: {str(e)}'
        }), 503


@health_bp.route('/deep')
def deep_health_check():
    """Comprehensive health check."""
    if not health_manager:
        return jsonify({
            'status': 'unhealthy',
            'message': 'Health monitoring not available',
            'checks': {}
        }), 503
    
    try:
        results = asyncio.run(health_manager.run_checks())
        overall_status = health_manager.get_overall_status(results)
        
        return jsonify({
            'status': overall_status.value,
            'timestamp': datetime.now().isoformat(),
            'checks': {
                name: {
                    'status': result.status.value,
                    'message': result.message,
                    'duration_ms': result.duration_ms,
                    'details': result.details,
                    'timestamp': result.timestamp.isoformat()
                }
                for name, result in results.items()
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'message': f'Deep health check error: {str(e)}',
            'checks': {}
        }), 503


@health_bp.route('/metrics')
def health_metrics():
    """Prometheus-style metrics endpoint."""
    if not health_manager:
        return 'health_monitoring_available 0\n', 503, {'Content-Type': 'text/plain'}
    
    try:
        results = asyncio.run(health_manager.run_checks())
        
        metrics = ['# Health check metrics for ScotRail Train Travel Advisor']
        
        for name, result in results.items():
            # Health status metric (1=healthy, 0.5=degraded, 0=unhealthy)
            status_value = {
                HealthStatus.HEALTHY: 1.0,
                HealthStatus.DEGRADED: 0.5,
                HealthStatus.UNHEALTHY: 0.0
            }[result.status]
            
            metrics.append(f'health_check_status{{check="{name}"}} {status_value}')
            metrics.append(f'health_check_duration_ms{{check="{name}"}} {result.duration_ms}')
        
        # Overall system health
        overall_status = health_manager.get_overall_status(results)
        overall_value = {
            HealthStatus.HEALTHY: 1.0,
            HealthStatus.DEGRADED: 0.5,
            HealthStatus.UNHEALTHY: 0.0
        }[overall_status]
        
        metrics.append(f'health_overall_status {overall_value}')
        metrics.append(f'health_checks_total {len(results)}')
        
        return '\n'.join(metrics) + '\n', 200, {'Content-Type': 'text/plain'}
        
    except Exception as e:
        return f'health_monitoring_error 1\n# Error: {str(e)}\n', 503, {'Content-Type': 'text/plain'}