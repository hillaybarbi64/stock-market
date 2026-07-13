# REDESIGN_PLAN — תוכנית ה־Redesign וההרחבות

מבוסס על UX_UI_AUDIT.md ו־UI_SYSTEM.md. עיקרון: **בונים שכבת מוצר חדשה מעל ה־Backend/Data שעובד** — בלי לגעת בחיבור IBKR, בחישובים, ב־DB או בסנכרון. כל שלב: מימוש קוד אמיתי → lint/build/tests → דיווח בעברית → commit.

## עקרונות שמירה (Guardrails)
- לא לשבור API Contracts קיימים; להרחיב, לא לשכתב.
- לא לשנות חישובים פיננסיים כדי להתאים UI.
- Read-Only מול IBKR נשמר; מודול המסחר נבנה **כבוי** (Feature Flags) ואני עוצר לפני הפעלת שיגור.
- אין נתוני דמה שמתחזים לאמיתיים; חדשות אמיתיות דרך ספק עם מפתח (Finnhub כברירת מחדל), אחרת Empty State כן.
- כל שלב מסתיים ב־build ירוק ו־regression בדיקות ליבה (IBKR/positions/P&L/returns/sync) עוברות.

## מפת שלבים

| # | שלב | תוצר עיקרי | סטטוס |
|---|---|---|---|
| A | Audit + מסמכי יסוד | UX_UI_AUDIT, UI_SYSTEM, REDESIGN_PLAN | ✅ |
| B | Design Foundation | טוקנים מורחבים, Type/Spacing/Elevation, Chart palette, רכיבי ליבה (Panel hierarchy, KPI Composition, Tabs, Drawer, DataTable, CommandPalette, GlobalSearch) | ⬜ |
| C | Dashboard Redesign | היררכיה, Primary metric, גרף מרכזי, Attribution, Movers, Risk snapshot, News snapshot | ⬜ |
| D | Positions + Asset Page | טבלת Pro (Views/Pin/Virtual/Expand), עמוד Asset Intelligence מלא + גרף מחיר | ⬜ |
| E | News Infrastructure | NewsProvider Adapter (Finnhub), DB model, ingestion, dedup, entity-mapping, relevance, caching, error/rate-limit | ⬜ |
| F | News UX | Portfolio/Asset/Market news, News Center, פילטרים, Saved/Read, Material events, חדשות על גרף | ⬜ |
| G | Performance + Risk Redesign | Benchmark overlay, Heatmap, Rolling, Distribution, Attribution; Treemap, Correlation matrix, Concentration, Scenario | ⬜ |
| H | Trade Planning module | Trade Plan → Draft Order → Validation → Review → (שיגור כבוי) + Kill Switch + Audit + Bracket + What-If (כבוי) | ⬜ |
| I | Polish | Microinteractions, Responsive, RTL, נגישות, ביצועים, עקביות | ⬜ |
| J | QA | Regression, בדיקות חדשות, build/lint/typecheck, סקירה ויזואלית | ⬜ |

## פירוט תמציתי

### B — Design Foundation
`globals.css` מורחב לכל טוקני UI_SYSTEM; רכיבים: `Panel` (variants + elevation), `StatBlock` (Primary+Secondary+delta+tooltip), `Tabs`, `Drawer`, `DataTable` (TanStack Table+Virtual), `CommandPalette` (⌘K), `GlobalSearch`, `MetricInfo` (tooltip "הסבר לי"), `PageExplain`. עדכון Top Bar (חיפוש, מטבע, טווח זמן, סטטוס, theme, משתמש) וניווט מכווץ + Active ברור.

### C — Dashboard
Grid: Primary (NLV + Δיומי + Δ%) גדול; שורת Secondary (YTD/מצטבר/מזומן/Buying Power/מרג'ין); **גרף מרכזי** (מצבים: שווי/תשואה/Benchmark/Drawdown, טווחי זמן, crosshair/zoom/סימוני תזרים); Attribution (Top contributors/detractors, לפי סקטור/Asset/מטבע/דיבידנד/עמלות); Movers; Risk snapshot; News snapshot. הכול Drill-down.

### E — News Infrastructure (מפורט)
Interface `NewsProvider`: `fetchNewsForAsset`, `fetchPortfolioNews`, `fetchMarketNews`, `normalizeArticle`, `deduplicateArticles`, `calculateRelevance`, `mapEntitiesToAssets`. מימוש `FinnhubProvider` (ברירת מחדל); מבנה מוכן ל־Marketaux. DB: טבלת `news_articles` (provider_id, canonical_url, headline, source, published_at, summary, symbols, entities, event_type, relevance, sentiment+confidence, is_read/saved/hidden, related_position_ids, ingestion_time, data_source). Dedup לפי canonical URL + דמיון כותרת + זמן + מקור. Relevance score (נכס בכותרת / נושא מרכזי / גודל פוזיציה / מהותיות / עדכניות / אמינות מקור). **פרטיות: נשלח לספק רק Symbol — לעולם לא תיק/פוזיציות/רווח/מספר חשבון.** מפתח ב־`.env` (`FINNHUB_API_KEY`); בלי מפתח → Empty State מוסבר, לא זיוף.

### H — Trade Planning (כבוי כברירת מחדל)
כל התכנון/טיוטות/Validation/Review/Audit/Bracket ייבנו ויבדקו. שיגור אמיתי מאחורי **שני** דגלים (`IBKR_TRADING_ENABLED`, `IBKR_LIVE_ORDER_TRANSMISSION_ENABLED`) שנשארים `false`. אני עוצר לפני הפעלה ומסביר: הגדרות, הרשאות IBKR, סיכונים, בדיקת חשבון, חזרה ל־Read-Only, Kill Switch. אין הוראת Live לבדיקה ללא אישור מפורש לכל בדיקה.

## מסמכי מעקב (מתעדכנים אחרי כל שלב)
`PROJECT_STATE.md` · `COMPLETED_WORK.md` · `CURRENT_PHASE.md` · `NEXT_STEPS.md` · `KNOWN_ISSUES.md` · `TEST_STATUS.md` · `CHANGELOG.md` · `UI_SYSTEM.md`.
