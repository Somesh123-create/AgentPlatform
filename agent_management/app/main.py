from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.agents import router as agents_router
from app.db.base import Base
from app.db.migrations import upgrade_agent_drafts
from app.db.session import engine
from app.models import agent_draft
from app.models import agent_build
from app.models import conversation


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await upgrade_agent_drafts(connection)
    yield
    await engine.dispose()


app = FastAPI(title="Agent Management Service", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(agents_router)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "agent-management"}
