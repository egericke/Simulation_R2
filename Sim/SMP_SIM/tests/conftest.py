"""
Configuration for pytest.

This file contains fixtures and configuration hooks for running tests
in the steel plant simulation project.
"""

import pytest
import sys
import os
import logging

# Add the project root to the path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configure logging for tests
@pytest.fixture(autouse=True)
def setup_logging():
    """Set up logging for tests."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.NullHandler()  # Add this to suppress log output during tests
        ]
    )
    # Disable some verbose logging during tests
    logging.getLogger('salabim').setLevel(logging.WARNING)
    
    # Return a logger for the test to use
    return logging.getLogger('test')