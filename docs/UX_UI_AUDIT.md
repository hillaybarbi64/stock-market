# UX_UI_AUDIT — ביקורת חוויה ועיצוב לפני ה־Redesign

תאריך: 2026-07-13 · נבדק על המערכת הרצה (Live Read-Only, נתונים אמיתיים מסונכרנים) עם צילומי מסך של סקירה כללית, פוזיציות, ביצועים, יומן וסיכונים.

מטרת המסמך: לתאר בכנות מה עובד, מה נראה גנרי, ומה דורש Redesign — כבסיס ל־REDESIGN_PLAN.md ו־UI_SYSTEM.md.

## 1. מה עובד היטב (לשמר)

- **הנתונים אמיתיים ומחוברים.** חיבור IBKR Live Read-Only, סנכרון Flex, חישובי TWR/XIRR/Drawdown, פרובננס לכל נתון (מקור/זמן/Stale). זה הנכס הכי חשוב ואסור לפגוע בו.
- **אסתטיקה מאופקת** — בלי גרדיאנטים/ניאון, מספרים טבלאיים, RTL אמיתי, Dark+Light, סימון Delayed. הבסיס הנכון.
- **מצבים כנים** — Empty/Error/Stale אמיתיים, מדדים עם ספי מינימום ("אין מספיק נתונים") במקום מספרים מזויפים.
- **שכבת תנועה** חדשה (tick-flash, reveals, reduced-motion) — פרימיום ולא צעקני.

## 2. חולשות מרכזיות (הליבה של ה־Redesign)

### 2.1 היעדר היררכיית מידע — הבעיה מספר 1
בסקירה הכללית כל המספרים באותו משקל ויזואלי (NLV באותו גודל כמו Excess Liquidity). אין **Primary Metric** אחד שהעין נחה עליו, אין Secondary מתחתיו. התוצאה: המסך "מדווח" אבל לא "מספר סיפור". זה מה שגורם לתחושת Admin Dashboard.

### 2.2 אין גרף מרכזי בדשבורד
עקומת התיק חיה רק בעמוד "ביצועים". הדשבורד הראשי חייב גרף מרכזי (שווי/תשואה/Benchmark/Drawdown) — זה הלב החזותי של מוצר Wealth.

### 2.3 חסרים אזורי ההבנה
אין **Performance Attribution** (מי תרם/פגע), אין **Movers**, אין **Risk Snapshot** תמציתי, אין **News**. המשתמש רואה "מה" אבל לא "למה" ו"מה דורש תשומת לב".

### 2.4 "מרק כרטיסים"
כל פאנל הוא אותו בורדר אחיד. חזרתיות מונוטונית, בלי היררכיית Elevation/צפיפות בין אזור ראשי למשני.

### 2.5 טיפוגרפיה דחוסה
טווח צר מדי (~11–17px). ההבחנה בין כותרת עמוד / כותרת סקציה / Metric ראשי / Label חלשה. חסר Type Scale אמיתי עם משקלים.

### 2.6 טבלת פוזיציות בסיסית
מיון בסיסי בלבד. חסר: ניהול עמודות, Pinning, Saved Views, Expandable Rows, Virtualization, Density control, ו־**Drill-down לעמוד נכס** (שלא קיים כלל).

### 2.7 אין עמוד נכס
אין Asset Intelligence page — הפער הכי גדול פונקציונלית מול החזון.

### 2.8 גרפים מוגבלים
ECharts תקין אך: אין Benchmark overlay, אין Candlestick למחיר נכס, אין Heatmap/Correlation Matrix/Treemap. צבעי הגרפים לא מנוהלים כמערכת סמנטית אחת.

### 2.9 ניווט וחיפוש
Sidebar = רשימת טקסט; Active state עדין מדי (שופר חלקית במנוע התנועה). **אין Command Palette, אין Global Search, אין קפיצה לנכס לפי Symbol.**

### 2.10 חסרים מוחלטים
News (לא קיים), Trade Planning/Draft Orders (לא קיים), עמוד "נכסים" ייעודי.

## 3. בדיקות רוחב

| תחום | מצב | הערה |
|---|---|---|
| RTL | טוב | טבלאות/מספרים/סימולים LTR נכונים. לבדוק שוב אחרי גרפים חדשים |
| Dark/Light | עובד | Light מעט שטוח; צריך Surface hierarchy עשיר יותר |
| Responsive | Desktop בלבד | אין התאמת Cards למובייל; טבלאות נשברות בצר |
| Loading | Skeletons קיימים (sheen) | לא בכל מקום; חלק מהמסכים קופצים |
| Console | נקי בעיקרון | לוודא 0 שגיאות אחרי Redesign |
| Layout Shift | קל | Skeleton→content לא שומר גובה בכל מקום |
| נגישות | חלקית | Focus states קיימים; חסר ARIA לגרפים/טבלאות, ניווט מקלדת חלקי |
| ביצועים | טוב לנתונים הנוכחיים | לא נבדק מול אלפי שורות/כתבות — צריך Virtualization |

## 4. מסכים: לשמר / לשדרג / לשכתב

| מסך | פסק דין |
|---|---|
| סקירה כללית | **שכתוב מלא** — היררכיה, גרף מרכזי, Attribution, Movers, Risk, News |
| פוזיציות | **שדרוג עמוק** — טבלת Pro + Saved Views + Drill-down |
| עמוד נכס | **חדש לגמרי** |
| ביצועים | **שדרוג** — Benchmark overlay, Heatmap, Rolling, Distribution, Attribution |
| סיכונים | **שדרוג** — Treemap, Correlation Matrix, Concentration curve |
| יומן | שדרוג בינוני + חיבור ל־Trade Planning |
| חדשות | **חדש לגמרי** |
| עסקאות/דוחות/סנכרון/מצב מערכת | שדרוג קוסמטי לפי ה־Design System החדש |

## 5. רכיבים: לשמר / להחליף

**לשמר (עם ליטוש):** `<Num>`/`<Sym>` (פורמט מספרים), פרובננס Badges, EChart wrapper, מנוע התנועה, מצבי Empty/Error.

**להחליף/לבנות:** Design tokens מורחבים (Type Scale, Spacing, Elevation, Chart palette), מערכת Panel עם היררכיה, DataTable מקצועי (TanStack Table + Virtual), Command Palette, Global Search, Drawer/Context Panel, KPI Composition (Primary+Secondary), Tabs, Chart system מורחב (candles/heatmap/treemap/correlation), News components, Trade Planning components.

## 6. מסקנה
הבסיס הפונקציונלי מצוין ואמין — הבעיה היא **שפה חזותית והיררכיה**, לא הנתונים. ה־Redesign יבנה שכבת מוצר חדשה מעל אותו Backend/Data שעובד, בלי לגעת בחיבור, בחישובים או בסנכרון. פירוט הביצוע: REDESIGN_PLAN.md. שפת העיצוב: UI_SYSTEM.md.
