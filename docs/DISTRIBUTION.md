# הפצה למשתמשים דרך GitHub ו־GHCR

החבילה הזו הופכת את המערכת למוצר שניתן למסור למשתמש אחר בלי להעביר אליו
קוד בנייה, סודות או מסד נתונים. הקוד וה־container images נשמרים ב־GitHub;
החשבון, הנתונים והסודות של כל משתמש נשארים במחשב שלו.

## גבול הארכיטקטורה

- **בענן/GitHub:** קוד מקור, בדיקות CI ו־images עם provenance ו־SBOM עבור
  backend ו־frontend.
- **אצל המשתמש:** IB Gateway, אימות דו־שלבי, PostgreSQL, נתוני התיק, Flex Token
  מוצפן ו־Finnhub key.
- **Finnhub אופציונלי:** כשהמפתח מוגדר, סמלי שמונה ההחזקות הגדולות וטווח
  תאריכים נשלחים ל־Finnhub לקבלת חדשות. משאירים את המפתח ריק כדי להשאיר
  גם את סמלי ההחזקות מקומיים.
- שם המשתמש, הסיסמה וקוד ה־2FA של IBKR מוקלדים רק ביישום הרשמי IB Gateway.
  הדשבורד אינו מקבל או שומר אותם.
- כל הפורטים המפורסמים קשורים ל־`127.0.0.1`. זו אינה גרסת SaaS ציבורית,
  ואין לחשוף את הפורטים ישירות לאינטרנט.

החלוקה הזו מכוונת: חיבור Gateway הוא session אישי של המשתמש ודורש אימות של
IBKR. הפצה מקומית של agent לכל משתמש בטוחה יותר מהעלאת session פיננסי משותף
לשרת ציבורי.

## התקנה אצל משתמש

דרישות:

1. macOS או Linux עם Bash וכלי Unix בסיסיים. ב־Linux/WSL נדרש גם `flock`
   (בדרך כלל מחבילת `util-linux`); ב־macOS נעשה שימוש ב־`lockf` המובנה.
   ב־Windows נדרש WSL2; PowerShell רגיל אינו נתמך כרגע.
2. Docker Desktop או Docker Engine עם Docker Compose v2.
3. IB Gateway הרשמי של Interactive Brokers.
4. חשבון IBKR פעיל; Flex Token ו־Query ID נדרשים רק להיסטוריה.

```bash
git clone https://github.com/hillaybarbi64/stock-market.git
cd stock-market
./scripts/install-release.sh
```

המתקין:

1. יוצר `.env` מקומי בהרשאות `0600` וסיסמת PostgreSQL אקראית.
2. מבקש לבחור Live (`4001`) או Paper (`4002`).
3. מוריד images מ־GHCR במקום לבנות את המערכת במחשב המשתמש.
4. בעדכון קיים יוצר backup מקומי לפני הפעלת migrations.
5. מעלה Postgres, backend ו־frontend וממתין ל־health.
6. משאיר `IBKR_READONLY=true` ו־`IBKR_FLEX_AUTOSYNC=false` באופן קשיח.

המתקין אינו מוחק תהליכים שתופסים פורטים ואינו דורס `.env` קיים. אפשר להריץ
אותו שוב כדי למשוך עדכון תוך שמירה על ה־volumes המקומיים.

### חיבור החשבון

1. פתח IB Gateway והתחבר שם לחשבון Live או Paper.
2. ב־API Settings הפעל **Read-Only API**, הגדר את הפורט שנבחר, והגבל
   חיבורים למחשב המקומי.
3. פתח `http://localhost:3000/connect` ועבור על אשף החיבור. ה־UI מציג
   `APP READ-ONLY`; את אכיפת Read-Only בצד IBKR מאמתים בצ'קבוקס של Gateway.
   אם זו התקנה משודרגת שכבר מכילה היסטוריה, אשר את הקישור רק לאחר שווידאת
   שמספר החשבון הממוסך המוצג הוא בעל הנתונים הקיימים.
4. אם צריך היסטוריה, הזן Flex Token ו־Query ID באשף. ה־Token מוצפן לפני
   כתיבה ל־PostgreSQL. הפעל סנכרון ידני אחד בלבד; התזמון האוטומטי נשאר כבוי.

