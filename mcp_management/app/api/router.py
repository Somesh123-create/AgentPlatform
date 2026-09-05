from fastapi import APIRouter

from app.api.routes.mcp import router as mcp_router
from app.api.routes.versions import router as versions_router


api_router = APIRouter()

api_router.include_router(
    mcp_router
)

api_router.include_router(
    versions_router
)