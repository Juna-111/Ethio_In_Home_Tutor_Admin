"""phase3_quality

Revision ID: 20260927_02
Revises: 20260927_01
Create Date: 2026-09-27 02:38:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260927_02'
down_revision: Union[str, None] = '20260927_01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('session_feedback',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('assignment_id', sa.Integer(), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('submitted_by', sa.String(length=20), nullable=False, server_default='parent'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['assignment_id'], ['assignments.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_session_feedback_assignment_id'), 'session_feedback', ['assignment_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_session_feedback_assignment_id'), table_name='session_feedback')
    op.drop_table('session_feedback')
