from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from agent_auth import CurrentUser

from app.core.auth import current_user
from app.db.session import get_db
from app.schemas.mcp import (
    MCPCreate,
    MCPResponse,
    MCPUpdate,
)
from app.services.mcp import MCPService


router = APIRouter(
    prefix="/mcps",
    tags=["MCP"],
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