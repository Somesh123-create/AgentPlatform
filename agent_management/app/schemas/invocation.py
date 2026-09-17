from pydantic import BaseModel, Field


class AgentInvocationRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)


class AgentInvocationResponse(BaseModel):
    agent_id: int
    build_id: int
    status: str
    output: str | None
    tools_available: int
    error: str | None