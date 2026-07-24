# DATA_DICTIONARY — מילון הנתונים

כל טבלה מציינת: מקור הנתונים, מפתח ייחודי (למניעת כפילויות בסנכרון), והערות.

סימוני מקור: `GW` = IBKR Gateway (חי) · `FLEX` = Flex Web Service (היסטורי) · `CALC` = מחושב על ידי המערכת · `MANUAL` = הוזן ידנית · `MKT` = נתוני שוק (ברים היסטוריים דרך Gateway)

## טבלאות ליבה

### instruments — נכסים
| שדה | תיאור | מקור |
|---|---|---|
| conid (PK) | מזהה החוזה הקבוע של IBKR | GW/FLEX |
| symbol, name, sec_type, currency, exchange | פרטי הנכס | GW/FLEX |
| sector, industry, country | סיווג (מ־Flex/Gateway; ניתן לתיקון ידני) | FLEX/MANUAL |

### account_snapshots — צילומי מצב חשבון (תוך־יומי)
| שדה | תיאור | מקור |
|---|---|---|
| id (PK), ts | חותמת זמן | — |
| net_liquidation, total_cash, gross_position_value, buying_power, excess_liquidity, init_margin, maint_margin, available_funds, leverage | ערכי החשבון במטבע הבסיס | GW |
| unrealized_pnl, realized_pnl | P&L נוכחי | GW |
| data_quality | REALTIME / DELAYED / STALE | CALC |

### cash_balances — יתרות לפי מטבע (snapshot)
currency, cash_balance, settled_cash, nlv_in_ccy, fx_rate_to_base, ts. מקור: GW.

### daily_equity — שורת הזהב של ההיסטוריה (יום לכל תאריך)
| שדה | תיאור | מקור |
|---|---|---|
| date (PK) | יום מסחר | FLEX |
| nav | Net Asset Value בסגירה, מטבע בסיס | FLEX (EquitySummaryInBase) |
| cash, stock_value, dividend_accruals, interest_accruals | פירוק | FLEX |
| deposits, withdrawals | תזרים חיצוני של היום | FLEX (מצטבר מ־cash_transactions) |
| twr_daily | תשואת היום בנטרול תזרים | CALC |
| source_line_hash | לזיהוי תיקון רטרואקטיבי בדוח | CALC |

### positions — פוזיציות נוכחיות
conid (FK), quantity, avg_cost, market_price, market_value, unrealized_pnl, daily_pnl, currency, price_quality, updated_at. מקור: GW. היסטוריית פוזיציות נגזרת מ־executions + position_snapshots יומיים (FLEX Open Positions).

### executions — ביצועים (fills)
| שדה | תיאור | מקור |
|---|---|---|
| exec_id (UNIQUE) | מזהה ביצוע של IBKR — המפתח לאידמפוטנטיות | GW/FLEX |
| order_id, perm_id | קישור להוראה | GW/FLEX |
| conid, side, quantity, price, trade_time (UTC + tz מקורי), exchange, order_type | פרטי הביצוע | GW/FLEX |
| commission, commission_currency | עמלה | FLEX (מדויק) / GW |
| realized_pnl_ib | כפי שמדווח IBKR (FIFO) | FLEX |
| fx_rate_to_base | שער ביום העסקה | FLEX |
| source | gateway / flex — לשקיפות והצלבה | — |

### orders — הוראות
perm_id (UNIQUE), conid, status, side, order_type, limit_price, aux_price, tif, quantity, filled, remaining, ts. מקור: GW (חי) + FLEX (היסטורי). לקריאה בלבד.

### cash_transactions — תנועות מזומן
| שדה | תיאור | מקור |
|---|---|---|
| transaction_id (UNIQUE) | מזהה IBKR | FLEX |
| type | DEPOSIT / WITHDRAWAL / DIVIDEND / PAYMENT_IN_LIEU / WITHHOLDING_TAX / FEE / COMMISSION_ADJ / BROKER_INTEREST_PAID / BROKER_INTEREST_RECEIVED / FX / OTHER | FLEX |
| amount, currency, fx_rate_to_base, date_time, settle_date, conid (nullable), description | פרטים | FLEX |

### corporate_actions — פעולות תאגידיות
action_id (UNIQUE), type (SPLIT/MERGER/SPINOFF/...), conid, ratio, ex_date, pay_date, description. מקור: FLEX.

