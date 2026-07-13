# ARCHITECTURE — ארכיטקטורת המערכת

מסמך זה מסביר איך המערכת בנויה, למה כך, ומה היו החלופות.

## 1. תמונה כללית

```
┌─────────────────────── ה-Mac שלך ────────────────────────┐
│                                                           │
│  ┌────────────┐   socket    ┌──────────────────────────┐  │
│  │ IB Gateway │◄───────────►│  Backend (FastAPI)       │  │
│  │ (Read-Only │  ib_async   │  ├─ ibkr/  שכבת אינטגרציה │  │
│  │  API מופעל)│             │  ├─ services/ לוגיקה      │  │
│  └────────────┘             │  ├─ api/   REST           │  │
│        ▲                    │  └─ ws/    WebSocket      │  │
│        │ login שלך          └─────┬──────────┬─────────┘  │
│        │ (2FA)                    │          │            │
│  ┌─────┴─────┐              ┌─────▼────┐ ┌───▼────────┐   │
│  │ IBKR      │   HTTPS      │PostgreSQL│ │ Frontend   │   │
│  │ Flex Web  │◄─────────────│(Docker)  │ │ (Next.js)  │   │
│  │ Service   │  token+query └──────────┘ │ בדפדפן שלך │   │
│  └───────────┘                           └────────────┘   │
└───────────────────────────────────────────────────────────┘
```

שני צינורות נתונים נפרדים ומשלימים:

1. **צינור חי (Live)** — IB Gateway ↔ Backend דרך ספריית `ib_async`. מספק: שווי חשבון, יתרות, מרג'ין, פוזיציות, P&L חי, פקודות פתוחות, ביצועים (Executions) אחרונים. עדכונים נדחפים לדפדפן דרך WebSocket.
2. **צינור היסטורי (Flex)** — משיכה תקופתית של דוח Activity Flex Query מהשרתים של IBKR. מספק: כל העסקאות מאז פתיחת החשבון, עמלות, דיבידנדים, ריבית, הפקדות/משיכות, המרות מט"ח, Corporate Actions ו־NAV יומי. זהו "מקור האמת" ההיסטורי־חשבונאי.

מונחים:
- **WebSocket** — חיבור קבוע בין הדפדפן לשרת שמאפשר לשרת "לדחוף" עדכונים בלי שהדפדפן ירענן את הדף. כך המספרים בדשבורד מתעדכנים חלק.
- **REST API** — הדרך הסטנדרטית שבה ה־Frontend מבקש נתונים מה־Backend (בקשה ← תשובה).
- **IB Gateway** — תוכנה רשמית של IBKR שרצה על המחשב שלך, מתחברת לחשבון שלך, ומאפשרת לתוכנות מקומיות לדבר איתה. גרסה "רזה" של TWS בלי מסכי מסחר.

## 2. הרכיבים והבחירות

### Backend — Python 3.11 + FastAPI

| החלטה | בחירה | חלופות שנשקלו | נימוק |
|---|---|---|---|
| שפה | Python | Node.js/TypeScript | האקוסיסטם של IBKR ל־Python (`ib_async`) הוא הבשל ביותר; חישובים פיננסיים נוחים ובדוקים |
| Framework | FastAPI | Flask, Django | אסינכרוני מלא (חיוני ל־ib_async ול־WebSocket), Validation מובנה עם Pydantic, תיעוד API אוטומטי |
| ORM | SQLAlchemy 2.0 (async) | Django ORM, raw SQL | סטנדרט בתעשייה, Type-safe, עובד עם Alembic |
| Migrations | Alembic | — | **Database Migration** = שינוי מבנה בסיס הנתונים בצורה מסודרת עם היסטוריה, כך ששדרוג גרסה לא הורס נתונים |
| רכיב IBKR חי | `ib_async` 2.x | `ibapi` הרשמית, Client Portal API | ראו IBKR_INTEGRATION.md |
| Background jobs | asyncio tasks + scheduler פנימי | Celery+Redis | Celery דורש Redis/worker נפרדים — Overengineering למשתמש יחיד. לולאת asyncio מספיקה ופשוטה לתפעול |
| לוגים | structlog (JSON/console) | logging רגיל | לוגים מובנים עם הקשר, בלי סודות |

### Frontend — Next.js + React + TypeScript

- **Next.js (App Router) + TypeScript** — כפי שהוגדר בדרישות.
- **Tailwind CSS + מערכת עיצוב פנימית** (טוקנים של צבע/מרווח/טיפוגרפיה) — עיצוב עקבי ומקצועי, RTL מלא עם `dir="rtl"` ו־logical properties.
- **TanStack Query** — ניהול נתוני שרת עם cache, כך שהדף לא "קופץ" בכל עדכון.
- **TanStack Table + virtualization** — טבלאות פיננסיות ברמה גבוהה (מיון/סינון/בחירת עמודות/וירטואליזציה לאלפי שורות).
- **ECharts** — ספריית גרפים אחת לכל המערכת (Equity Curve, Drawdown, Heatmaps, Correlation Matrix, התפלגויות). נימוק: תומכת בכל סוגי הגרפים הנדרשים כולל Calendar Heatmap ו־Zoom, מהירה (canvas), ללא תלות בשירות חיצוני. חלופות: Recharts (אין Heatmap/Zoom ברמה הזו), TradingView lightweight-charts (יפה לסדרות זמן אבל מוגבל לסוג אחד), D3 ידני (איטי לפיתוח ותחזוקה).
- מספרים, סימולים ותאריכים מוצגים LTR בתוך ממשק RTL באמצעות רכיבי תצוגה ייעודיים (`<Num>`, `<Sym>`) — כך טבלאות פיננסיות לא נשברות.

