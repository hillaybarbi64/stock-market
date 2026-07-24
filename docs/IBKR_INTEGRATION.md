# IBKR_INTEGRATION — החיבור ל־Interactive Brokers

נבדק מול התיעוד הרשמי של IBKR בתאריך **2026-07-13**. מקורות: IBKR Campus (עמודי Web API, TWS API, Flex Web Service), התיעוד של ibkrguides.com, והתיעוד של ספריית `ib_async`.

## 1. השוואת אפשרויות החיבור

| קריטריון | TWS API דרך IB Gateway | Client Portal Web API (CP Gateway) | Flex Web Service |
|---|---|---|---|
| מה זה | ממשק socket מקומי מול תוכנת IB Gateway | REST+WebSocket מול תוכנת Java מקומית | משיכת דוחות XML מוגדרים מראש ב־HTTPS |
| נתונים חיים (שווי, פוזיציות, P&L) | ✅ Streaming אמיתי | ✅ (polling + websocket) | ❌ (דוח, לא זמן־אמת) |
| פקודות פתוחות | ✅ | ✅ | חלקי |
| Executions | ✅ אך רק ימים אחרונים | ✅ אך רק ~שבוע | ✅ היסטוריה מלאה (עד 365 יום לכל בקשה) |
| דיבידנדים, ריבית, עמלות, הפקדות/משיכות, המרות מט"ח, Corporate Actions | ❌ | חלקי מאוד | ✅ המקור המלא היחיד |
| NAV יומי היסטורי | ❌ | חלקי (Portfolio Analyst) | ✅ EquitySummary יומי |
| התחברות | login ידני ב־Gateway + 2FA; ניתוק תחזוקה יומי מתוזמן; אימות מחדש ~שבועי | login ידני בדפדפן; session מת תוך ~24 שעות; **OAuth ללקוחות פרטיים עדיין לא זמין** (נכון ל־2026-07) | Token (תוקף עד שנה) + Query ID — אוטומטי לחלוטין |
| אכיפת Read-Only בצד IBKR | ✅ צ'קבוקס "Read-Only API" בהגדרות ה־Gateway | ❌ אין מצב כזה — session מלא | ✅ קריאה בלבד מטבעו |
| יציבות לריצה ממושכת | טובה, עם דפוסי reconnect בשלים | בינונית (session קצר) | מצוינת |
| Rate limits | 50 הודעות/שניה (הרבה מעבר לצורך) | ~10 בקשות/שניה | ~1 בקשה/שניה; דוח נוצר אסינכרונית |
| התאמה ל־Mac מקומי | ✅ | ✅ (דורש Java) | ✅ (HTTPS בלבד) |

## 2. ההחלטה

**שילוב: IB Gateway + `ib_async` לחי, Flex Web Service להיסטוריה.**

נימוקים:
1. **Read-Only נאכף על ידי IBKR עצמה** — רק ל־TWS API יש צ'קבוקס Read-Only ב־Gateway. עם CP Gateway היינו תלויים רק במשמעת של הקוד שלנו. זו הדרישה הקריטית ביותר שלך, ולכן זה שיקול מכריע.
2. **אין ל־retail גישת OAuth ל־Web API** — כלומר גם CP Gateway היה דורש login ידני, אבל כל ~24 שעות (מול פעם בשבוע ב־IB Gateway).
3. **Flex הוא המקור היחיד המלא להיסטוריה חשבונאית** — כל ארכיטקטורה סבירה חייבת אותו ממילא.
4. `ib_async` (גרסה 2.x) היא הספרייה המתוחזקת כיום; `ib_insync` הוותיקה אינה מתוחזקת עוד. החלופה הרשמית `ibapi` נמוכת־רמה ודורשת פי כמה קוד לאותה תוצאה.

חסרונות שאנחנו מקבלים במודע, וכיצד מטופלים:
- Gateway דורש login ידני אחרי ניתוק/ריסטארט ⇒ המערכת שורדת ניתוק: מציגה נתונים אחרונים + זמן עדכון, ומתחברת מחדש אוטומטית כשה־Gateway חוזר.
- Executions חיים מוגבלים לימים אחרונים ⇒ Flex משלים את החסר בכל סנכרון.
- שני מקורות לאותם נתונים ⇒ בדיוק בשביל זה קיים Reconciliation Report שמצליב ביניהם ולא מתקן פערים בשקט.

## 3. מה תצטרך להפעיל בצד שלך (סיכום; צעד־אחר־צעד ב־RUNBOOK.md)

