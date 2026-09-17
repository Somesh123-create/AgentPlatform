import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes import invocation


class FakeMCPService:
    def __init__(self, db):
        self.db = db

    async def get(self, mcp_id: int):
        return SimpleNamespace(id=mcp_id, owner_id=99)


class FakeRuntime:
    def __init__(self, db):
        self.db = db

    async def list_tools(self, mcp_id: int, version_id: int):
        return {"tools": [], "error": None}

    async def invoke_tool(self, mcp_id: int, version_id: int, tool_name: str, tool_input: dict):
        return {"output": "ok", "error": None, "status": "success"}


class FakeVersionRepository:
    def __init__(self, db):
        self.db = db

    async def get_by_id(self, mcp_id: int, version_id: int):
        return SimpleNamespace(id=11, mcp_id=mcp_id) if version_id == 11 else None

    async def get_version(self, mcp_id: int, version_number: int):
        return SimpleNamespace(id=11, mcp_id=mcp_id) if version_number == 2 else None


def test_runtime_routes_reject_another_users_mcp(monkeypatch):
    monkeypatch.setattr("app.services.mcp.MCPService", FakeMCPService)
    user = SimpleNamespace(user_id=42)

    with pytest.raises(HTTPException) as error:
        asyncio.run(invocation.list_tools(7, 10, user, object()))

    assert error.value.status_code == 403


def test_runtime_routes_allow_owner_and_use_version_id(monkeypatch):
    monkeypatch.setattr("app.services.mcp.MCPService", lambda db: SimpleNamespace(
        get=lambda mcp_id: asyncio.sleep(0, result=SimpleNamespace(id=mcp_id, owner_id=42)),
    ))
    monkeypatch.setattr(invocation, "EphemeralRuntime", FakeRuntime)
    monkeypatch.setattr(invocation, "VersionRepository", FakeVersionRepository)
    user = SimpleNamespace(user_id=42)

    result = asyncio.run(invocation.list_tools(7, 11, user, object()))

    assert result == {"tools": [], "error": None}


def test_runtime_route_resolves_human_version_number(monkeypatch):
    monkeypatch.setattr("app.services.mcp.MCPService", lambda db: SimpleNamespace(
        get=lambda mcp_id: asyncio.sleep(0, result=SimpleNamespace(id=mcp_id, owner_id=42)),
    ))
    monkeypatch.setattr(invocation, "EphemeralRuntime", FakeRuntime)
    monkeypatch.setattr(invocation, "VersionRepository", FakeVersionRepository)
    user = SimpleNamespace(user_id=42)

    result = asyncio.run(invocation.list_tools(9, 2, user, object()))

    assert result == {"tools": [], "error": None}


def test_runtime_container_keeps_mcp_stdio_open():
    from app.runtime.ephemeral import EphemeralRuntime

    command = EphemeralRuntime(None)._build_container_command("image:latest")

    assert "--interactive" in command
