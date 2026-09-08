from datetime import datetime

from pydantic import BaseModel

from app.models.deployment import MCPDeploymentStatus


class MCPDeploymentResponse(BaseModel):
    id: int
    mcp_id: int
    version_id: int
    build_id: int
    status: MCPDeploymentStatus
    container_id: str | None
    image_ref: str
    logs: str
    error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}