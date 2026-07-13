# UI_SYSTEM — שפת העיצוב (Design System)

מסמך חי. מגדיר את הטוקנים והכללים שכל מסך ורכיב חייב לציית להם, כדי שהמערכת תיראה עקבית, בוגרת ומקצועית. הערכים ממומשים כ־CSS variables ב־`frontend/src/app/globals.css`.

עיקרון על: **צפיפות מידע גבוהה + רוגע ויזואלי.** משיגים זאת עם היררכיה חדה (טיפוגרפיה, משקל, צבע), לא עם עומס.

## 1. Typography Scale

פונטים: **Inter** (מספרים/לטינית, tabular-nums) + **IBM Plex Sans Hebrew** (עברית). מספרים תמיד `font-variant-numeric: tabular-nums`.

| טוקן | גודל / משקל / Line-height | שימוש |
|---|---|---|
| `text-display` | 28px / 600 / 1.1 | Primary Metric יחיד (NLV בדשבורד) |
| `text-h1` | 18px / 600 / 1.25 | כותרת עמוד |
| `text-h2` | 14px / 600 / 1.3 | כותרת סקציה/פאנל |
| `text-metric` | 17px / 600 / 1.2 | Metric משני |
| `text-body` | 13px / 400 / 1.5 | טקסט רגיל |
| `text-label` | 11px / 500 / 1.3 · letter-spacing .02em · uppercase (לועזי) | Labels, Table headers |
| `text-help` | 10.5px / 400 | Helper/Tooltip/Timestamp |
| `text-mono-num` | Inter tabular | כל מספר פיננסי |

כלל: לכל מסך **Primary אחד** בולט, סביבו Secondary, וסביבם Labels שקטים. לעולם לא שלושה גדלים "גדולים" באותו אזור.

## 2. Spacing & Layout (בסיס 4px)

`4 · 8 · 12 · 16 · 20 · 24 · 32 · 40 · 48`. רכיבים צמודים = 8/12; בין סקציות = 16/20; שוליים ראשיים = 20/24.

- Sidebar: 208px (מכווץ: 56px, אייקונים).
- Header: 48px.
- Container ראשי: max 1280px (טבלאות רחבות: full-bleed עם scroll פנימי).
- Grid: 12 עמודות, gap 16px.

## 3. Radius / Border / Elevation

- Radius: `sm 4px` (רוב), `md 6px` (פאנלים), `lg 8px` (Drawer/Modal). **בלי פינות ענק.**
- Borders: `--line` עדין; `--line-strong` להפרדות משמעותיות בלבד. **למעט בגבולות — עדיף הפרדה בצבע Surface מאשר עוד קו.**
- Elevation (מדורגת, לא צללים כבדים):
  - `elev-0` — רקע עמוד `--bg`.
  - `elev-1` — פאנל `--bg-panel` + border.
  - `elev-2` — פאנל מודגש `--bg-panel` + border + צל עדין מאוד.
  - `elev-overlay` — Drawer/Palette: `--bg-panel` + border-strong + צל בינוני.

## 4. Color Tokens

פלטה מצומצמת. Dark = לא שחור מוחלט; Light = לא לבן מסנוור.

### Dark (ברירת מחדל)
`--bg #101216` · `--bg-panel #171a21` · `--bg-subtle #1e222b` · `--bg-hover #242935` · `--line #2a2e39` · `--line-strong #3a3f4d` · `--fg #e9ebf0` · `--fg-muted #9aa0b0` · `--fg-faint #6b7180` · `--accent #5b8cff` · `--accent-fg #0c0e14`

### Light
`--bg #f6f7f9` · `--bg-panel #ffffff` · `--bg-subtle #f0f2f5` · `--bg-hover #e9ecf1` · `--line #e3e6ec` · `--line-strong #cdd2db` · `--fg #171a21` · `--fg-muted #5a6172` · `--fg-faint #8b92a3` · `--accent #2f5fd6` · `--accent-fg #ffffff`

