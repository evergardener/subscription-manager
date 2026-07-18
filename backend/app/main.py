import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.auth import token_router
from app.api.business import router as business_router
from app.api.health import router as health_router
from app.api.reminders import router as reminders_router
from app.core.config import get_settings
from app.core.database import dispose_engine
from app.core.errors import install_exception_handlers
from app.core.event_loop import configure_windows_event_loop
from app.core.logging import configure_logging
from app.core.middleware import RequestIdMiddleware

configure_windows_event_loop()
settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("application_started environment=%s", settings.environment)
    yield
    await dispose_engine()
    logger.info("application_stopped")


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(RequestIdMiddleware)
    install_exception_handlers(application)
    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(token_router)
    application.include_router(business_router)
    application.include_router(reminders_router)
    return application


app = create_app()
