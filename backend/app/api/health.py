from typing import Literal

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import check_database

router = APIRouter(prefix="/api/v1/health", tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok", "not_ready"]


@router.get("/live", response_model=HealthResponse)
async def live() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse}},
)
async def ready() -> HealthResponse | JSONResponse:
    try:
        await check_database()
    except (SQLAlchemyError, OSError):
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    return HealthResponse(status="ok")
