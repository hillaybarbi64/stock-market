"""Built-in journal templates, seeded idempotently at startup."""

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.base import db_session
from app.db.models import JournalTemplate

BUILTIN_TEMPLATES: list[dict] = [
    {"name": "Swing Trade", "description": "עסקת סווינג של ימים עד שבועות",
     "fields": [{"key": "timeframe", "label": "טווח זמן מתוכנן", "type": "text"}]},
    {"name": "Position Trade", "description": "פוזיציה של שבועות עד חודשים",
     "fields": [{"key": "trend_basis", "label": "בסיס המגמה", "type": "text"}]},
    {"name": "Long-Term Investment", "description": "השקעה ארוכת טווח",
     "fields": [{"key": "valuation_notes", "label": "הערות שווי", "type": "textarea"}]},
    {"name": "Earnings Trade", "description": "עסקה סביב דוחות",
     "fields": [{"key": "earnings_date", "label": "תאריך הדוח", "type": "date"},
                 {"key": "expected_move", "label": "תנועה מגולמת", "type": "text"}]},
    {"name": "Breakout", "description": "פריצת רמה",
     "fields": [{"key": "level", "label": "רמת הפריצה", "type": "number"},
                 {"key": "volume_confirmation", "label": "אישור מחזור", "type": "boolean"}]},
    {"name": "Mean Reversion", "description": "חזרה לממוצע",
     "fields": [{"key": "reference_mean", "label": "הממוצע הנמדד", "type": "text"}]},
    {"name": "Short Trade", "description": "עסקת שורט",
     "fields": [{"key": "borrow_cost", "label": "עלות השאלה", "type": "text"}]},
    {"name": "Options Trade", "description": "עסקת אופציות",
     "fields": [{"key": "structure", "label": "מבנה (Call/Put/Spread)", "type": "text"},
                 {"key": "expiry", "label": "פקיעה", "type": "date"}]},
    {"name": "Event-Driven", "description": "עסקה מבוססת אירוע",
     "fields": [{"key": "event", "label": "האירוע", "type": "text"},
                 {"key": "event_date", "label": "תאריך", "type": "date"}]},
]


async def ensure_builtin_templates() -> None:
    async with db_session() as session:
        for t in BUILTIN_TEMPLATES:
            stmt = pg_insert(JournalTemplate).values(
                name=t["name"],
                description=t["description"],
                fields_schema={"fields": t["fields"]},
                is_builtin=True,
            )
            stmt = stmt.on_conflict_do_nothing(index_elements=[JournalTemplate.name])
            await session.execute(stmt)
        await session.commit()
