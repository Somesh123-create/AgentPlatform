from fastapi import APIRouter
from app.api.routes.llm import router as llm_router
api_router = APIRouter()
api_router.include_router(llm_router)
