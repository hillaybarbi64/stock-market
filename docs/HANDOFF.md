# Handoff למפתח נוסף

המסמך הזה מאפשר למפתח אחר להמשיך את העבודה בלי לקבל credentials של IBKR
ובלי לסכן את נתוני התיק.

## גישה ו־Git

1. לפני פיילוט עם IBKR, ודא שה־repository מוגדר Private; לאחר מכן הוסף את
   המפתח כ־Collaborator. אם הוא עדיין Public, אין בו סודות אבל אין למסור
   release מסחרי עד להשלמת בדיקת הרישוי.
2. המפתח משכפל את המאגר ועובר ל־branch הפעיל:

```bash
git clone https://github.com/hillaybarbi64/stock-market.git
cd stock-market
git switch claude/ibkr-trading-dashboard-ml90kp
```

מומלץ שהמשך פיתוח חדש ייעשה ב־branch נפרד וב־Pull Request, אחרי שה־branch
הפעיל מוזג. אין לצרף ל־commit קובצי `.env`, dumps, backups, uploads או לוגים.

## הקמה בטוחה למפתח

```bash
bash <<'BOOTSTRAP_ENV'
set -euo pipefail
umask 077

if [[ -e .env ]]; then
  echo "ERROR: .env already exists; review it instead of overwriting it." >&2
  exit 1
fi

random_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 24
  else
    LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 48 || true
  fi
}

postgres_password="$(random_secret)"
app_secret_key="$(random_secret)"
if [[ ${#postgres_password} -lt 24 || ${#app_secret_key} -lt 24 ]]; then
  echo "ERROR: Could not generate strong local secrets." >&2
  exit 1
fi

awk -F= -v password="${postgres_password}" -v app_key="${app_secret_key}" '
  $1 == "POSTGRES_PASSWORD" {
    print "POSTGRES_PASSWORD=" password
    next
  }
  $1 == "DATABASE_URL" {
    print "DATABASE_URL=postgresql+asyncpg://ibkr:" password \
      "@localhost:5432/ibkr_dashboard"
    next
  }
  $1 == "APP_SECRET_KEY" {
    print "APP_SECRET_KEY=" app_key
    next
  }
  $1 == "IBKR_GATEWAY_PORT" {
    print "IBKR_GATEWAY_PORT=4002"
    next
  }
  { print }
' .env.example > .env
chmod 600 .env
unset postgres_password app_secret_key
BOOTSTRAP_ENV

./scripts/start.sh
```

הפקודות יוצרות סיסמאות אקראיות מקומיות לפני הפעלת השירותים ומגדירות
`IBKR_GATEWAY_PORT=4002` עבור Paper. לפיתוח חיבור broker משתמשים תחילה
ב־IBKR Paper Account וב־IB Gateway הרשמי עם Read-Only API. שם משתמש, סיסמה
ו־2FA מוקלדים רק ב־IB Gateway.

אין צורך ב־Flex כדי לפתח את רוב המערכת. אם מסך `/sync` מציג cooldown או
IBKR error 1025, לא שולחים בקשת Flex נוספת ולא “בודקים” עם curl. ממתינים
לפקיעת החסימה ומפעילים סנכרון ידני יחיד דרך ה־UI.

## בדיקות לפני Pull Request

```bash
cd backend
uv sync --frozen
uv run ruff check app tests
uv run alembic upgrade head
uv run pytest

cd ../frontend
corepack enable pnpm
pnpm install --frozen-lockfile
pnpm lint
pnpm build

cd ..
bash -n scripts/*.sh scripts/lib/*.sh
docker compose config --quiet
docker compose -f docker-compose.release.yml config --quiet
```

בדיקות backend חייבות לרוץ רק מול PostgreSQL ייעודי ששמו מסתיים ב־`_test`.
ה־test suite מסרב בכוונה להשתמש במסד הפיתוח/הייצור.

## העברת נתונים אופציונלית

ברירת המחדל היא שהמפתח עובד עם DB נקי וחשבון Paper משלו. אם יש צורך מפורש
לשחזר instance קיים:

```bash
./scripts/backup.sh
./scripts/restore.sh /secure/path/db_YYYYmmdd_HHMMSS.sql.gz \
  /secure/path/data_YYYYmmdd_HHMMSS
```

את ה־backup ואת `.env` מעבירים בערוץ מוצפן ונפרד מ־GitHub. קובץ `.env`
נדרש כדי לפענח Flex Token שנשמר ב־DB ולאמת את קישור החשבון. לאחר המסירה
יש לבצע rotation לסודות שאפשר להחליף. לעולם אין להעביר סיסמת IBKR או קוד
2FA; אלה אינם נדרשים למפתח.

## גבולות המוצר הנוכחי

- זו appliance מקומית ומבודדת לחשבון יחיד, לא SaaS multi-tenant.
- backend, frontend ו־PostgreSQL חשופים רק ל־`127.0.0.1`.
- לכל משתמש יש IB Gateway ו־DB משלו.
- הפצה מסחרית או הפצת Market Data דורשות בירור ואישור מתאים מול IBKR.
- תכנון עסקאות נשאר כבוי ולא נבנה עדיין; אין במערכת שליחת orders.

מסמכי ההמשך העיקריים: `DISTRIBUTION.md`, `CLOUD_ROADMAP.md`, `RUNBOOK.md`,
`SECURITY.md` ו־`IBKR_INTEGRATION.md`.