### fx_rates — שערי מט"ח יומיים
date+currency (PK), rate_to_base, source. מקור: FLEX/MKT. נשמר כדי שכל חישוב יהיה ניתן לשחזור.

### benchmark_prices
symbol+date (PK), close, adj_close, currency, source. מקור: MKT.

## טבלאות יומן וניתוח

### trade_cycles — מחזורי עסקה
id, conid, open_exec_id (מזהה ה־execution שפתח את המחזור; יחד עם conid הוא
המפתח היציב), direction (LONG/SHORT), open_time, close_time (nullable=פתוח),
max_quantity, realized_pnl, fees_total, dividends_total, matching_method
(FIFO/MANUAL), is_manually_adjusted, original_matching (JSON — השיוך
האוטומטי נשמר תמיד). מקור: CALC + MANUAL.

### cycle_executions — שיוך ביצועים למחזורים
cycle_id + exec_id + allocated_quantity. שיוך חלקי נתמך.

### journal_entries — רשומות יומן
id, cycle_id (nullable), entry_date, strategy, setup, entry_reason, thesis, catalyst, exit_reason, target_price, stop_price, planned_rr, actual_rr, amount_at_risk, pct_at_risk, confidence (1-5), emotional_state, followed_plan (bool), changed_plan_midway (bool), mistake, done_right, key_lesson, next_time, rating (1-5), free_notes. מקור: MANUAL.

### journal_templates — תבניות (Swing/Position/Earnings/Breakout/...)
id, name, fields_schema (JSON), is_builtin.

### tags / entity_tags — תגיות חופשיות לכל ישות (עסקה, מחזור, רשומה)

### attachments — קבצים/צילומי מסך
id, entity_type, entity_id, file_path (מקומי בלבד), mime, size, uploaded_at. הקבצים נשמרים בתיקיית data מקומית, לא ב־DB ולא ב־Git.

## טבלאות מערכת

### insights — תובנות
id, kind, severity (INFO/WARN/ALERT), confidence (LOW/MED/HIGH), title, body, evidence (JSON — הנתונים שעליהם מבוססת), assumptions, links, created_at, dismissed_at. מקור: CALC.

### alert_rules / alert_events — כללי התראה ואירועים
rule: metric, operator, threshold, scope, enabled. event: rule_id, fired_at, value, acknowledged.

### sync_runs — ריצות סנכרון
id, kind (FLEX_FULL/FLEX_INCREMENTAL/SNAPSHOT/BENCHMARKS), started_at, finished_at, status, date_range, records_upserted, records_skipped, errors (JSON).

### audit_log — יומן ביקורת
ts, actor (system/user/ai_assistant), action, entity, details (JSON, ללא סודות). כל קריאת IBKR, כל שינוי ידני, כל שאלת AI עתידית — נרשמים.

### settings — הגדרות
key, value (JSON): מטבע תצוגה, אזור זמן (ברירת מחדל Asia/Jerusalem), benchmarks, כללי סיכון (מגבלת פוזיציה/סקטור/DD), ריבית חסרת סיכון, שיטת cost basis לתצוגה, תחילת שבוע, מסכת מספר חשבון, theme, שפה.

### schema_migrations — מנוהל על ידי Alembic

## עקרונות רוחביים

1. **זמנים**: כל חותמת נשמרת UTC + ציון ה־timezone המקורי של האירוע. תצוגה לפי אזור הזמן בהגדרות.
2. **כסף**: `NUMERIC` (לא float) בכל עמודת כסף/כמות. מטבע מפורש לצד כל סכום.
3. **אידמפוטנטיות**: כל טבלת נתונים חיצוניים — מפתח ייחודי טבעי + upsert. סנכרון חוזר לא מכפיל.
4. **תיקונים רטרואקטיביים**: אם Flex מחזיר ערך שונה לרשומה קיימת (למשל עמלה מתוקנת), הרשומה מתעדכנת, ההבדל נרשם ב־audit_log, ומופיע בדוח ה־Reconciliation.
5. **מחיקה**: אין מחיקת נתוני מקור; ביטול = סימון. מחיקת כל הנתונים המקומיים אפשרית דרך סקריפט ייעודי מתועד.
