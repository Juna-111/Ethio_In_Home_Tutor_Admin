"""phase5_analytics_and_ops

Revision ID: 20260927_04
Revises: 20260927_03
Create Date: 2026-09-27 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260927_04'
down_revision: Union[str, None] = '20260927_03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Scheduled event claims (durable/idempotent claiming)
    op.create_table(
        'scheduled_event_claims',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('event_key', sa.String(length=255), nullable=False),
        sa.Column('check_type', sa.String(length=50), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('claimed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_scheduled_event_claims_event_key'), 'scheduled_event_claims', ['event_key'], unique=True)
    op.create_index(op.f('ix_scheduled_event_claims_check_type'), 'scheduled_event_claims', ['check_type'], unique=False)

    # 2. Notification outbox (durable message queue)
    op.create_table(
        'notification_outbox',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('event_key', sa.String(length=255), nullable=False),
        sa.Column('target_type', sa.String(length=50), nullable=False),
        sa.Column('recipient_id', sa.BigInteger(), nullable=True),
        sa.Column('topic_id', sa.BigInteger(), nullable=True),
        sa.Column('message_text', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_notification_outbox_event_key'), 'notification_outbox', ['event_key'], unique=False)
    op.create_index(op.f('ix_notification_outbox_status'), 'notification_outbox', ['status'], unique=False)

    # 3. Registration funnel events (intake conversion tracking)
    op.create_table(
        'registration_funnel_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.String(length=100), nullable=False),
        sa.Column('stage', sa.String(length=50), nullable=False),
        sa.Column('tutor_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tutor_id'], ['tutors.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_registration_funnel_events_session_id'), 'registration_funnel_events', ['session_id'], unique=False)
    op.create_index(op.f('ix_registration_funnel_events_stage'), 'registration_funnel_events', ['stage'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_registration_funnel_events_stage'), table_name='registration_funnel_events')
    op.drop_index(op.f('ix_registration_funnel_events_session_id'), table_name='registration_funnel_events')
    op.drop_table('registration_funnel_events')

    op.drop_index(op.f('ix_notification_outbox_status'), table_name='notification_outbox')
    op.drop_index(op.f('ix_notification_outbox_event_key'), table_name='notification_outbox')
    op.drop_table('notification_outbox')

    op.drop_index(op.f('ix_scheduled_event_claims_check_type'), table_name='scheduled_event_claims')
    op.drop_index(op.f('ix_scheduled_event_claims_event_key'), table_name='scheduled_event_claims')
    op.drop_table('scheduled_event_claims')
