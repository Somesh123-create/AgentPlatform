import ast
import json
import posixpath
from datetime import datetime, timezone
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from app.models.agent_draft import AgentDraft, AgentDraftStatus
from app.repositories.agent import AgentDraftRepository
from app.schemas.agent import AgentDraftCreate, AgentDraftUpdate
from app.services.generator import generate_files


class AgentDraftService:
    def __init__(self, db):
        self.repository = AgentDraftRepository(db)

    async def create(self, owner_id: int, data: AgentDraftCreate) -> AgentDraft:
        values = data.model_dump()
        connections = values.get("mcp_connections") or [
            {"mcp_id": values["mcp_id"], "mcp_version_id": values["mcp_version_id"], "mcp_version": values["mcp_version"]}
        ]
        values["mcp_connections"] = connections
        return await self.repository.create(AgentDraft(owner_id=owner_id, **values, files={}, project_revision=0))

    async def list(self, owner_id: int):
        drafts = await self.repository.list_for_owner(owner_id)
        return [self._ensure_connections(draft) for draft in drafts]

    async def get(self, owner_id: int, draft_id: int):
        draft = await self.repository.get_owned(draft_id, owner_id)
        return self._ensure_connections(draft) if draft else None

    @staticmethod
    def _ensure_connections(draft: AgentDraft) -> AgentDraft:
        if not draft.mcp_connections:
            draft.mcp_connections = [{"mcp_id": draft.mcp_id, "mcp_version_id": draft.mcp_version_id, "mcp_version": draft.mcp_version}]
        return draft

    async def update(self, owner_id: int, draft_id: int, data: AgentDraftUpdate):
        draft = await self.get(owner_id, draft_id)
        if not draft:
            return None
        updates = data.model_dump(exclude_unset=True)
        for field, value in updates.items():
            if field == "mcp_connections" and not value:
                continue
            setattr(draft, field, value)
        if data.mcp_connections:
            first = data.mcp_connections[0]
            draft.mcp_id = first.mcp_id
            draft.mcp_version_id = first.mcp_version_id
            draft.mcp_version = first.mcp_version
        if set(updates) != {"default_build_id"}:
            draft.status = AgentDraftStatus.DRAFT
        return await self.repository.save(draft)

    async def generate(self, owner_id: int, draft_id: int):
        draft = await self.get(owner_id, draft_id)
        if not draft:
            return None
        if not draft.mcp_connections:
            draft.mcp_connections = [{"mcp_id": draft.mcp_id, "mcp_version_id": draft.mcp_version_id, "mcp_version": draft.mcp_version}]
        draft.files = {**(draft.files or {}), **generate_files(draft)}
        draft.status = AgentDraftStatus.GENERATED
        return await self.repository.save(draft)

    @staticmethod
    def normalize_path(path: str) -> str:
        raw = path.replace("\\", "/")
        if raw.startswith("/") or any(part == ".." for part in raw.split("/")):
            raise ValueError("Path must stay inside the project directory")
        normalized = posixpath.normpath(raw).strip("/")
        if not normalized or normalized == "." or normalized.startswith("../") or normalized == "..":
            raise ValueError("Path must be a non-empty relative project path")
        if any(part in {"", ".", ".."} for part in normalized.split("/")):
            raise ValueError("Path must be a normalized relative project path")
        return normalized

    async def update_file(self, owner_id: int, draft_id: int, path: str, content: str, revision: int):
        draft = await self.get(owner_id, draft_id)
        if not draft:
            return None
        if revision != draft.project_revision:
            raise ValueError("Project changed; reload before saving")
        normalized = self.normalize_path(path)
        draft.files = {**(draft.files or {}), normalized: content}
        draft.project_revision += 1
        return await self.repository.save(draft)

    async def create_folder(self, owner_id: int, draft_id: int, path: str, revision: int):
        folder = self.normalize_path(path)
        draft = await self.get(owner_id, draft_id)
        if not draft:
            return None
        if revision != draft.project_revision:
            raise ValueError("Project changed; reload before saving")
        marker = f"{folder}/.gitkeep"
        draft.files = {**(draft.files or {}), marker: ""}
        draft.project_revision += 1
        return await self.repository.save(draft)

    async def delete(self, owner_id: int, draft_id: int) -> bool:
        draft = await self.get(owner_id, draft_id)
        if not draft:
            return False
        await self.repository.delete(draft)
        return True

    def export_zip(self, draft: AgentDraft) -> BytesIO:
        archive = BytesIO()
        with ZipFile(archive, "w", ZIP_DEFLATED) as zip_file:
            for filename, content in draft.files.items():
                zip_file.writestr(filename, content)
        archive.seek(0)
        return archive

    def validate_artifact(self, draft: AgentDraft) -> dict:
        checks = []
        required = {"agent.py", "mcp_adapter.py", "runtime.py", "config.json", "project_manifest.json", "requirements.txt", ".env.example", ".gitignore", "Dockerfile", "compose.yaml", "README.md"}
        missing = sorted(required - set(draft.files))
        checks.append({"name": "required-files", "passed": not missing, "detail": "All required files are present." if not missing else f"Missing: {', '.join(missing)}"})
        try:
            config = json.loads(draft.files.get("config.json", ""))
            connections = config.get("mcp_connections", [])
            config_ok = config.get("agent_name") == draft.name and bool(connections) and connections[0].get("mcp_id") == draft.mcp_id
            checks.append({"name": "config", "passed": config_ok, "detail": "Configuration matches the draft." if config_ok else "Generated configuration does not match the draft."})
        except (json.JSONDecodeError, AttributeError):
            checks.append({"name": "config", "passed": False, "detail": "config.json is not valid JSON."})
        env_content = draft.files.get(".env.example", "")
        env_keys = ("LLM_API_URL", "LLM_ACCESS_TOKEN", "LLM_MODEL_ID", "MCP_1_ACCESS_TOKEN")
        env_valid = all(key in env_content for key in env_keys) and not any(secret in env_content for secret in ("replace-me", "sk-", "gsk_", "nvapi-"))
        checks.append({"name": "runtime-env", "passed": env_valid, "detail": "Runtime placeholders are present and empty." if env_valid else "Runtime environment placeholders are missing or contain a credential."})
        for filename in ("agent.py", "mcp_adapter.py", "runtime.py"):
            try:
                ast.parse(draft.files.get(filename, ""), filename=filename)
                checks.append({"name": filename, "passed": True, "detail": "Python syntax is valid."})
            except SyntaxError as error:
                checks.append({"name": filename, "passed": False, "detail": f"Python syntax error at line {error.lineno}."})
        return {"agent_id": draft.id, "valid": all(check["passed"] for check in checks), "checks": checks}
