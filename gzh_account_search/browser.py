"""Browser session helpers for WeChat public platform."""

from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

from loguru import logger

MP_HOMEPAGE = "https://mp.weixin.qq.com/"
HEADLESS_PROBE_TIMEOUT_MS = 8000


def extract_token(url: str) -> Optional[str]:
    parsed = urlparse(url)
    token_values = parse_qs(parsed.query).get("token")
    return token_values[0] if token_values else None


def resolve_initial_headless(browser_mode: str, storage_state_path: Path) -> bool:
    """Resolve first launch headless state for auto/visible/headless modes."""
    if browser_mode == "visible":
        return False
    if browser_mode == "headless":
        return True
    return storage_state_path.exists()


class BrowserSession:
    """Logged-in WeChat public platform browser session."""

    def __init__(
        self,
        storage_state_path: Path,
        browser_mode: str,
        login_timeout_seconds: int,
        slow_mo_ms: int = 0,
    ) -> None:
        self.storage_state_path = Path(storage_state_path)
        self.browser_mode = browser_mode
        self.login_timeout_seconds = login_timeout_seconds
        self.slow_mo_ms = slow_mo_ms
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._timeout_error = None

    def __enter__(self):
        self.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
        self._start_playwright()

        headless = resolve_initial_headless(self.browser_mode, self.storage_state_path)
        token = self._launch_and_login(headless=headless)

        if token is None and headless and self.browser_mode == "auto":
            logger.warning("Headless login state is invalid; reopening visibly")
            self._cleanup()
            self._start_playwright()
            token = self._launch_and_login(headless=False)

        if token is None:
            self._cleanup()
            raise RuntimeError("Failed to log in to mp.weixin.qq.com or extract token")

        return self._context, self._page, token

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if self._context is not None:
                self._context.storage_state(path=str(self.storage_state_path))
        except Exception as exc:
            logger.warning(f"Failed to save browser storage state: {exc}")
        self._cleanup()

    def _start_playwright(self) -> None:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright

        self._timeout_error = PlaywrightTimeoutError
        self._playwright = sync_playwright().start()

    def _launch_and_login(self, headless: bool) -> Optional[str]:
        self._browser = self._playwright.chromium.launch(
            headless=headless,
            slow_mo=self.slow_mo_ms,
        )
        context_options = {"no_viewport": True}
        if self.storage_state_path.exists():
            context_options["storage_state"] = str(self.storage_state_path)

        self._context = self._browser.new_context(**context_options)
        self._page = self._context.new_page()

        logger.info(f"Opening WeChat public platform (headless={headless})")
        self._page.goto(MP_HOMEPAGE, wait_until="domcontentloaded", timeout=60000)

        token = extract_token(self._page.url)
        if token:
            logger.info("Reused existing login state")
            return token

        if headless:
            try:
                self._page.wait_for_function(
                    "() => location.href.includes('token=')",
                    timeout=HEADLESS_PROBE_TIMEOUT_MS,
                )
            except self._timeout_error:
                return None
            return extract_token(self._page.url)

        logger.info(f"Please scan QR code within {self.login_timeout_seconds} seconds")
        try:
            self._page.wait_for_function(
                "() => location.href.includes('token=')",
                timeout=self.login_timeout_seconds * 1000,
            )
        except self._timeout_error:
            logger.error("Timed out while waiting for QR login")
            return None

        token = extract_token(self._page.url)
        if token:
            self._context.storage_state(path=str(self.storage_state_path))
            logger.info(f"Saved browser storage state: {self.storage_state_path}")
        return token

    def _cleanup(self) -> None:
        try:
            if self._browser is not None:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright is not None:
                self._playwright.stop()
        except Exception:
            pass
        self._browser = None
        self._context = None
        self._page = None
        self._playwright = None
