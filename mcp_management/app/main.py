from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.db.base import Base
from app.db.session import engine
from app.models import mcp, mcp_build_job, mcp_version


@asynccontextmanager
async def lifespan(app: FastAPI):

    async with engine.begin() as connection:

        await connection.run_sync(
            Base.metadata.create_all
        )

    yield

    await engine.dispose()


app = FastAPI(
    title="AgentPlatform MCP Service",
    version="0.1.0",
    lifespan=lifespan,
)


app.include_router(
    api_router,
)


@app.get("/health")
async def health():

    return {
        "status": "healthy",
        "service": "mcp-service",
    }