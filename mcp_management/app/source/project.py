import hashlib
import io
import json
import posixpath
import zipfile

from app.source.validator import MANIFEST_NAME, validate_zip_archive


MAX_FILE_BYTES = 2 * 1024 * 1024

TRANSPORT_BY_PROTOCOL = {
    "STDIO": "stdio",
    "SSE": "sse",
    "STREAMABLE_HTTP": "streamable-http",
}


def safe_path(path: str) -> str:
    raw_path = path.strip().replace("\\", "/")
    if any(part in {"", ".", ".."} for part in raw_path.split("/")):
        raise ValueError("file path is invalid")
    normalized = posixpath.normpath(raw_path)
    if not normalized or normalized in {".", ".."} or normalized.startswith("../") or normalized.startswith("/"):
        raise ValueError("file path must stay inside the MCP project")
    return normalized


def files_from_archive(content: bytes) -> dict[str, str]:
    files: dict[str, str] = {}
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            if info.file_size > MAX_FILE_BYTES:
                raise ValueError("project file exceeds the maximum editable size")
            try:
                files[info.filename] = archive.read(info).decode("utf-8")
            except UnicodeDecodeError as error:
                raise ValueError(f"{info.filename} is not a UTF-8 text file") from error
    return dict(sorted(files.items()))


def zip_bytes(files: dict[str, str]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.writestr(path, files[path])
    return output.getvalue()


def archive_from_files(files: dict[str, str]) -> tuple[bytes, dict[str, object]]:
    normalized_files: dict[str, str] = {}
    for path, content in files.items():
        normalized = safe_path(path)
        if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_FILE_BYTES:
            raise ValueError(f"{normalized} exceeds the maximum editable size")
        normalized_files[normalized] = content
    if MANIFEST_NAME not in normalized_files:
        raise ValueError(f"project must contain {MANIFEST_NAME}")
    try:
        json.loads(normalized_files[MANIFEST_NAME])
    except json.JSONDecodeError as error:
        raise ValueError("mcp.manifest.json is not valid JSON") from error
    validated = validate_zip_archive(zip_bytes(normalized_files))
    return zip_bytes(normalized_files), validated.manifest


def revision_for(content: bytes) -> int:
    return int(hashlib.sha256(content).hexdigest()[:12], 16)


def sample_project(name: str, protocol: str) -> dict[str, str]:
    safe_name = name.strip() or "AgentHub MCP Server"
    transport = TRANSPORT_BY_PROTOCOL.get(protocol.upper(), "stdio")
    manifest = {
        "name": safe_name,
        "version": "0.1.0",
        "description": f"Production-ready MCP server for {safe_name}.",
        "command": ["python", "server.py"],
        "requirements": "requirements.txt",
        "protocol": protocol,
    }
    return {
        MANIFEST_NAME: json.dumps(manifest, indent=2) + "\n",
        "server.py": f'import logging\nimport os\n\nfrom mcp.server.fastmcp import FastMCP\n\n\nlogging.basicConfig(level=os.getenv("MCP_LOG_LEVEL", "INFO").upper(), format="%(asctime)s %(levelname)s %(name)s %(message)s")\nlogger = logging.getLogger("agenthub-mcp")\nmcp = FastMCP(\n    os.getenv("MCP_SERVER_NAME", "AgentHub MCP Server"),\n    host=os.getenv("MCP_HOST", "127.0.0.1"),\n    port=int(os.getenv("MCP_PORT", "8000")),\n)\n\n\n@mcp.tool()\ndef health_check() -> str:\n    """Return a lightweight health response for connectivity checks."""\n    logger.info("health_check called")\n    return "ok"\n\n\n@mcp.tool()\ndef echo(message: str) -> str:\n    """Return the supplied message. Replace this with your business capability."""\n    logger.info("echo called with %d characters", len(message))\n    return message\n\n\nif __name__ == "__main__":\n    transport = os.getenv("MCP_TRANSPORT", "{transport}")\n    logger.info("Starting MCP server with %s transport on %s:%s", transport, os.getenv("MCP_HOST", "127.0.0.1"), os.getenv("MCP_PORT", "8000"))\n    mcp.run(transport=transport)\n',
        "requirements.txt": "mcp>=1.9.0,<2.0.0\n",
        ".env": "MCP_SERVER_NAME=" + safe_name + "\nMCP_TRANSPORT=" + transport + "\nMCP_HOST=0.0.0.0\nMCP_PORT=8000\n# Add provider credentials here when your tools need them.\n",
        ".env.example": "MCP_SERVER_NAME=" + safe_name + "\nMCP_TRANSPORT=" + transport + "\nMCP_HOST=0.0.0.0\nMCP_PORT=8000\n",
        "README.md": f"# {safe_name}\n\nInstall dependencies with `pip install -r requirements.txt`, then run `python server.py`.\n",
    }
