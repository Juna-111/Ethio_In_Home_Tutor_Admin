"""Add admin verification checklist and audit log tables.

Revision ID: 20260927_01
Revises: 20260926_02
"""
from alembic import op
import sqlalchemy as sa


revision = "20260927_01"
down_revision = "20260926_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tutor_verifications",
        sa.Column("tutor_id", sa.Integer(), nullable=False),
        sa.Column("id_verified", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("entrance_result_verified", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("phone_confirmed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("claims_plausible", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["tutor_id"], ["tutors.id"]),
        sa.PrimaryKeyConstraint("tutor_id"),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("actor_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("target_type", sa.String(length=30), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=20), server_default="miniapp", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_actor_telegram_id", "audit_log", ["actor_telegram_id"], unique=False)
    op.create_index("ix_audit_log_action", "audit_log", ["action"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_log_action", table_name="audit_log")
    op.drop_index("ix_audit_log_actor_telegram_id", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("tutor_verifications")