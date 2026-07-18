import asyncio
import sys

import uvicorn

from app.core.config import get_settings
from app.core.event_loop import configure_windows_event_loop


def main() -> None:
    configure_windows_event_loop()
    config = uvicorn.Config(
        "app.main:app",
        host="0.0.0.0",
        port=get_settings().backend_port,
        log_config="logging.json",
    )
    server = uvicorn.Server(config)
    if sys.platform == "win32":
        asyncio.run(server.serve(), loop_factory=asyncio.SelectorEventLoop)
    else:
        asyncio.run(server.serve())


if __name__ == "__main__":
    main()
