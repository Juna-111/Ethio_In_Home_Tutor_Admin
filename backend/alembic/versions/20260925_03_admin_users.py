"""Add persistent admin user registry.

Revision ID: 20260925_03
Revises: 20260925_02
"""
from alembic import op
import sqlalchemy as sa


revision = "20260925_03"
down_revision = "20260925_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="admin"),
        sa.Column("added_by", sa.BigInteger(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("telegram_id"),
    )
    op.create_index("ix_admin_users_role", "admin_users", ["role"], unique=False)
    op.create_index("ix_admin_users_is_active", "admin_users", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_admin_users_is_active", table_name="admin_users")
    op.drop_index("ix_admin_users_role", table_name="admin_users")
    op.drop_table("admin_users")