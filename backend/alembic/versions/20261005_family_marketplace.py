"""Family-aware marketplace requests.

Revision ID: 20261005_family_marketplace
Revises: 29416b8b59b0
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261005_family_marketplace"
down_revision: Union[str, None] = "29416b8b59b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "children",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("parent_telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("normalized_name", sa.String(length=150), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("parent_telegram_user_id", "normalized_name", name="uq_child_parent_name"),
    )
    op.create_index("ix_children_parent_telegram_user_id", "children", ["parent_telegram_user_id"])
    op.create_index("ix_children_normalized_name", "children", ["normalized_name"])
    op.create_index("ix_children_is_active", "children", ["is_active"])

    op.add_column("parent_requests", sa.Column("child_id", sa.Integer(), nullable=True))
    op.add_column("parent_requests", sa.Column("preferred_tutor_id", sa.Integer(), nullable=True))
    op.create_index("ix_parent_requests_child_id", "parent_requests", ["child_id"])
    op.create_index("ix_parent_requests_preferred_tutor_id", "parent_requests", ["preferred_tutor_id"])
    op.create_foreign_key("fk_parent_requests_child_id", "parent_requests", "children", ["child_id"], ["id"])
    op.create_foreign_key("fk_parent_requests_preferred_tutor_id", "parent_requests", "tutors", ["preferred_tutor_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_parent_requests_preferred_tutor_id", "parent_requests", type_="foreignkey")
    op.drop_constraint("fk_parent_requests_child_id", "parent_requests", type_="foreignkey")
    op.drop_index("ix_parent_requests_preferred_tutor_id", table_name="parent_requests")
    op.drop_index("ix_parent_requests_child_id", table_name="parent_requests")
    op.drop_column("parent_requests", "preferred_tutor_id")
    op.drop_column("parent_requests", "child_id")
    op.drop_index("ix_children_is_active", table_name="children")
    op.drop_index("ix_children_normalized_name", table_name="children")
    op.drop_index("ix_children_parent_telegram_user_id", table_name="children")
    op.drop_table("children")
