"""Add stable external identifiers to events.

Revision ID: 20261010_0003
Revises: 20261010_0002
Create Date: 2026-10-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261010_0003"
down_revision: Union[str, None] = "20261010_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("events", sa.Column("external_id", sa.String(length=255), nullable=True))
    op.create_index(
        "uq_events_source_external_id",
        "events",
        ["source", "external_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_events_source_external_id", table_name="events")
    op.drop_column("events", "external_id")
