"""Portfolio news feed (Finnhub, read-only).

Optional module: needs a free FINNHUB_API_KEY. Without it the endpoint reports
`available: false` with a reason instead of failing — the UI shows a setup
prompt. News is fetched for the largest open positions and cached briefly so
the free-tier rate limit is respected.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.base import get_db
from app.db.models import Instrument, Position

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db)]
log = get_logger(__name__)

_FINNHUB = "https://finnhub.io/api/v1/company-news"
_CACHE_TTL_S = 300
_cache: dict = {"ts": None, "data": None}


async def _portfolio_symbols(db: AsyncSession, limit: int = 8) -> list[str]:
    """Ticker symbols for the largest open equity positions."""
    rows = (
        await db.execute(
            select(Instrument.symbol, Position.market_value)
            .join(Position, Position.conid == Instrument.conid)
            .where(Position.is_open.is_(True), Instrument.sec_type == "STK")
        )
    ).all()
    ordered = sorted(rows, key=lambda r: abs(float(r[1] or 0)), reverse=True)
    out: list[str] = []
    for sym, _ in ordered:
        if sym not in out:
            out.append(sym)
        if len(out) >= limit:
            break
    return out


@router.get("")
async def portfolio_news(db: DbSession, limit: int = 40) -> dict:
    key = get_settings().finnhub_api_key
    if not key:
        return {
            "available": False,
            "reason": "מרכז החדשות דורש מפתח Finnhub חינמי. הירשם ב-finnhub.io, "
            "והוסף FINNHUB_API_KEY ל-.env (ואז docker compose up -d backend).",
            "symbols": [],
            "articles": [],
        }

    symbols = await _portfolio_symbols(db)
    if not symbols:
        return {"available": True, "symbols": [], "articles": []}

    now = datetime.now(UTC)
    cached = _cache["data"]
    if cached is not None and _cache["ts"] and (now - _cache["ts"]).total_seconds() < _CACHE_TTL_S:
        return cached

    frm = (now - timedelta(days=7)).date().isoformat()
    to = now.date().isoformat()
    articles: list[dict] = []
    seen: set[str] = set()
    async with httpx.AsyncClient(timeout=10) as client:
        for sym in symbols:
            try:
                resp = await client.get(
                    _FINNHUB, params={"symbol": sym, "from": frm, "to": to, "token": key}
                )
                resp.raise_for_status()
                items = resp.json()
            except Exception as exc:  # never let one symbol break the feed
                log.warning("news_fetch_failed", symbol=sym, error=str(exc))
                continue
            for it in items[:8] if isinstance(items, list) else []:
                aid = f"{sym}:{it.get('id')}"
                if aid in seen or not it.get("headline"):
                    continue
                seen.add(aid)
                ts = it.get("datetime")
                articles.append(
                    {
                        "id": aid,
                        "symbol": sym,
                        "headline": it.get("headline"),
                        "summary": it.get("summary") or None,
                        "source": it.get("source") or None,
                        "url": it.get("url") or None,
                        "image": it.get("image") or None,
                        "datetime": datetime.fromtimestamp(ts, UTC).isoformat() if ts else None,
                    }
                )

    articles.sort(key=lambda a: a["datetime"] or "", reverse=True)
    data = {"available": True, "symbols": symbols, "articles": articles[:limit]}
    _cache["data"] = data
    _cache["ts"] = now
    return data
