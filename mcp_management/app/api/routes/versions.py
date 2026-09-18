import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from agent_auth import CurrentUser

from app.core.auth import current_user
from app.core.config import settings
from app.db.session import get_db
from app.source.storage import SourceArtifactStore
from app.source.validator import MAX_ARCHIVE_BYTES, ArchiveValidationError, validate_zip_archive
from app.schemas.version import MCPProjectFileDelete, MCPProjectFileUpdate, MCPProjectFolderCreate, MCPProjectResponse, MCPVersionCreate, MCPVersionResponse
from app.services.mcp import MCPService
from app.services.version import VersionService
from app.source.project import archive_from_files, files_from_archive, revision_for, safe_path


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


def _project_response(version, content: bytes) -> MCPProjectResponse:
    return MCPProjectResponse(version_id=version.id, revision=revision_for(content), files=files_from_archive(content))


def _store() -> SourceArtifactStore:
    return SourceArtifactStore(settings.artifact_storage_path)


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


async def _load_owned_version(mcp_id: int, version_number: int, user_id: int, db: AsyncSession):
    await _owned_mcp(mcp_id, user_id, db)
    version = await VersionService(db).get(mcp_id, version_number)
    if not version:
        raise HTTPException(status_code=404, detail="MCP version not found")
    return version


async def _save_project(version, revision: int, files: dict[str, str], db: AsyncSession):
    try:
        current = _store().get(version.source_digest)
        if revision != revision_for(current):
            raise HTTPException(status_code=409, detail="Project changed on the server; reload before saving")
        archive, manifest = archive_from_files(files)
    except HTTPException:
        raise
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    validated = validate_zip_archive(archive)
    _store().put(validated.digest, archive)
    version.source_digest = validated.digest
    version.source_reference = validated.digest
    version.manifest = json.dumps(manifest, sort_keys=True)
    await db.commit()
    await db.refresh(version)
    return _project_response(version, archive)


@router.get("/{version_number}/project", response_model=MCPProjectResponse)
async def get_project(mcp_id: int, version_number: int, authenticated_user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    version = await _load_owned_version(mcp_id, version_number, authenticated_user.user_id, db)
    try:
        return _project_response(version, _store().get(version.source_digest))
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.put("/{version_number}/project/file", response_model=MCPProjectResponse)
async def update_project_file(mcp_id: int, version_number: int, data: MCPProjectFileUpdate, authenticated_user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    version = await _load_owned_version(mcp_id, version_number, authenticated_user.user_id, db)
    try:
        files = files_from_archive(_store().get(version.source_digest))
        files[safe_path(data.path)] = data.content
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return await _save_project(version, data.revision, files, db)


@router.post("/{version_number}/project/folder", response_model=MCPProjectResponse)
async def create_project_folder(mcp_id: int, version_number: int, data: MCPProjectFolderCreate, authenticated_user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    version = await _load_owned_version(mcp_id, version_number, authenticated_user.user_id, db)
    try:
        files = files_from_archive(_store().get(version.source_digest))
        files[f"{safe_path(data.path)}/.gitkeep"] = ""
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return await _save_project(version, data.revision, files, db)


@router.delete("/{version_number}/project/file", response_model=MCPProjectResponse)
async def delete_project_file(mcp_id: int, version_number: int, data: MCPProjectFileDelete, authenticated_user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    version = await _load_owned_version(mcp_id, version_number, authenticated_user.user_id, db)
    try:
        files = files_from_archive(_store().get(version.source_digest))
        files.pop(safe_path(data.path), None)
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return await _save_project(version, data.revision, files, db)


@router.get("/{version_number}/project/export")
async def export_project(mcp_id: int, version_number: int, authenticated_user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    version = await _load_owned_version(mcp_id, version_number, authenticated_user.user_id, db)
    try:
        content = _store().get(version.source_digest)
    except FileNotFoundError as error:
        raise HTTPException(status_code=409, detail="MCP source artifact is unavailable") from error
    return Response(content=content, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="mcp-v{version.version}.zip"'})
