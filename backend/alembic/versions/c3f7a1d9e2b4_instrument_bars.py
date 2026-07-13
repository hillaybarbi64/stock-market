"""instrument_bars — cached daily OHLCV for candlestick/sparkline charts

Revision ID: c3f7a1d9e2b4
Revises: 0741eb72f8ee
Create Date: 2026-07-13

Additive only: a new cache table. No existing table is touched, so this is a
safe forward migration for a running database.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3f7a1d9e2b4"
down_revision: str | None = "0741eb72f8ee"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "instrument_bars",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conid", sa.Integer(), nullable=False),
        sa.Column("bar_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(20, 6), nullable=False),
        sa.Column("high", sa.Numeric(20, 6), nullable=False),
        sa.Column("low", sa.Numeric(20, 6), nullable=False),
        sa.Column("close", sa.Numeric(20, 6), nullable=False),
        sa.Column("volume", sa.Numeric(20, 2), nullable=True),
        sa.Column("source", sa.String(16), nullable=False, server_default="gateway"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("conid", "bar_date", name="uq_bar_conid_date"),
    )
    op.create_index("ix_instrument_bars_conid", "instrument_bars", ["conid"])
    op.create_index("ix_instrument_bars_bar_date", "instrument_bars", ["bar_date"])


def downgrade() -> None:
    op.drop_index("ix_instrument_bars_bar_date", table_name="instrument_bars")
    op.drop_index("ix_instrument_bars_conid", table_name="instrument_bars")
    op.drop_table("instrument_bars")