### Semantic (משמעות פיננסית בלבד — לא קישוט)
`--gain` (ירוק מאופק) · `--loss` (אדום מאופק) · `--warn` (ענבר) · `--info` (הצללת accent). ערכים חיוביים/שליליים נצבעים **רק** כשהם מייצגים רווח/הפסד אמיתי; מספרים ניטרליים ב־`--fg`.

## 5. Chart Color System (עקבי בכל המערכת)

- **Portfolio** = `--accent` תמיד.
- **Benchmark** = ניטרלי `--fg-faint`/מקווקו — **אותו צבע בכל מסך**.
- **Drawdown** = `--loss` בשקיפות.
- **P&L חיובי/שלילי** = gain/loss.
- סדרות קטגוריות (סקטורים/מטבעות): רמפה מקצועית של 8 גוונים מאופקים (מוגדרת ב־globals.css, נבדקת ל־CVD). אותה ישות = אותו צבע תמיד.
- **בלי pie** להשוואות; Treemap/Bar במקום.

## 6. States (חובה לכל רכיב)

Loading (skeleton sheen, שומר גובה) · Empty (הסבר + פעולה, לא ריק) · Error (מה קרה + Retry) · Partial · **Stale** (badge + last update) · Disconnected (נתונים אחרונים נשמרים) · **Delayed** (סימון מפורש) · Rate-limit · Permission-missing.

כלל קריטי: **אל תציג `0` כשהמשמעות "לא ידוע".** הבחן: אפס אמיתי · אין נתונים · בטעינה · לא נתמך · נכשל · מושהה.

## 7. Tables

- Density: `comfortable` (36px שורה) / `compact` (28px) — בורר משתמש.
- Sticky header + sticky Symbol column. Zebra עדין (hover-first, לא זברה קבועה).
- מיושר: טקסט ל־start, מספרים ל־end, tabular.
- יכולות: Sort/Multi-sort, Filter, Column visibility+order+width, Pin, Saved Views, Expand row, Export, Virtualization (>200 שורות), Keyboard nav.

## 8. Number / Currency / % / Date

- מספרים: tabular, LTR מבודד (`unicode-bidi: isolate`) גם ב־RTL.
- מטבע: קוד (`USD`) בגופן קטן ומעומעם אחרי הסכום; לא שובר יישור טבלה.
- אחוזים: 2 ספרות עקבי; חיובי עם `+` רק כשמשמעותי (signed).
- שליליים: מינוס + צבע loss (לא סוגריים אלא אם דוח מודפס).
- תאריך/שעה: אזור זמן מהגדרות (ברירת מחדל Asia/Jerusalem); זמני ביצוע מקוריים נשמרים עם tz.

## 9. RTL

Layout לוגי (`inset-inline`, `ms/me`, `text-start/end`). LTR מבודד: מספרים, סימולים, קוד, צירי זמן בגרפים, שמות שוק. לבדוק: Tabs, Drawers, Timeline, Correlation matrix, News cards.

## 10. Motion (קיים — לא לגעת ללא צורך)

טוקנים: `--dur-fast 120 / base 180 / slow 240`, easing אחד. Tick-flash מכוון (gain/loss), reveals, live-dot, reduced-motion floor. אנימציה מבהירה שינוי — לא מקשטת. **אין אנימציית מספרים בכל טעינה** (רק count-up חד־פעמי מהיר ל־Primary, ומדולג ב־reduced-motion).

## 11. Focus / Hover / Disabled

Focus-visible: טבעת `--focus` 2px. Hover: שינוי Surface עדין (`--bg-hover`), לא הגדלה. Disabled: opacity .4 + cursor not-allowed.

## 12. עקרון "הסבר לי"

לכל Metric מרכזי: Tooltip/Info עם — מה זה, איך מחושב, מקור, זמן עדכון, מטבע, כולל עמלות/דיבידנדים/תזרים?, חי/היסטורי, מגבלות. בנוסף כפתור **"הסבר לי את המסך"** לכל מסך.
