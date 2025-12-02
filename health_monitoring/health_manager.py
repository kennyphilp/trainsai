"""Health check manager implementation."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .models import HealthResult, HealthStatus
from .checks import (
    ApplicationHealthCheck,
    DatabaseHealthCheck, 
    SystemHealthCheck
    # OpenAIHealthCheck,     # Phase II implementation
    # TrainAPIHealthCheck    # Phase II implementation
)

logger = logging.getLogger(__name__)


class HealthCheckManager:
    """Manages all health checks."""
    
    def __init__(self, config, agents_dict=None):
        """Initialize health check manager.
        
        Args:
            config: Application configuration
            agents_dict: Dictionary of active agents (optional)
        """
        self.config = config
        self.agents_dict = agents_dict or {}
        self.checks = []
        self.cache_ttl = timedelta(seconds=getattr(config, 'health_cache_timeout', 30))
        self.enabled = getattr(config, 'health_check_enabled', True)
        
        if self.enabled:
            self._setup_checks()
        else:
            logger.info("Health checks disabled by configuration")
    
    def _setup_checks(self):
        """Initialize all health checks."""
        try:
            # Always include basic checks
            self.checks.extend([
                ApplicationHealthCheck(self.config, self.agents_dict),
                DatabaseHealthCheck(self.config.timetable_db_path),
                SystemHealthCheck()
            ])
            
            # Add external API checks with dependency injection
            try:
                from dependencies import get_container
                container = get_container()
                
                # Phase II: Add OpenAI check (not implemented yet)
                # try:
                #     openai_client = container.get_openai_client()
                #     self.checks.append(OpenAIHealthCheck(openai_client))
                # except Exception as e:
                #     logger.warning(f"Could not initialize OpenAI health check: {e}")
                
                # Phase II: Add Train API check (not implemented yet)
                # try:
                #     train_tools = container.get_train_tools()
                #     self.checks.append(TrainAPIHealthCheck(train_tools))
                # except Exception as e:
                #     logger.warning(f"Could not initialize Train API health check: {e}")
                    
            except ImportError as e:
                logger.warning(f"Could not import dependency container: {e}")
            
            logger.info(f"Initialized {len(self.checks)} health checks: {[c.name for c in self.checks]}")
            
        except Exception as e:
            logger.error(f"Failed to setup health checks: {e}")
            # Continue with empty checks list rather than failing completely
            self.checks = []
    
    async def run_checks(self, check_types: Optional[List[str]] = None) -> Dict[str, HealthResult]:
        """Run health checks.
        
        Args:
            check_types: Optional list of check names to run. If None, runs all checks.
            
        Returns:
            Dictionary mapping check names to results
        """
        if not self.enabled:
            return {
                'health_monitoring': HealthResult(
                    name='health_monitoring',
                    status=HealthStatus.DEGRADED,
                    message='Health monitoring disabled',
                    details={'enabled': False},
                    duration_ms=0,
                    timestamp=datetime.now()
                )
            }
        
        # Determine which checks to run
        if check_types is None:
            checks_to_run = self.checks
        else:
            checks_to_run = [c for c in self.checks if c.name in check_types]
        
        if not checks_to_run:
            logger.warning(f"No health checks found for types: {check_types}")
            return {}
        
        # Run checks in parallel
        tasks = []
        for check in checks_to_run:
            if check.should_check(self.cache_ttl):
                tasks.append(self._run_single_check(check))
            else:
                # Use cached result
                tasks.append(self._get_cached_result(check))
        
        # Execute all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Build result dictionary
        result_dict = {}
        for check, result in zip(checks_to_run, results):
            if isinstance(result, Exception):
                result_dict[check.name] = self._error_result(check.name, result)
            else:
                result_dict[check.name] = result
        
        return result_dict
    
    async def _run_single_check(self, check) -> HealthResult:
        """Run a single health check with timeout."""
        try:
            return await check.run_with_timeout()
        except Exception as e:
            logger.error(f"Error running health check {check.name}: {e}")
            return self._error_result(check.name, e)
    
    async def _get_cached_result(self, check) -> HealthResult:
        """Get cached result for a check."""
        cached = check.get_cached_result()
        if cached:
            return cached
        
        # If no cached result, run the check
        return await self._run_single_check(check)
    
    def _error_result(self, check_name: str, error: Exception) -> HealthResult:
        """Create error result for failed check."""
        return HealthResult(
            name=check_name,
            status=HealthStatus.UNHEALTHY,
            message=f"Health check error: {str(error)}",
            details={'error': str(error), 'error_type': type(error).__name__},
            duration_ms=0,
            timestamp=datetime.now()
        )
    
    def get_overall_status(self, results: Dict[str, HealthResult]) -> HealthStatus:
        """Determine overall system health status.
        
        Args:
            results: Dictionary of health check results
            
        Returns:
            Overall health status
        """
        if not results:
            return HealthStatus.UNHEALTHY
        
        statuses = [result.status for result in results.values()]
        
        # If any check is unhealthy, system is unhealthy
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        
        # If any check is degraded, system is degraded
        if HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        
        # All checks are healthy
        return HealthStatus.HEALTHY
    
    def update_agents_dict(self, new_agents_dict: dict):
        """Update the agents dictionary reference for application health checks.
        
        Args:
            new_agents_dict: Updated agents dictionary
        """
        self.agents_dict = new_agents_dict
        
        # Update the reference in application health check
        for check in self.checks:
            if isinstance(check, ApplicationHealthCheck):
                check.agents_dict = new_agents_dict
                break