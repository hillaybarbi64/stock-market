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
   - אין לבטל **Read-Only API** בגרסה הזו. אין בה מודול מסחר והיא מסרבת
     לעלות עם `IBKR_READONLY=false`.
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
4. את שני הערכים אפשר להזין ישירות במסך **סנכרון** בדשבורד (מומלץ). ברירת המחדל בטוחה: התזמון היומי כבוי, והרצה מתבצעת רק בלחיצה מפורשת. לחלופין הזן ב־`.env` (סעיף הבא). אל תשלח אותם בצ'אט.

## 4. התקנת המערכת

```
$ git clone <repo> && cd stock-market
$ ./scripts/setup.sh
```

הסקריפט: בודק דרישות, יוצר `.env` מ־`.env.example` (עם סיסמת DB אקראית), בונה את הקונטיינרים ומריץ מיגרציות. לאחר מכן ערוך את `.env` והשלם:

```
IBKR_FLEX_TOKEN=...   # מהסעיף הקודם
IBKR_FLEX_QUERY_ID=...
IBKR_FLEX_AUTOSYNC=false  # השאר כבוי עד שסנכרון ידני מבוקר מצליח
```

## 5. הפעלה יומיומית

```
$ ./scripts/start.sh        # הפקודה היחידה להפעלה יומית
```

`start.sh` מטפל לבד בכל שרשרת ההפעלה:
1. יוצר `.env` אם חסר
2. אם Docker כבוי ב־macOS — פותח **Docker Desktop** ומחכה עד שהוא מוכן (עד ~3 דקות)
3. בונה ומעלה db + backend + frontend, וממתין ל־health
4. ב־macOS פותח את http://localhost:3000 בדפדפן

ודא ש־IB Gateway פתוח ומחובר (ירוק, Read-Only API, פורט 4001 ל־Live או
4002 ל־Paper). בפס העליון אמור להופיע `APP READ-ONLY · CONNECTED`.

אבחון: `./scripts/doctor.sh`. עצירה: `./scripts/stop.sh`.

## 6. בדיקת תקינות (צ'קליסט אחרי התקנה)

| בדיקה | איך | תוצאה תקינה |
|---|---|---|
| Backend חי | `curl http://localhost:8000/api/system/health` | `"status":"ok"`, db ok |
| חיבור Gateway | מסך System Status | IBKR: CONNECTED, Read-Only: true |
| נתוני אמת | דשבורד | NLV תואם למה שמוצג ב־IBKR Mobile |
| Flex | רק לאחר שאין cooldown: מסך Sync → Run Sync פעם אחת | ריצה מסתיימת בהצלחה, נספרות רשומות |
| אין כפילויות | בדיקות ה־CI; אין להריץ Flex פעם נוספת רק לצורך בדיקה | סנכרון עתידי שנדרש אינו יוצר כפילויות |

## 7. גיבוי ושחזור

```
$ ./scripts/backup.sh                 # dump של ה-DB + קבצים → ~/.ibkr-dashboard/backups
$ ./scripts/restore.sh <backup-file> [data-directory]  # החלפה מלאה עם safety backup
```

גיבוי ושחזור משתמשים באותה נעילת מערכת־הפעלה, ולכן אינם יכולים לרוץ
במקביל. הנעילה משתחררת אוטומטית גם אם התהליך נעצר או קורס.
מומלץ: גיבוי שבועי (הסקריפט מתאים ל־cron/launchd; הוראה בתוך הקובץ).

## 8. פתרון תקלות

| תסמין | סיבה סבירה | פעולה |
|---|---|---|
| `Docker daemon is not running` / `Cannot connect to the Docker daemon` | Docker Desktop סגור | הרץ שוב `./scripts/start.sh` (מנסה לפתוח Desktop אוטומטית). אם נכשל — פתח Docker Desktop ידנית, חכה ל־"Docker is running", ואז `./scripts/start.sh` |
| `ERR_CONNECTION_REFUSED` על `:3000` | ה־stack לא רץ (בדרך כלל Docker כבוי) | `./scripts/doctor.sh` ואז `./scripts/start.sh` |
| `ports are not available` / `address already in use` על `:8000` או `:3000` | תהליך שאינו שייך לפרויקט תופס את הפורט | `start.sh` מציג את התהליך ומסרב להרוג אותו; עצור או הגדר אותו מחדש ואז הרץ שוב |
| סטטוס `GATEWAY_DOWN` | IB Gateway סגור / לא מחובר | פתח את ה־Gateway והתחבר; המערכת תתחבר מחדש לבד תוך ~30 שניות |
| סטטוס `AUTH_REQUIRED` | פג האימות השבועי | התחבר מחדש ב־Gateway (2FA) |
| מחירים מסומנים DELAYED | אין מנוי Market Data בזמן אמת | תקין; אפשר לרכוש מנוי אצל IBKR אם רוצים Real-Time |
| Sync מציג "generation in progress" אחרי שהבקשה התקבלה | Flex עדיין מכין את הדוח | המערכת ממשיכה לבד רק לבדוק את אותו דוח, במרווחים בטוחים; היא אינה שולחת בקשת דוח חדשה |
| Sync נכשל עם קוד 1025 (`too many failed attempts`) | חסימת קצב זמנית ברמת חשבון IBKR, לא טוקן שגוי | אל תשלח בקשות Flex ידניות. המערכת מפעילה cooldown עמיד ל־restart למשך שעתיים, משביתה את הכפתור ומאפשרת ניסיון יחיד בסיום |
| Sync נכשל עם קוד 1012/1015 | טוקן פג/שגוי | הפק טוקן חדש בפורטל ועדכן במסך הסנכרון (או ב־`.env`) |
| Sync נכשל עם **`1013: IP restriction`** | ה־IP הציבורי של המחשב לא מורשה לטוקן Flex | Client Portal → Settings → Account Settings → **Flex Web Service** → הוסף את ה־IP שמוצג במסך הסנכרון (או צור Token חדש עם ה־IP הנוכחי). אל תלחץ שוב ושוב — אחרי העדכון המתן דקה והרץ סנכרון פעם אחת בלבד |
| הדשבורד מציג STALE | ניתוק זמני | בדוק Gateway; הנתונים האחרונים נשמרים, כלום לא אבד |
| פורט תפוס בהרצה | תהליך ישן | `./scripts/stop.sh` ואז start מחדש |
| "no space left" ב־Docker | דיסק דוקר מלא | `docker system prune` (לא נוגע ב־volume הנתונים) |

הערות תפעול נוספות:
- **סנכרון אוטומטי**: כבוי כברירת מחדל. רק לאחר שסנכרון ידני מבוקר הצליח, אפשר להגדיר `IBKR_FLEX_AUTOSYNC=true`; אז הוא רץ לכל היותר אחת ל־24 שעות.
- **מחזורי עסקה**: אחרי סנכרון ראשון, לחץ "בנה מחזורי עסקה מחדש" במסך "יומן מסחר".
- **דוחות**: מסך "דוחות" → בחר טווח → "הדפס / שמור כ-PDF"; ייצוא CSV מאותו מסך.
- **התראות**: מוגדרות במסך "הגדרות"; מופיעות בתוך המערכת (אין שליחה החוצה בשלב זה).
- **הרצה מרוחקת**: אם אי-פעם תריץ על שרת — רק מאחורי VPN (למשל Tailscale), לעולם לא חשיפה ישירה לאינטרנט. ראו SECURITY.md.

## 9. עדכון גרסה

```
$ git pull
$ ./scripts/setup.sh      # מריץ מיגרציות חדשות אם יש; לא מוחק נתונים
$ ./scripts/start.sh
```
