"""Flex credentials persistence + service hot-reload."""

from app.core.config import Settings
from app.services.flex_credentials import mask_token
from app.services.flex_sync import FlexSyncService


def test_mask_token():
    assert mask_token("") == ""
    assert mask_token("abcd") == "****"
    assert mask_token("abcdefghij") == "…ghij"


def test_set_credentials_hot_reload():
    svc = FlexSyncService(Settings(ibkr_flex_token="", ibkr_flex_query_id="", _env_file=None))
    assert not svc.is_configured
    svc.set_credentials("tok-123456", "99999")
    assert svc.is_configured
    assert svc.token == "tok-123456"
    assert svc.query_id == "99999"
