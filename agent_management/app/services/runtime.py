import httpx

from app.core.runtime_config import runtime_settings
from app.models.agent_draft import AgentDraft


async def test_agent(draft: AgentDraft, prompt: str, token: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    tools = await _request_mcp(draft, headers)
    system_prompt = draft.system_prompt
    if tools:
        tool_names = ", ".join(str(tool.get("name", "unknown")) for tool in tools if isinstance(tool, dict))
        system_prompt = f"{system_prompt}\n\nAvailable MCP tools: {tool_names}"
    if draft.llm_model_id is None:
        raise ValueError("Select an LLM model before testing the agent.")
    async with httpx.AsyncClient(timeout=75) as client:
        response = await client.post(f"{runtime_settings.llm_api_url.rstrip('/')}/models/{draft.llm_model_id}/complete", headers=headers, json={"prompt": prompt, "system_prompt": system_prompt, "temperature": draft.temperature, "max_output_tokens": draft.max_output_tokens})
    if not response.is_success:
        detail = response.json().get("detail", "LLM completion failed") if response.headers.get("content-type", "").startswith("application/json") else "LLM completion failed"
        raise ValueError(detail)
    result = response.json()
    return {"agent_id": draft.id, "output": result["output"], "tools_available": len(tools), "mcp_connected": True, "llm_model_id": draft.llm_model_id}


async def _request_mcp(draft: AgentDraft, headers: dict[str, str]) -> list[dict]:
    connections = draft.mcp_connections or [{"mcp_id": draft.mcp_id, "mcp_version_id": draft.mcp_version_id}]
    async with httpx.AsyncClient(timeout=30) as client:
        tools = []
        for connection in connections:
            mcp_id = connection.get("mcp_id") if isinstance(connection, dict) else connection.mcp_id
            version_id = connection.get("mcp_version_id") if isinstance(connection, dict) else connection.mcp_version_id
            response = await client.post(f"{runtime_settings.mcp_api_url.rstrip('/')}/mcps/{mcp_id}/{version_id}/list-tools", headers=headers)
            if not response.is_success:
                detail = response.json().get("detail", "MCP tool discovery failed") if response.headers.get("content-type", "").startswith("application/json") else "MCP tool discovery failed"
                raise ValueError(detail)
            result = response.json()
            if result.get("error"):
                raise ValueError(result["error"])
            tools.extend(result.get("tools", []))
        return tools