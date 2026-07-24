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
from app.services.flex_cooldown import (
    FlexAttemptBlocked,
    FlexCooldownActive,
    get_active_flex_cooldown,
)
from app.services.flex_sync import FlexSyncService, SyncAlreadyRunning

log = get_logger(__name__)

CHECK_INTERVAL_S = 30 * 60
SYNC_EVERY = timedelta(hours=24)
STARTUP_DELAY_S = 120  # don't hit IBKR the instant we boot
MAX_BACKOFF_S = 4 * 60 * 60  # cap failure backoff at 4h


async def daily_sync_loop(service: FlexSyncService) -> None:
    # A cold start must NOT immediately hammer the Flex endpoint — repeated
    # restarts otherwise pile up attempts and trip IBKR's 1025 rate-limit lock,
    # which then never clears because the loop keeps retrying.
    await asyncio.sleep(STARTUP_DELAY_S)
    consecutive_failures = 0
    while True:
        wait = CHECK_INTERVAL_S
        try:
            if service.is_configured and await _due(service):
                log.info("auto_sync_starting")
                await service.run(trigger="scheduled")
            consecutive_failures = 0
        except SyncAlreadyRunning:
            pass
        except FlexCooldownActive as exc:
            wait = min(CHECK_INTERVAL_S, exc.cooldown.remaining_seconds)
            log.info(
                "auto_sync_skipped_flex_cooldown",
                remaining_s=exc.cooldown.remaining_seconds,
            )
        except FlexAttemptBlocked as exc:
            wait = min(CHECK_INTERVAL_S, max(1, exc.block.remaining_seconds))
            log.info(
                "auto_sync_skipped_attempt_guard",
                reason=exc.block.reason,
                remaining_s=exc.block.remaining_seconds,
            )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — loop survives; failure is on the SyncRun row
            consecutive_failures += 1
            # Exponential backoff so repeated failures stop hammering IBKR and
            # let any temporary token lock clear (30m → 1h → 2h → 4h cap).
            wait = min(CHECK_INTERVAL_S * 2 ** (consecutive_failures - 1), MAX_BACKOFF_S)
            log.warning(
                "auto_sync_backoff", consecutive_failures=consecutive_failures, next_wait_s=wait
            )
        await asyncio.sleep(wait)


async def _due(service: FlexSyncService) -> bool:
    async with db_session() as session:
        cooldown = await get_active_flex_cooldown(session)
        if cooldown:
            log.info(
                "auto_sync_skipped_flex_cooldown",
                error_code=cooldown.error_code,
                remaining_s=cooldown.remaining_seconds,
            )
            return False
        last_ok = (
            await session.execute(
                select(SyncRun.finished_at)
                .where(SyncRun.kind == "flex_full", SyncRun.status == "ok")
                .order_by(desc(SyncRun.finished_at))
                .limit(1)
            )
        ).scalar_one_or_none()
    return last_ok is None or datetime.now(UTC) - last_ok > SYNC_EVERY
