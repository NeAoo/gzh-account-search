"""Crawler pure-function tests without launching a browser."""

import json
from datetime import datetime, timedelta

from gzh_account_search.crawler import (
    parse_publish_time,
    safe_path_name,
    save_grouped_raw_data,
    split_article_row_text,
    within_lookback_days,
)
from gzh_account_search.models import Article


def test_parse_publish_time_full_datetime():
    result = parse_publish_time("2026-04-30 14:25")
    assert result == datetime(2026, 4, 30, 14, 25)


def test_parse_publish_time_chinese_format():
    result = parse_publish_time("2026年4月30日")
    assert result == datetime(2026, 4, 30)


def test_parse_publish_time_yesterday_returns_recent():
    result = parse_publish_time("昨天 10:00")
    assert (datetime.now() - result) < timedelta(days=2)


def test_parse_publish_time_unknown_returns_now():
    before = datetime.now()
    result = parse_publish_time("无法解析的时间字符串")
    after = datetime.now()
    assert before <= result <= after


def test_split_article_row_text_extracts_date():
    raw = "标题\n2026-04-30\n[查看文章](https://x)"
    title, date = split_article_row_text(raw)
    assert title == "标题"
    assert date == "2026-04-30"


def test_split_article_row_text_no_date():
    raw = "纯标题\n查看文章"
    title, date = split_article_row_text(raw)
    assert title == "纯标题"
    assert date == ""


def test_within_lookback_days_recent():
    publish_time = datetime.now() - timedelta(days=3)
    assert within_lookback_days(publish_time, lookback_days=7) is True


def test_within_lookback_days_old():
    publish_time = datetime.now() - timedelta(days=10)
    assert within_lookback_days(publish_time, lookback_days=7) is False


def test_safe_path_name_strips_invalid_chars():
    assert safe_path_name("公众号A/测试:1") == "公众号A_测试_1"


def test_safe_path_name_empty_input():
    assert safe_path_name("") == "未知公众号"


def test_save_grouped_raw_data_writes_per_account_json(tmp_path):
    article = Article(
        title="标题",
        source="公众号A",
        author="公众号A",
        publish_time=datetime(2026, 5, 1, 10),
        url="https://example.com/1",
        content="正文",
    )
    save_grouped_raw_data(
        items=[article],
        raw_data_dir=tmp_path,
        lookback_days=7,
        max_articles_per_account=10,
    )
    date_dirs = list(tmp_path.iterdir())
    assert len(date_dirs) == 1
    summary_files = list(date_dirs[0].glob("all_accounts_*.json"))
    assert len(summary_files) == 1
    payload = json.loads(summary_files[0].read_text(encoding="utf-8"))
    assert payload["metadata"]["total_count"] == 1
    assert "公众号A" in payload["accounts"]
