from fastapi import APIRouter
from app.api.routes.agents import router as agents_router

api_router = APIRouter()
api_router.include_router(agents_router)
