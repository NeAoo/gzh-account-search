"""Pipeline integration tests with mocked browser, crawler, and scorer."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

from gzh_account_search.config import (
    Config,
    FetchConfig,
    LLMConfig,
    OutputConfig,
    PathsConfig,
    ScoringConfig,
)
from gzh_account_search.models import Article, CollectionResult


def _build_config(tmp_path: Path, scoring_enabled: bool = True) -> Config:
    prompt_file = tmp_path / "prompts" / "scoring.txt"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text("评估: {{ title }}", encoding="utf-8")

    template_dir = tmp_path / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    (template_dir / "report.md.j2").write_text(
        "# 报告\n{% for article in articles %}- {{ article.title }} ({{ article.score }})\n{% endfor %}",
        encoding="utf-8",
    )
    (template_dir / "report_no_score.md.j2").write_text(
        "# 简报\n{% for article in articles %}- {{ article.title }}\n{% endfor %}",
        encoding="utf-8",
    )

    return Config(
        llm=LLMConfig(
            api_key="sk-test" if scoring_enabled else "",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            workers=1,
        ),
        fetch=FetchConfig(
            accounts=["公众号A"],
            max_articles_per_account=5,
            lookback_days=7,
            fetch_full_content=False,
            browser_mode="auto",
            login_timeout_seconds=180,
            slow_mo_ms=300,
            action_delay_seconds=1.5,
            article_delay_seconds=3.0,
            page_delay_seconds=4.0,
            account_delay_seconds=8.0,
        ),
        scoring=ScoringConfig(
            enabled=scoring_enabled,
            prompt_file=str(prompt_file),
        ),
        output=OutputConfig(
            dir=str(tmp_path / "output"),
            template_file=str(template_dir / "report.md.j2"),
            no_score_template_file=str(template_dir / "report_no_score.md.j2"),
            top_n=5,
            filename_pattern="日报_{date}.md",
        ),
        paths=PathsConfig(
            raw_data_dir=str(tmp_path / "raw_data"),
            browser_data=str(tmp_path / "browser_data" / "state.json"),
            log_file=str(tmp_path / "logs" / "run.log"),
        ),
    )


def _fake_articles() -> list[Article]:
    return [
        Article(
            title="文章 1",
            source="公众号A",
            author="公众号A",
            publish_time=datetime(2026, 5, 1, 10),
            url="https://example.com/1",
            content="正文 1",
        ),
        Article(
            title="文章 2",
            source="公众号A",
            author="公众号A",
            publish_time=datetime(2026, 4, 30, 10),
            url="https://example.com/2",
            content="正文 2",
        ),
    ]


class FakeBrowserSession:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __enter__(self):
        return MagicMock(), MagicMock(), "fake-token"

    def __exit__(self, exc_type, exc_value, traceback):
        return False


def test_pipeline_with_scoring(tmp_path, monkeypatch):
    from gzh_account_search.pipeline import Pipeline

    config = _build_config(tmp_path, scoring_enabled=True)
    monkeypatch.setattr("gzh_account_search.pipeline.BrowserSession", FakeBrowserSession)

    fake_crawler_cls = MagicMock()
    fake_crawler_cls.return_value.collect.return_value = CollectionResult(
        success_count=2, items=_fake_articles()
    )
    monkeypatch.setattr("gzh_account_search.pipeline.WechatMpCrawler", fake_crawler_cls)

    scored = _fake_articles()
    scored[0].score = 9.0
    scored[1].score = 7.0
    fake_scorer_cls = MagicMock()
    fake_scorer_cls.return_value.score_batch.return_value = scored
    fake_scorer_cls.return_value.select_top_n.return_value = scored
    monkeypatch.setattr("gzh_account_search.pipeline.Scorer", fake_scorer_cls)

    output_file = Pipeline(config).run()
    text = Path(output_file).read_text(encoding="utf-8")
    assert "文章 1" in text
    assert "9.0" in text


def test_pipeline_without_scoring(tmp_path, monkeypatch):
    from gzh_account_search.pipeline import Pipeline

    config = _build_config(tmp_path, scoring_enabled=False)
    monkeypatch.setattr("gzh_account_search.pipeline.BrowserSession", FakeBrowserSession)

    fake_crawler_cls = MagicMock()
    fake_crawler_cls.return_value.collect.return_value = CollectionResult(
        success_count=2, items=_fake_articles()
    )
    monkeypatch.setattr("gzh_account_search.pipeline.WechatMpCrawler", fake_crawler_cls)

    fake_scorer_cls = MagicMock()
    monkeypatch.setattr("gzh_account_search.pipeline.Scorer", fake_scorer_cls)

    output_file = Pipeline(config).run()
    fake_scorer_cls.assert_not_called()
    text = Path(output_file).read_text(encoding="utf-8")
    assert "文章 1" in text
    assert "简报" in text


def test_pipeline_returns_none_when_no_articles(tmp_path, monkeypatch):
    from gzh_account_search.pipeline import Pipeline

    config = _build_config(tmp_path, scoring_enabled=True)
    monkeypatch.setattr("gzh_account_search.pipeline.BrowserSession", FakeBrowserSession)

    fake_crawler_cls = MagicMock()
    fake_crawler_cls.return_value.collect.return_value = CollectionResult(
        success_count=0,
        items=[],
    )
    monkeypatch.setattr("gzh_account_search.pipeline.WechatMpCrawler", fake_crawler_cls)

    output_file = Pipeline(config).run()
    assert output_file is None
