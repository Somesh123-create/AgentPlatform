import asyncio
from types import SimpleNamespace

import pytest

from app.models.mcp_version import MCPSourceKind
from app.services.build import BuildService


class RecordingBuildRepository:
    def __init__(self):
        self.created = []

    async def create(self, build):
        self.created.append(build)
        return build

    async def save(self, build):
        return build


def test_build_persists_the_selected_version_id():
    service = BuildService(None)
    repository = RecordingBuildRepository()
    service.repository = repository
    version = SimpleNamespace(id=42, mcp_id=7, version=3, source_kind=MCPSourceKind.GIT)

    build = asyncio.run(service.build_version(7, version))

    assert build.mcp_id == 7
    assert build.version_id == 42
    assert build.version == 3
    assert repository.created == [build]


def test_build_rejects_a_version_from_another_mcp():
    service = BuildService(None)
    repository = RecordingBuildRepository()
    service.repository = repository
    version = SimpleNamespace(id=42, mcp_id=8, source_kind=MCPSourceKind.GIT)

    with pytest.raises(ValueError, match="does not belong"):
        asyncio.run(service.build_version(7, version))

    assert repository.created == []