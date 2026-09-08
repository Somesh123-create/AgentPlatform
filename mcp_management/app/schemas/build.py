from datetime import datetime

from pydantic import BaseModel

from app.models.build import MCPBuildStatus


class MCPBuildResponse(BaseModel):
    id: int
    mcp_id: int
    version_id: int
    status: MCPBuildStatus
    image_ref: str | None
    logs: str
    error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}