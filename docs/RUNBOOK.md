# RUNBOOK — התקנה, הפעלה, גיבוי ופתרון תקלות

מדריך תפעול על ה־Mac שלך. כל פקודה מסומנת `$` רצה בטרמינל.

> המסמך יתעדכן בכל שלב. סעיפים המסומנים 🔜 יושלמו כשהרכיב ייבנה.

## 1. דרישות מוקדמות (חד־פעמי)

1. **Docker Desktop for Mac** — https://www.docker.com/products/docker-desktop/
2. **IB Gateway (Stable)** — הורדה מאתר IBKR: Trading → API → IB Gateway. גרסת macOS.
3. חשבון IBKR פעיל + אפליקציית IBKR Mobile לאימות דו־שלבי.

## 2. הגדרת IB Gateway (חד־פעמי, ~5 דקות)

1. פתח את IB Gateway, בחר **IB API** (לא FIX) והתחבר עם המשתמש שלך למצב **Live**.
2. Configure → Settings → API → Settings:
   - ✅ **Read-Only API** ← זה מה שמבטיח שאי אפשר לשלוח פקודות. חובה.
   - Socket port: **4001**.
   - ✅ Allow connections from localhost only (Trusted IPs: 127.0.0.1).
   - ❌ בטל "Read-Only API" רק אם אי־פעם תבקש במפורש מסחר מהמערכת (לא מומלץ כעת).
3. Configure → Lock and Exit → קבע שעת Restart יומית נוחה (למשל 04:00). היה מודע: פעם בשבוע לערך תידרש התחברות ידנית מחדש עם 2FA — זו מדיניות של IBKR, המערכת מציגה זאת בסטטוס.

**הסיסמה שלך מוקלדת רק בחלון של IB Gateway. המערכת לא רואה ולא שומרת אותה.**

## 3. הגדרת Flex Web Service (חד־פעמי, ~10 דקות, בפורטל IBKR)

1. התחבר ל־Client Portal של IBKR בדפדפן.
2. **Performance & Reports → Flex Queries → Activity Flex Query → צור חדש**:
   - Sections לסימון: **Trades** (עם Executions), **Cash Transactions**, **Cash Report**, **Change in NAV / Equity Summary in Base**, **Open Positions**, **Corporate Actions**, **Transfers**, **Statement of Funds**.
   - בכל סקציה בחר "Select All" לשדות.
   - Period: **Last 365 Calendar Days**. Format: XML. Date format: yyyy-MM-dd, כולל שעה + timezone.
   - שמור ורשום את ה־**Query ID** (מספר).
3. **Settings (גלגל שיניים) → Account Settings → Flex Web Service → Configure**:
   - הפעל, צור **Token**. תוקף מומלץ: שנה. רשום את הטוקן (מוצג פעם אחת).
4. את שני הערכים תזין ב־`.env` (סעיף הבא). אל תשלח אותם בצ'אט ואל תשמור אותם בקובץ אחר.

## 4. התקנת המערכת

```
$ git clone <repo> && cd stock-market
$ ./scripts/setup.sh
```

הסקריפט: בודק דרישות, יוצר `.env` מ־`.env.example` (עם סיסמת DB אקראית), בונה את הקונטיינרים ומריץ מיגרציות. לאחר מכן ערוך את `.env` והשלם:

```
IBKR_FLEX_TOKEN=...   # מהסעיף הקודם
IBKR_FLEX_QUERY_ID=...
```

## 5. הפעלה יומיומית

```
$ ./scripts/start.sh        # מרים db+backend+frontend
```
1. ודא ש־IB Gateway פתוח ומחובר (ירוק).
2. פתח דפדפן: **http://localhost:3000**
3. בפס העליון אמור להופיע: `LIVE · READ ONLY · CONNECTED` + זמן עדכון אחרון.

עצירה: `./scripts/stop.sh` (או `docker compose down`). הנתונים נשמרים ב־volume.

## 6. בדיקת תקינות (צ'קליסט אחרי התקנה)

| בדיקה | איך | תוצאה תקינה |
|---|---|---|
| Backend חי | `curl http://localhost:8000/api/system/health` | `"status":"ok"`, db ok |
| חיבור Gateway | מסך System Status | IBKR: CONNECTED, Read-Only: true |
| נתוני אמת | דשבורד | NLV תואם למה שמוצג ב־IBKR Mobile |
| Flex | מסך Sync → Run Sync | ריצה מסתיימת בהצלחה, נספרות רשומות |
| אין כפילויות | הרץ Sync פעמיים | ריצה שנייה: 0 רשומות חדשות |

## 7. גיבוי ושחזור

```
$ ./scripts/backup.sh                 # dump של ה-DB + קבצים → ~/.ibkr-dashboard/backups
$ ./scripts/restore.sh <backup-file>  # שחזור (עם אישור)
```
מומלץ: גיבוי שבועי (הסקריפט מתאים ל־cron/launchd; הוראה בתוך הקובץ).

## 8. פתרון תקלות

| תסמין | סיבה סבירה | פעולה |
|---|---|---|
| סטטוס `GATEWAY_DOWN` | IB Gateway סגור / לא מחובר | פתח את ה־Gateway והתחבר; המערכת תתחבר מחדש לבד תוך ~30 שניות |
| סטטוס `AUTH_REQUIRED` | פג האימות השבועי | התחבר מחדש ב־Gateway (2FA) |
| מחירים מסומנים DELAYED | אין מנוי Market Data בזמן אמת | תקין; אפשר לרכוש מנוי אצל IBKR אם רוצים Real-Time |
| Sync נכשל עם "generation in progress" | Flex עדיין מכין את הדוח | המערכת מנסה שוב לבד; אם חוזר — הקטן את טווח ה־Query |
| Sync נכשל עם קוד 1012/1015 | טוקן פג/שגוי | הפק טוקן חדש בפורטל ועדכן `.env` |
| הדשבורד מציג STALE | ניתוק זמני | בדוק Gateway; הנתונים האחרונים נשמרים, כלום לא אבד |
| פורט תפוס בהרצה | תהליך ישן | `./scripts/stop.sh` ואז start מחדש |
| "no space left" ב־Docker | דיסק דוקר מלא | `docker system prune` (לא נוגע ב־volume הנתונים) |

🔜 סעיפים שיתווספו עם השלמת השלבים: תזמון sync אוטומטי, ייצוא דוחות, נעילת ממשק בהרצה מרוחקת.

## 9. עדכון גרסה

```
$ git pull
$ ./scripts/setup.sh      # מריץ מיגרציות חדשות אם יש; לא מוחק נתונים
$ ./scripts/start.sh
```
