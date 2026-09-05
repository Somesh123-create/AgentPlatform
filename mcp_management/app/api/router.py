from fastapi import APIRouter

from app.api.routes.mcp import router as mcp_router


api_router = APIRouter()

api_router.include_router(
    mcp_router
)