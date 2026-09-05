from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp import MCP
from app.repositories.mcp import MCPRepository
from app.schemas.mcp import MCPCreate, MCPUpdate


class MCPService:

    def __init__(self, db: AsyncSession):
        self.repository = MCPRepository(db)

    async def create(
            self,
            owner_id: int,
            data: MCPCreate,
        ) -> MCP:

        mcp = MCP(
            owner_id=owner_id,
            name=data.name,
            description=data.description,
            mcp_type=data.mcp_type,
            protocol=data.protocol,
            access=data.access,
        )

        return await self.repository.create(mcp)

    async def get(
            self,
            mcp_id: int,
        ) -> MCP | None:

        return await self.repository.get_by_id(mcp_id)

    async def list_by_owner(
            self,
            owner_id: int,
        ) -> list[MCP]:

        return await self.repository.get_by_owner(owner_id)

    async def update(
            self,
            mcp: MCP,
            data: MCPUpdate,
        ) -> MCP:

        updates = data.model_dump(
            exclude_unset=True
        )

        for field, value in updates.items():
            setattr(mcp, field, value)

        return await self.repository.create(mcp)

    async def delete(
            self,
            mcp: MCP,
        ) -> None:

        await self.repository.delete(mcp)
