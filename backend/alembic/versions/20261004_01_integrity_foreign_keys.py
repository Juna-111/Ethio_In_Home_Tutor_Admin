"""enforce assignment and match invite relationships

Revision ID: 20261004_01
Revises: 7cb11ca8e49f
"""

from alembic import op
import sqlalchemy as sa

revision = "20261004_01"
down_revision = "7cb11ca8e49f"
branch_labels = None
depends_on = None


def _assert_no_orphans() -> None:
    connection = op.get_bind()
    checks = (
        (
            "assignments.request_id",
            "SELECT COUNT(*) FROM assignments a LEFT JOIN parent_requests r ON r.id = a.request_id WHERE r.id IS NULL",
        ),
        (
            "assignments.tutor_id",
            "SELECT COUNT(*) FROM assignments a LEFT JOIN tutors t ON t.id = a.tutor_id WHERE t.id IS NULL",
        ),
        (
            "match_invites.request_id",
            "SELECT COUNT(*) FROM match_invites i LEFT JOIN parent_requests r ON r.id = i.request_id WHERE r.id IS NULL",
        ),
        (
            "match_invites.tutor_id",
            "SELECT COUNT(*) FROM match_invites i LEFT JOIN tutors t ON t.id = i.tutor_id WHERE t.id IS NULL",
        ),
    )
    for label, query in checks:
        count = connection.execute(sa.text(query)).scalar_one()
        if count:
            raise RuntimeError(
                f"Cannot add production foreign key for {label}: {count} orphaned row(s) exist. "
                "Repair the data first; this migration intentionally never deletes records."
            )


def upgrade() -> None:
    _assert_no_orphans()

    with op.batch_alter_table("assignments") as batch:
        batch.create_foreign_key(
            "fk_assignments_request_id_parent_requests",
            "parent_requests",
            ["request_id"],
            ["id"],
        )
        batch.create_foreign_key(
            "fk_assignments_tutor_id_tutors",
            "tutors",
            ["tutor_id"],
            ["id"],
        )

    with op.batch_alter_table("match_invites") as batch:
        batch.create_foreign_key(
            "fk_match_invites_request_id_parent_requests",
            "parent_requests",
            ["request_id"],
            ["id"],
        )
        batch.create_foreign_key(
            "fk_match_invites_tutor_id_tutors",
            "tutors",
            ["tutor_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("match_invites") as batch:
        batch.drop_constraint("fk_match_invites_tutor_id_tutors", type_="foreignkey")
        batch.drop_constraint("fk_match_invites_request_id_parent_requests", type_="foreignkey")

    with op.batch_alter_table("assignments") as batch:
        batch.drop_constraint("fk_assignments_tutor_id_tutors", type_="foreignkey")
        batch.drop_constraint("fk_assignments_request_id_parent_requests", type_="foreignkey")
