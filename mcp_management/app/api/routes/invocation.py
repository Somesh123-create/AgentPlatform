from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from agent_auth import CurrentUser
from typing import Annotated

from app.core.auth import current_user
from app.db.session import get_db
from app.runtime.ephemeral import EphemeralRuntime


router = APIRouter(prefix="/mcps/{mcp_id}", tags=["MCP Invocation"])


async def _owned_mcp(mcp_id: int, user_id: int, db: AsyncSession):
    from app.services.mcp import MCPService
    mcp = await MCPService(db).get(mcp_id)
    if not mcp:
        raise HTTPException(status_code=404, detail="MCP not found")
    if mcp.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return mcp


@router.post("/{version_id}/invoke-tool", response_model=dict)
async def invoke_tool(
    mcp_id: int,
    version_id: int,
    authenticated_user: Annotated[CurrentUser, Depends(current_user)],
    db: AsyncSession = Depends(get_db),
    tool_name: str = Body(...),
    tool_input: dict = Body(...),
):
    runtime = EphemeralRuntime(db)
    return await runtime.invoke_tool(mcp_id, version_id, tool_name, tool_input)


@router.post("/{version_id}/list-tools", response_model=dict)
async def list_tools(
    mcp_id: int,
    version_id: int,
    authenticated_user: Annotated[CurrentUser, Depends(current_user)],
    db: AsyncSession = Depends(get_db),
):
    runtime = EphemeralRuntime(db)
    return await runtime.list_tools(mcp_id, version_id)