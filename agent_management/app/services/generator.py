import json
from typing import Any

from app.models.agent_draft import AgentDraft, AgentFramework


def generate_files(draft: AgentDraft) -> dict[str, str]:
    connections = _connections(draft)
    config = {
        "schema_version": 2,
        "agent_name": draft.name,
        "framework": draft.framework.value,
        "project_directory": getattr(draft, "project_directory", "") or "agent-project",
        "prompts": {"system": draft.system_prompt, "user": draft.user_prompt},
        "llm": {
            "model_id": draft.llm_model_id,
            "provider": draft.llm_provider,
            "model_name": draft.llm_model_name,
            "api_family": _api_family(draft.llm_provider),
            "temperature": draft.temperature,
            "max_output_tokens": draft.max_output_tokens,
            "api_key_env": "LLM_ACCESS_TOKEN",
            "provider_api_key_env": _llm_key_env(draft.llm_provider),
        },
        "mcp_connections": connections,
    }
    framework_import = "from google.adk.agents import Agent" if draft.framework is AgentFramework.GOOGLE_ADK else "from langgraph.graph import END, START, StateGraph"
    framework_body = _google_body(draft) if draft.framework is AgentFramework.GOOGLE_ADK else _langgraph_body(draft)
    requirements = "google-adk>=1.0,<2\n" if draft.framework is AgentFramework.GOOGLE_ADK else "langgraph>=0.2,<1\n"
    requirements += "httpx>=0.27,<1\npython-dotenv>=1,<2\n"
    return {
        "agent.py": f"{framework_import}\nfrom mcp_adapter import MCPToolClient\n\n{framework_body}\n",
        "mcp_adapter.py": _adapter_body(),
        "runtime.py": _runtime_body(),
        "config.json": json.dumps(config, indent=2) + "\n",
        "project_manifest.json": json.dumps(config, indent=2) + "\n",
        "requirements.txt": requirements,
        ".env.example": _env_example(draft, connections),
        ".gitignore": ".env\n__pycache__/\n*.pyc\n",
        "Dockerfile": _dockerfile(),
        "compose.yaml": _compose_file(draft),
        "README.md": _readme(draft, connections),
    }


def _connections(draft: AgentDraft) -> list[dict[str, Any]]:
    configured = getattr(draft, "mcp_connections", None) or []
    if not configured:
        configured = [{"mcp_id": draft.mcp_id, "mcp_version_id": draft.mcp_version_id, "mcp_version": draft.mcp_version}]
    result = []
    for index, connection in enumerate(configured, start=1):
        item = connection if isinstance(connection, dict) else connection.__dict__
        result.append({
            "name": item.get("name") or f"mcp_{index}",
            "mcp_id": item["mcp_id"],
            "version_id": item.get("mcp_version_id", item.get("version_id")),
            "version": item["mcp_version"],
            "protocol": item.get("protocol") or "STREAMABLE_HTTP",
            "mcp_type": item.get("mcp_type") or "REMOTE",
            "image_ref": item.get("image_ref"),
            "api_url_env": f"MCP_{index}_API_URL",
            "token_env": f"MCP_{index}_ACCESS_TOKEN",
        })
    return result


def _api_family(provider: str | None) -> str | None:
    if not provider:
        return None
    return {"openai": "openai_compatible", "groq": "openai_compatible", "nvidia": "openai_compatible", "google": "google"}.get(provider, provider)


def _llm_key_env(provider: str | None) -> str:
    return f"{(provider or 'CUSTOM').upper().replace('-', '_')}_API_KEY"


def _google_body(draft: AgentDraft) -> str:
    return f'''mcp_client = MCPToolClient()\n\nroot_agent = Agent(\n    name={draft.name!r},\n    model={(draft.llm_model_name or "gemini-2.0-flash")!r},\n    instruction={draft.system_prompt!r},\n    tools=mcp_client.tools(),\n)'''


def _langgraph_body(draft: AgentDraft) -> str:
    return f'''def call_agent(state: dict) -> dict:\n    state["system_prompt"] = {draft.system_prompt!r}\n    state["user_prompt"] = {draft.user_prompt!r}\n    state["llm_provider"] = {draft.llm_provider!r}\n    state["llm_model"] = {(draft.llm_model_name or "default")!r}\n    state["tools"] = MCPToolClient().tools()\n    return state\n\ngraph = StateGraph(dict)\ngraph.add_node("agent", call_agent)\ngraph.add_edge(START, "agent")\ngraph.add_edge("agent", END)\nagent = graph.compile()'''


