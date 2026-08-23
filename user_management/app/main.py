from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import auth
from app.api.routes import health
from app.api.routes import users
from app.core.database import engine
from app.core.logger_setup import configure_logging
from app.core.redis import redis_client
from app.models.user import Base


configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):

    # Startup

    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all
        )

    yield

    # Shutdown

    await redis_client.close()
    await engine.dispose()


app = FastAPI(
    title="AgentPlatform",
    version="1.0.0",
    lifespan=lifespan,
)


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)


@app.get("/")
async def root():

    return {
        "application": "AgentPlatform",
        "status": "running",
    }