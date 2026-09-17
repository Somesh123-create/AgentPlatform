from datetime import datetime
from pydantic import BaseModel, Field
from app.models.llm import ConnectionTestStatus, CredentialStatus, LLMStatus

class ProviderResponse(BaseModel):
    id: int
    slug: str
    display_name: str
    api_family: str
    status: LLMStatus
    model_config = {"from_attributes": True}

class ModelResponse(BaseModel):
    id: int
    provider_id: int
    provider_slug: str
    model_name: str
    display_name: str
    capabilities: dict
    context_window: int | None
    max_output_tokens: int | None
    status: LLMStatus
    enabled: bool
    is_default: bool
    test_status: ConnectionTestStatus
    last_tested_at: datetime | None
    last_test_error: str | None

class ModelCreate(BaseModel):
    provider_id: int = Field(gt=0)
    model_name: str = Field(min_length=1, max_length=150)
    display_name: str = Field(min_length=1, max_length=150)
    capabilities: dict = Field(default_factory=dict)
    context_window: int | None = Field(default=None, gt=0)
    max_output_tokens: int | None = Field(default=None, gt=0)

class ModelUpdate(BaseModel):
    model_name: str | None = Field(default=None, min_length=1, max_length=150)
    display_name: str | None = Field(default=None, min_length=1, max_length=150)
    capabilities: dict | None = None
    context_window: int | None = Field(default=None, gt=0)
    max_output_tokens: int | None = Field(default=None, gt=0)
    status: LLMStatus | None = None

class ConnectionTestResponse(BaseModel):
    model_id: int
    status: ConnectionTestStatus
    tested_at: datetime
    error: str | None = None

class CompletionRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    system_prompt: str = Field(default="", max_length=20000)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_output_tokens: int | None = Field(default=None, gt=0, le=100000)

class CompletionResponse(BaseModel):
    model_id: int
    output: str

class CredentialCreate(BaseModel):
    api_key: str = Field(min_length=1, max_length=4096)

class CredentialResponse(BaseModel):
    provider_id: int
    status: CredentialStatus
    configured: bool
    updated_at: datetime | None

class ModelAccessUpdate(BaseModel):
    enabled: bool = True

class DefaultResponse(BaseModel):
    model_id: int | None
