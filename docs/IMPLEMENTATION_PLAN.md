# IMPLEMENTATION_PLAN — תוכנית עבודה מדורגת

עשרה שלבים. בסוף כל שלב: סיכום מה בוצע, אילו קבצים נוצרו/שונו, איך בודקים, ומה חסר. התוכנית חיה — סטיות מתועדות כאן.

## סטטוס

| שלב | תיאור | סטטוס |
|---|---|---|
| 1 | Audit ותכנון (8 מסמכים) | ✅ הושלם 2026-07-13 |
| 2 | שלד המערכת | ✅ הושלם 2026-07-13 |
| 3 | חיבור Live Read-Only | ✅ קוד הושלם 2026-07-13 · אימות סופי מול Gateway חי מתבצע על ה־Mac (RUNBOOK §6) |
| 4 | דשבורד חי | ✅ הושלם 2026-07-13 (גרף שווי תיק יתווסף עם נתוני ההיסטוריה בשלבים 5–6) |
| 5 | היסטוריה וסנכרון | ✅ הושלם 2026-07-13 (הריצה הראשונה מול Flex אמיתי — לאחר הזנת הטוקן על ה־Mac) |
| 6 | מנוע ביצועים | ✅ הושלם 2026-07-13 · TWR אומת מול IBKR PA בדיוק של 6 ספרות |
| 7 | יומן מסחר | 🔄 בעבודה |
| 8 | סיכונים ותובנות | ⬜ |
| 9 | דוחות וייצוא | ⬜ |
| 10 | QA | ⬜ |

## שלב 1 — Audit ותכנון ✅
בדיקת סביבה וריפו (ריק), אימות גישת קריאה לחשבון ה־Live דרך קונקטור IBKR, בדיקת תיעוד רשמי של שיטות חיבור, בחירת סטאק וארכיטקטורה, כתיבת שמונת המסמכים.

## שלב 2 — שלד המערכת
- Monorepo: `backend/` (FastAPI + SQLAlchemy async + Alembic + structlog), `frontend/` (Next.js + TS + Tailwind), `docker-compose.yml` (db/backend/frontend), `.env.example`, `scripts/`.
- מיגרציה ראשונה עם כל טבלאות הליבה.
- Health checks: `/api/system/health`.
- Design System בסיסי: טוקנים, טיפוגרפיה (Inter + IBM Plex Sans Hebrew), רכיבי `<Num>`/`<Sym>` ל־RTL, Layout ניווט.
- **בדיקת קבלה**: `docker compose up` מרים את הכול; health ירוק; דף נטען RTL תקין.

## שלב 3 — חיבור Live Read-Only
- `backend/app/ibkr/gateway.py`: חיבור ib_async עם `readonly=True`, מכונת מצבים לחיבור, reconnect עם backoff, מנויי account/positions/PnL.
- `backend/app/ibkr/flex.py`: קליינט Flex Web Service (request→poll→download, retry על קודי in-progress).
- שמירת snapshots ל־DB; endpoints: account, positions, connection status; WebSocket hub.
- **בדיקת קבלה**: בדיקות אינטגרציה עם Gateway מדומה עוברות; על ה־Mac שלך — סטטוס CONNECTED ונתוני אמת (צ'קליסט ב־RUNBOOK).

## שלב 4 — דשבורד חי
Overview (NLV, מזומן, מרג'ין, P&L יומי/שבועי/חודשי/שנתי), טבלת פוזיציות חיה, גרף שווי תיק ראשוני, פס סטטוס `LIVE · READ ONLY · CONNECTED`, עדכוני WebSocket חלקים עם timestamps.

## שלב 5 — היסטוריה וסנכרון
פרסור Activity Flex (Trades, Cash Transactions, Equity Summary, Open Positions, Corporate Actions), upsert אידמפוטנטי, sync מתוזמן + ידני, מסך Sync Status, דוח Reconciliation ראשון.

## שלב 6 — מנוע ביצועים
TWR יומי ומצטבר, XIRR, Drawdown, מדדי סיכון עם ספי מינימום, השוואת Benchmark, Contribution, טבלת תשואות חודשית, Calendar Heatmap, בדיקות לכל מקרי הקצה.

## שלב 7 — יומן מסחר
בניית Trade Cycles (FIFO + תיקון ידני), רשומות יומן עם כל השדות, Templates, תגיות, העלאת צילומי מסך, ניתוח לפי קטגוריות (אסטרטגיה/Setup/יום/שעה/גודל/רגש/משמעת).

## שלב 8 — סיכונים ותובנות
Exposure (ברוטו/נטו/סקטור/מטבע/מדינה), ריכוזיות, מטריצת קורלציות, Stress Tests עם הנחות גלויות, מנוע Insights מבוסס כללים עם evidence, severity, confidence.

## שלב 9 — דוחות וייצוא
Export CSV/Excel לכל טבלה, דוח תקופתי (יומי/שבועי/חודשי/רבעוני/שנתי) כ־HTML להדפסה/PDF, מערכת התראות פנימית עם כללים מוגדרים.

## שלב 10 — QA
הרצת מלוא הבדיקות, בדיקות עומס (אלפי עסקאות), סריקת אבטחה, ליטוש UI (dark/light, ריקים, שגיאות, מקלדת), עדכון סופי של כל המסמכים + רשימת מגבלות ידועות (LIMITATIONS ב־README).

## עקרונות ביצוע
- כל שלב מסתיים ב־commit(ים) ברורים ובהרצת הבדיקות הקיימות.
- אין עצירה לאישור על שינויים קטנים; עצירה רק על שאלה חוסמת אמיתית.
- מה שדורש את ה־Mac שלך (login ל־Gateway, טוקן Flex) מסומן במפורש ומרוכז ב־RUNBOOK.
