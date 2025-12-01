"""
Dependency Injection Container for ScotRail Train Travel Advisor.

This module provides a lightweight dependency injection container that manages
the lifecycle and dependencies of service objects throughout the application.

Benefits:
- Improved testability: easily inject mock dependencies in tests
- Loose coupling: components depend on abstractions, not concrete implementations
- Centralized configuration: all service initialization in one place
- Easier maintenance: change implementations without modifying dependent code
"""

import os
import logging
from typing import Optional
from openai import OpenAI

from config import get_config, get_train_movements_config
from train_tools import TrainTools
from timetable_parser import StationResolver
from timetable_tools import TimetableTools
from cancellations_service import CancellationsService
from train_movements_client import TrainMovementsClient

logger = logging.getLogger(__name__)


class ServiceContainer:
    """
    Dependency injection container for managing application services.
    
    This container provides lazy initialization of services and caches instances
    to ensure singleton behavior for stateless services.
    """
    
    def __init__(self):
        """Initialize the service container with empty caches."""
        self._config = None
        self._train_tools = None
        self._station_resolver = None
        self._timetable_tools = None
        self._openai_client = None
        self._test_agent = None  # For test mocking
        self._cancellations_service = None
        self._train_movements_client = None
        
    def get_config(self):
        """Get the application configuration (singleton)."""
        if self._config is None:
            self._config = get_config()
        return self._config
    
    def get_openai_client(self) -> OpenAI:
        """
        Get OpenAI client instance (singleton).
        
        Returns:
            Configured OpenAI client
            
        Raises:
            ValueError: If OPENAI_API_KEY is not configured
        """
        if self._openai_client is None:
            config = self.get_config()
            api_key = config.openai_api_key
            if not api_key:
                raise ValueError("OPENAI_API_KEY not found in configuration")
            self._openai_client = OpenAI(api_key=api_key)
            logger.info("OpenAI client initialized")
        return self._openai_client
    
    def get_train_tools(self) -> TrainTools:
        """
        Get TrainTools instance for live train data access (singleton).
        
        Returns:
            TrainTools instance configured for National Rail API access
        """
        if self._train_tools is None:
            self._train_tools = TrainTools()
            logger.info("TrainTools initialized")
        return self._train_tools
    
    def get_station_resolver(self) -> Optional[StationResolver]:
        """
        Get StationResolver instance for fuzzy station name matching (singleton).
        
        Returns:
            StationResolver instance if MSN file exists, None otherwise
        """
        if self._station_resolver is None:
            config = self.get_config()
            msn_path = os.path.join(os.path.dirname(__file__), config.timetable_msn_path)
            
            if os.path.exists(msn_path):
                try:
                    self._station_resolver = StationResolver(msn_path)
                    logger.info(f"Station resolver initialized with {len(self._station_resolver)} stations")
                except Exception as e:
                    logger.warning(f"Could not initialize station resolver: {e}")
                    self._station_resolver = None
            else:
                logger.warning(f"MSN file not found at {msn_path}. Station name resolution disabled.")
                self._station_resolver = None
                
        return self._station_resolver
    
    def get_timetable_tools(self) -> Optional[TimetableTools]:
        """
        Get TimetableTools instance for schedule data access (singleton).
        
        Returns:
            TimetableTools instance if database exists, None otherwise
        """
        if self._timetable_tools is None:
            config = self.get_config()
            db_path = os.path.join(os.path.dirname(__file__), config.timetable_db_path)
            msn_path = os.path.join(os.path.dirname(__file__), config.timetable_msn_path)
            
            try:
                self._timetable_tools = TimetableTools(
                    db_path=db_path,
                    msn_path=msn_path if os.path.exists(msn_path) else None
                )
                logger.info("TimetableTools initialized for schedule queries")
            except Exception as e:
                logger.warning(f"Could not initialize timetable tools: {e}")
                self._timetable_tools = None
                
        return self._timetable_tools
    
    def create_agent(self, from_scotrail_agent):
        """
        Factory method to create a ScotRailAgent with injected dependencies.
        
        Args:
            from_scotrail_agent: The ScotRailAgent class (imported to avoid circular import)
            
        Returns:
            ScotRailAgent instance with all dependencies injected
        """
        # Allow tests to override agent creation by setting _test_agent
        if hasattr(self, '_test_agent') and self._test_agent is not None:
            return self._test_agent
            
        return from_scotrail_agent(
            openai_client=self.get_openai_client(),
            train_tools=self.get_train_tools(),
            station_resolver=self.get_station_resolver(),
            timetable_tools=self.get_timetable_tools()
        )
    
    def set_test_agent(self, agent):
        """
        Set a mock agent for testing purposes.
        
        Args:
            agent: Mock agent instance to use instead of creating real ones
        """
        self._test_agent = agent
    
    def clear_test_agent(self):
        """Clear the test agent override."""
        self._test_agent = None
    
    def get_cancellations_service(self) -> CancellationsService:
        """Get the cancellations service (singleton)."""
        if self._cancellations_service is None:
            self._cancellations_service = CancellationsService(max_stored=50)
            logger.info("CancellationsService initialized (max_stored=50)")
        return self._cancellations_service
    
    def get_train_movements_client(self) -> TrainMovementsClient:
        """Get the train movements client (singleton).
        
        The client automatically starts in a background thread and begins
        receiving real-time train cancellation data from Darwin Push Port.
        """
        if self._train_movements_client is None:
            config = get_train_movements_config()
            cancellations_service = self.get_cancellations_service()
            
            # Callback for when cancellations are detected
            def on_cancellation(cancellation_data):
                cancellations_service.add_cancellation(cancellation_data)
            
            self._train_movements_client = TrainMovementsClient(config, on_cancellation)
            self._train_movements_client.start()
            logger.info("TrainMovementsClient initialized and started")
        return self._train_movements_client
    
    def reset(self):
        """
        Reset all cached instances. Useful for testing.
        
        This forces recreation of all services on next access.
        """
        # Stop train movements client if running
        if self._train_movements_client is not None:
            try:
                self._train_movements_client.stop()
            except Exception as e:
                logger.error(f"Error stopping train movements client: {e}")
        
        self._config = None
        self._train_tools = None
        self._station_resolver = None
        self._timetable_tools = None
        self._openai_client = None
        self._test_agent = None
        self._cancellations_service = None
        self._train_movements_client = None
        logger.info("Service container reset")


# Global container instance
_container: Optional[ServiceContainer] = None


def get_container() -> ServiceContainer:
    """
    Get the global service container instance (singleton).
    
    Returns:
        ServiceContainer instance
    """
    global _container
    if _container is None:
        _container = ServiceContainer()
    return _container


def reset_container():
    """
    Reset the global container. Useful for testing.
    
    Forces recreation of all services on next access.
    """
    global _container
    if _container is not None:
        _container.reset()
    _container = None
