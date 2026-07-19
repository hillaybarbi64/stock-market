# IBKR Portfolio & Trading Journal

מערכת אישית לניתוח תיק השקעות, יומן מסחר ודשבורד ביצועים, מחוברת בחיבור **Live · Read-Only** לחשבון Interactive Brokers אמיתי. רצה מקומית בלבד — הנתונים לא עוזבים את המחשב.

## מסמכים

| מסמך | תוכן |
|---|---|
| [docs/PROJECT_AUDIT.md](docs/PROJECT_AUDIT.md) | בדיקת הסביבה והפרויקט לפני תחילת העבודה |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | הארכיטקטורה, הבחירות והחלופות |
| [docs/IBKR_INTEGRATION.md](docs/IBKR_INTEGRATION.md) | השוואת שיטות החיבור ל־IBKR וההחלטה |
| [docs/PERFORMANCE_CALCULATIONS.md](docs/PERFORMANCE_CALCULATIONS.md) | איך מחושבות תשואות (TWR/XIRR) וכל מדד |
| [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md) | כל טבלה ושדה, עם מקור הנתונים |
| [docs/SECURITY.md](docs/SECURITY.md) | אבטחת מידע |
| [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) | תוכנית העבודה וסטטוס |
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | התקנה, הפעלה, גיבוי ופתרון תקלות |

## תמצית טכנית

- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2 (async), Alembic, `ib_async` (IB Gateway, readonly), Flex Web Service client, structlog.
- **Frontend**: Next.js, React, TypeScript, Tailwind, TanStack Query/Table, ECharts. RTL מלא.
- **DB**: PostgreSQL 16 (Docker, מקומי בלבד).
- **חיבור IBKR**: IB Gateway (חי, Read-Only נאכף בצד IBKR) + Flex Web Service (היסטוריה מלאה).

## הפעלה מהירה

ראו [docs/RUNBOOK.md](docs/RUNBOOK.md). בקצרה: התקנת IB Gateway עם Read-Only API, הגדרת Flex Token חד־פעמית, `./scripts/setup.sh`, `./scripts/start.sh`, ופתיחת http://localhost:3000.

`start.sh` / `setup.sh` מרימים את Docker Desktop אוטומטית ב־macOS אם ה־daemon כבוי. לאבחון: `./scripts/doctor.sh`.

## סטטוס

בפיתוח פעיל לפי [תוכנית העבודה](docs/IMPLEMENTATION_PLAN.md). מגבלות ידועות מתועדות שם ובסוף כל שלב.
