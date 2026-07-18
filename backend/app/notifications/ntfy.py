from dataclasses import dataclass

import httpx


class NotificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Notification:
    title: str
    message: str
    tags: str = "calendar"


class NtfyAdapter:
    def __init__(self, base_url: str, topic: str, timeout: float = 10.0) -> None:
        self.endpoint = f"{base_url.rstrip('/')}/{topic}"
        self.timeout = timeout

    async def send(self, notification: Notification) -> None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.endpoint,
                    content=notification.message.encode(),
                    headers={"Title": notification.title, "Tags": notification.tags},
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise NotificationError("ntfy delivery failed") from exc
