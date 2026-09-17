from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.models.agent_draft import AgentDraftStatus, AgentFramework


class AgentMcpConnection(BaseModel):
    mcp_id: int = Field(gt=0)
    mcp_version_id: int = Field(gt=0)
    mcp_version: int = Field(gt=0)
    protocol: str | None = Field(default=None, max_length=40)
    mcp_type: str | None = Field(default=None, max_length=40)
    image_ref: str | None = Field(default=None, max_length=500)
    name: str | None = Field(default=None, max_length=150)


class AgentDraftCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    framework: AgentFramework
    mcp_id: int = Field(gt=0)
    mcp_version_id: int = Field(gt=0)
    mcp_version: int = Field(gt=0)
    system_prompt: str = Field(default="", max_length=20000)
    user_prompt: str = Field(default="", max_length=20000)
    llm_model_id: int | None = Field(default=None, gt=0)
    llm_provider: str | None = Field(default=None, max_length=80)
    llm_model_name: str | None = Field(default=None, max_length=150)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_output_tokens: int | None = Field(default=None, gt=0)
    project_directory: str = Field(default="", max_length=500)
    mcp_connections: list[AgentMcpConnection] = Field(default_factory=list, max_length=20)


class AgentDraftUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    framework: AgentFramework | None = None
    mcp_id: int | None = Field(default=None, gt=0)
    mcp_version_id: int | None = Field(default=None, gt=0)
    mcp_version: int | None = Field(default=None, gt=0)
    system_prompt: str | None = Field(default=None, max_length=20000)
    user_prompt: str | None = Field(default=None, max_length=20000)
    llm_model_id: int | None = Field(default=None, gt=0)
    llm_provider: str | None = Field(default=None, max_length=80)
    llm_model_name: str | None = Field(default=None, max_length=150)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_output_tokens: int | None = Field(default=None, gt=0)
    project_directory: str | None = Field(default=None, max_length=500)
    mcp_connections: list[AgentMcpConnection] | None = Field(default=None, max_length=20)
    default_build_id: int | None = Field(default=None, gt=0)


class AgentDraftResponse(BaseModel):
    id: int
    owner_id: int
    name: str
    description: str | None
    framework: AgentFramework
    mcp_id: int
    mcp_version_id: int
    mcp_version: int
    system_prompt: str
    user_prompt: str
    llm_model_id: int | None
    llm_provider: str | None
    llm_model_name: str | None
    temperature: float | None
    max_output_tokens: int | None
    project_directory: str
    mcp_connections: list[AgentMcpConnection]
    project_revision: int
    default_build_id: int | None
    files: dict
    status: AgentDraftStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class ArtifactCheck(BaseModel):
    name: str
    passed: bool
    detail: str

class ArtifactValidationResponse(BaseModel):
    agent_id: int
    valid: bool
    checks: list[ArtifactCheck]


class AgentFileUpdate(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    content: str = Field(default="", max_length=500000)
    revision: int = Field(default=0, ge=0)


class AgentFolderCreate(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    revision: int = Field(default=0, ge=0)


class AgentProjectResponse(BaseModel):
    project_directory: str
    project_revision: int
    files: dict[str, str]
    mcp_connections: list[AgentMcpConnection]
