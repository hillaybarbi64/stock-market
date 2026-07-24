from datetime import UTC, datetime, timedelta

from app.api.sync import _last_failure_from_runs
from app.db.models import SyncRun
from app.ibkr.flex import FlexError
from app.ibkr.flex_help import explain_flex_error, help_for_code


def test_help_for_1013():
    help_he = help_for_code("1013")
    assert help_he is not None
    assert "IP" in help_he


def test_explain_flex_error_1013():
    explained = explain_flex_error(FlexError("1013", "IP restriction."))
    assert explained["code"] == "1013"
    assert "IP" in explained["help_he"]


def test_explain_legacy_error_string():
    explained = explain_flex_error(RuntimeError("FlexError: Flex error 1013: IP restriction."))
    assert explained["code"] == "1013"
    assert explained["help_he"]


def test_latest_failed_outcome_is_safe_and_actionable():
    started_at = datetime(2026, 7, 24, 8, 0, tzinfo=UTC)
    failed = SyncRun(
        kind="flex_full",
        started_at=started_at,
        finished_at=started_at + timedelta(seconds=2),
        status="failed",
        errors={
            "error": (
                "FlexError: Flex error 1013: IP restriction "
                "https://example.test/?t=SUPERSECRET"
            ),
            "error_code": "1013",
        },
    )

    failure = _last_failure_from_runs([failed])

    assert failure is not None
    assert failure["code"] == "1013"
    assert failure["error"] == "Flex error 1013"
    assert "IP" in failure["help_he"]
    assert "SUPERSECRET" not in str(failure)


def test_newer_success_clears_older_failure():
    started_at = datetime(2026, 7, 24, 8, 0, tzinfo=UTC)
    failed = SyncRun(
        kind="flex_full",
        started_at=started_at,
        finished_at=started_at + timedelta(seconds=2),
        status="failed",
        errors={"error": "Flex error 1013", "error_code": "1013"},
    )
    success = SyncRun(
        kind="flex_full",
        started_at=started_at + timedelta(minutes=2),
        finished_at=started_at + timedelta(minutes=3),
        status="ok",
        errors={"trigger": "manual"},
    )

    assert _last_failure_from_runs([success, failed]) is None
