from datetime import datetime

from pydantic import BaseModel

from app.models.agent_build import AgentBuildStatus


class AgentBuildResponse(BaseModel):
    id: int
    agent_id: int
    owner_id: int
    status: AgentBuildStatus
    image_ref: str | None
    logs: str
    error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}