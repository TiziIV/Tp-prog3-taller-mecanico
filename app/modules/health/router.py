from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live", status_code=status.HTTP_200_OK)
async def health_live() -> dict[str, str]:
    """Liveness probe: returns 200 without touching the database."""
    return {"status": "live"}


@router.get("/ready", status_code=status.HTTP_200_OK)
async def health_ready(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    """Readiness probe: executes SELECT 1 and responds 503 if the database does not answer."""
    try:
        await session.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de datos no disponible",
        ) from e
