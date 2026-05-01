"""Config loading and validation tests."""

from pathlib import Path

import pytest
import yaml

from gzh_account_search.config import Config


def _write_yaml(tmp_path: Path, payload: dict) -> Path:
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w", encoding="utf-8") as file:
        yaml.safe_dump(payload, file, allow_unicode=True)
    return config_file


def _minimal_payload() -> dict:
    return {
        "llm": {
            "api_key": "sk-test",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o-mini",
            "workers": 5,
        },
        "fetch": {
            "accounts": ["公众号A"],
            "max_articles_per_account": 10,
            "lookback_days": 7,
            "fetch_full_content": True,
            "browser_mode": "auto",
            "login_timeout_seconds": 180,
            "slow_mo_ms": 300,
            "action_delay_seconds": 1.5,
            "article_delay_seconds": 3.0,
            "page_delay_seconds": 4.0,
            "account_delay_seconds": 8.0,
        },
        "scoring": {
            "enabled": True,
            "prompt_file": "prompts/scoring.txt",
        },
        "output": {
            "dir": "./output",
            "template_file": "templates/report.md.j2",
            "no_score_template_file": "templates/report_no_score.md.j2",
            "top_n": 10,
            "filename_pattern": "公众号日报_{date}.md",
        },
        "paths": {
            "raw_data_dir": "./raw_data/wechat_mp",
            "browser_data": "./browser_data/wechat_mp_state.json",
            "log_file": "./logs/run.log",
        },
    }


def test_load_minimal_valid_config(tmp_path):
    config_file = _write_yaml(tmp_path, _minimal_payload())
    config = Config.from_yaml(config_file)
    assert config.llm.api_key == "sk-test"
    assert config.fetch.accounts == ["公众号A"]
    assert config.fetch.slow_mo_ms == 300
    assert config.fetch.account_delay_seconds == 8.0
    assert config.scoring.enabled is True


def test_scoring_enabled_but_no_api_key_raises(tmp_path):
    payload = _minimal_payload()
    payload["llm"]["api_key"] = ""
    config_file = _write_yaml(tmp_path, payload)
    with pytest.raises(ValueError, match="api_key"):
        Config.from_yaml(config_file)


def test_scoring_disabled_allows_empty_api_key(tmp_path):
    payload = _minimal_payload()
    payload["llm"]["api_key"] = ""
    payload["scoring"]["enabled"] = False
    config_file = _write_yaml(tmp_path, payload)
    config = Config.from_yaml(config_file)
    assert config.scoring.enabled is False


def test_browser_mode_invalid_raises(tmp_path):
    payload = _minimal_payload()
    payload["fetch"]["browser_mode"] = "invalid"
    config_file = _write_yaml(tmp_path, payload)
    with pytest.raises(Exception):
        Config.from_yaml(config_file)


def test_accounts_empty_raises(tmp_path):
    payload = _minimal_payload()
    payload["fetch"]["accounts"] = []
    config_file = _write_yaml(tmp_path, payload)
    with pytest.raises(ValueError, match="accounts"):
        Config.from_yaml(config_file)


def test_top_n_must_be_positive(tmp_path):
    payload = _minimal_payload()
    payload["output"]["top_n"] = 0
    config_file = _write_yaml(tmp_path, payload)
    with pytest.raises(Exception):
        Config.from_yaml(config_file)


def test_negative_delay_raises(tmp_path):
    payload = _minimal_payload()
    payload["fetch"]["article_delay_seconds"] = -1
    config_file = _write_yaml(tmp_path, payload)
    with pytest.raises(Exception):
        Config.from_yaml(config_file)
