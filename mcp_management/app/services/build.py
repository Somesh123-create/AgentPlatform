import asyncio
import json
import tempfile
import zipfile
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.build import MCPBuild, MCPBuildStatus
from app.models.mcp_version import MCPSourceKind, MCPVersion
from app.repositories.build import BuildRepository
from app.source.validator import validate_zip_archive


class BuildService:
    def __init__(self, db: AsyncSession):
        self.repository = BuildRepository(db)

    async def list_for_mcp(self, mcp_id: int) -> list[MCPBuild]:
        return await self.repository.list_for_mcp(mcp_id)

    async def get(self, build_id: int) -> MCPBuild | None:
        return await self.repository.get(build_id)

    async def build_version(self, mcp_id: int, version: MCPVersion) -> MCPBuild:
        build = await self.repository.create(MCPBuild(mcp_id=mcp_id, version_id=version.id))

        # Uploaded code is untrusted. It is only copied into a temporary build
        # context and is never imported or executed by the API process.
        if version.source_kind is not MCPSourceKind.ZIP:
            build.status = MCPBuildStatus.FAILED
            build.error = "Only ZIP sources can be built at this time."
            return await self.repository.save(build)

        artifact = Path(settings.artifact_storage_path) / f"{version.source_digest}.zip"
        if not artifact.exists():
            build.status = MCPBuildStatus.FAILED
            build.error = "Source artifact was not found."
            return await self.repository.save(build)

        try:
            archive = artifact.read_bytes()
            validated = validate_zip_archive(archive)
            manifest = validated.manifest
            command = manifest["command"]
            if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
                raise ValueError("manifest command must be a list of strings")
            image_ref = f"{settings.build_image_namespace}/mcp-{mcp_id}:v{version.version}"
            build.status = MCPBuildStatus.BUILDING
            build.image_ref = image_ref
            await self.repository.save(build)

            with tempfile.TemporaryDirectory(prefix="agenthub-mcp-build-") as directory:
                context = Path(directory)
                with zipfile.ZipFile(artifact) as source:
                    source.extractall(context)
                dockerfile = self._dockerfile(manifest, command)
                (context / "Dockerfile").write_text(dockerfile, encoding="utf-8")
                output = await self._run_engine(context, image_ref)

            build.logs = output[-settings.build_log_limit:]
            build.status = MCPBuildStatus.SUCCEEDED
        except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, asyncio.TimeoutError) as error:
            build.status = MCPBuildStatus.FAILED
            build.error = str(error) or "MCP image build failed."
            build.logs = (build.logs or "")[-settings.build_log_limit:]

        return await self.repository.save(build)

    @staticmethod
    def _dockerfile(manifest: dict[str, object], command: list[str]) -> str:
        requirements = manifest.get("requirements")
        install = ""
        if isinstance(requirements, str) and requirements:
            install = f"COPY {requirements} /tmp/requirements.txt\nRUN pip install --no-cache-dir -r /tmp/requirements.txt\n"
        return "\n".join([
            "FROM python:3.12-slim",
            "WORKDIR /app",
            "ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1",
            "RUN adduser --disabled-password --gecos '' --uid 10001 appuser",
            "COPY . /app",
            install.rstrip(),
            "RUN chown -R appuser:appuser /app",
            "USER appuser",
            f"CMD {json.dumps(command)}",
            "",
        ])

    async def _run_engine(self, context: Path, image_ref: str) -> str:
        # The engine runs only the image build here. Runtime execution is a
        # separate deployment concern and must apply stricter isolation limits.
        process = await asyncio.create_subprocess_exec(
            settings.container_engine,
            "build",
            "--tag",
            image_ref,
            str(context),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            output, _ = await asyncio.wait_for(process.communicate(), settings.build_timeout_seconds)
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            raise
        text = output.decode("utf-8", errors="replace")
        if process.returncode != 0:
            raise RuntimeError(text[-settings.build_log_limit:] or "Container image build failed.")
        return text