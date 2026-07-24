"""Manual Flex jobs must not outlive application shutdown."""

import asyncio
from contextlib import suppress

from app.api.sync import (
    _BACKGROUND_SYNC_TASKS,
    _start_background_sync,
    drain_background_sync_tasks,
)


async def test_background_sync_tasks_are_cancelled_and_drained():
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def worker() -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    _start_background_sync(worker())
    await started.wait()
    await drain_background_sync_tasks()

    assert cancelled.is_set()
    assert not _BACKGROUND_SYNC_TASKS


async def test_drain_is_idempotent():
    await drain_background_sync_tasks()
    with suppress(Exception):
        await drain_background_sync_tasks()
    assert not _BACKGROUND_SYNC_TASKS
