from pydantic import BaseModel, Field


class AgentTestRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)


class AgentTestResponse(BaseModel):
    agent_id: int
    output: str
    tools_available: int
    mcp_connected: bool
    llm_model_id: int