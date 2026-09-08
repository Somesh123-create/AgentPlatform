import hashlib
import logging
import os
from datetime import UTC, datetime

from mcp.server.fastmcp import FastMCP


logging.basicConfig(
    level=os.getenv("MCP_LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("sample-mcp")

mcp = FastMCP(
    os.getenv("MCP_SERVER_NAME", "sample-mcp"),
)


@mcp.tool()
def echo(message: str) -> str:
    """Return the supplied message after validating its size."""
    if not message:
        raise ValueError("message must not be empty")
    if len(message) > 10_000:
        raise ValueError("message must not exceed 10,000 characters")
    return message


@mcp.tool()
def sha256_text(text: str) -> dict[str, str | int]:
    """Return the SHA-256 digest and UTF-8 byte length of text."""
    if len(text) > 1_000_000:
        raise ValueError("text must not exceed 1,000,000 characters")
    encoded = text.encode("utf-8")
    return {"sha256": hashlib.sha256(encoded).hexdigest(), "bytes": len(encoded)}


@mcp.tool()
def server_status() -> dict[str, str]:
    """Return non-sensitive health and build information for this server."""
    return {
        "status": "healthy",
        "server": os.getenv("MCP_SERVER_NAME", "sample-mcp"),
        "version": os.getenv("MCP_SERVER_VERSION", "1.0.0"),
        "time_utc": datetime.now(UTC).isoformat(),
    }


@mcp.resource("health://status")
def health_resource() -> str:
    """Expose a lightweight health resource for MCP clients."""
    return "healthy"


if __name__ == "__main__":
    logger.info("starting MCP server")
    mcp.run(transport="stdio")