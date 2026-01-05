"""
Cortex test configuration.
"""

import pytest


@pytest.fixture(autouse=True)
def reset_service_singleton():
    """Reset the global service singleton between tests."""
    from cortex.mcp import server as mcp_server
    from cortex.api import app as api_app
    
    # Reset MCP singleton
    mcp_server._namespaced_service = None
    mcp_server._namespace = None
    
    # Reset API singleton
    api_app._namespaced_service = None
    
    yield
