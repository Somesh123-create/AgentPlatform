from types import SimpleNamespace

from app.models.agent_draft import AgentFramework
from app.services.generator import generate_files
from app.services.agent import AgentDraftService


def test_generator_creates_framework_files_without_secrets():
    draft = SimpleNamespace(
        name="Support Agent",
        framework=AgentFramework.LANGGRAPH,
        mcp_id=9,
        mcp_version_id=11,
        mcp_version=2,
        system_prompt="Be concise.",
        user_prompt="Help the user.",
        llm_model_id=4,
        llm_provider="google",
        llm_model_name="gemini-test",
        temperature=0.2,
        max_output_tokens=500,
    )
    files = generate_files(draft)
    assert {"agent.py", "mcp_adapter.py", "runtime.py", "config.json", "project_manifest.json", "requirements.txt", ".env.example", ".gitignore", "Dockerfile", "compose.yaml", "README.md"} <= set(files)
    assert "MCP_1_ACCESS_TOKEN" in files[".env.example"]
    assert "LLM_MODEL_ID" in files[".env.example"]
    assert "GOOGLE_API_KEY=" in files[".env.example"]
    assert "MCP_1_ACCESS_TOKEN=" in files[".env.example"]
    assert "secret-value" not in "".join(files.values())
    assert "gemini-test" in files["agent.py"]
    assert '"mcp_connections"' in files["config.json"]
    compile(files["agent.py"], "agent.py", "exec")


def test_project_paths_are_normalized_and_contained():
    assert AgentDraftService.normalize_path("src\\agent.py") == "src/agent.py"
    assert AgentDraftService.normalize_path("agent.py") == "agent.py"
    for invalid in ("/agent.py", "../agent.py", "src/../agent.py", ""):
        try:
            AgentDraftService.normalize_path(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected invalid path: {invalid}")
