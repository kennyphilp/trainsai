"""
Pytest configuration for all tests.
Sets up environment variables and fixtures used across test modules.
"""

import os
import pytest
from unittest.mock import Mock


# Set environment variable BEFORE any other imports
# This must happen at module import time to affect app.py initialization
os.environ['TESTING'] = 'true'


@pytest.fixture(autouse=True)
def reset_container():
    """Reset the dependency injection container before each test."""
    from dependencies import reset_container
    reset_container()
    yield
    reset_container()


@pytest.fixture
def mock_agent_in_container():
    """
    Fixture that injects a mock agent into the DI container.
    Use this when you need the container to return a mock agent.
    """
    from dependencies import get_container
    
    mock_agent = Mock()
    mock_agent.chat.return_value = "Test response from agent"
    mock_agent.last_timetable_data = None
    
    container = get_container()
    container.set_test_agent(mock_agent)
    
    yield mock_agent
    
    container.clear_test_agent()
