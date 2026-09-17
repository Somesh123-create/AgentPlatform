from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import AgentConversation, AgentMessage


class ConversationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_agent(self, conversation_id: int, agent_id: int, owner_id: int):
        result = await self.db.execute(select(AgentConversation).where(AgentConversation.id == conversation_id, AgentConversation.agent_id == agent_id, AgentConversation.owner_id == owner_id))
        return result.scalar_one_or_none()

    async def list_for_agent(self, agent_id: int, owner_id: int):
        result = await self.db.execute(select(AgentConversation).where(AgentConversation.agent_id == agent_id, AgentConversation.owner_id == owner_id).order_by(AgentConversation.updated_at.desc()))
        return list(result.scalars().all())

    async def create(self, conversation: AgentConversation):
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation

    async def messages(self, conversation_id: int):
        result = await self.db.execute(select(AgentMessage).where(AgentMessage.conversation_id == conversation_id).order_by(AgentMessage.created_at.asc(), AgentMessage.id.asc()))
        return list(result.scalars().all())

    async def add_message(self, message: AgentMessage):
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message