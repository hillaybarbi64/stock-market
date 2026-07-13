"""The log masking layer must strip account ids and tokens no matter what
the call site passes — this is a security control, not a formatting nicety."""

from app.core.logging import _mask_value, _masking_processor


def test_account_id_is_masked():
    assert _mask_value("account U1234567 connected") == "account U***567 connected"
    assert _mask_value("paper DU7654321") == "paper DU***321"


def test_long_digit_tokens_are_masked():
    masked = _mask_value("token 123456789012345678901234 used")
    assert "123456789012345678901234" not in masked
    assert "***" in masked


def test_sensitive_keys_are_masked():
    event = _masking_processor(None, "", {"flex_token": "abc123", "password": "x", "msg": "hi"})
    assert event["flex_token"] == "***"
    assert event["password"] == "***"
    assert event["msg"] == "hi"


def test_short_numbers_untouched():
    assert _mask_value("price 123.45 qty 8") == "price 123.45 qty 8"
