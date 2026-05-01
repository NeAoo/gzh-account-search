"""Renderer tests."""

import json
from pathlib import Path

from gzh_account_search.models import Article
from gzh_account_search.renderer import Renderer


def _load_articles() -> list[Article]:
    fixture = Path(__file__).parent / "fixtures" / "sample_articles.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    return [Article.model_validate(item) for item in payload]


def test_render_with_scores_uses_template():
    renderer = Renderer(
        template_file=Path("templates/report.md.j2"),
        no_score_template_file=Path("templates/report_no_score.md.j2"),
    )
    content = renderer.render_with_scores(_load_articles())
    assert "gzh 文章精选" in content
    assert "文章 1" in content
    assert "9.00" in content


def test_render_no_score_uses_template():
    renderer = Renderer(
        template_file=Path("templates/report.md.j2"),
        no_score_template_file=Path("templates/report_no_score.md.j2"),
    )
    content = renderer.render_no_score(_load_articles())
    assert "gzh 文章简报" in content
    assert "评分模式" in content
    assert "文章 2" in content


def test_save_writes_file(tmp_path):
    renderer = Renderer(
        template_file=Path("templates/report.md.j2"),
        no_score_template_file=Path("templates/report_no_score.md.j2"),
    )
    target = tmp_path / "out" / "report.md"
    renderer.save("hello", target)
    assert target.read_text(encoding="utf-8") == "hello"
