from datetime import datetime

from pydantic import BaseModel, Field

from app.models.conversation import MessageRole


class ConversationCreate(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=120)


class ConversationResponse(BaseModel):
    id: int
    agent_id: int
    owner_id: int
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    role: MessageRole
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    build_id: int = Field(gt=0)