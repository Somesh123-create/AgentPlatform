import asyncio
import json
import tempfile
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.build_config import build_settings
from app.models.agent_build import AgentBuild, AgentBuildStatus
from app.models.agent_draft import AgentDraft
from app.repositories.build import AgentBuildRepository


class AgentBuildService:
    def __init__(self, db: AsyncSession):
        self.repository = AgentBuildRepository(db)

    async def list_for_agent(self, agent_id: int, owner_id: int):
        return await self.repository.list_for_agent(agent_id, owner_id)

    async def build(self, draft: AgentDraft, owner_id: int) -> AgentBuild:
        build = await self.repository.create(AgentBuild(agent_id=draft.id, owner_id=owner_id))
        image_ref = f"{build_settings.build_image_namespace}/agent-{draft.id}:latest"
        build.status = AgentBuildStatus.BUILDING
        build.image_ref = image_ref
        await self.repository.save(build)
        try:
            with tempfile.TemporaryDirectory(prefix="agenthub-agent-build-") as directory:
                context = Path(directory)
                for filename, content in draft.files.items():
                    target = context / filename
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(content, encoding="utf-8")
                (context / "Dockerfile").write_text(self._dockerfile(), encoding="utf-8")
                process = await asyncio.create_subprocess_exec(build_settings.container_engine, "build", "--tag", image_ref, str(context), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
                output, _ = await asyncio.wait_for(process.communicate(), build_settings.build_timeout_seconds)
                build.logs = output.decode("utf-8", errors="replace")[-build_settings.build_log_limit:]
                if process.returncode != 0:
                    raise RuntimeError("Agent image build failed.")
            build.status = AgentBuildStatus.SUCCEEDED
        except (OSError, RuntimeError, asyncio.TimeoutError) as error:
            build.status = AgentBuildStatus.FAILED
            build.error = str(error)
        return await self.repository.save(build)

    @staticmethod
    def _dockerfile() -> str:
        return "\n".join([
            "FROM python:3.12-slim",
            "WORKDIR /app",
            "ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1",
            "COPY requirements.txt /tmp/requirements.txt",
            "RUN pip install --no-cache-dir -r /tmp/requirements.txt",
            "COPY . /app",
            "CMD [\"python\", \"runtime.py\"]",
            "",
        ])