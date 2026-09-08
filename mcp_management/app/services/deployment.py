import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.deployment import MCPDeployment, MCPDeploymentStatus
from app.repositories.build import BuildRepository
from app.repositories.deployment import DeploymentRepository


class DeploymentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = DeploymentRepository(db)
        self.builds = BuildRepository(db)

    async def list_for_mcp(self, mcp_id: int) -> list[MCPDeployment]:
        return await self.repository.list_for_mcp(mcp_id)

    async def get(self, deployment_id: int) -> MCPDeployment | None:
        return await self.repository.get(deployment_id)

    async def deploy(self, mcp_id: int, version_id: int, build_id: int) -> MCPDeployment:
        build = await self.builds.get(build_id)
        if not build or build.mcp_id != mcp_id or build.version_id != version_id or str(build.status) not in {"MCPBuildStatus.SUCCEEDED", "SUCCEEDED"}:
            raise ValueError("A successful build is required before deployment.")
        deployment = await self.repository.create(MCPDeployment(mcp_id=mcp_id, version_id=version_id, build_id=build_id, image_ref=build.image_ref or ""))
        try:
            container_id, logs = await self._run("start", deployment.id, build.image_ref or "")
            deployment.container_id = container_id
            deployment.logs = logs[-settings.build_log_limit:]
            deployment.status = MCPDeploymentStatus.RUNNING
        except (OSError, RuntimeError, asyncio.TimeoutError) as error:
            deployment.status = MCPDeploymentStatus.FAILED
            deployment.error = str(error)
        return await self.repository.save(deployment)

    async def undeploy(self, deployment: MCPDeployment) -> MCPDeployment:
        if deployment.container_id:
            try:
                await self._run("stop", deployment.id, deployment.image_ref, deployment.container_id)
            except (OSError, RuntimeError, asyncio.TimeoutError) as error:
                deployment.error = str(error)
                deployment.status = MCPDeploymentStatus.FAILED
                return await self.repository.save(deployment)
        deployment.status = MCPDeploymentStatus.STOPPED
        return await self.repository.save(deployment)

    async def restart(self, deployment: MCPDeployment) -> MCPDeployment:
        await self.undeploy(deployment)
        deployment.status = MCPDeploymentStatus.STARTING
        deployment.error = None
        try:
            container_id, logs = await self._run("start", deployment.id, deployment.image_ref)
            deployment.container_id = container_id
            deployment.logs = logs[-settings.build_log_limit:]
            deployment.status = MCPDeploymentStatus.RUNNING
        except (OSError, RuntimeError, asyncio.TimeoutError) as error:
            deployment.status = MCPDeploymentStatus.FAILED
            deployment.error = str(error)
        return await self.repository.save(deployment)

    async def refresh(self, deployment: MCPDeployment) -> MCPDeployment:
        if deployment.container_id and deployment.status == MCPDeploymentStatus.RUNNING:
            try:
                output = await self._inspect(deployment.container_id)
                if "true" not in output.lower():
                    deployment.status = MCPDeploymentStatus.STOPPED
                    deployment.logs = (deployment.logs + "\n" + output)[-settings.build_log_limit:]
            except (OSError, RuntimeError, asyncio.TimeoutError) as error:
                deployment.status = MCPDeploymentStatus.FAILED
                deployment.error = str(error)
            return await self.repository.save(deployment)
        return deployment

    async def _run(self, action: str, deployment_id: int, image_ref: str, container_id: str | None = None) -> tuple[str, str]:
        name = f"agenthub-mcp-{deployment_id}"
        if action == "stop":
            args = [settings.container_engine, "rm", "-f", container_id or name]
        else:
            # User images run without host mounts, privileges, or network access.
            args = [settings.container_engine, "run", "-d", "--name", name, "--read-only", "--cap-drop=ALL", "--security-opt", "no-new-privileges", "--pids-limit", "128", "--memory", "512m", "--cpus", "1", "--network", "none", image_ref]
        process = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        try:
            output, _ = await asyncio.wait_for(process.communicate(), settings.build_timeout_seconds)
        except asyncio.TimeoutError:
            process.kill(); await process.communicate(); raise
        text = output.decode("utf-8", errors="replace")
        if process.returncode != 0:
            raise RuntimeError(text[-settings.build_log_limit:] or f"Container {action} failed.")
        return text.strip(), text

    async def _inspect(self, container_id: str) -> str:
        process = await asyncio.create_subprocess_exec(settings.container_engine, "inspect", "--format", "{{.State.Running}}", container_id, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        output, _ = await asyncio.wait_for(process.communicate(), settings.build_timeout_seconds)
        text = output.decode("utf-8", errors="replace")
        if process.returncode != 0:
            raise RuntimeError(text.strip() or "Unable to inspect deployment.")
        return text