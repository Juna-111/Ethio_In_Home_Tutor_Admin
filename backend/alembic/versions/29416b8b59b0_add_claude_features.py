"""Compatibility revision for the historical Claude feature migration.

Revision ID: 29416b8b59b0
Revises: None

The original migration created operational tables that are already part of the
canonical initial schema (7cb11ca8e49f). Re-running those CREATE TABLE
statements against a database initialized from that schema causes PostgreSQL
to fail with "relation already exists".

Keep this revision in the migration graph because existing environments may
already reference it, but make it a no-op. The actual schema is supplied by
the canonical initial schema plus the migrations that follow it.
"""

from typing import Sequence, Union

from alembic import op  # noqa: F401


revision: str = "29416b8b59b0"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
