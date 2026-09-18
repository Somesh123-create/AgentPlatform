import asyncio
from types import SimpleNamespace

import pytest

from app.models.mcp_version import MCPSourceKind
from app.repositories.build import BuildRepository
from app.services.build import BuildService


class RecordingBuildRepository:
    def __init__(self):
        self.created = []

    async def get_for_version(self, mcp_id, version_id):
        return None

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


def test_build_reuses_existing_build_record():
    service = BuildService(None)
    existing = SimpleNamespace(
        id=9,
        mcp_id=7,
        version_id=42,
        version=1,
        status="SUCCEEDED",
        image_ref="old-image",
        logs="old logs",
        error="old error",
    )

    class ReusingRepository(RecordingBuildRepository):
        async def get_for_version(self, mcp_id, version_id):
            return existing

    repository = ReusingRepository()
    service.repository = repository
    service.execute_build = lambda mcp_id, version, build: asyncio.sleep(0, result=build)

    result = asyncio.run(service.build_version(7, SimpleNamespace(id=42, mcp_id=7, version=3)))

    assert result is existing
    assert repository.created == []
    assert result.version == 3
    assert result.image_ref is None
    assert result.logs == ""
    assert result.error is None


def test_generated_manifest_installs_requirements():
    dockerfile = BuildService._dockerfile(
        {"requirements": "requirements.txt"},
        ["python", "server.py"],
    )

    assert "COPY requirements.txt /tmp/requirements.txt" in dockerfile
    assert "pip install --no-cache-dir -r /tmp/requirements.txt" in dockerfile


def test_latest_succeeded_query_returns_one_when_multiple_builds_exist():
    class ScalarResult:
        def first(self):
            return "newest-build"

    class QueryResult:
        def scalars(self):
            return ScalarResult()

    class RecordingSession:
        statement = None

        async def execute(self, statement):
            self.statement = statement
            return QueryResult()

    session = RecordingSession()
    result = asyncio.run(BuildRepository(session).latest_succeeded_for_version(7, 11))

    assert result == "newest-build"
    assert session.statement._limit_clause is not None