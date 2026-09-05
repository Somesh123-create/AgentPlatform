from datetime import datetime

from pydantic import BaseModel, Field

from app.models.mcp import (
    MCPAccess,
    MCPProtocol,
    MCPStatus,
    MCPType,
)

class MCPCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=100,
    )
    description: str | None = None
    mcp_type: MCPType
    protocol: MCPProtocol
    access: MCPAccess = MCPAccess.PRIVATE
    
    
class MCPUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    description: str | None = None
    access: MCPAccess | None = None
    status: MCPStatus | None = None
    

class MCPResponse(BaseModel):
    id: int
    owner_id: int
    name: str
    description: str | None
    mcp_type: MCPType
    protocol: MCPProtocol
    access: MCPAccess
    status: MCPStatus
    created_at: datetime
    updated_at: datetime
    model_config = {
        "from_attributes": True
    }

