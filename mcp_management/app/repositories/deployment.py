from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployment import MCPDeployment


class DeploymentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, deployment: MCPDeployment) -> MCPDeployment:
        self.db.add(deployment)
        await self.db.commit()
        await self.db.refresh(deployment)
        return deployment

    async def get(self, deployment_id: int) -> MCPDeployment | None:
        result = await self.db.execute(select(MCPDeployment).where(MCPDeployment.id == deployment_id))
        return result.scalar_one_or_none()

    async def list_for_mcp(self, mcp_id: int) -> list[MCPDeployment]:
        result = await self.db.execute(select(MCPDeployment).where(MCPDeployment.mcp_id == mcp_id).order_by(MCPDeployment.created_at.desc()))
        return list(result.scalars().all())

    async def save(self, deployment: MCPDeployment) -> MCPDeployment:
        await self.db.commit()
        await self.db.refresh(deployment)
        return deployment