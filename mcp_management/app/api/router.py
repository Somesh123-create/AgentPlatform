from fastapi import APIRouter

from app.api.routes.mcp import router as mcp_router
from app.api.routes.versions import router as versions_router
from app.api.routes.builds import router as builds_router
from app.api.routes.deployments import router as deployments_router


api_router = APIRouter()

api_router.include_router(
    mcp_router
)

api_router.include_router(
    versions_router
)

api_router.include_router(
    builds_router
)

api_router.include_router(
    deployments_router
)