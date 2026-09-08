from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from agent_auth import CurrentUser

from app.core.auth import current_user
from app.db.session import get_db
from app.models.mcp_version import MCPVersion
from app.repositories.version import VersionRepository
from app.schemas.build import MCPBuildResponse
from app.services.build import BuildService
from app.services.mcp import MCPService


router = APIRouter(prefix="/mcps/{mcp_id}", tags=["MCP Builds"])


async def _owned_version(mcp_id: int, version_number: int, user_id: int, db: AsyncSession) -> MCPVersion:
    mcp = await MCPService(db).get(mcp_id)
    if not mcp:
        raise HTTPException(status_code=404, detail="MCP not found")
    if mcp.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    version = await VersionRepository(db).get_version(mcp_id, version_number)
    if not version:
        raise HTTPException(status_code=404, detail="MCP version not found")
    return version


@router.post("/versions/{version_number}/build", response_model=MCPBuildResponse, status_code=status.HTTP_201_CREATED)
async def build_version(
    mcp_id: int,
    version_number: int,
    authenticated_user: Annotated[CurrentUser, Depends(current_user)],
    db: AsyncSession = Depends(get_db),
):
    version = await _owned_version(mcp_id, version_number, authenticated_user.user_id, db)
    return await BuildService(db).build_version(mcp_id, version)


@router.get("/builds", response_model=list[MCPBuildResponse])
async def list_builds(
    mcp_id: int,
    authenticated_user: Annotated[CurrentUser, Depends(current_user)],
    db: AsyncSession = Depends(get_db),
):
    mcp = await MCPService(db).get(mcp_id)
    if not mcp:
        raise HTTPException(status_code=404, detail="MCP not found")
    if mcp.owner_id != authenticated_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return await BuildService(db).list_for_mcp(mcp_id)


@router.get("/builds/{build_id}", response_model=MCPBuildResponse)
async def get_build(
    mcp_id: int,
    build_id: int,
    authenticated_user: Annotated[CurrentUser, Depends(current_user)],
    db: AsyncSession = Depends(get_db),
):
    mcp = await MCPService(db).get(mcp_id)
    build = await BuildService(db).get(build_id)
    if not mcp or not build or build.mcp_id != mcp_id:
        raise HTTPException(status_code=404, detail="Build not found")
    if mcp.owner_id != authenticated_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return build