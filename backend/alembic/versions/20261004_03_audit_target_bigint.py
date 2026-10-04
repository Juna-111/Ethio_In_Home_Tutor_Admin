"""widen audit target ids for Telegram identifiers

Revision ID: 20261004_03
Revises: 20261004_02
"""

from alembic import op
import sqlalchemy as sa


revision = "20261004_03"
down_revision = "20261004_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "audit_log",
        "target_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "audit_log",
        "target_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
    )
