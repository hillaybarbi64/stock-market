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
