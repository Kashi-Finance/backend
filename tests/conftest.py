"""
Pytest configuration for Kashi backend tests.

Sets up test environment and global fixtures.
"""
import os
import pytest
from unittest.mock import MagicMock

# Disable config validation during tests
# This allows tests to run without requiring real environment variables
os.environ["VALIDATE_CONFIG"] = "false"

# Set test environment variables
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_PUBLISHABLE_KEY", "test-publishable-key")
# Note: SUPABASE_JWT_SECRET no longer needed - we use JWKS (ES256) now
os.environ.setdefault("GOOGLE_API_KEY", "test-google-api-key")


@pytest.fixture
def supabase_client():
    """
    Mock Supabase client for testing RPC functions.
    Returns a MagicMock that simulates Supabase client behavior.
    """
    mock_client = MagicMock()
    return mock_client
