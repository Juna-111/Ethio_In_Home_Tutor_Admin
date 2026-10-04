"""add persisted marketplace favorites

Revision ID: 20261004_04
Revises: 20261004_03
"""

from alembic import op
import sqlalchemy as sa

revision = "20261004_04"
down_revision = "20261004_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketplace_favorites",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("parent_telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("tutor_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tutor_id"], ["tutors.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("parent_telegram_user_id", "tutor_id", name="uq_marketplace_favorite_parent_tutor"),
    )
    op.create_index("ix_marketplace_favorites_parent_telegram_user_id", "marketplace_favorites", ["parent_telegram_user_id"])
    op.create_index("ix_marketplace_favorites_tutor_id", "marketplace_favorites", ["tutor_id"])


def downgrade() -> None:
    op.drop_index("ix_marketplace_favorites_tutor_id", table_name="marketplace_favorites")
    op.drop_index("ix_marketplace_favorites_parent_telegram_user_id", table_name="marketplace_favorites")
    op.drop_table("marketplace_favorites")
