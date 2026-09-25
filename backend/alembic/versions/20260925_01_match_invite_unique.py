"""Enforce one invite per request and tutor pair.

Revision ID: 20260925_01
Revises:
"""
from alembic import op
import sqlalchemy as sa


revision = "20260925_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    duplicate = bind.execute(sa.text(
        """
        SELECT request_id, tutor_id, COUNT(*) AS duplicate_count
        FROM match_invites
        GROUP BY request_id, tutor_id
        HAVING COUNT(*) > 1
        LIMIT 1
        """
    )).first()
    if duplicate:
        raise RuntimeError(
            "Cannot add match invite uniqueness: duplicate request_id/tutor_id rows exist. "
            "Resolve them explicitly and rerun this migration."
        )

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("match_invites") as batch_op:
            batch_op.create_unique_constraint(
                "uq_match_invites_request_tutor", ["request_id", "tutor_id"]
            )
    else:
        op.create_unique_constraint(
            "uq_match_invites_request_tutor",
            "match_invites",
            ["request_id", "tutor_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("match_invites") as batch_op:
            batch_op.drop_constraint("uq_match_invites_request_tutor", type_="unique")
    else:
        op.drop_constraint(
            "uq_match_invites_request_tutor", "match_invites", type_="unique"
        )