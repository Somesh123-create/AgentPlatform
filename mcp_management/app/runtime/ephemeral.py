import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.build import MCPBuild
from app.repositories.build import BuildRepository


class EphemeralRuntime:
    """
    Run MCP images on-demand with automatic cleanup.

    Every operation:
        1. Finds the latest successful build.
        2. Starts the MCP container.
        3. Communicates with the MCP server over STDIO.
        4. Performs the requested MCP operation.
        5. Terminates the container.

    Supported MCP operations:
        - initialize
        - notifications/initialized
        - tools/list
        - tools/call
    """

    MCP_PROTOCOL_VERSION = "2025-06-18"

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================================================
    # PUBLIC API
    # ============================================================

    async def list_tools(
        self,
        mcp_id: int,
        version_id: int,
    ) -> dict:
        """
        Discover tools exposed by an MCP image.

        Returns:

            {
                "tools": [...],
                "error": None
            }

        or:

            {
                "tools": [],
                "error": "..."
            }
        """

        build = await self._get_build(
            mcp_id=mcp_id,
            version_id=version_id,
        )

        if not build:
            return {
                "tools": [],
                "error": "No successful build found",
            }

        if not build.image_ref:
            return {
                "tools": [],
                "error": "No image reference available",
            }

        return await self._run_ephemeral_list_tools(build)

    async def invoke_tool(
        self,
        mcp_id: int,
        version_id: int,
        tool_name: str,
        tool_input: dict,
    ) -> dict:
        """
        Invoke an MCP tool from an image.

        Returns:

            {
                "output": "...",
                "error": None,
                "status": "success"
            }
        """

        build = await self._get_build(
            mcp_id=mcp_id,
            version_id=version_id,
        )

        if not build:
            return {
                "output": None,
                "error": "No successful build found",
                "status": "not_found",
            }

        if not build.image_ref:
            return {
                "output": None,
                "error": "No image reference available",
                "status": "no_image",
            }

        return await self._run_ephemeral_tool(
            build=build,
            tool_name=tool_name,
            tool_input=tool_input,
        )

    # ============================================================
    # BUILD LOOKUP
    # ============================================================

    async def _get_build(
        self,
        mcp_id: int,
        version_id: int,
    ) -> MCPBuild | None:
        """
        Get the latest successful build for a version.
        """

        build_repo = BuildRepository(self.db)

        build = await build_repo.latest_succeeded_for_version(
            version_id
        )
        print("Build:", str(build))
        if not build:
            return None

        if build.mcp_id != mcp_id:
            return None

        return build

    # ============================================================
    # CONTAINER COMMAND
    # ============================================================

    def _build_container_command(
        self,
        image_ref: str,
    ) -> list[str]:
        """
        Build the Podman/Docker command.

        The MCP server is expected to run as the image's
        ENTRYPOINT/CMD and communicate over STDIO.
        """

        return [
            settings.container_engine,
            "run",

            # Automatically remove the container.
            "--rm",

            # Security restrictions.
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt",
            "no-new-privileges",

            # Resource limits.
            "--pids-limit",
            "128",
            "--memory",
            "512m",
            "--cpus",
            "1",

            # No network access by default.
            "--network",
            "none",

            # Image.
            image_ref,
        ]

    # ============================================================
    # LIST TOOLS
    # ============================================================

    async def _run_ephemeral_list_tools(
        self,
        build: MCPBuild,
    ) -> dict:
        """
        Start an MCP container and perform:

            initialize
            notifications/initialized
            tools/list
        """

        image_ref = build.image_ref

        if not image_ref:
            return {
                "tools": [],
                "error": "No image reference available",
            }

        cmd = self._build_container_command(image_ref)

        process = None

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # ----------------------------------------------------
            # 1. MCP INITIALIZE
            # ----------------------------------------------------

            initialize_response = await self._send_request(
                process=process,
                method="initialize",
                params={
                    "protocolVersion": self.MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {
                        "name": "agent-platform",
                        "version": "1.0.0",
                    },
                },
                request_id=1,
                timeout=30,
            )

            if "error" in initialize_response:
                return {
                    "tools": [],
                    "error": self._extract_rpc_error(
                        initialize_response
                    ),
                }

            # ----------------------------------------------------
            # 2. INITIALIZED NOTIFICATION
            # ----------------------------------------------------

            await self._send_notification(
                process=process,
                method="notifications/initialized",
                params={},
            )

            # ----------------------------------------------------
            # 3. TOOLS/LIST
            # ----------------------------------------------------

            tools_response = await self._send_request(
                process=process,
                method="tools/list",
                params={},
                request_id=2,
                timeout=30,
            )

            if "error" in tools_response:
                return {
                    "tools": [],
                    "error": self._extract_rpc_error(
                        tools_response
                    ),
                }

            result = tools_response.get("result") or {}

            tools = result.get("tools") or []

            if not isinstance(tools, list):
                return {
                    "tools": [],
                    "error": "MCP server returned invalid tools list",
                }

            return {
                "tools": tools,
                "error": None,
            }

        except asyncio.TimeoutError:
            return {
                "tools": [],
                "error": "Tool discovery timed out",
            }

        except Exception as exc:
            stderr = await self._read_stderr(process)

            error_message = str(exc)

            if stderr:
                error_message = (
                    f"{error_message}. "
                    f"MCP stderr: {stderr}"
                )

            return {
                "tools": [],
                "error": error_message,
            }

        finally:
            await self._cleanup_process(process)

    # ============================================================
    # INVOKE TOOL
    # ============================================================

    async def _run_ephemeral_tool(
        self,
        build: MCPBuild,
        tool_name: str,
        tool_input: dict,
    ) -> dict:
        """
        Start an MCP container and perform:

            initialize
            notifications/initialized
            tools/call
        """

        image_ref = build.image_ref

        if not image_ref:
            return {
                "output": None,
                "error": "No image reference available",
                "status": "no_image",
            }

        cmd = self._build_container_command(image_ref)

        process = None

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # ----------------------------------------------------
            # 1. MCP INITIALIZE
            # ----------------------------------------------------

            initialize_response = await self._send_request(
                process=process,
                method="initialize",
                params={
                    "protocolVersion": self.MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {
                        "name": "agent-platform",
                        "version": "1.0.0",
                    },
                },
                request_id=1,
                timeout=30,
            )

            if "error" in initialize_response:
                return {
                    "output": None,
                    "error": self._extract_rpc_error(
                        initialize_response
                    ),
                    "status": "initialize_error",
                }

            # ----------------------------------------------------
            # 2. INITIALIZED NOTIFICATION
            # ----------------------------------------------------

            await self._send_notification(
                process=process,
                method="notifications/initialized",
                params={},
            )

            # ----------------------------------------------------
            # 3. TOOLS/CALL
            # ----------------------------------------------------

            call_response = await self._send_request(
                process=process,
                method="tools/call",
                params={
                    "name": tool_name,
                    "arguments": tool_input,
                },
                request_id=2,
                timeout=30,
            )

            # ----------------------------------------------------
            # MCP ERROR
            # ----------------------------------------------------

            if "error" in call_response:
                return {
                    "output": None,
                    "error": self._extract_rpc_error(
                        call_response
                    ),
                    "status": "error",
                }

            result = call_response.get("result") or {}

            # ----------------------------------------------------
            # MCP TOOL ERROR
            # ----------------------------------------------------

            if result.get("isError") is True:
                return {
                    "output": self._extract_tool_output(result),
                    "error": self._extract_tool_error(result),
                    "status": "tool_error",
                }

            # ----------------------------------------------------
            # SUCCESS
            # ----------------------------------------------------

            return {
                "output": self._extract_tool_output(result),
                "error": None,
                "status": "success",
            }

        except asyncio.TimeoutError:
            return {
                "output": None,
                "error": "Tool invocation timed out after 30 seconds",
                "status": "timeout",
            }

        except Exception as exc:
            stderr = await self._read_stderr(process)

            error_message = str(exc)

            if stderr:
                error_message = (
                    f"{error_message}. "
                    f"MCP stderr: {stderr}"
                )

            return {
                "output": None,
                "error": error_message,
                "status": "error",
            }

        finally:
            await self._cleanup_process(process)

    # ============================================================
    # JSON-RPC REQUEST
    # ============================================================

    async def _send_request(
        self,
        process: asyncio.subprocess.Process,
        method: str,
        params: dict,
        request_id: int,
        timeout: int = 30,
    ) -> dict:
        """
        Send a JSON-RPC request through MCP STDIO
        and wait for the matching response.
        """

        if process.stdin is None:
            raise RuntimeError("MCP process stdin is unavailable")

        if process.stdout is None:
            raise RuntimeError("MCP process stdout is unavailable")

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        payload = (
            json.dumps(
                request,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")

        process.stdin.write(payload)

        await process.stdin.drain()

        while True:
            line = await asyncio.wait_for(
                process.stdout.readline(),
                timeout=timeout,
            )

            if not line:
                stderr = await self._read_stderr(process)

                if stderr:
                    raise RuntimeError(
                        f"MCP process exited without response: {stderr}"
                    )

                raise RuntimeError(
                    "MCP process exited without response"
                )

            line = line.decode(
                "utf-8",
                errors="replace",
            ).strip()

            if not line:
                continue

            # MCP STDIO should contain JSON-RPC messages.
            # Ignore malformed/log lines defensively.
            try:
                response = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Ignore notifications and responses for other IDs.
            if response.get("id") != request_id:
                continue

            return response

    # ============================================================
    # JSON-RPC NOTIFICATION
    # ============================================================

    async def _send_notification(
        self,
        process: asyncio.subprocess.Process,
        method: str,
        params: dict | None = None,
    ) -> None:
        """
        Send a JSON-RPC notification.

        Notifications do not have an id and do not expect
        a response.
        """

        if process.stdin is None:
            raise RuntimeError("MCP process stdin is unavailable")

        notification = {
            "jsonrpc": "2.0",
            "method": method,
        }

        if params is not None:
            notification["params"] = params

        payload = (
            json.dumps(
                notification,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")

        process.stdin.write(payload)

        await process.stdin.drain()

    # ============================================================
    # RESPONSE HELPERS
    # ============================================================

    @staticmethod
    def _extract_rpc_error(
        response: dict,
    ) -> str:
        """
        Extract an MCP/JSON-RPC error.
        """

        error = response.get("error")

        if not error:
            return "Unknown MCP error"

        if isinstance(error, str):
            return error

        if isinstance(error, dict):
            code = error.get("code")
            message = error.get("message")

            if code is not None and message:
                return f"{message} (code: {code})"

            if message:
                return str(message)

            return json.dumps(error)

        return str(error)

    @staticmethod
    def _extract_tool_output(
        result: dict,
    ) -> str | None:
        """
        Extract human-readable output from MCP content.

        MCP content can contain:

            text
            image
            resource
            etc.

        We preserve text content here for the current API.
        """

        content = result.get("content") or []

        if not isinstance(content, list):
            return None

        text_parts: list[str] = []

        for item in content:
            if not isinstance(item, dict):
                continue

            if item.get("type") == "text":
                text = item.get("text")

                if text is not None:
                    text_parts.append(str(text))

        if not text_parts:
            return None

        return "\n".join(text_parts)

    @staticmethod
    def _extract_tool_error(
        result: dict,
    ) -> str:
        """
        Extract error information from an MCP tool result.
        """

        output = EphemeralRuntime._extract_tool_output(result)

        if output:
            return output

        return "MCP tool returned an error"

    # ============================================================
    # STDERR
    # ============================================================

    async def _read_stderr(
        self,
        process: asyncio.subprocess.Process | None,
    ) -> str:
        """
        Read available stderr from the MCP process.

        MCP servers should write logs to stderr, not stdout.
        """

        if not process or process.stderr is None:
            return ""

        try:
            data = await asyncio.wait_for(
                process.stderr.read(),
                timeout=1,
            )

            return data.decode(
                "utf-8",
                errors="replace",
            ).strip()

        except Exception:
            return ""

    # ============================================================
    # CLEANUP
    # ============================================================

    async def _cleanup_process(
        self,
        process: asyncio.subprocess.Process | None,
    ) -> None:
        """
        Ensure the MCP process/container is terminated.
        """

        if process is None:
            return

        try:
            if process.stdin:
                try:
                    process.stdin.close()
                except Exception:
                    pass

            if process.returncode is None:
                process.terminate()

                try:
                    await asyncio.wait_for(
                        process.wait(),
                        timeout=5,
                    )
                except asyncio.TimeoutError:
                    process.kill()

                    try:
                        await asyncio.wait_for(
                            process.wait(),
                            timeout=5,
                        )
                    except asyncio.TimeoutError:
                        pass

        except ProcessLookupError:
            pass

        except Exception:
            pass

