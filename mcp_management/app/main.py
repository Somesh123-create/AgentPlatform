from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.builds import router as builds_router
from app.api.routes.deployments import router as deployments_router
from app.api.routes.invocation import router as invocation_router
from app.api.routes.mcp import router as mcp_router
from app.api.routes.versions import router as versions_router
from app.db.base import Base
from app.db.session import engine
from app.models import build, deployment, mcp, mcp_version


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Register concrete routers directly so FastAPI flattens every endpoint. A
# nested APIRouter object is not exposed as an application route by itself.
app.include_router(mcp_router)
app.include_router(versions_router)
app.include_router(deployments_router)
app.include_router(invocation_router)
app.include_router(builds_router)
app.include_router(deployments_router)


@app.get("/health")
async def health():

    return {
        "status": "healthy",
        "service": "mcp-service",
    }