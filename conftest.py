"""Pytest configuration for Options Agents."""
import os
import pytest

# Set default environment variables for tests
os.environ.setdefault("POLYGON_KEY", "TEST_KEY")
os.environ.setdefault("OA_GAMMA_DB", "test.db")

# Configure pytest-asyncio
pytest_plugins = ('pytest_asyncio',)