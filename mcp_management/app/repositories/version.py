from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp_version import MCPVersion


class VersionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def next_version_number(self, mcp_id: int) -> int:
        result = await self.db.execute(
            select(func.coalesce(func.max(MCPVersion.version), 0)).where(MCPVersion.mcp_id == mcp_id)
        )
        return int(result.scalar_one()) + 1

    async def create_version(self, version: MCPVersion) -> MCPVersion:
        self.db.add(version)
        await self.db.commit()
        await self.db.refresh(version)
        return version

    async def get_version(self, mcp_id: int, version_number: int) -> MCPVersion | None:
        result = await self.db.execute(
            select(MCPVersion).where(
                MCPVersion.mcp_id == mcp_id,
                MCPVersion.version == version_number,
            )
        )
        return result.scalar_one_or_none()

    async def list_versions(self, mcp_id: int) -> list[MCPVersion]:
        result = await self.db.execute(
            select(MCPVersion)
            .where(MCPVersion.mcp_id == mcp_id)
            .order_by(MCPVersion.version.desc())
        )
        return list(result.scalars().all())
