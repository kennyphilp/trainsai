"""Integration layer for health monitoring in Flask application."""

from health_monitoring.health_routes import init_health_monitoring, update_health_monitoring_agents


def setup_health_monitoring(app, config, agents_dict=None):
    """Setup health monitoring for the Flask application.
    
    Args:
        app: Flask application instance
        config: Application configuration
        agents_dict: Dictionary of active agents (optional)
    """
    init_health_monitoring(app, config, agents_dict)


def update_agents_health_monitoring(app, agents_dict):
    """Update the agents dictionary in health monitoring.
    
    Args:
        app: Flask application instance
        agents_dict: Updated agents dictionary
    """
    # Update via the app reference if available
    if hasattr(app, 'health_manager') and app.health_manager:
        app.health_manager.update_agents_dict(agents_dict)
    
    # Also update via the global function
    update_health_monitoring_agents(agents_dict)