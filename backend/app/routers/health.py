from fastapi import APIRouter
from app.schemas.financial import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="ok", version="0.1.0", database="connected")
