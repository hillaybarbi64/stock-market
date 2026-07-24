"""Trade cycles, journal entries, templates, tags and attachments."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TradeCycle(Base):
    """A full round-trip (open → close) built from executions.

    Automatic matching is FIFO; manual corrections are allowed and the
    original automatic matching is always preserved in original_matching."""

    __tablename__ = "trade_cycles"
    __table_args__ = (
        UniqueConstraint(
            "conid",
            "open_exec_id",
            name="uq_cycle_conid_open_exec",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    conid: Mapped[int] = mapped_column(ForeignKey("instruments.conid"), index=True)
    open_exec_id: Mapped[str] = mapped_column(String(64))
    direction: Mapped[str] = mapped_column(String(8))  # LONG | SHORT
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    close_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # null = open
    max_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    fees_total: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    dividends_total: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    matching_method: Mapped[str] = mapped_column(String(16), default="FIFO")
    is_manually_adjusted: Mapped[bool] = mapped_column(Boolean, default=False)
    original_matching: Mapped[dict | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CycleExecution(Base):
    """Allocation of an execution (possibly partial) to a trade cycle."""

    __tablename__ = "cycle_executions"
    __table_args__ = (UniqueConstraint("cycle_id", "exec_id", name="uq_cycle_exec"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cycle_id: Mapped[int] = mapped_column(
        ForeignKey("trade_cycles.id", ondelete="CASCADE"), index=True
    )
    exec_id: Mapped[str] = mapped_column(ForeignKey("executions.exec_id"), index=True)
    allocated_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 6))


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    cycle_id: Mapped[int | None] = mapped_column(ForeignKey("trade_cycles.id"), index=True)
    entry_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    strategy: Mapped[str | None] = mapped_column(String(64), index=True)
    setup: Mapped[str | None] = mapped_column(String(64))
    entry_reason: Mapped[str | None] = mapped_column(Text)
    thesis: Mapped[str | None] = mapped_column(Text)
    catalyst: Mapped[str | None] = mapped_column(String(256))
    exit_reason: Mapped[str | None] = mapped_column(Text)
    invalidation: Mapped[str | None] = mapped_column(Text)  # conditions that void the thesis
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    stop_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    planned_rr: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    actual_rr: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    amount_at_risk: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    pct_at_risk: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    confidence: Mapped[int | None] = mapped_column(Integer)  # 1-5
    emotional_state: Mapped[str | None] = mapped_column(String(64))
    followed_plan: Mapped[bool | None] = mapped_column(Boolean)
    changed_plan_midway: Mapped[bool | None] = mapped_column(Boolean)
    mistake: Mapped[str | None] = mapped_column(Text)
    done_right: Mapped[str | None] = mapped_column(Text)
    key_lesson: Mapped[str | None] = mapped_column(Text)
    next_time: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[int | None] = mapped_column(Integer)  # 1-5
    free_notes: Mapped[str | None] = mapped_column(Text)
    template_id: Mapped[int | None] = mapped_column(ForeignKey("journal_templates.id"))
    extra_fields: Mapped[dict | None] = mapped_column(JSON)  # template-specific answers
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class JournalTemplate(Base):
    __tablename__ = "journal_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str | None] = mapped_column(String(256))
    fields_schema: Mapped[dict] = mapped_column(JSON)  # extra fields definition
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    color: Mapped[str | None] = mapped_column(String(16))


class EntityTag(Base):
    """Polymorphic tag attachment: entity_type in (cycle, execution, journal_entry)."""

    __tablename__ = "entity_tags"
    __table_args__ = (UniqueConstraint("tag_id", "entity_type", "entity_id", name="uq_tag_entity"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), index=True)
    entity_type: Mapped[str] = mapped_column(String(24))
    entity_id: Mapped[str] = mapped_column(String(64), index=True)


class Attachment(Base):
    """Screenshots/files stored on local disk (data dir), never in git or DB."""

    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(24))
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    file_path: Mapped[str] = mapped_column(String(512))
    original_name: Mapped[str | None] = mapped_column(String(256))
    mime: Mapped[str | None] = mapped_column(String(64))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
