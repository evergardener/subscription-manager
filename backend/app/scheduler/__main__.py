import asyncio
import logging
import signal
import sys

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import get_settings
from app.core.database import dispose_engine, get_session_factory
from app.core.event_loop import configure_windows_event_loop
from app.core.logging import configure_logging
from app.services.reminders import scan_and_deliver

logger = logging.getLogger(__name__)


async def heartbeat() -> None:
    logger.info("scheduler_heartbeat")


async def reminder_scan() -> None:
    settings = get_settings()
    if settings.ntfy_topic == "replace-me":
        logger.warning("reminder_scan_skipped ntfy_topic_not_configured")
        return
    result = await scan_and_deliver(get_session_factory(), settings)
    logger.info("reminder_scan_completed result=%s", result)


def build_scheduler() -> AsyncIOScheduler:
    settings = get_settings()
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        heartbeat,
        trigger="interval",
        seconds=settings.scheduler_heartbeat_seconds,
        id="p0-heartbeat",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        reminder_scan,
        trigger="interval",
        minutes=5,
        id="reminder-scan",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    return scheduler


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    scheduler = build_scheduler()
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stopped.set)
        except NotImplementedError:
            pass
    scheduler.start()
    logger.info("scheduler_started")
    try:
        await stopped.wait()
    finally:
        scheduler.shutdown(wait=False)
        await dispose_engine()
        logger.info("scheduler_stopped")


if __name__ == "__main__":
    configure_windows_event_loop()
    try:
        if sys.platform == "win32":
            asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
        else:
            asyncio.run(run())
    except KeyboardInterrupt:
        pass
