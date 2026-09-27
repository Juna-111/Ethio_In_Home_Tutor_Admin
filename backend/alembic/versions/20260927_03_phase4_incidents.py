"""phase4_incidents

Revision ID: 20260927_03
Revises: 20260927_02
Create Date: 2026-09-27 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260927_03'
down_revision: Union[str, None] = '20260927_02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('tutor_incidents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tutor_id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.Integer(), nullable=True),
        sa.Column('severity', sa.String(length=20), nullable=False, server_default='low'),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='open'),
        sa.Column('reported_by', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['tutor_id'], ['tutors.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tutor_incidents_tutor_id'), 'tutor_incidents', ['tutor_id'], unique=False)
    op.create_index(op.f('ix_tutor_incidents_status'), 'tutor_incidents', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_tutor_incidents_status'), table_name='tutor_incidents')
    op.drop_index(op.f('ix_tutor_incidents_tutor_id'), table_name='tutor_incidents')
    op.drop_table('tutor_incidents')
