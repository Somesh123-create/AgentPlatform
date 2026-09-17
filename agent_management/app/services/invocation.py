import asyncio
import json

from app.core.build_config import build_settings
from app.models.agent_build import AgentBuild
from app.models.agent_draft import AgentDraft


async def invoke_build(draft: AgentDraft, build: AgentBuild, prompt: str, token: str) -> dict:
    if not build.image_ref:
        raise ValueError("Build has no image reference.")
    connections = draft.mcp_connections or [{"mcp_id": draft.mcp_id, "mcp_version_id": draft.mcp_version_id, "mcp_version": draft.mcp_version}]
    environment = {
        "LLM_API_URL": "http://host.containers.internal:8003",
        "LLM_ACCESS_TOKEN": token,
        "LLM_MODEL_ID": str(draft.llm_model_id or ""),
        "TEMPERATURE": str(draft.temperature or 0.2),
        "MAX_OUTPUT_TOKENS": str(draft.max_output_tokens or 512),
    }
    for index, connection in enumerate(connections, start=1):
        environment[f"MCP_{index}_API_URL"] = "http://host.containers.internal:8001"
        environment[f"MCP_{index}_ACCESS_TOKEN"] = token
    command = [build_settings.container_engine, "run", "--rm", "--interactive", "--read-only", "--cap-drop=ALL", "--security-opt", "no-new-privileges", "--memory", "512m", "--cpus", "1", "--pids-limit", "128"]
    for key, value in environment.items():
        command.extend(["--env", f"{key}={value}"])
    command.append(build.image_ref)
    process = await asyncio.create_subprocess_exec(*command, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate((json.dumps({"prompt": prompt, "system_prompt": draft.system_prompt}) + "\n").encode()), build_settings.runtime_timeout_seconds)
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()
        raise ValueError("Agent runtime timed out.")
    if process.returncode != 0:
        raise ValueError(stderr.decode("utf-8", errors="replace")[-build_settings.build_log_limit:] or "Agent runtime failed.")
    try:
        result = json.loads(stdout.decode("utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("Agent runtime returned invalid output.") from error
    return {"agent_id": draft.id, "build_id": build.id, "status": result.get("status", "success"), "output": result.get("output"), "tools_available": result.get("tools_available", 0), "error": result.get("error")}