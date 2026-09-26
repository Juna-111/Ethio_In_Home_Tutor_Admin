"""Add numeric entrance result score to tutor profiles.

Revision ID: 20260926_02
Revises: 20260926_01
"""
from alembic import op
import sqlalchemy as sa


revision = "20260926_02"
down_revision = "20260926_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tutors", sa.Column("entrance_result", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("tutors", "entrance_result")