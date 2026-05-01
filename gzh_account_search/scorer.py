"""LLM scoring for collected articles."""

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from jinja2 import Template
from loguru import logger

from gzh_account_search.config import LLMConfig
from gzh_account_search.models import Article

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - dependency is required for real scoring
    OpenAI = None

DEFAULT_SCORE = 5.0
SCORE_MIN = 1.0
SCORE_MAX = 10.0


def render_prompt(prompt_file: Path, article: Article) -> str:
    template_text = Path(prompt_file).read_text(encoding="utf-8")
    template = Template(template_text)
    return template.render(
        title=article.title,
        source=article.source,
        publish_time=article.publish_time.strftime("%Y-%m-%d %H:%M"),
        content=article.content or "",
        url=article.url,
        author=article.author or "",
    )


def parse_score_json(result_text: str) -> dict:
    """Parse JSON from common LLM response shapes."""
    data = _try_load_json(result_text)
    if not data:
        return {}
    if isinstance(data.get("scores"), list) and data["scores"]:
        first = data["scores"][0]
        return first if isinstance(first, dict) else {}
    if isinstance(data.get("score"), dict):
        return data["score"]
    if "overall" in data:
        return data
    return {}


def _try_load_json(text: str) -> dict:
    try:
        loaded = json.loads(text)
        return loaded if isinstance(loaded, dict) else {}
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return {}
    try:
        loaded = json.loads(match.group())
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return {}


def _clamp_score(value, default: float = DEFAULT_SCORE) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = default
    return max(SCORE_MIN, min(SCORE_MAX, result))


class Scorer:
    """OpenAI-compatible scorer using a Jinja2 prompt template."""

    def __init__(self, llm_config: LLMConfig, prompt_file: Path) -> None:
        if OpenAI is None:
            raise RuntimeError("openai package is not installed")
        self.config = llm_config
        self.prompt_file = Path(prompt_file)
        if not self.prompt_file.exists():
            raise FileNotFoundError(f"Prompt file does not exist: {self.prompt_file}")
        self.client = OpenAI(
            api_key=llm_config.api_key,
            base_url=llm_config.base_url,
        )

    def score_batch(self, articles: list[Article]) -> list[Article]:
        if not articles:
            return []

        worker_count = min(self.config.workers, len(articles))
        logger.info(f"Scoring {len(articles)} articles with {worker_count} workers")
        scored: list[Article | None] = [None] * len(articles)

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_to_index = {
                executor.submit(self._score_single, article, index + 1): index
                for index, article in enumerate(articles)
            }
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    scored[index] = future.result()
                except Exception as exc:
                    fallback = articles[index]
                    fallback.score = DEFAULT_SCORE
                    fallback.score_details = {"error": str(exc)}
                    scored[index] = fallback
                    logger.error(f"Article {index + 1} scoring failed: {exc}")

        return [item for item in scored if item is not None]

    def _score_single(self, article: Article, item_number: int) -> Article:
        prompt = render_prompt(self.prompt_file, article)
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "你是一位严谨的内容评估专家。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=1000,
            )
        except Exception as exc:
            article.score = DEFAULT_SCORE
            article.score_details = {"error": str(exc)}
            logger.warning(f"Article {item_number} LLM call failed: {exc}")
            return article

        result_text = (response.choices[0].message.content or "").strip()
        score_info = parse_score_json(result_text)
        if not score_info:
            article.score = DEFAULT_SCORE
            article.score_details = {"note": "JSON parse failed"}
            logger.warning(f"Article {item_number} score JSON parse failed")
            return article

        article.score = _clamp_score(score_info.get("overall"))
        article.score_details = {
            "heat": _clamp_score(score_info.get("heat")),
            "authority": _clamp_score(score_info.get("authority")),
            "quality": _clamp_score(score_info.get("quality")),
            "practicality": _clamp_score(score_info.get("practicality")),
            "timeliness": _clamp_score(score_info.get("timeliness")),
            "reason": score_info.get("reason", ""),
        }
        logger.info(f"Article {item_number} scored {article.score:.2f}: {article.title[:30]}")
        return article

    def select_top_n(self, articles: list[Article], n: int) -> list[Article]:
        if n <= 0:
            return []
        return sorted(articles, key=lambda item: item.score or 0, reverse=True)[:n]
