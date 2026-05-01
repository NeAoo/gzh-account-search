"""Markdown report rendering."""

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from loguru import logger

from gzh_account_search.models import Article


class Renderer:
    """Render scored or unscored Markdown reports from Jinja2 templates."""

    def __init__(self, template_file: Path, no_score_template_file: Path) -> None:
        self.template_file = Path(template_file)
        self.no_score_template_file = Path(no_score_template_file)
        self._validate_template(self.template_file)
        self._validate_template(self.no_score_template_file)

    def render_with_scores(self, articles: list[Article]) -> str:
        return self._render(self.template_file, articles)

    def render_no_score(self, articles: list[Article]) -> str:
        return self._render(self.no_score_template_file, articles)

    def save(self, content: str, target: Path) -> str:
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        logger.info(f"Report saved: {target}")
        return str(target)

    def _render(self, template_file: Path, articles: list[Article]) -> str:
        scores = [article.score or 0 for article in articles]
        context = {
            "articles": articles,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "max_score": max(scores) if scores else 0,
            "avg_score": sum(scores) / len(scores) if scores else 0,
        }
        template = self._load_template(template_file)
        return template.render(**context)

    def _load_template(self, template_file: Path):
        environment = Environment(
            loader=FileSystemLoader(str(template_file.parent)),
            undefined=StrictUndefined,
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        return environment.get_template(template_file.name)

    def _validate_template(self, template_file: Path) -> None:
        if not template_file.exists():
            raise FileNotFoundError(f"Template file does not exist: {template_file}")
