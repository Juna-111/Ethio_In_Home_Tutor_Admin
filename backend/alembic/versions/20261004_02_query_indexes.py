"""add production query indexes for operational workloads

Revision ID: 20261004_02
Revises: 20261004_01
"""

from alembic import op


revision = "20261004_02"
down_revision = "20261004_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_parent_requests_status_created_at",
        "parent_requests",
        ["status", "created_at", "id"],
    )
    op.create_index(
        "ix_parent_requests_phone_created_at",
        "parent_requests",
        ["phone_number", "created_at", "id"],
    )
    op.create_index(
        "ix_tutors_status_paused_created_at",
        "tutors",
        ["status", "is_paused", "created_at", "id"],
    )
    op.create_index(
        "ix_assignments_status_assigned_at",
        "assignments",
        ["status", "assigned_at", "tutor_id"],
    )
    op.create_index(
        "ix_match_invites_request_status",
        "match_invites",
        ["request_id", "status", "tutor_id"],
    )
    op.create_index(
        "ix_audit_log_actor_created_at",
        "audit_log",
        ["actor_telegram_id", "created_at", "id"],
    )
    op.create_index(
        "ix_tutor_incidents_status_created_at",
        "tutor_incidents",
        ["status", "created_at", "tutor_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_tutor_incidents_status_created_at", table_name="tutor_incidents")
    op.drop_index("ix_audit_log_actor_created_at", table_name="audit_log")
    op.drop_index("ix_match_invites_request_status", table_name="match_invites")
    op.drop_index("ix_assignments_status_assigned_at", table_name="assignments")
    op.drop_index("ix_tutors_status_paused_created_at", table_name="tutors")
    op.drop_index("ix_parent_requests_phone_created_at", table_name="parent_requests")
    op.drop_index("ix_parent_requests_status_created_at", table_name="parent_requests")
