"""
Pytest configuration for all tests.
Sets up environment variables and fixtures used across test modules.
"""

import os


# Set environment variable BEFORE any other imports
# This must happen at module import time to affect app.py initialization
os.environ['TESTING'] = 'true'
