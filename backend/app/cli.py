import argparse
import asyncio
import getpass
import sys
from datetime import UTC, datetime

from sqlalchemy import select

from app.auth.security import Actor
from app.core.database import get_session_factory
from app.models.tables import ActorType, User
from app.services.accounts import replace_password


async def reset_admin_password(username: str, new_password: str) -> None:
    async with get_session_factory()() as session:
        user = await session.scalar(
            select(User).where(User.normalized_username == username.strip().casefold())
        )
        if user is None:
            raise ValueError("administrator not found")
        actor = Actor(ActorType.SYSTEM, "local-password-reset", frozenset())
        await replace_password(
            session,
            user,
            new_password,
            actor,
            f"local-cli-{datetime.now(UTC).isoformat()}",
            "password_reset",
        )


def read_password(password_stdin: bool) -> str:
    if password_stdin:
        password = sys.stdin.readline().rstrip("\r\n")
    else:
        password = getpass.getpass("New password: ")
        confirmation = getpass.getpass("Confirm new password: ")
        if password != confirmation:
            raise ValueError("password confirmation does not match")
    if len(password) < 12:
        raise ValueError("password must contain at least 12 characters")
    return password


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    reset = subparsers.add_parser("reset-admin-password")
    reset.add_argument("--username", required=True)
    reset.add_argument(
        "--password-stdin",
        action="store_true",
        help="read one password line from stdin; intended for controlled automation",
    )
    arguments = parser.parse_args()
    try:
        if arguments.command == "reset-admin-password":
            asyncio.run(
                reset_admin_password(arguments.username, read_password(arguments.password_stdin))
            )
    except ValueError as exc:
        parser.error(str(exc))
    print("Administrator password reset; all existing sessions were revoked.")


if __name__ == "__main__":
    main()
