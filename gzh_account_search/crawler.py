"""WeChat public platform fixed-account crawler."""

import json
import random
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from loguru import logger

from gzh_account_search.config import FetchConfig
from gzh_account_search.models import Article, CollectionResult

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext, Page


def parse_publish_time(raw: str) -> datetime:
    """Parse publish time text from the WeChat article picker."""
    text = raw.strip()
    patterns = [
        r"(20\d{2})[-/年.](\d{1,2})[-/月.](\d{1,2})\s+(\d{1,2}):(\d{1,2})",
        r"(20\d{2})[-/年.](\d{1,2})[-/月.](\d{1,2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        parts = [int(part) for part in match.groups()]
        try:
            if len(parts) == 5:
                return datetime(parts[0], parts[1], parts[2], parts[3], parts[4])
            return datetime(parts[0], parts[1], parts[2])
        except ValueError:
            continue

    if "昨天" in text:
        return datetime.now() - timedelta(days=1)
    if "今天" in text:
        return datetime.now()

    logger.debug(f"Could not parse publish time, using now: {raw}")
    return datetime.now()


def split_article_row_text(raw_text: str) -> tuple[str, str]:
    """Extract title and date from a fallback row text blob."""
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    date_text = ""
    title_parts: list[str] = []

    for line in lines:
        cleaned = re.sub(r"\[?查看文章\]?\([^)]+\)", "", line)
        cleaned = cleaned.replace("查看文章", "").strip()
        date_match = re.search(r"20\d{2}[-/年.]\d{1,2}[-/月.]\d{1,2}", cleaned)
        if date_match and not date_text:
            date_text = date_match.group(0)
            cleaned = cleaned.replace(date_text, "").strip()
        if cleaned:
            title_parts.append(cleaned)

    return " ".join(title_parts).strip(), date_text


def within_lookback_days(publish_time: datetime, lookback_days: int) -> bool:
    return datetime.now() - publish_time <= timedelta(days=lookback_days)


def safe_path_name(raw_name: str) -> str:
    safe_name = re.sub(r'[\\/:*?"<>|]+', "_", raw_name).strip()
    return safe_name or "未知公众号"


def save_grouped_raw_data(
    items: list[Article],
    raw_data_dir: Path,
    lookback_days: int,
    max_articles_per_account: int,
) -> None:
    """Persist raw collected articles grouped by date and account."""
    if not items:
        return

    date_label = datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    day_dir = Path(raw_data_dir) / date_label
    day_dir.mkdir(parents=True, exist_ok=True)

    grouped: dict[str, list[Article]] = {}
    for item in items:
        account = item.author or item.source or "未知公众号"
        grouped.setdefault(account, []).append(item)

    summary_payload = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "source": "wechat_mp",
            "lookback_days": lookback_days,
            "max_articles_per_account": max_articles_per_account,
            "total_count": len(items),
            "accounts": list(grouped.keys()),
        },
        "accounts": {},
    }

    for account, account_items in grouped.items():
        account_dir = day_dir / safe_path_name(account)
        account_dir.mkdir(parents=True, exist_ok=True)
        articles = [_serialize_article(item) for item in account_items]
        payload = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "source": "wechat_mp",
                "account": account,
                "lookback_days": lookback_days,
                "max_articles_per_account": max_articles_per_account,
                "total_count": len(articles),
            },
            "articles": articles,
        }

        account_file = account_dir / f"articles_{timestamp}.json"
        with open(account_file, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        logger.info(f"Raw account data saved: {account_file}")
        summary_payload["accounts"][account] = articles

    summary_file = day_dir / f"all_accounts_{timestamp}.json"
    with open(summary_file, "w", encoding="utf-8") as file:
        json.dump(summary_payload, file, ensure_ascii=False, indent=2)
    logger.info(f"Raw summary data saved: {summary_file}")


def _serialize_article(item: Article) -> dict:
    return {
        "title": item.title,
        "account": item.author,
        "source": item.source,
        "publish_time": item.publish_time.isoformat(),
        "content": item.content,
        "url": item.url,
        "tags": item.tags,
    }


class WechatMpCrawler:
    """Collect recent articles from configured WeChat public account names."""

    def __init__(self, fetch_config: FetchConfig, raw_data_dir: Path) -> None:
        self.config = fetch_config
        self.raw_data_dir = Path(raw_data_dir)

    def collect(
        self,
        context: "BrowserContext",
        page: "Page",
        token: str,
    ) -> CollectionResult:
        result = CollectionResult()
        accounts = self.config.accounts
        logger.info(f"Collecting public accounts: {', '.join(accounts)}")
        logger.info(
            f"max_articles_per_account={self.config.max_articles_per_account}, "
            f"lookback_days={self.config.lookback_days}"
        )

        for account_index, account in enumerate(accounts):
            try:
                if account_index > 0:
                    self._pause(page, self.config.account_delay_seconds)
                items = self._collect_account(context, page, token, account)
                result.items.extend(items)
                result.success_count += len(items)
                logger.info(f"{account} done: {len(items)} articles")
            except Exception as exc:
                logger.error(f"Failed to collect account {account}: {exc}")
                result.failed_count += 1
                result.error_messages.append(f"{account}: {exc}")

        if result.items:
            result.items.sort(key=lambda item: item.publish_time, reverse=True)
            save_grouped_raw_data(
                items=result.items,
                raw_data_dir=self.raw_data_dir,
                lookback_days=self.config.lookback_days,
                max_articles_per_account=self.config.max_articles_per_account,
            )

        return result

    def _collect_account(
        self,
        context: "BrowserContext",
        page: "Page",
        token: str,
        account: str,
    ) -> list[Article]:
        self._open_account_article_picker(page, token, account)

        articles: list[Article] = []
        while len(articles) < self.config.max_articles_per_account:
            page.wait_for_selector(
                'xpath=//*[@id="vue_app"]//label[contains(@class, "inner_link_article_item")]',
                timeout=30000,
            )
            article_items = page.locator(
                'xpath=//*[@id="vue_app"]//label[contains(@class, "inner_link_article_item")]'
            )
            item_count = article_items.count()
            logger.info(f"{account} current page article count: {item_count}")
            if item_count == 0:
                break

            saw_recent_article = False
            for index in range(item_count):
                if len(articles) >= self.config.max_articles_per_account:
                    break

                raw_item = self._read_article_item(
                    context, account, article_items.nth(index), index + 1
                )
                self._pause(page, self.config.article_delay_seconds)
                if not raw_item:
                    continue
                if not within_lookback_days(
                    raw_item["publish_time"], self.config.lookback_days
                ):
                    continue

                saw_recent_article = True
                articles.append(self._build_article(raw_item))
                logger.info(f"Collected [{account}] {raw_item['title'][:40]}")

            if len(articles) >= self.config.max_articles_per_account:
                break
            if not saw_recent_article:
                break
            if not self._go_next_page(page):
                break

        return articles

    def _build_article(self, raw_item: dict) -> Article:
        account = raw_item.get("account", "")
        return Article(
            title=raw_item.get("title", ""),
            source=account,
            author=account,
            publish_time=raw_item.get("publish_time", datetime.now()),
            content=raw_item.get("content") or "",
            url=raw_item.get("url", ""),
            tags=[],
        )

    def _open_account_article_picker(
        self,
        page: "Page",
        token: str,
        account: str,
    ) -> None:
        edit_url = (
            "https://mp.weixin.qq.com/cgi-bin/appmsg?"
            "t=media/appmsg_edit_v2&action=edit&isNew=1&type=77&createType=0"
            f"&token={token}&lang=zh_CN"
        )
        page.goto(edit_url, wait_until="domcontentloaded", timeout=60000)
        self._pause(page, self.config.action_delay_seconds)
        page.locator("#js_editor_insertlink").click(timeout=30000)
        self._pause(page, self.config.action_delay_seconds)
        page.locator("text=选择其他账号").click(timeout=30000)
        self._pause(page, self.config.action_delay_seconds)

        search_box = page.locator(
            'xpath=//input[@placeholder="输入文章来源的账号名称或微信号，回车进行搜索"]'
        )
        search_box.click(timeout=30000)
        self._pause(page, self.config.action_delay_seconds)
        search_box.fill(account)
        self._pause(page, self.config.action_delay_seconds)
        search_box.press("Enter")
        self._pause(page, self.config.page_delay_seconds)

        page.wait_for_selector(".inner_link_account_avatar", timeout=30000)
        page.locator(".inner_link_account_avatar").first.click()
        self._pause(page, self.config.page_delay_seconds)

    def _read_article_item(
        self,
        context: "BrowserContext",
        account: str,
        item,
        index: int,
    ) -> Optional[dict]:
        try:
            title = self._read_item_title(item)
            date_text = self._read_item_date(item)
            publish_time = parse_publish_time(date_text)
            url = self._read_item_url(item)
            content = ""
            if self.config.fetch_full_content:
                detail = self._fetch_article_detail(context, url, item, index)
                if detail:
                    url = detail["url"] or url
                    content = detail["content"]

            return {
                "account": account,
                "title": title,
                "url": url,
                "publish_time": publish_time,
                "content": content,
            }
        except Exception as exc:
            logger.warning(f"Failed to parse article row index={index}: {exc}")
            return None

    def _read_item_title(self, item) -> str:
        title = (
            item.locator(".inner_link_article_span")
            .first.text_content(timeout=5000)
            or ""
        ).strip()
        if title:
            return title

        row_text = item.inner_text(timeout=5000)
        title, _ = split_article_row_text(row_text)
        if title:
            return title

        raise ValueError("Article title not found")

    def _read_item_date(self, item) -> str:
        date_text = (
            item.locator(".inner_link_article_date").first.text_content(timeout=5000)
            or ""
        ).strip()
        if date_text:
            return date_text

        row_text = item.inner_text(timeout=5000)
        _, fallback_date = split_article_row_text(row_text)
        if fallback_date:
            return fallback_date

        raise ValueError("Article date not found")

    def _read_item_url(self, item) -> str:
        try:
            item.hover(timeout=5000)
            anchor = item.locator(
                "a.weui-desktop-vm_default, a",
                has_text="查看文章",
            ).first
            return anchor.get_attribute("href", timeout=3000) or ""
        except Exception:
            return ""

    def _fetch_article_detail(
        self,
        context: "BrowserContext",
        url: str,
        item,
        index: int,
    ) -> Optional[dict]:
        if url:
            return self._open_article_url(context, url, index)
        return self._open_article_detail_link(context, item, index)

    def _open_article_url(
        self,
        context: "BrowserContext",
        url: str,
        index: int,
    ) -> Optional[dict]:
        new_page = context.new_page()
        try:
            new_page.goto(url, wait_until="domcontentloaded", timeout=20000)
            self._pause(new_page, self.config.action_delay_seconds)
            content = ""
            try:
                content = new_page.locator("#js_content").inner_text(timeout=10000)
            except Exception:
                logger.info(f"Article {index} detail content not readable")
            return {"url": new_page.url, "content": content}
        except Exception as exc:
            logger.info(f"Failed to open article {index} URL, keeping list data: {exc}")
            return None
        finally:
            new_page.close()

    def _open_article_detail_link(
        self,
        context: "BrowserContext",
        item,
        index: int,
    ) -> Optional[dict]:
        try:
            item.hover(timeout=5000)
            detail_link = item.locator(
                "a.weui-desktop-vm_default, a",
                has_text="查看文章",
            ).first
            if not detail_link.is_visible(timeout=3000):
                return None

            with context.expect_page(timeout=8000) as new_page_info:
                detail_link.click(timeout=5000)
            new_page = new_page_info.value
            try:
                new_page.wait_for_load_state("domcontentloaded", timeout=15000)
                self._pause(new_page, self.config.action_delay_seconds)
                content = ""
                try:
                    content = new_page.locator("#js_content").inner_text(timeout=10000)
                except Exception:
                    logger.info(f"Article {index} detail content not readable")
                return {"url": new_page.url, "content": content}
            finally:
                new_page.close()
        except Exception as exc:
            logger.info(f"Failed to open article {index} detail: {exc}")
            return None

    def _go_next_page(self, page: "Page") -> bool:
        try:
            next_button = page.get_by_text("下一页", exact=True)
            if not next_button.is_visible(timeout=3000):
                return False
            next_button.click(timeout=5000)
            self._pause(page, self.config.page_delay_seconds)
            return True
        except Exception:
            return False

    def _pause(self, page: Optional["Page"], seconds: float) -> None:
        if seconds <= 0:
            return
        duration = seconds * random.uniform(0.75, 1.35)
        if page is not None and not page.is_closed():
            page.wait_for_timeout(int(duration * 1000))
            return
        time.sleep(duration)
