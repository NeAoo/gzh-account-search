"""End-to-end collection, optional scoring, and report rendering pipeline."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

from gzh_account_search.browser import BrowserSession
from gzh_account_search.config import Config
from gzh_account_search.crawler import WechatMpCrawler
from gzh_account_search.models import Article
from gzh_account_search.renderer import Renderer
from gzh_account_search.scorer import Scorer


class Pipeline:
    """Config-driven application pipeline."""

    def __init__(self, config: Config) -> None:
        self.config = config

    def run(self) -> Optional[str]:
        logger.info("=" * 60)
        logger.info("gzh-account-search started")
        logger.info(f"Accounts: {', '.join(self.config.fetch.accounts)}")
        logger.info(f"Scoring enabled: {self.config.scoring.enabled}")
        logger.info("=" * 60)

        articles = self._collect()
        if not articles:
            logger.warning("No articles collected")
            return None

        if self.config.scoring.enabled:
            articles = self._score(articles)

        return self._render_and_save(articles)

    def _collect(self) -> list[Article]:
        with BrowserSession(
            storage_state_path=Path(self.config.paths.browser_data),
            browser_mode=self.config.fetch.browser_mode,
            login_timeout_seconds=self.config.fetch.login_timeout_seconds,
            slow_mo_ms=self.config.fetch.slow_mo_ms,
        ) as (context, page, token):
            crawler = WechatMpCrawler(
                fetch_config=self.config.fetch,
                raw_data_dir=Path(self.config.paths.raw_data_dir),
            )
            result = crawler.collect(context, page, token)

        logger.info(
            f"Collection finished: success={result.success_count}, "
            f"failed={result.failed_count}"
        )
        if result.error_messages:
            for message in result.error_messages:
                logger.warning(message)
        return result.items

    def _score(self, articles: list[Article]) -> list[Article]:
        scorer = Scorer(
            llm_config=self.config.llm,
            prompt_file=Path(self.config.scoring.prompt_file),
        )
        scored = scorer.score_batch(articles)
        selected = scorer.select_top_n(scored, n=self.config.output.top_n)
        logger.info(f"Selected {len(selected)} scored articles")
        return selected

    def _render_and_save(self, articles: list[Article]) -> str:
        renderer = Renderer(
            template_file=Path(self.config.output.template_file),
            no_score_template_file=Path(self.config.output.no_score_template_file),
        )
        if self.config.scoring.enabled:
            content = renderer.render_with_scores(articles)
        else:
            content = renderer.render_no_score(articles)

        now = datetime.now()
        filename = self.config.output.filename_pattern.format(
            date=now.strftime("%Y%m%d"),
            datetime=now.strftime("%Y%m%d_%H%M%S"),
        )
        target = Path(self.config.output.dir) / filename
        return renderer.save(content, target)
