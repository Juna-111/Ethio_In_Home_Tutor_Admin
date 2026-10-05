"""merge the operational and family marketplace migration heads.

Revision ID: 20261005_02
Revises: 20261004_04, 20261005_family_marketplace
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20261005_02"
down_revision: Union[str, tuple[str, str], None] = (
    "20261004_04",
    "20261005_family_marketplace",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
