from datetime import datetime

from pydantic import BaseModel, Field

from app.models.mcp_build_job import MCPBuildJobStatus
from app.models.mcp_version import MCPSourceKind, MCPVersionStatus


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
    image_reference: str | None
    image_digest: str | None
    status: MCPVersionStatus
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None


class MCPBuildRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=255)


class MCPBuildJobResponse(BaseModel):
    id: int
    version_id: int
    idempotency_key: str
    status: MCPBuildJobStatus
    attempt_count: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None