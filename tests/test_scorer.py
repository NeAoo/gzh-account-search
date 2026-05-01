"""Scorer unit tests."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gzh_account_search.config import LLMConfig
from gzh_account_search.models import Article
from gzh_account_search.scorer import Scorer, parse_score_json, render_prompt

PROMPT_TEMPLATE = """评估文章:
- 标题: {{ title }}
- 来源: {{ source }}
- 发布: {{ publish_time }}
- 正文: {{ content }}
"""


@pytest.fixture
def prompt_file(tmp_path: Path) -> Path:
    file_path = tmp_path / "scoring.txt"
    file_path.write_text(PROMPT_TEMPLATE, encoding="utf-8")
    return file_path


@pytest.fixture
def article() -> Article:
    return Article(
        title="测试标题",
        source="某公众号",
        publish_time=datetime(2026, 5, 1, 10, 0),
        url="https://example.com/1",
        content="正文内容",
    )


def test_render_prompt_substitutes_fields(prompt_file, article):
    prompt = render_prompt(prompt_file, article)
    assert "测试标题" in prompt
    assert "某公众号" in prompt
    assert "2026-05-01" in prompt


def test_parse_score_json_bare():
    text = '{"heat":8,"authority":9,"quality":8,"practicality":7,"timeliness":6,"overall":7.8,"reason":"ok"}'
    result = parse_score_json(text)
    assert result["overall"] == 7.8
    assert result["reason"] == "ok"


def test_parse_score_json_wrapped_in_text():
    text = '前缀\n{"overall":6.0,"reason":"x"}\n后缀'
    result = parse_score_json(text)
    assert result["overall"] == 6.0


def test_parse_score_json_invalid_returns_empty():
    assert parse_score_json("not json at all") == {}


def test_parse_score_json_nested_score():
    text = '{"score":{"overall":7.5,"reason":"r"}}'
    result = parse_score_json(text)
    assert result["overall"] == 7.5


def test_scorer_score_batch_uses_mock(prompt_file, article, monkeypatch):
    fake_response = MagicMock()
    fake_response.choices = [
        MagicMock(
            message=MagicMock(
                content='{"heat":8,"authority":8,"quality":8,"practicality":8,"timeliness":8,"overall":8.0,"reason":"ok"}'
            )
        )
    ]
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_response
    monkeypatch.setattr("gzh_account_search.scorer.OpenAI", lambda **kwargs: fake_client)

    llm_config = LLMConfig(
        api_key="sk-test",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        workers=2,
    )
    scorer = Scorer(llm_config, prompt_file)
    scored = scorer.score_batch([article])
    assert len(scored) == 1
    assert scored[0].score == 8.0
    assert scored[0].score_details["heat"] == 8.0


def test_scorer_select_top_n_sorts_descending(prompt_file, monkeypatch):
    monkeypatch.setattr("gzh_account_search.scorer.OpenAI", lambda **kwargs: MagicMock())
    llm_config = LLMConfig(api_key="sk-test", base_url="x", model="m", workers=1)
    scorer = Scorer(llm_config, prompt_file)
    a = Article(title="a", source="s", publish_time=datetime.now(), url="u")
    a.score = 5.0
    b = Article(title="b", source="s", publish_time=datetime.now(), url="u")
    b.score = 9.0
    c = Article(title="c", source="s", publish_time=datetime.now(), url="u")
    c.score = 7.0
    top = scorer.select_top_n([a, b, c], n=2)
    assert [item.title for item in top] == ["b", "c"]


def test_scorer_handles_llm_failure_with_default_score(prompt_file, article, monkeypatch):
    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = RuntimeError("api boom")
    monkeypatch.setattr("gzh_account_search.scorer.OpenAI", lambda **kwargs: fake_client)

    llm_config = LLMConfig(api_key="sk-test", base_url="x", model="m", workers=1)
    scorer = Scorer(llm_config, prompt_file)
    scored = scorer.score_batch([article])
    assert len(scored) == 1
    assert scored[0].score == 5.0
    assert "error" in scored[0].score_details
