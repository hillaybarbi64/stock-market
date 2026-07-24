"""cycle natural key

Revision ID: 0741eb72f8ee
Revises: b2f33c05b3d0
Create Date: 2026-07-13 09:16:32.215450

"""

revision = "0741eb72f8ee"
down_revision = "b2f33c05b3d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Superseded by d4a9c2e1f6b8. A timestamp is not a safe natural key:
    # multiple valid round trips can open in the same second. This revision is
    # intentionally a no-op for installations that have not applied it yet.
    pass


def downgrade() -> None:
    pass