כל משתמש מבצע את השלבים עם החשבון שלו; אין חשבון מרכזי ואין שיתוף credentials.

## פרסום גרסה על ידי maintainer

ה־workflow
`.github/workflows/publish-images.yml` מפרסם images מרובי־ארכיטקטורות
(`linux/amd64` ו־`linux/arm64`) בעת דחיפת tag סמנטי:

```bash
git tag v0.1.0
git push origin v0.1.0
```

ה־images יפורסמו רק עם תג הגרסה המלא והבלתי־משתנה:

- `ghcr.io/hillaybarbi64/ibkr-dashboard-backend:0.1.0`
- `ghcr.io/hillaybarbi64/ibkr-dashboard-frontend:0.1.0`

לא מפורסמים aliases משתנים כמו `latest` או `0.1`, ולכן backend ו־frontend
נמשכים תמיד מאותה גרסה מפורשת. אפשר גם להריץ את ה־workflow ידנית עם גרסה
סמנטית מלאה וייחודית, למשל `0.2.0-rc.1`, שלא ייעשה בה שימוש חוזר.

עד לקבלת עמדה מתאימה מ־IBKR להפצה לצדדים שלישיים, יש להשאיר את ה־repository
וה־packages פרטיים ולמסור גישה רק לפיילוט מאושר. Package פרטי דורש
`docker login ghcr.io` עם token בעל `read:packages`. רק לאחר אישור ההפצה
אפשר לשקול להפוך את שני ה־packages ל־Public.

## CI

`.github/workflows/ci.yml` רץ על push, pull request והרצה ידנית:

- Ruff lint וכל בדיקות backend מול PostgreSQL ייעודי בשם
  שמסתיים ב־`_test`.
- ESLint ובניית production של Next.js.
- בניית שני Dockerfiles ללא פרסום.

ב־CI כל ספק חיצוני כבוי: אין Flex token, אין Finnhub key, אין חיבור ל־Gateway
ו־Flex autosync כבוי.

## עדכון, עצירה וגיבוי

התקנה או עדכון לגרסה המוצמדת ב־`.env`:

```bash
./scripts/install-release.sh
```

עצירה בלי מחיקת נתונים:

```bash
docker compose -f docker-compose.release.yml down
```

המתקין החדש ננעל כברירת מחדל ל־`DASHBOARD_IMAGE_TAG=0.1.0`. שדרוג לגרסה
מאוחרת יותר נעשה בשינוי מפורש של הערך בתוך `.env`, ואז הרצה חוזרת של המתקין.

גיבוי ושחזור:

```bash
./scripts/backup.sh
./scripts/restore.sh ~/.ibkr-dashboard/backups/db_YYYYmmdd_HHMMSS.sql.gz \
  ~/.ibkr-dashboard/backups/data_YYYYmmdd_HHMMSS
```

הסקריפטים מזהים התקנת release לפי `.env`, עוצרים writers לפני restore,
יוצרים safety backup ואז מחליפים את ה־DB. לשחזור במחשב אחר צריך להעביר
בנפרד ובאופן מאובטח גם את `.env`/`APP_SECRET_KEY`; בלי אותו מפתח אי אפשר
לפענח את Flex Token או לאמת את קישור החשבון.

הנתונים נמצאים ב־Docker volumes בשם הפרויקט `ibkr-dashboard`. לעולם אין לצרף
את `.env`, dumps או backups ל־GitHub issue, release או repository.

## רישוי ואישור IBKR לפני מסירה מסחרית

תשתית ההפצה היא טכנית ואינה מהווה אישור מסחרי מצד IBKR. רישיון ה־TWS API
הרשמי מבחין בין כלי פנימי לחשבון של המפתח לבין תוכנה שמופצת לצדדים שלישיים,
ומורה ליצור קשר עם IBKR כאשר מוכרים את המוצר או מפיקים ממנו תועלת עקיפה.
הוא גם מגביל הפצת Market Data ללא אישור בכתב:

- https://interactivebrokers.github.io/
- https://ibkrcampus.com/campus/ibkr-api-page/webapi-doc/

לכן אפשר להשתמש בחבילה לפיתוח ולפיילוט פרטי מבודד, אבל לפני launch מסחרי יש
לקבל מ־IBKR עמדה/אישור מתאים ולבדוק את תנאי נתוני השוק. זו אינה חוות דעת משפטית.
