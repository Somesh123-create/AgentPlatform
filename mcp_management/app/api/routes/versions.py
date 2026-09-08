import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from agent_auth import CurrentUser

from app.core.auth import current_user
from app.core.config import settings
from app.db.session import get_db
from app.source.storage import SourceArtifactStore
from app.source.validator import MAX_ARCHIVE_BYTES, ArchiveValidationError, validate_zip_archive
from app.schemas.version import MCPVersionCreate, MCPVersionResponse
from app.services.mcp import MCPService
from app.services.version import VersionService


router = APIRouter(prefix="/mcps/{mcp_id}/versions", tags=["MCP Versions"])


async def _owned_mcp(mcp_id: int, user_id: int, db: AsyncSession):
    mcp = await MCPService(db).get(mcp_id)
    if not mcp:
        raise HTTPException(status_code=404, detail="MCP not found")
    if mcp.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return mcp


def _version_response(version):
    return MCPVersionResponse(
        id=version.id,
        mcp_id=version.mcp_id,
        version=version.version,
        source_kind=version.source_kind,
        source_digest=version.source_digest,
        source_reference=version.source_reference,
        manifest=json.loads(version.manifest),
        created_at=version.created_at,
        updated_at=version.updated_at,
    )


@router.post("", response_model=MCPVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_version(
    mcp_id: int,
    data: MCPVersionCreate,
    authenticated_user: Annotated[CurrentUser, Depends(current_user)],
    db: AsyncSession = Depends(get_db),
):
    await _owned_mcp(mcp_id, authenticated_user.user_id, db)
    version = await VersionService(db).create(mcp_id, data)
    return _version_response(version)


@router.post("/upload", response_model=MCPVersionResponse, status_code=status.HTTP_201_CREATED)
async def upload_version(
    mcp_id: int,
    authenticated_user: Annotated[CurrentUser, Depends(current_user)],
    archive: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    await _owned_mcp(mcp_id, authenticated_user.user_id, db)
    content = await archive.read(MAX_ARCHIVE_BYTES + 1)
    if len(content) > MAX_ARCHIVE_BYTES:
        raise HTTPException(status_code=413, detail="source archive exceeds the maximum size")
    try:
        validated = validate_zip_archive(content)
    except ArchiveValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    SourceArtifactStore(settings.artifact_storage_path).put(validated.digest, content)
    version = await VersionService(db).create(
        mcp_id,
        MCPVersionCreate(
            source_kind="ZIP",
            source_digest=validated.digest,
            source_reference=validated.digest,
            manifest=validated.manifest,
        ),
    )
    return _version_response(version)


@router.get("", response_model=list[MCPVersionResponse])
async def list_versions(
    mcp_id: int,
    authenticated_user: Annotated[CurrentUser, Depends(current_user)],
    db: AsyncSession = Depends(get_db),
):
    await _owned_mcp(mcp_id, authenticated_user.user_id, db)
    versions = await VersionService(db).list(mcp_id)
    return [_version_response(version) for version in versions]


@router.get("/{version_number}", response_model=MCPVersionResponse)
async def get_version(
    mcp_id: int,
    version_number: int,
    authenticated_user: Annotated[CurrentUser, Depends(current_user)],
    db: AsyncSession = Depends(get_db),
):
    await _owned_mcp(mcp_id, authenticated_user.user_id, db)
    version = await VersionService(db).get(mcp_id, version_number)
    if not version:
        raise HTTPException(status_code=404, detail="MCP version not found")
    return _version_response(version)
