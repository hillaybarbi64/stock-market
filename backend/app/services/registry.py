"""Process-wide service registry, populated during app startup.

Kept deliberately simple: one process, one account, one gateway connection.
"""

from app.ibkr.gateway import GatewaySupervisor
from app.services.flex_sync import FlexSyncService
from app.services.live_state import LiveStateService

live_state: LiveStateService | None = None
supervisor: GatewaySupervisor | None = None
flex_sync: FlexSyncService | None = None


def require_live_state() -> LiveStateService:
    if live_state is None:
        raise RuntimeError("live state service not initialized")
    return live_state
