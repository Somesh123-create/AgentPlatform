from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp import MCP


class MCPRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, mcp: MCP) -> MCP:
        self.db.add(mcp)
        await self.db.commit()
        await self.db.refresh(mcp)
        return mcp

    async def get_by_id(
            self,
            mcp_id: int,
        ) -> MCP | None:

        result = await self.db.execute(
            select(MCP).where(
                MCP.id == mcp_id
            )
        )

        return result.scalar_one_or_none()

    async def get_by_owner(
            self,
            owner_id: int,
        ) -> list[MCP]:

        result = await self.db.execute(
            select(MCP)
            .where(MCP.owner_id == owner_id)
            .order_by(MCP.created_at.desc())
        )

        return list(result.scalars().all())

    async def delete(
            self,
            mcp: MCP,
        ) -> None:

        await self.db.delete(mcp)
        await self.db.commit()
