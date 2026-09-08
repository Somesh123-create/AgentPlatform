from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.build import MCPBuild


class BuildRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, build: MCPBuild) -> MCPBuild:
        self.db.add(build)
        await self.db.commit()
        await self.db.refresh(build)
        return build

    async def get(self, build_id: int) -> MCPBuild | None:
        result = await self.db.execute(select(MCPBuild).where(MCPBuild.id == build_id))
        return result.scalar_one_or_none()

    async def list_for_mcp(self, mcp_id: int) -> list[MCPBuild]:
        result = await self.db.execute(select(MCPBuild).where(MCPBuild.mcp_id == mcp_id).order_by(MCPBuild.created_at.desc()))
        return list(result.scalars().all())

    async def latest_succeeded_for_version(self, version_id: int) -> MCPBuild | None:
        result = await self.db.execute(
            select(MCPBuild)
            .where(MCPBuild.version_id == version_id, MCPBuild.status == "SUCCEEDED")
            .order_by(MCPBuild.created_at.desc())
        )
        return result.scalar_one_or_none()

    async def save(self, build: MCPBuild) -> MCPBuild:
        await self.db.commit()
        await self.db.refresh(build)
        return build