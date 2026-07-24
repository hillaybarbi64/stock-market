# מסלול ענן בטוח למוצר IBKR רב־משתמשים

## מה נתמך עכשיו

הגרסה הנוכחית היא **appliance פרטי לחשבון יחיד**:

- הקוד, ה־CI וה־container images נמצאים ב־GitHub/GHCR.
- כל משתמש מתקין instance נפרד עם PostgreSQL ו־IB Gateway משלו.
- כל הפורטים קשורים ל־`127.0.0.1`; אין חשיפה ציבורית.
- שם משתמש, סיסמה ו־2FA של IBKR נשארים בתוך IB Gateway הרשמי.
- Flex Token מוצפן לפני כתיבה למסד המקומי.

אין לפרוס את ה־Compose הנוכחי כשרת משותף. הוא משתמש ב־service registry,
cache, WebSocket וטבלאות גלובליים של חשבון יחיד, ואין בו auth או tenant isolation.

## למה חיבור retail חי אינו cloud-only

לפי תיעוד IBKR הנוכחי, לקוח Individual שמשתמש ב־Client Portal API נדרש
להפעיל Gateway מקומי, להשלים כניסה ו־2FA בדפדפן על אותו מחשב, וגם קריאות ה־API
צריכות לצאת מאותו מחשב. IBKR אינה ממליצה לאוטומט כניסה באמצעות צד שלישי:

- https://ibkrcampus.com/campus/ibkr-api-page/cpapi-v1/

למוצר צד שלישי שמתחבר לחשבונות של לקוחות לא קשורים נדרש מסלול onboarding
ואישור Compliance של IBKR; התיעוד מפנה ספקי צד שלישי ל־OAuth ולתהליך אישור:

- https://ibkrcampus.com/campus/ibkr-api-page/webapi-doc/

לכן UX של “הקלד מספר חשבון או סיסמה באתר והתחבר” אינו מסלול תקין או בטוח.

## ארכיטקטורת היעד

```text
דפדפן המשתמש
    │ HTTPS + OIDC/MFA
    ▼
Cloud dashboard / API
    │
    ├── PostgreSQL מנוהל + RLS + PITR
    ├── Queue/Workers מבודדים לכל tenant
    └── Secret Manager / KMS עבור Flex
              ▲
              │ outbound mTLS / pairing
              │
Local Connector חתום אצל המשתמש
              │ localhost בלבד
              ▼
IB Gateway הרשמי + login/2FA של IBKR
```

ה־connector פותח רק חיבור outbound לענן, מזווג ל־tenant ול־portfolio מסוימים,
ומעביר אירועים מנורמלים. הוא אינו מקבל או שומר את סיסמת IBKR.

## אבני דרך

1. **Release appliance** — CI, GHCR, מתקין, Live/Paper, אשף חיבור, הצפנת Flex,
   חסימת multi-account וסנכרון בטוח. זה השלב הפעיל.
2. **Local hardening** — login מקומי, session מאובטח, עדכונים חתומים, rotation
   למפתח ההצפנה ו־backup/restore מאומת.
3. **Tenant data model** — `users`, `organizations`, `memberships`,
   `portfolios`, `broker_connections`; כל נתון פרטי מקבל `portfolio_id`.
4. **Cloud security** — OIDC/MFA, RBAC, PostgreSQL RLS, CSRF/rate limiting,
   WebSocket channels מבודדים, KMS ו־audit מזוהה.
5. **Connector** — pairing חד־פעמי, mTLS, health/update channel ו־offline queue.
6. **IBKR approval** — השלמת מסלול vendor/OAuth, בדיקת רישוי והגבלות Market Data.
7. **Pilot** — Paper accounts תחילה, penetration test, restore drill ו־incident runbook.

רק לאחר שלבים 3–6 אפשר לקרוא למערכת SaaS רב־משתמשים.
