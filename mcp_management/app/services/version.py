import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp_build_job import MCPBuildJob, MCPBuildJobStatus
from app.models.mcp_version import MCPVersion
from app.repositories.version import VersionRepository
from app.schemas.version import MCPBuildRequest, MCPVersionCreate


class VersionService:
    def __init__(self, db: AsyncSession):
        self.repository = VersionRepository(db)

    async def create(self, mcp_id: int, data: MCPVersionCreate) -> MCPVersion:
        version = MCPVersion(
            mcp_id=mcp_id,
            version=await self.repository.next_version_number(mcp_id),
            source_kind=data.source_kind,
            source_digest=data.source_digest.lower(),
            source_reference=data.source_reference,
            manifest=json.dumps(data.manifest, sort_keys=True),
        )
        return await self.repository.create_version(version)

    async def get(self, mcp_id: int, version_number: int) -> MCPVersion | None:
        return await self.repository.get_version(mcp_id, version_number)

    async def list(self, mcp_id: int) -> list[MCPVersion]:
        return await self.repository.list_versions(mcp_id)

    async def enqueue_build(self, version: MCPVersion, data: MCPBuildRequest) -> MCPBuildJob:
        existing = await self.repository.get_build_job(version.id, data.idempotency_key)
        if existing:
            return existing

        job = MCPBuildJob(
            version_id=version.id,
            idempotency_key=data.idempotency_key,
            status=MCPBuildJobStatus.QUEUED,
        )
        return await self.repository.create_build_job(job)