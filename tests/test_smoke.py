"""Smoke tests that exercise YAML config loading and pipeline orchestration."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import yaml

from gzh_account_search.config import Config
from gzh_account_search.models import Article, CollectionResult


def _build_config_yaml(tmp_path: Path, scoring_enabled: bool) -> Path:
    prompt_file = tmp_path / "prompts" / "scoring.txt"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text("评估: {{ title }}", encoding="utf-8")

    template_dir = tmp_path / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    (template_dir / "report.md.j2").write_text(
        "# 报告\n{% for article in articles %}{{ article.title }} {{ article.score }}\n{% endfor %}",
        encoding="utf-8",
    )
    (template_dir / "report_no_score.md.j2").write_text(
        "# 简报\n{% for article in articles %}{{ article.title }}\n{% endfor %}",
        encoding="utf-8",
    )

    payload = {
        "llm": {
            "api_key": "sk-test" if scoring_enabled else "",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o-mini",
            "workers": 1,
        },
        "fetch": {
            "accounts": ["公众号A"],
            "max_articles_per_account": 5,
            "lookback_days": 7,
            "fetch_full_content": False,
            "browser_mode": "auto",
            "login_timeout_seconds": 180,
            "slow_mo_ms": 300,
            "action_delay_seconds": 1.5,
            "article_delay_seconds": 3.0,
            "page_delay_seconds": 4.0,
            "account_delay_seconds": 8.0,
        },
        "scoring": {
            "enabled": scoring_enabled,
            "prompt_file": str(prompt_file),
        },
        "output": {
            "dir": str(tmp_path / "output"),
            "template_file": str(template_dir / "report.md.j2"),
            "no_score_template_file": str(template_dir / "report_no_score.md.j2"),
            "top_n": 5,
            "filename_pattern": "report_{date}.md",
        },
        "paths": {
            "raw_data_dir": str(tmp_path / "raw_data"),
            "browser_data": str(tmp_path / "browser_data" / "state.json"),
            "log_file": str(tmp_path / "logs" / "run.log"),
        },
    }
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    return config_file


def _fake_article() -> Article:
    return Article(
        title="烟测文章",
        source="公众号A",
        author="公众号A",
        publish_time=datetime(2026, 5, 1, 10),
        url="https://example.com/1",
        content="正文",
    )


class FakeBrowserSession:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __enter__(self):
        return MagicMock(), MagicMock(), "fake-token"

    def __exit__(self, exc_type, exc_value, traceback):
        return False


def test_smoke_without_scoring(tmp_path, monkeypatch):
    from gzh_account_search.pipeline import Pipeline

    config = Config.from_yaml(_build_config_yaml(tmp_path, scoring_enabled=False))
    monkeypatch.setattr("gzh_account_search.pipeline.BrowserSession", FakeBrowserSession)

    fake_crawler_cls = MagicMock()
    fake_crawler_cls.return_value.collect.return_value = CollectionResult(
        success_count=1,
        items=[_fake_article()],
    )
    monkeypatch.setattr("gzh_account_search.pipeline.WechatMpCrawler", fake_crawler_cls)

    output_file = Pipeline(config).run()
    assert Path(output_file).exists()
    assert "烟测文章" in Path(output_file).read_text(encoding="utf-8")


def test_smoke_with_scoring(tmp_path, monkeypatch):
    from gzh_account_search.pipeline import Pipeline

    config = Config.from_yaml(_build_config_yaml(tmp_path, scoring_enabled=True))
    monkeypatch.setattr("gzh_account_search.pipeline.BrowserSession", FakeBrowserSession)

    fake_crawler_cls = MagicMock()
    fake_crawler_cls.return_value.collect.return_value = CollectionResult(
        success_count=1,
        items=[_fake_article()],
    )
    monkeypatch.setattr("gzh_account_search.pipeline.WechatMpCrawler", fake_crawler_cls)

    scored_article = _fake_article()
    scored_article.score = 8.0
    scored_article.score_details = {
        "heat": 8.0,
        "authority": 8.0,
        "quality": 8.0,
        "practicality": 8.0,
        "timeliness": 8.0,
        "reason": "ok",
    }
    fake_scorer_cls = MagicMock()
    fake_scorer_cls.return_value.score_batch.return_value = [scored_article]
    fake_scorer_cls.return_value.select_top_n.return_value = [scored_article]
    monkeypatch.setattr("gzh_account_search.pipeline.Scorer", fake_scorer_cls)

    output_file = Pipeline(config).run()
    assert Path(output_file).exists()
    assert "8.0" in Path(output_file).read_text(encoding="utf-8")
