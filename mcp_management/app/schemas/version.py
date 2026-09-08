from datetime import datetime

from pydantic import BaseModel, Field

from app.models.mcp_version import MCPSourceKind


class MCPVersionCreate(BaseModel):
    source_kind: MCPSourceKind
    source_digest: str = Field(min_length=64, max_length=64, pattern=r"^[a-fA-F0-9]{64}$")
    source_reference: str | None = Field(default=None, max_length=2048)
    manifest: dict[str, object]


class MCPVersionResponse(BaseModel):
    id: int
    mcp_id: int
    version: int
    source_kind: MCPSourceKind
    source_digest: str
    source_reference: str | None
    manifest: dict[str, object]
    created_at: datetime
    updated_at: datetime