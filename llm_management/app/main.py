from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.llm import router as llm_router
from app.db.base import Base
from app.db.migrations import upgrade_model_access
from app.db.session import AsyncSessionLocal, engine
from app.models import llm
from app.services.catalog import seed_catalog

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await upgrade_model_access(connection)
    async with AsyncSessionLocal() as session:
        await seed_catalog(session)
    yield
    await engine.dispose()

app = FastAPI(title="LLM Management Service", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(llm_router)

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "llm-management"}
