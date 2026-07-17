"""Create an empty P0 migration baseline.

Revision ID: 0001_p0_baseline
Revises:
Create Date: 2026-07-16
"""

from collections.abc import Sequence

revision: str = "0001_p0_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """P0 intentionally creates no business tables."""


def downgrade() -> None:
    """P0 intentionally creates no business tables."""