def _adapter_body() -> str:
    return '''import json
import os
from pathlib import Path

import httpx


class MCPToolClient:
    def __init__(self):
        self.connections = json.loads(Path("config.json").read_text(encoding="utf-8"))["mcp_connections"]

    def _headers(self, connection):
        return {"Authorization": "Bearer " + os.environ[connection["token_env"]]}

    def tools(self):
        discovered = []
        for connection in self.connections:
            url = os.environ[connection["api_url_env"]].rstrip("/")
            response = httpx.post(
                f"{url}/mcps/{connection['mcp_id']}/{connection['version_id']}/list-tools",
                headers=self._headers(connection), timeout=60,
            )
            response.raise_for_status()
            for tool in response.json().get("tools", []):
                tool["name"] = f"{connection['name']}.{tool.get('name', tool.get('id', 'tool'))}"
                tool["mcp_connection"] = connection["name"]
                discovered.append(tool)
        return discovered

    def call(self, qualified_name: str, arguments: dict):
        connection_name, _, tool_name = qualified_name.partition(".")
        connection = next(item for item in self.connections if item["name"] == connection_name)
        url = os.environ[connection["api_url_env"]].rstrip("/")
        response = httpx.post(
            f"{url}/mcps/{connection['mcp_id']}/{connection['version_id']}/invoke-tool",
            headers=self._headers(connection),
            json={"tool_name": tool_name, "tool_input": arguments}, timeout=60,
        )
        response.raise_for_status()
        return response.json()
'''

def _runtime_body() -> str:
    return '''import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

from mcp_adapter import MCPToolClient


def main():
    load_dotenv()
    config = json.loads(Path("config.json").read_text(encoding="utf-8"))
    request = json.loads(sys.stdin.readline())
    tools = MCPToolClient().tools()
    llm = config["llm"]
    api_key = os.environ[llm["api_key_env"]]
    response = httpx.post(
        f"{os.environ['LLM_API_URL'].rstrip('/')}/models/{llm['model_id']}/complete",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"prompt": request.get("prompt", ""), "system_prompt": config["prompts"]["system"], "temperature": llm.get("temperature") or 0.2, "max_output_tokens": llm.get("max_output_tokens") or 512},
        timeout=60,
    )
    response.raise_for_status()
    result = response.json()
    print(json.dumps({"status": "success", "output": result.get("output", ""), "tools_available": len(tools), "model_id": llm["model_id"]}), flush=True)


if __name__ == "__main__":
    main()
'''


def _env_example(draft: AgentDraft, connections: list[dict[str, Any]]) -> str:
    lines = ["LLM_API_URL=http://localhost:8003", "LLM_ACCESS_TOKEN=", f"LLM_MODEL_ID={draft.llm_model_id or ''}", f"LLM_PROVIDER={draft.llm_provider or ''}", f"LLM_MODEL_NAME={draft.llm_model_name or ''}", f"{_llm_key_env(draft.llm_provider)}=", f"TEMPERATURE={draft.temperature or 0.2}", f"MAX_OUTPUT_TOKENS={draft.max_output_tokens or 512}"]
    for connection in connections:
        lines.extend([f"{connection['api_url_env']}=http://localhost:8001", f"{connection['token_env']}=", f"MCP_{connection['name'].upper()}_IMAGE_REF={connection['image_ref'] or ''}"])
    return "\n".join(lines) + "\n"


def _dockerfile() -> str:
    return """FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "runtime.py"]
"""


def _compose_file(draft: AgentDraft) -> str:
    service = (getattr(draft, "project_directory", "") or "agent").replace("_", "-").replace(" ", "-")
    return f"""services:
  {service}:
    build: .
    env_file: .env
    stdin_open: true
    read_only: true
"""


def _readme(draft: AgentDraft, connections: list[dict[str, Any]]) -> str:
    names = ", ".join(connection["name"] for connection in connections)
    return f'''# {draft.name}\n\nGenerated {draft.framework.value} agent project.\n\nConfigured MCP connections: {names}.\n\n## Run\n\n1. Copy `.env.example` to `.env` and fill the selected LLM API key and MCP access tokens.\n2. Run `docker compose up --build`.\n3. Send one JSON request per line to the container.\n\nCredentials are intentionally excluded from this archive.\n'''
