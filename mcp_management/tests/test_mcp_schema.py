import pytest
from pydantic import ValidationError

from app.schemas.mcp import MCPCreate


def test_local_mcp_requires_stdio():
    with pytest.raises(ValidationError):
        MCPCreate(name="local", mcp_type="LOCAL", protocol="SSE")


def test_remote_mcp_rejects_stdio():
    with pytest.raises(ValidationError):
        MCPCreate(name="remote", mcp_type="REMOTE", protocol="STDIO")


def test_remote_http_protocol_is_valid():
    MCPCreate(name="remote", mcp_type="REMOTE", protocol="STREAMABLE_HTTP")