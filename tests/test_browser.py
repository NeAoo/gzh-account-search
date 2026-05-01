"""Browser mode and token parsing tests."""

from gzh_account_search.browser import (
    HEADLESS_PROBE_TIMEOUT_MS,
    extract_token,
    resolve_initial_headless,
)


def test_extract_token_from_url():
    url = "https://mp.weixin.qq.com/cgi-bin/home?token=12345&lang=zh_CN"
    assert extract_token(url) == "12345"


def test_extract_token_missing_returns_none():
    url = "https://mp.weixin.qq.com/cgi-bin/loginpage?lang=zh_CN"
    assert extract_token(url) is None


def test_resolve_visible_mode_always_returns_false(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text("{}", encoding="utf-8")
    assert resolve_initial_headless("visible", state_path) is False


def test_resolve_headless_mode_always_returns_true(tmp_path):
    state_path = tmp_path / "state.json"
    assert resolve_initial_headless("headless", state_path) is True


def test_resolve_auto_no_state_returns_false(tmp_path):
    state_path = tmp_path / "missing.json"
    assert resolve_initial_headless("auto", state_path) is False


def test_resolve_auto_with_state_returns_true(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text("{}", encoding="utf-8")
    assert resolve_initial_headless("auto", state_path) is True


def test_headless_probe_timeout_is_8_seconds():
    assert HEADLESS_PROBE_TIMEOUT_MS == 8000
