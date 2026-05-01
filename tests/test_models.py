"""Article data model tests."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from gzh_account_search.models import CONTENT_MAX_LENGTH, Article, CollectionResult


def test_article_required_fields():
    article = Article(
        title="标题",
        source="某公众号",
        publish_time=datetime(2026, 5, 1, 10, 0),
        url="https://mp.weixin.qq.com/s/abc",
    )
    assert article.title == "标题"
    assert article.content == ""
    assert article.score is None
    assert article.tags == []


def test_article_truncates_long_content():
    long_text = "a" * (CONTENT_MAX_LENGTH + 100)
    article = Article(
        title="t",
        source="s",
        publish_time=datetime.now(),
        url="u",
        content=long_text,
    )
    assert len(article.content) == CONTENT_MAX_LENGTH


def test_article_missing_required_field_raises():
    with pytest.raises(ValidationError):
        Article(title="t", source="s", publish_time=datetime.now())


def test_article_serializes_datetime_to_isoformat():
    publish_time = datetime(2026, 5, 1, 10, 0)
    article = Article(title="t", source="s", publish_time=publish_time, url="u")
    dumped = article.model_dump(mode="json")
    assert dumped["publish_time"] == "2026-05-01T10:00:00"


def test_collection_result_default_empty():
    result = CollectionResult()
    assert result.success_count == 0
    assert result.failed_count == 0
    assert result.items == []
    assert result.error_messages == []
