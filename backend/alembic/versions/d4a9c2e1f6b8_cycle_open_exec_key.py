"""Use the opening execution as the stable trade-cycle identity.

Revision ID: d4a9c2e1f6b8
Revises: c3f7a1d9e2b4
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4a9c2e1f6b8"
down_revision: str | None = "c3f7a1d9e2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Some already-running installations applied the old timestamp constraint;
    # new installations see no constraint because 0741 is now a safe no-op.
    op.execute(sa.text("ALTER TABLE trade_cycles DROP CONSTRAINT IF EXISTS uq_cycle_conid_open"))
    op.add_column(
        "trade_cycles",
        sa.Column("open_exec_id", sa.String(length=64), nullable=True),
    )

    # The builder orders same-second fills by exec_id, so this selects the same
    # opening allocation deterministically. Allocation-less legacy/manual rows
    # receive a stable synthetic identity and are never merged.
    op.execute(
        sa.text(
            """
            UPDATE trade_cycles cycle
            SET open_exec_id = COALESCE(
                (
                    SELECT allocation.exec_id
                    FROM cycle_executions allocation
                    JOIN executions execution
                      ON execution.exec_id = allocation.exec_id
                    WHERE allocation.cycle_id = cycle.id
                    ORDER BY execution.trade_time, execution.exec_id
                    LIMIT 1
                ),
                'legacy-cycle-' || cycle.id::text
            )
            """
        )
    )

    # If an older rebuild created duplicate rows for the same opening
    # execution, keep the manually adjusted row first, then the oldest row.
    # Rows with different opening executions remain separate even when their
    # timestamps are identical.
    _merge_duplicate_references()

    op.alter_column(
        "trade_cycles",
        "open_exec_id",
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.create_unique_constraint(
        "uq_cycle_conid_open_exec",
        "trade_cycles",
        ["conid", "open_exec_id"],
    )


def _merge_duplicate_references() -> None:
    mapping = """
        SELECT id AS duplicate_id, keep_id
        FROM (
            SELECT
                id,
                FIRST_VALUE(id) OVER (
                    PARTITION BY conid, open_exec_id
                    ORDER BY is_manually_adjusted DESC, id
                ) AS keep_id,
                ROW_NUMBER() OVER (
                    PARTITION BY conid, open_exec_id
                    ORDER BY is_manually_adjusted DESC, id
                ) AS row_number
            FROM trade_cycles
        ) ranked
        WHERE row_number > 1
    """

    op.execute(
        sa.text(
            f"""
            WITH mapping AS ({mapping}),
            normalized AS (
                SELECT
                    allocation.id,
                    ROW_NUMBER() OVER (
                        PARTITION BY
                            COALESCE(mapping.keep_id, allocation.cycle_id),
                            allocation.exec_id
                        ORDER BY
                            CASE WHEN mapping.duplicate_id IS NULL THEN 0 ELSE 1 END,
                            allocation.id
                    ) AS row_number
                FROM cycle_executions allocation
                LEFT JOIN mapping
                  ON allocation.cycle_id = mapping.duplicate_id
            )
            DELETE FROM cycle_executions allocation
            USING normalized
            WHERE allocation.id = normalized.id
              AND normalized.row_number > 1
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            WITH mapping AS ({mapping})
            UPDATE cycle_executions allocation
            SET cycle_id = mapping.keep_id
            FROM mapping
            WHERE allocation.cycle_id = mapping.duplicate_id
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            WITH mapping AS ({mapping})
            UPDATE journal_entries journal
            SET cycle_id = mapping.keep_id
            FROM mapping
            WHERE journal.cycle_id = mapping.duplicate_id
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            WITH mapping AS ({mapping}),
            normalized AS (
                SELECT
                    tag.id,
                    ROW_NUMBER() OVER (
                        PARTITION BY
                            tag.tag_id,
                            tag.entity_type,
                            COALESCE(mapping.keep_id::text, tag.entity_id)
                        ORDER BY
                            CASE WHEN mapping.duplicate_id IS NULL THEN 0 ELSE 1 END,
                            tag.id
                    ) AS row_number
                FROM entity_tags tag
                LEFT JOIN mapping
                  ON tag.entity_type IN ('cycle', 'trade_cycle')
                 AND tag.entity_id = mapping.duplicate_id::text
                WHERE tag.entity_type IN ('cycle', 'trade_cycle')
            )
            DELETE FROM entity_tags tag
            USING normalized
            WHERE tag.id = normalized.id
              AND normalized.row_number > 1
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            WITH mapping AS ({mapping})
            UPDATE entity_tags tag
            SET entity_id = mapping.keep_id::text
            FROM mapping
            WHERE tag.entity_type IN ('cycle', 'trade_cycle')
              AND tag.entity_id = mapping.duplicate_id::text
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            WITH mapping AS ({mapping})
            UPDATE attachments attachment
            SET entity_id = mapping.keep_id::text
            FROM mapping
            WHERE attachment.entity_type IN ('cycle', 'trade_cycle')
              AND attachment.entity_id = mapping.duplicate_id::text
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            WITH mapping AS ({mapping})
            DELETE FROM trade_cycles cycle
            USING mapping
            WHERE cycle.id = mapping.duplicate_id
            """
        )
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_cycle_conid_open_exec",
        "trade_cycles",
        type_="unique",
    )
    op.drop_column("trade_cycles", "open_exec_id")
