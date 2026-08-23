from fastapi import APIRouter

from app.core.redis import redis_client


router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


@router.get("")
async def health():

    redis_status = "ok"

    try:
        await redis_client.ping()

    except Exception:
        redis_status = "unhealthy"

    return {
        "status": "ok",
        "services": {
            "redis": redis_status,
        },
    }