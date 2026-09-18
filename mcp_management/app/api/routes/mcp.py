from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from agent_auth import CurrentUser

from app.core.auth import current_user
from app.core.config import settings
from app.db.session import get_db
from app.schemas.mcp import (
    MCPCreate,
    MCPResponse,
    MCPUpdate,
)
from app.services.mcp import MCPService
from app.services.version import VersionService
from app.schemas.version import MCPVersionCreate, MCPVersionResponse
from app.source.project import archive_from_files, sample_project
from app.source.storage import SourceArtifactStore
from app.source.validator import validate_zip_archive


router = APIRouter(
    prefix="/mcps",
    tags=["MCP"],
)


@router.post("/{mcp_id}/generate", response_model=MCPVersionResponse, status_code=status.HTTP_201_CREATED)
async def generate_mcp_project(
    mcp_id: int,
    authenticated_user: Annotated[CurrentUser, Depends(current_user)],
    db: AsyncSession = Depends(get_db),
):
    service = MCPService(db)
    mcp = await service.get(mcp_id)
    if not mcp:
        raise HTTPException(status_code=404, detail="MCP not found")
    if mcp.owner_id != authenticated_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    protocol = getattr(mcp.protocol, "value", mcp.protocol)
    archive, manifest = archive_from_files(sample_project(mcp.name, str(protocol)))
    validated = validate_zip_archive(archive)
    SourceArtifactStore(settings.artifact_storage_path).put(validated.digest, archive)
    version = await VersionService(db).create(
        mcp_id,
        MCPVersionCreate(
            source_kind="ZIP",
            source_digest=validated.digest,
            source_reference=validated.digest,
            manifest=manifest,
        ),
    )
    return MCPVersionResponse(
        id=version.id,
        mcp_id=version.mcp_id,
        version=version.version,
        source_kind=version.source_kind,
        source_digest=version.source_digest,
        source_reference=version.source_reference,
        manifest=manifest,
        created_at=version.created_at,
        updated_at=version.updated_at,
    )


@router.post(
    "",
    response_model=MCPResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_mcp(
        data: MCPCreate,
    authenticated_user: Annotated[CurrentUser, Depends(current_user)],
        db: AsyncSession = Depends(get_db),
    ):

    service = MCPService(db)

    return await service.create(
        owner_id=authenticated_user.user_id,
        data=data,
    )


@router.get(
    "",
    response_model=list[MCPResponse],
)
async def list_mcps(
    authenticated_user: Annotated[CurrentUser, Depends(current_user)],
        db: AsyncSession = Depends(get_db),
    ):

    service = MCPService(db)

    return await service.list_by_owner(
        owner_id=authenticated_user.user_id,
    )


@router.get(
    "/{mcp_id}",
    response_model=MCPResponse,
)
async def get_mcp(
        mcp_id: int,
    authenticated_user: Annotated[CurrentUser, Depends(current_user)],
        db: AsyncSession = Depends(get_db),
    ):

    service = MCPService(db)

    mcp = await service.get(mcp_id)

    if not mcp:
        raise HTTPException(
            status_code=404,
            detail="MCP not found",
        )

    if mcp.owner_id != authenticated_user.user_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied",
        )

    return mcp


@router.patch(
    "/{mcp_id}",
    response_model=MCPResponse,
)
async def update_mcp(
        mcp_id: int,
        data: MCPUpdate,
    authenticated_user: Annotated[CurrentUser, Depends(current_user)],
        db: AsyncSession = Depends(get_db),
    ):

    service = MCPService(db)

    mcp = await service.get(mcp_id)

    if not mcp:
        raise HTTPException(
            status_code=404,
            detail="MCP not found",
        )

    if mcp.owner_id != authenticated_user.user_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied",
        )

    return await service.update(
        mcp,
        data,
    )


@router.delete(
    "/{mcp_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_mcp(
        mcp_id: int,
    authenticated_user: Annotated[CurrentUser, Depends(current_user)],
        db: AsyncSession = Depends(get_db),
    ):

    service = MCPService(db)

    mcp = await service.get(mcp_id)

    if not mcp:
        raise HTTPException(
            status_code=404,
            detail="MCP not found",
        )

    if mcp.owner_id != authenticated_user.user_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied",
        )

    await service.delete(mcp)