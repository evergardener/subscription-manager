"""add external reminder claim owner

Revision ID: b6d2c9e41a70
Revises: ae17e2c0f9f8
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b6d2c9e41a70"
down_revision: str | None = "ae17e2c0f9f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "reminder_deliveries",
        sa.Column(
            "claimed_by_actor_type",
            postgresql.ENUM(
                "user",
                "hermes",
                "system",
                "import",
                name="actor_type",
                create_type=False,
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "reminder_deliveries",
        sa.Column("claimed_by_actor_id", sa.String(length=200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("reminder_deliveries", "claimed_by_actor_id")
    op.drop_column("reminder_deliveries", "claimed_by_actor_type")
