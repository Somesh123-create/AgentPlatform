from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_draft import AgentDraft


class AgentDraftRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, draft: AgentDraft) -> AgentDraft:
        self.db.add(draft)
        try:
            await self.db.commit()
        except SQLAlchemyError:
            await self.db.rollback()
            raise
        await self.db.refresh(draft)
        return draft

    async def list_for_owner(self, owner_id: int) -> list[AgentDraft]:
        result = await self.db.execute(select(AgentDraft).where(AgentDraft.owner_id == owner_id).order_by(AgentDraft.updated_at.desc()))
        return list(result.scalars().all())

    async def get_owned(self, draft_id: int, owner_id: int) -> AgentDraft | None:
        result = await self.db.execute(select(AgentDraft).where(AgentDraft.id == draft_id, AgentDraft.owner_id == owner_id))
        return result.scalar_one_or_none()

    async def save(self, draft: AgentDraft) -> AgentDraft:
        try:
            await self.db.commit()
        except SQLAlchemyError:
            await self.db.rollback()
            raise
        await self.db.refresh(draft)
        return draft

    async def delete(self, draft: AgentDraft) -> None:
        await self.db.delete(draft)
        try:
            await self.db.commit()
        except SQLAlchemyError:
            await self.db.rollback()
            raise
