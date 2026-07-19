"""Human-readable guidance for IBKR Flex Web Service error codes."""

from __future__ import annotations

from app.ibkr.flex import FlexError

# Hebrew guidance shown in the Sync UI. Keep factual and actionable.
_FLEX_HELP_HE: dict[str, str] = {
    "1013": (
        "הגבלת IP בפורטל IBKR — הכתובת שממנה רצה הסנכרון לא מורשית לטוקן Flex. "
        "Client Portal → Settings → Account Settings → Flex Web Service → "
        "הוסף את כתובת ה-IP הציבורית הנוכחית (מוצגת במסך סנכרון) לרשימת ה-IPs המורשים, "
        "או צור Token חדש בלי הגבלת IP / עם ה-IP הנוכחי. אחר כך הרץ סנכרון שוב."
    ),
    "1012": "טוקן Flex שגוי או פג תוקף. צור Token חדש בפורטל והזן אותו במסך סנכרון.",
    "1015": "Query ID שגוי או שהשאילתה לא פעילה. בדוק את מזהה ה-Activity Flex Query בפורטל.",
    "1018": "הטוקן לא מורשה לשאילתה הזו. ודא שה-Token וה-Query שייכים לאותו חשבון.",
    "1025": (
        "IBKR נעל את הטוקן זמנית אחרי יותר מדי ניסיונות כושלים. "
        "המתן לפחות שעה (לעיתים עד יום), אל תלחץ סנכרון שוב ושוב, ואז נסה פעם אחת."
    ),
    "1003": "השאילתה לא קיימת או הושבתה. בדוק את ה-Query ID בפורטל.",
    "1019": "IBKR עדיין מכין את הדוח — זה זמני; המערכת מנסה שוב לבד.",
    "1021": "IBKR עדיין מכין את הדוח — זה זמני; המערכת מנסה שוב לבד.",
    "1001": "IBKR מבקש לנסות שוב בקרוב (throttle) — המערכת מנסה שוב לבד.",
}


def help_for_code(code: str | None) -> str | None:
    if not code:
        return None
    return _FLEX_HELP_HE.get(str(code))


def explain_flex_error(exc: BaseException) -> dict[str, str]:
    """Return {code, message, help_he} for storage on SyncRun.errors."""
    if isinstance(exc, FlexError):
        code = str(exc.code)
        message = str(exc)
        help_he = help_for_code(code) or (
            "סנכרון Flex נכשל. בדוק Token, Query ID, והגדרות Flex Web Service בפורטל IBKR (RUNBOOK §3)."
        )
        return {"code": code, "message": message, "help_he": help_he}
    # Legacy / non-Flex exceptions — still try to detect known codes in the text.
    message = f"{type(exc).__name__}: {exc}"
    for code in _FLEX_HELP_HE:
        if code in message:
            return {"code": code, "message": message, "help_he": _FLEX_HELP_HE[code]}
    return {
        "code": "?",
        "message": message,
        "help_he": "שגיאה לא צפויה בסנכרון. בדוק את לוג ה-backend או הרץ ./scripts/doctor.sh",
    }
