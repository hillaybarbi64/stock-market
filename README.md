# IBKR Portfolio & Trading Journal

מערכת אישית לניתוח תיק השקעות, יומן מסחר ודשבורד ביצועים, המחוברת לחשבון
Interactive Brokers דרך IB Gateway ו־Flex. הקוד ו־container images מיועדים
להפצה דרך GitHub; כל משתמש מריץ instance מבודד ומסד הנתונים נשאר אצלו.
מודול החדשות הוא opt-in: אם מוגדר Finnhub, סמלי ההחזקות נשלחים אליו כדי
להביא חדשות רלוונטיות.

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
| [docs/DISTRIBUTION.md](docs/DISTRIBUTION.md) | מסירת appliance מבודד דרך GitHub/GHCR |
| [docs/CLOUD_ROADMAP.md](docs/CLOUD_ROADMAP.md) | הדרך מגרסה מקומית למוצר ענן מאובטח |
| [docs/HANDOFF.md](docs/HANDOFF.md) | העברת הפיתוח למפתח נוסף בלי למסור סודות |

## תמצית טכנית

- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2 (async), Alembic, `ib_async` (IB Gateway, readonly), Flex Web Service client, structlog.
- **Frontend**: Next.js, React, TypeScript, Tailwind, TanStack Query/Table, ECharts. RTL מלא.
- **DB**: PostgreSQL 16 (Docker, מקומי בלבד).
- **חיבור IBKR**: IB Gateway חי עם Read-Only API שמופעל ב־Gateway, קוד אפליקטיבי
  ללא פעולות order, ו־Flex Web Service להיסטוריה מלאה.
- **מודל הפצה נוכחי**: instance נפרד לכל משתמש; אין ערבוב חשבונות ואין SaaS משותף.
- **בידוד חשבון**: החיבור הראשון קושר את מסד הנתונים לחשבון IBKR יחיד באמצעות
  fingerprint בלתי־הפיך; חיבור לחשבון אחר נדחה. בשדרוג של מסד שכבר מכיל
  נתונים, הקישור מחייב אישור מפורש של מספר החשבון הממוסך לפני קליטה נוספת.

## הפעלה מהירה

למפתח: ראו [docs/RUNBOOK.md](docs/RUNBOOK.md).

הפעלה יומית (פקודה אחת): `./scripts/start.sh`  
הסקריפט יוצר `.env` אם צריך, מפעיל Docker Desktop ב־macOS אם כבוי, מרים את כל השירותים, ממתין ל־health, ופותח את הדשבורד. לאבחון: `./scripts/doctor.sh`.

למשתמש שמקבל release:

```bash
git clone https://github.com/hillaybarbi64/stock-market.git
cd stock-market
./scripts/install-release.sh
```

לאחר ההתקנה פותחים `http://localhost:3000/connect`. שם המשתמש, הסיסמה ו־2FA
מוקלדים רק בתוך IB Gateway הרשמי — לעולם לא בדשבורד.

> המערכת הנוכחית אינה שרת multi-tenant ואין לחשוף את הפורטים שלה לאינטרנט.
> לפני הפצה מסחרית או הפצת נתוני שוק לצדדים שלישיים נדרש בירור ואישור מתאים
> מול Interactive Brokers; ראו `docs/DISTRIBUTION.md`.

## סטטוס

בפיתוח פעיל לפי [תוכנית העבודה](docs/IMPLEMENTATION_PLAN.md). מגבלות ידועות מתועדות שם ובסוף כל שלב.
