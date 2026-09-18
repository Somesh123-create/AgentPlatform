import asyncio
import json
import re
import tempfile
import uuid
from pathlib import Path
from typing import Any
import httpx

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.build import MCPBuild
from app.repositories.build import BuildRepository
from app.repositories.version import VersionRepository


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
                "logs": ["No successful build found for this MCP version."],
            }

        if not build.image_ref:
            return {
                "tools": [],
                "error": "No image reference available",
                "logs": ["The successful build has no image reference."],
            }

        protocol = await self._version_protocol(mcp_id, version_id)
        if protocol in {"SSE", "STREAMABLE_HTTP"}:
            return await self._run_http_list_tools(build, protocol)
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
                "logs": ["No successful build found for this MCP version."],
            }

        if not build.image_ref:
            return {
                "output": None,
                "error": "No image reference available",
                "status": "no_image",
                "logs": ["The successful build has no image reference."],
            }

        protocol = await self._version_protocol(mcp_id, version_id)
        if protocol in {"SSE", "STREAMABLE_HTTP"}:
            return await self._run_http_tool(build, protocol, tool_name, tool_input)
        return await self._run_ephemeral_tool(build=build, tool_name=tool_name, tool_input=tool_input)

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

        return await build_repo.latest_succeeded_for_version(mcp_id, version_id)

    async def _version_protocol(self, mcp_id: int, version_id: int) -> str:
        version = await VersionRepository(self.db).get_by_id(mcp_id, version_id)
        if not version:
            return "STDIO"
        try:
            manifest = json.loads(version.manifest)
        except (TypeError, json.JSONDecodeError):
            return "STDIO"
        return str(manifest.get("protocol", "STDIO")).upper()

    # ============================================================
    # CONTAINER COMMAND
    # ============================================================

    def _build_container_command(self, image_ref: str, transport: str = "stdio", port: int | None = None) -> list[str]:
        """
        Build the Podman/Docker command.

        The MCP server is expected to run as the image's
        ENTRYPOINT/CMD and communicate over STDIO.
        """

        container_name = f"agenthub-mcp-{uuid.uuid4().hex[:12]}"
        return [
            settings.container_engine,
            "run",
            "--name",
            container_name,

            # Automatically remove the container.
            "--rm",

            "--interactive",

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

            "--network",
            "none" if transport == "stdio" else "bridge",
            "--env",
            f"MCP_TRANSPORT={transport}",

            *(["--env", "MCP_HOST=0.0.0.0", "--env", "MCP_PORT=8000", "--publish", "127.0.0.1::8000"] if port else []),

            # Image.
            image_ref,
        ]

    async def _start_http_process(self, build: MCPBuild, protocol: str):
        transport = "sse" if protocol == "SSE" else "streamable-http"
        command = self._build_container_command(build.image_ref or "", transport, 1)
        container_name = command[command.index("--name") + 1]
        create_command = [*command]
        create_command[1] = "create"
        create_process = await asyncio.create_subprocess_exec(
            *create_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, create_error = await create_process.communicate()
        if create_process.returncode != 0:
            raise RuntimeError(create_error.decode("utf-8", errors="replace").strip() or "Unable to create temporary MCP container")

        process = await asyncio.create_subprocess_exec(
            settings.container_engine,
            "start",
            "--attach",
            container_name,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Podman allocates an empty host port (127.0.0.1::8000) when the
        # container starts, not when it is created.
        port_output = b""
        port_error = b""
        match = None
        for _ in range(50):
            port_process = await asyncio.create_subprocess_exec(
                settings.container_engine,
                "port",
                container_name,
                "8000/tcp",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            port_output, port_error = await port_process.communicate()
            match = re.search(r":(\d+)\s*$", port_output.decode("utf-8", errors="replace").strip())
            if match:
                break
            if process.returncode is not None:
                break
            await asyncio.sleep(0.1)

        if not match:
            stderr = port_error.decode("utf-8", errors="replace").strip()
            if process.returncode is not None and process.stderr is not None:
                stderr = (await process.stderr.read()).decode("utf-8", errors="replace").strip() or stderr
            await self._remove_container(container_name)
            raise RuntimeError(stderr or "Podman did not report the published MCP port")

        return process, int(match.group(1)), transport, container_name

    async def _remove_container(self, container_name: str) -> None:
        process = await asyncio.create_subprocess_exec(
            settings.container_engine,
            "rm",
            "--force",
            container_name,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await process.communicate()

    @staticmethod
    def _http_client(logs: list[str]):
        async def record_response(response: httpx.Response) -> None:
            logs.append(
                f"HTTP {response.request.method} {response.request.url.path} -> "
                f"{response.status_code} {response.headers.get('content-type', 'unknown')}"
            )

        return httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30, read=300),
            event_hooks={"response": [record_response]},
        )

    async def _run_http_list_tools(self, build: MCPBuild, protocol: str) -> dict:
        process = None
        container_name: str | None = None
        output_tasks: list[asyncio.Task[None]] = []
        logs = [f"Starting {protocol} MCP image {build.image_ref}."]
        try:
            process, port, transport, container_name = await self._start_http_process(build, protocol)
            logs.append(f"Started temporary container {container_name}.")
            output_tasks = self._capture_process_output(process, logs)
            url = f"http://127.0.0.1:{port}/{'sse' if protocol == 'SSE' else 'mcp'}"
            await self._wait_for_http_port(port, process)
            logs.append(f"MCP HTTP endpoint is ready on port {port}.")
            logs.append(f"Connecting to {url}.")
            async with self._http_client(logs) as client:
                async with (sse_client(url) if protocol == "SSE" else streamable_http_client(url, http_client=client)) as streams:
                    read_stream, write_stream = streams[:2]
                    async with ClientSession(read_stream, write_stream) as session:
                        await asyncio.wait_for(session.initialize(), 30)
                        logs.append("MCP initialized over HTTP.")
                        result = await asyncio.wait_for(session.list_tools(), 30)
                        tools = [tool.model_dump() for tool in result.tools]
                        return {"tools": tools, "error": None, "logs": logs + [f"Discovery completed. Found {len(tools)} tool(s)."]}
        except Exception as error:
            stderr = await self._read_process_streams(process)
            detail = self._exception_message(error)
            if stderr:
                detail = f"{detail}. MCP stderr: {stderr}"
            elif process and process.returncode is not None:
                detail = f"{detail}. MCP container exited with code {process.returncode}."
            return {"tools": [], "error": detail, "logs": logs + [detail]}
        finally:
            await self._stop_output_capture(output_tasks)
            await self._cleanup_process(process)
            if container_name:
                await self._remove_container(container_name)

    async def _run_http_tool(self, build: MCPBuild, protocol: str, tool_name: str, tool_input: dict) -> dict:
        process = None
        container_name: str | None = None
        output_tasks: list[asyncio.Task[None]] = []
        logs = [f"Starting {protocol} MCP image {build.image_ref}.", f"Calling tool {tool_name} over HTTP."]
        try:
            process, port, transport, container_name = await self._start_http_process(build, protocol)
            logs.append(f"Started temporary container {container_name}.")
            output_tasks = self._capture_process_output(process, logs)
            url = f"http://127.0.0.1:{port}/{'sse' if protocol == 'SSE' else 'mcp'}"
            await self._wait_for_http_port(port, process)
            logs.append(f"MCP HTTP endpoint is ready on port {port}.")
            async with self._http_client(logs) as client:
                async with (sse_client(url) if protocol == "SSE" else streamable_http_client(url, http_client=client)) as streams:
                    read_stream, write_stream = streams[:2]
                    async with ClientSession(read_stream, write_stream) as session:
                        await asyncio.wait_for(session.initialize(), 30)
                        result = await asyncio.wait_for(session.call_tool(tool_name, tool_input), 30)
                        output = self._extract_tool_output(result.model_dump())
                        if result.isError:
                            return {"output": output, "error": output or "MCP tool returned an error", "status": "tool_error", "logs": logs + ["MCP tool returned an error."]}
                        return {"output": output, "error": None, "status": "success", "logs": logs + ["Tool call completed successfully."]}
        except Exception as error:
            stderr = await self._read_process_streams(process)
            detail = self._exception_message(error)
            if stderr:
                detail = f"{detail}. MCP stderr: {stderr}"
            elif process and process.returncode is not None:
                detail = f"{detail}. MCP container exited with code {process.returncode}."
            return {"output": None, "error": detail, "status": "error", "logs": logs + [detail]}
        finally:
            await self._stop_output_capture(output_tasks)
            await self._cleanup_process(process)
            if container_name:
                await self._remove_container(container_name)

    @staticmethod
    def _capture_process_output(
        process: asyncio.subprocess.Process,
        logs: list[str],
        capture_stdout: bool = True,
    ) -> list[asyncio.Task[None]]:
        tasks: list[asyncio.Task[None]] = []
        if capture_stdout and process.stdout is not None:
            tasks.append(asyncio.create_task(EphemeralRuntime._drain_stream(process.stdout, "stdout", logs)))
        if process.stderr is not None:
            tasks.append(asyncio.create_task(EphemeralRuntime._drain_stream(process.stderr, "stderr", logs)))
        return tasks

    @staticmethod
    async def _drain_stream(stream: asyncio.StreamReader, name: str, logs: list[str]) -> None:
        try:
            while line := await stream.readline():
                message = line.decode("utf-8", errors="replace").strip()
                if message:
                    logs.append(f"MCP {name}: {message}")
        except (asyncio.CancelledError, ConnectionError):
            return

    @staticmethod
    async def _stop_output_capture(tasks: list[asyncio.Task[None]]) -> None:
        if not tasks:
            return
        try:
            await asyncio.wait_for(asyncio.gather(*tasks), timeout=0.2)
        except asyncio.TimeoutError:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

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
        output_tasks: list[asyncio.Task[None]] = []
        logs = [f"Starting MCP image {image_ref}.", "Sending initialize request."]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            output_tasks = self._capture_process_output(process, logs, capture_stdout=False)

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
                logs.append("MCP initialize returned an error.")
                return {
                    "tools": [],
                    "error": self._extract_rpc_error(
                        initialize_response
                    ),
                    "logs": logs,
                }

            # ----------------------------------------------------
            # 2. INITIALIZED NOTIFICATION
            # ----------------------------------------------------

            await self._send_notification(
                process=process,
                method="notifications/initialized",
                params={},
            )
            logs.append("MCP initialized. Requesting tools/list.")

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
                logs.append("MCP tools/list returned an error.")
                return {
                    "tools": [],
                    "error": self._extract_rpc_error(
                        tools_response
                    ),
                    "logs": logs,
                }

            result = tools_response.get("result") or {}

            tools = result.get("tools") or []

            if not isinstance(tools, list):
                return {
                    "tools": [],
                    "error": "MCP server returned invalid tools list",
                    "logs": logs + ["MCP returned an invalid tools list."],
                }

            await self._stop_output_capture(output_tasks)
            logs.append(f"Discovery completed. Found {len(tools)} tool(s).")
            return {
                "tools": tools,
                "error": None,
                "logs": logs,
            }

        except asyncio.TimeoutError:
            stderr = await self._read_stderr(process)
            detail = "Tool discovery timed out after 30 seconds"
            if stderr:
                detail = f"{detail}. MCP stderr: {stderr}"
                logs.append(f"stderr: {stderr}")
            return {
                "tools": [],
                "error": detail,
                "logs": logs + [detail],
            }

        except Exception as exc:
            await self._stop_output_capture(output_tasks)
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
                "logs": logs + [error_message],
            }
        finally:
            await self._stop_output_capture(output_tasks)
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
        output_tasks: list[asyncio.Task[None]] = []
        logs = [f"Starting MCP image {image_ref}.", f"Calling tool {tool_name}."]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            output_tasks = self._capture_process_output(process, logs, capture_stdout=False)

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
                                    "logs": logs + ["MCP initialize returned an error."],
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
                                    "logs": logs + ["MCP tools/call returned an error."],
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
                                "logs": logs + ["MCP tool returned an error."],
                }

            # ----------------------------------------------------
            # SUCCESS
            # ----------------------------------------------------

            await self._stop_output_capture(output_tasks)
            logs.append("Tool call completed successfully.")
            return {
                "output": self._extract_tool_output(result),
                "error": None,
                "status": "success",
                "logs": logs,
            }

        except asyncio.TimeoutError:
            await self._stop_output_capture(output_tasks)
            stderr = await self._read_stderr(process)
            detail = "Tool invocation timed out after 30 seconds"
            if stderr:
                detail = f"{detail}. MCP stderr: {stderr}"
            return {
                "output": None,
                "error": detail,
                "status": "timeout",
                            "logs": logs + [detail],
            }

        except Exception as exc:
            await self._stop_output_capture(output_tasks)
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
                "logs": logs + [error_message],
            }

        finally:
            await self._stop_output_capture(output_tasks)
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

    async def _read_process_streams(self, process: asyncio.subprocess.Process | None) -> str:
        if process is None:
            return ""
        chunks: list[str] = []
        for stream_name, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
            if stream is None:
                continue
            try:
                data = await asyncio.wait_for(stream.read(), timeout=0.2)
            except (asyncio.TimeoutError, Exception):
                continue
            if data:
                chunks.append(f"{stream_name}: {data.decode('utf-8', errors='replace').strip()}")
        return " ".join(chunks)

    async def _wait_for_http_port(self, port: int, process: asyncio.subprocess.Process) -> None:
        while process.returncode is None:
            try:
                reader, writer = await asyncio.open_connection("127.0.0.1", port)
                writer.close()
                await writer.wait_closed()
                return
            except (ConnectionRefusedError, OSError):
                await asyncio.sleep(0.1)
        raise RuntimeError(f"MCP container exited with code {process.returncode} before HTTP endpoint became ready")

    @staticmethod
    def _exception_message(error: BaseException) -> str:
        if isinstance(error, BaseExceptionGroup):
            nested = "; ".join(
                EphemeralRuntime._exception_message(item)
                for item in error.exceptions
            )
            return nested or str(error)
        return str(error) or error.__class__.__name__

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

