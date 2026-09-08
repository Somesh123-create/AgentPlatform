from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from agent_auth import CurrentUser

from app.core.auth import current_user
from app.db.session import get_db
from app.repositories.version import VersionRepository
from app.schemas.deployment import MCPDeploymentResponse
from app.services.deployment import DeploymentService
from app.services.mcp import MCPService


router = APIRouter(prefix="/mcps/{mcp_id}", tags=["MCP Deployments"])


async def _owned_mcp(mcp_id: int, user_id: int, db: AsyncSession):
    mcp = await MCPService(db).get(mcp_id)
    if not mcp:
        raise HTTPException(status_code=404, detail="MCP not found")
    if mcp.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return mcp


@router.post("/versions/{version_number}/deploy", response_model=MCPDeploymentResponse, status_code=status.HTTP_201_CREATED)
async def deploy_version(mcp_id: int, version_number: int, authenticated_user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    await _owned_mcp(mcp_id, authenticated_user.user_id, db)
    version = await VersionRepository(db).get_version(mcp_id, version_number)
    if not version:
        raise HTTPException(status_code=404, detail="MCP version not found")
    try:
        return await DeploymentService(db).deploy(mcp_id, version.id, await _successful_build_id(db, mcp_id, version.id))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


async def _successful_build_id(db: AsyncSession, mcp_id: int, version_id: int) -> int:
    from app.repositories.build import BuildRepository
    build = await BuildRepository(db).latest_succeeded_for_version(version_id)
    if not build or build.mcp_id != mcp_id:
        raise ValueError("A successful build is required before deployment.")
    return build.id


@router.get("/deployments", response_model=list[MCPDeploymentResponse])
async def list_deployments(mcp_id: int, authenticated_user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    await _owned_mcp(mcp_id, authenticated_user.user_id, db)
    return await DeploymentService(db).list_for_mcp(mcp_id)


@router.get("/deployments/{deployment_id}", response_model=MCPDeploymentResponse)
async def get_deployment(mcp_id: int, deployment_id: int, authenticated_user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    await _owned_mcp(mcp_id, authenticated_user.user_id, db)
    deployment = await DeploymentService(db).get(deployment_id)
    if not deployment or deployment.mcp_id != mcp_id:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return await DeploymentService(db).refresh(deployment)


@router.post("/deployments/{deployment_id}/undeploy", response_model=MCPDeploymentResponse)
async def undeploy(mcp_id: int, deployment_id: int, authenticated_user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    await _owned_mcp(mcp_id, authenticated_user.user_id, db)
    deployment = await DeploymentService(db).get(deployment_id)
    if not deployment or deployment.mcp_id != mcp_id:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return await DeploymentService(db).undeploy(deployment)


@router.post("/deployments/{deployment_id}/restart", response_model=MCPDeploymentResponse)
async def restart(mcp_id: int, deployment_id: int, authenticated_user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    await _owned_mcp(mcp_id, authenticated_user.user_id, db)
    deployment = await DeploymentService(db).get(deployment_id)
    if not deployment or deployment.mcp_id != mcp_id:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return await DeploymentService(db).restart(deployment)