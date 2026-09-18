from datetime import datetime

from pydantic import BaseModel, Field, model_validator

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

    @model_validator(mode="after")
    def validate_type_protocol(self):
        if self.mcp_type is MCPType.LOCAL and self.protocol is not MCPProtocol.STDIO:
            raise ValueError("LOCAL MCP servers must use the STDIO protocol")
        if self.mcp_type is MCPType.REMOTE and self.protocol is MCPProtocol.STDIO:
            raise ValueError("REMOTE MCP servers must use SSE or STREAMABLE_HTTP")
        return self
    
    
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

