"""Background scheduling: automatic daily Flex sync.

Deliberately simple (no Celery/cron dependency): every 30 minutes check
whether a successful flex sync happened in the last 24h; if not and Flex is
configured, run one. Manual runs via the API are always possible.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, select

from app.core.logging import get_logger
from app.db.base import db_session
from app.db.models import SyncRun
from app.services.flex_sync import FlexSyncService, SyncAlreadyRunning

log = get_logger(__name__)

CHECK_INTERVAL_S = 30 * 60
SYNC_EVERY = timedelta(hours=24)


async def daily_sync_loop(service: FlexSyncService) -> None:
    while True:
        try:
            if service.is_configured and await _due(service):
                log.info("auto_sync_starting")
                await service.run(trigger="scheduled")
        except SyncAlreadyRunning:
            pass
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — the loop must survive; failure is on the SyncRun row
            log.exception("auto_sync_failed")
        await asyncio.sleep(CHECK_INTERVAL_S)


async def _due(service: FlexSyncService) -> bool:
    async with db_session() as session:
        last_ok = (
            await session.execute(
                select(SyncRun.finished_at)
                .where(SyncRun.kind == "flex_full", SyncRun.status == "ok")
                .order_by(desc(SyncRun.finished_at))
                .limit(1)
            )
        ).scalar_one_or_none()
    return last_ok is None or datetime.now(UTC) - last_ok > SYNC_EVERY
