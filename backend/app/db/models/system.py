"""System tables: insights, alerts, sync runs, audit log, settings."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Insight(Base):
    """A data-grounded observation. Always carries the evidence it is based on."""

    __tablename__ = "insights"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(48), index=True)
    severity: Mapped[str] = mapped_column(String(8))  # INFO | WARN | ALERT
    confidence: Mapped[str] = mapped_column(String(8))  # LOW | MED | HIGH
    title: Mapped[str] = mapped_column(String(256))
    body: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSON)  # the data the insight is based on
    assumptions: Mapped[str | None] = mapped_column(Text)
    links: Mapped[dict | None] = mapped_column(JSON)  # deep links to relevant pages
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    metric: Mapped[str] = mapped_column(String(48))  # daily_loss_pct, position_weight_pct, ...
    operator: Mapped[str] = mapped_column(String(4))  # gt | lt | gte | lte
    threshold: Mapped[float] = mapped_column(Numeric(20, 6))
    scope: Mapped[dict | None] = mapped_column(JSON)  # e.g. {"conid": 123} or {"sector": "Tech"}
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("alert_rules.id", ondelete="CASCADE"), index=True)
    fired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    value: Mapped[float] = mapped_column(Numeric(20, 6))
    message: Mapped[str] = mapped_column(String(512))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)  # flex_full | snapshot | benchmarks
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="running")  # running|ok|failed|partial
    date_range_from: Mapped[str | None] = mapped_column(String(10))
    date_range_to: Mapped[str | None] = mapped_column(String(10))
    records_upserted: Mapped[int] = mapped_column(default=0)
    records_skipped: Mapped[int] = mapped_column(default=0)
    errors: Mapped[dict | None] = mapped_column(JSON)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    actor: Mapped[str] = mapped_column(String(24))  # system | user | ai_assistant
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict | None] = mapped_column(JSON)  # must never contain secrets


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
