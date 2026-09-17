from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_build import AgentBuild


class AgentBuildRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, build: AgentBuild) -> AgentBuild:
        self.db.add(build)
        await self.db.commit()
        await self.db.refresh(build)
        return build

    async def save(self, build: AgentBuild) -> AgentBuild:
        await self.db.commit()
        await self.db.refresh(build)
        return build

    async def list_for_agent(self, agent_id: int, owner_id: int):
        result = await self.db.execute(select(AgentBuild).where(AgentBuild.agent_id == agent_id, AgentBuild.owner_id == owner_id).order_by(AgentBuild.created_at.desc()))
        return list(result.scalars().all())

    async def get_owned(self, build_id: int, agent_id: int, owner_id: int):
        result = await self.db.execute(select(AgentBuild).where(AgentBuild.id == build_id, AgentBuild.agent_id == agent_id, AgentBuild.owner_id == owner_id))
        return result.scalar_one_or_none()