### Database — PostgreSQL 16

- רץ ב־Docker Compose מקומי. הנתונים נשארים על המחשב שלך בלבד.
- שומר: snapshots של חשבון, NAV יומי, פוזיציות, עסקאות, תנועות מזומן, דיבידנדים, עמלות, שערי מט"ח, מחזורי עסקה (Trade Cycles), רשומות יומן, תובנות, התראות, Audit Log ו־Sync Runs. פירוט מלא: DATA_DICTIONARY.md.
- **ללא Redis / Kafka / message queue** — אין בהם צורך אמיתי למשתמש יחיד; הוספתם רק תסבך תפעול.

### Infrastructure

- `docker-compose.yml` — שלושה שירותים: `db` (PostgreSQL), `backend`, `frontend`. ה־Gateway של IBKR רץ מחוץ ל־Docker (חובה — הוא דורש UI להתחברות).
- `.env.example` — כל המשתנים, בלי ערכים אמיתיים.
- `scripts/setup.sh`, `scripts/start.sh`, `scripts/backup.sh`.
- Health checks: `/api/system/health` בודק DB, חיבור Gateway, טריות נתונים.
- כל השירותים מאזינים על `localhost` בלבד. שום דבר לא נחשף לאינטרנט.

## 3. עקרונות מרכזיים

### 3.1 מקור לכל נתון (Data Provenance)
כל ערך שמוצג ב־UI נושא מטא־נתונים: מקור (`ibkr_gateway` / `ibkr_flex` / `computed` / `manual` / `market_data`), זמן עדכון, מטבע, והאם הוא אומדן. ה־UI מציג זאת ב־Tooltip של כל מדד.

### 3.2 אין נתוני דמה במסלול הראשי
אין מצב "Demo". אם אין חיבור — מוצגים הנתונים האחרונים שנשמרו עם חותמת זמן ברורה ומצב `STALE`. נתוני בדיקה קיימים רק תחת `backend/tests/fixtures/` ולעולם לא נטענים למסד הייצור.

### 3.3 Read-Only בשלוש שכבות
1. הגדרת **Read-Only API** ב־IB Gateway עצמו (אכיפה בצד IBKR).
2. `readonly=True` בחיבור `ib_async` (הספרייה מסרבת לשלוח פקודות).
3. ב־Backend לא קיים בכלל קוד לשליחת/שינוי/ביטול הוראות — אין endpoint כזה.

### 3.4 אידמפוטנטיות בסנכרון
כל רשומה היסטורית נשמרת עם מזהה טבעי ייחודי של IBKR (`execution_id`, `transaction_id` וכו'). סנכרון חוזר = upsert, לעולם לא כפילות.

### 3.5 עדכון חי בלי רעש
עדכוני WebSocket הם דלתא ממוקדת (מחיר של פוזיציה, ערך של תג חשבון) — לא רענון מסך. ה־Frontend ממזג אותם לתוך ה־cache של TanStack Query. Throttling בצד השרת מונע הצפה.

## 4. זרימת נתונים — דוגמה מלאה (מחיר פוזיציה מתעדכן)

1. IB Gateway דוחף עדכון מחיר ל־`ib_async`.
2. שכבת האינטגרציה מנרמלת: `{conid, market_price, market_value, unrealized_pnl, ts, source: "ibkr_gateway", data_type: "realtime"|"delayed"}`.
3. ה־Hub משדר ללקוחות WebSocket מחוברים (עם throttle של עד ~2 עדכונים/שניה לנכס).
4. ה־Frontend מעדכן את התא הרלוונטי בלבד; שינוי צבע עדין מסמן עדכון, בלי הבהוב.
5. אחת ל־N דקות (מוגדר) נשמר Snapshot ל־DB לצורך היסטוריה תוך־יומית.

## 5. מה לא נבנה בכוונה (ולמה)

- **מודול מסחר** — נאסר במפורש בדרישות עד לבקשה עתידית. אין שום קוד שליחת הוראות.
- **Multi-user / הרשאות משתמשים** — המערכת אישית ורצה מקומית. תוכנן כך שאפשר להוסיף בעתיד (עמודת account קיימת בסכמה).
- **Redis/Kafka/Microservices** — עומס תפעולי ללא תועלת בהיקף הזה.
- **שירותי ענן / Analytics חיצוני** — הנתונים לא עוזבים את המחשב שלך.