1. **התקנת IB Gateway** (הורדה מאתר IBKR, גרסת Stable) על ה־Mac.
2. בהגדרות ה־Gateway: **API → Settings → סימון "Read-Only API"**, הפעלת socket על פורט 4001 (Live), הגבלה ל־localhost בלבד (ברירת המחדל: Trusted IP = 127.0.0.1).
3. התחברות ל־Gateway עם המשתמש שלך (2FA דרך IBKR Mobile). *הסיסמה מוקלדת רק ב־Gateway של IBKR — המערכת שלנו לעולם לא רואה אותה.*
4. **הגדרת Flex בצד IBKR** (בפורטל של IBKR, חד־פעמי):
   - Performance & Reports → Flex Queries → יצירת **Activity Flex Query** עם הסקציות: Trades (Executions), Cash Transactions, Cash Report, Equity Summary (EquitySummaryInBase), Open Positions, Corporate Actions, Transfers, FX (Statement of Funds/Trades לפי הצורך). טווח: Last 365 Days.
   - Settings → API → Flex Web Service → **הפקת Token** (מומלץ תוקף שנה, מוגבל ל־IP הביתי אם קבוע).
5. הזנת ה־Token וה־Query ID במסך `/connect` (מומלץ; ה־Token מוצפן
   לפני שמירה מקומית), או לחלופין ב־`.env` המקומי שאינו נכנס ל־Git.

## 4. שמירה על Read-Only — שלוש שכבות

1. **IBKR עצמה**: "Read-Only API" ב־Gateway ⇒ כל ניסיון לשלוח הוראה נdenied ברמת ה־Gateway.
2. **מצב החיבור באפליקציה**: `IB.connect(..., readonly=True)` מצמצם את פעולות ה־startup, אך אינו מוכיח לבדו שה־Gateway חוסם הוראות. לכן ה־UI מציג אותו כ־`APP READ-ONLY`, לא כאישור broker-side.
3. **הקוד שלנו**: לא קיימים endpoints או פונקציות של placeOrder/cancelOrder
   בכלל. אירועי חיבור ושגיאות נרשמים בלוג תפעולי ממוסך.

Flex הוא שירות דוחות לקריאה בלבד מטבעו.

## 5. ניהול חיבור ו־Reconnect

- מצבי חיבור: `CONNECTED` / `CONNECTING` / `DISCONNECTED` / `GATEWAY_DOWN` / `AUTH_REQUIRED`.
- Reconnect עם **exponential backoff**: 5s → 10s → 20s → 40s → 80s → תקרה 5 דקות, בלי לולאה אינסופית צפופה. כפתור Manual Reconnect ב־UI.
- בניתוק: הנתונים האחרונים נשארים על המסך, מסומנים `STALE` עם זמן העדכון האחרון. שום דבר לא מתאפס.
- ה־Gateway מבצע ניתוק תחזוקה יומי מתוזמן (מוגדר בהגדרותיו) — המערכת מזהה חלון זה ולא מציפה שגיאות.
- אירועי חיבור נכתבים ללוג המובנה הממוסך.

## 6. Rate Limits והתנהגות אדיבה

- Gateway: מנויי שוק חיים הם משאב מוגבל (ברירת מחדל ~100 טיקרים בו־זמנית) — אנו רושמים מנוי רק לפוזיציות פתוחות + benchmarks.
- Flex: בקשה אחת לשנייה ולכל היותר 10 בדקה לכל Token. כל ריצה שולחת `SendRequest` יחיד; לאחר קבלת ReferenceCode היא בודקת את אותו דוח כל 10 שניות. התזמון היומי כבוי כברירת מחדל ומופעל רק אחרי סנכרון ידני מבוקר שהצליח.
- אין שמירת Tick Data — snapshots תוך־יומיים במרווח מוגדר בלבד.

## 7. נתוני שוק (מחירים)

- מחירי הפוזיציות מגיעים מה־Gateway. אם אין מנוי Real-Time — IBKR מספקת Delayed (~15 דק'); המערכת מסמנת כל מחיר כ־`REALTIME` / `DELAYED` / `FROZEN` ומציגה זאת.
- מחירי Benchmark (למשל SPY/QQQ) נמשכים כ־ברים יומיים היסטוריים דרך ה־Gateway — ללא צורך בספק חיצוני, כך ששום נתון לא עוזב את המחשב.

## 8. מה עדיין דורש אימות מולך על ה־Mac

- שה־Gateway המותקן אצלך אכן חשוף על פורט 4001 ושה־login עובד (צ'קליסט ב־RUNBOOK).
- אילו הרשאות Market Data יש לחשבון (יוצג אוטומטית במסך System Status).
- שה־Flex Query שהוגדר כולל את כל הסקציות (המערכת מדווחת על סקציות חסרות במסך Sync).
