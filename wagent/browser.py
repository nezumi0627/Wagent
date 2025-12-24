"""
Browser Controller - Playwrightによるブラウザ自動操作

ステルス機能と人間らしい挙動のシミュレーションを提供。
"""

from __future__ import annotations

import asyncio
import random
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, AsyncGenerator, Optional

from loguru import logger
from playwright.async_api import (
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

if TYPE_CHECKING:
    from wagent.config import Config, Selectors


# =============================================================================
# ステルスモジュール
# =============================================================================


class StealthModule(ABC):
    """ステルス機能の抽象基底クラス"""

    @abstractmethod
    async def apply(self, page: Page) -> None:
        """ページにステルス機能を適用"""
        ...


class PlaywrightStealthModule(StealthModule):
    """playwright-stealthを使用したステルス機能"""

    def __init__(self) -> None:
        self._stealth_available = False
        self._stealth_func = None

        try:
            from playwright_stealth import stealth_async

            self._stealth_func = stealth_async
            self._stealth_available = True
            logger.debug("playwright-stealth is available")
        except ImportError:
            logger.warning(
                "playwright-stealth not installed. "
                "Install it with: pip install playwright-stealth"
            )

    @property
    def is_available(self) -> bool:
        return self._stealth_available

    async def apply(self, page: Page) -> None:
        if self._stealth_available and self._stealth_func:
            await self._stealth_func(page)
            logger.debug("Stealth mode applied via playwright-stealth")


class CustomStealthModule(StealthModule):
    """カスタムステルススクリプト"""

    STEALTH_SCRIPTS: list[str] = [
        # WebDriver property を隠す
        """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        """,
        # Chrome runtime を偽装
        """
        window.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {}
        };
        """,
        # Plugins を偽装
        """
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
        """,
        # Languages を設定
        """
        Object.defineProperty(navigator, 'languages', {
            get: () => ['ja-JP', 'ja', 'en-US', 'en']
        });
        """,
        # Permissions を偽装
        """
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
        );
        """,
    ]

    async def apply(self, page: Page) -> None:
        for script in self.STEALTH_SCRIPTS:
            await page.add_init_script(script)
        logger.debug("Custom stealth scripts applied")


# =============================================================================
# 人間らしい挙動シミュレーター
# =============================================================================


@dataclass
class HumanBehaviorSimulator:
    """人間らしい挙動をシミュレートするクラス"""

    typing_min_delay: int = 30
    typing_max_delay: int = 120
    word_pause_probability: float = 0.1
    word_pause_min: int = 100
    word_pause_max: int = 300
    action_delay_min: int = 500
    action_delay_max: int = 1500

    async def type_like_human(self, page: Page, selector: str, text: str) -> None:
        """人間らしいタイピング速度でテキストを入力"""
        element = await page.wait_for_selector(selector, timeout=10000)
        if element is None:
            raise RuntimeError(f"Element not found: {selector}")

        await element.click()
        await self.random_delay(100, 300)

        for i, char in enumerate(text):
            # 文字を入力
            delay = random.randint(self.typing_min_delay, self.typing_max_delay)
            await page.keyboard.type(char, delay=delay)

            # 単語区切りでランダムに休憩
            if char == " " and random.random() < self.word_pause_probability:
                pause = random.randint(self.word_pause_min, self.word_pause_max)
                await asyncio.sleep(pause / 1000)

        logger.debug(f"Typed {len(text)} characters with human-like timing")

    async def random_delay(self, min_ms: int, max_ms: int) -> None:
        """ランダムな遅延を追加"""
        delay = random.randint(min_ms, max_ms) / 1000
        await asyncio.sleep(delay)

    async def action_delay(self) -> None:
        """アクション間の標準遅延"""
        await self.random_delay(self.action_delay_min, self.action_delay_max)


# =============================================================================
# ブラウザコントローラー
# =============================================================================


class BrowserController:
    """
    Playwrightベースのブラウザコントローラー

    ChatGPT Web UIの自動操作、ステルス機能、人間らしい挙動を提供。

    Usage:
        async with BrowserController.create() as browser:
            await browser.navigate_to_chatgpt()
            await browser.send_prompt("Hello!")
            response = await browser.wait_for_response()
    """

    def __init__(
        self,
        config: Config,
        selectors: Selectors,
        playwright: Playwright,
        context: BrowserContext,
        page: Page,
        stealth: StealthModule,
        human: HumanBehaviorSimulator,
    ) -> None:
        self._config = config
        self._selectors = selectors
        self._playwright = playwright
        self._context = context
        self._page = page
        self._stealth = stealth
        self._human = human
        self._is_closed = False

    @classmethod
    @asynccontextmanager
    async def create(
        cls,
        config: Optional[Config] = None,
        selectors: Optional[Selectors] = None,
    ) -> AsyncGenerator[BrowserController, None]:
        """
        ブラウザコントローラーを作成するファクトリメソッド

        Args:
            config: 設定オブジェクト（省略時は自動読み込み）
            selectors: セレクタオブジェクト（省略時は自動読み込み）

        Yields:
            BrowserController インスタンス
        """
        from wagent.config import Config, Selectors

        # 設定を読み込み
        if config is None:
            config = Config.load()
        if selectors is None:
            selectors = Selectors.load()

        logger.info("Initializing browser controller...")

        playwright = await async_playwright().start()

        try:
            # ブラウザ設定を構築
            user_data_path = Path(config.browser.user_data_dir).absolute()
            user_data_path.mkdir(parents=True, exist_ok=True)

            # ランチ引数
            browser_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ]

            if config.stealth.hide_webdriver:
                browser_args.append("--disable-automation")

            # ユーザーエージェント
            user_agent = config.get_user_agent()
            logger.debug(f"Using User-Agent: {user_agent[:50]}...")

            # 永続コンテキストでブラウザを起動
            context = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(user_data_path),
                headless=config.browser.headless,
                slow_mo=config.browser.slow_mo,
                viewport={
                    "width": config.browser.viewport.width,
                    "height": config.browser.viewport.height,
                },
                user_agent=user_agent,
                locale=config.stealth.locale,
                timezone_id=config.stealth.timezone,
                args=browser_args,
                ignore_default_args=["--enable-automation"],
            )

            # ページを取得または作成
            page = context.pages[0] if context.pages else await context.new_page()

            # ステルスモジュールを適用
            stealth: StealthModule
            if config.stealth.enabled:
                pw_stealth = PlaywrightStealthModule()
                if pw_stealth.is_available:
                    stealth = pw_stealth
                else:
                    stealth = CustomStealthModule()
                await stealth.apply(page)
            else:
                stealth = CustomStealthModule()  # ダミー

            # 人間挙動シミュレーター
            hb = config.human_behavior
            human = HumanBehaviorSimulator(
                typing_min_delay=hb.typing.min_delay,
                typing_max_delay=hb.typing.max_delay,
                word_pause_probability=hb.typing.word_pause_probability,
                word_pause_min=hb.typing.word_pause_min,
                word_pause_max=hb.typing.word_pause_max,
                action_delay_min=hb.action_delay.min,
                action_delay_max=hb.action_delay.max,
            )

            controller = cls(
                config=config,
                selectors=selectors,
                playwright=playwright,
                context=context,
                page=page,
                stealth=stealth,
                human=human,
            )

            logger.info("Browser controller initialized")
            yield controller

        finally:
            logger.info("Closing browser controller...")
            await context.close()
            await playwright.stop()

    # =========================================================================
    # プロパティ
    # =========================================================================

    @property
    def page(self) -> Page:
        """現在のページ"""
        return self._page

    @property
    def config(self) -> Config:
        """設定オブジェクト"""
        return self._config

    # =========================================================================
    # ナビゲーション
    # =========================================================================

    async def navigate_to_chatgpt(self) -> None:
        """ChatGPTのページに移動"""
        base_url = self._selectors.get("chatgpt.base_url", "https://chatgpt.com")
        logger.info(f"Navigating to {base_url}")

        await self._page.goto(
            base_url,
            wait_until=self._config.browser.wait_until,  # type: ignore
            timeout=self._config.browser.timeout,
        )
        await self._human.action_delay()

    async def is_logged_in(self) -> bool:
        """ログイン状態を確認"""
        try:
            indicator = self._selectors.get("chatgpt.auth.logged_in_indicator")
            if indicator:
                element = await self._page.query_selector(indicator)
                return element is not None
        except Exception as e:
            logger.error(f"Error checking login status: {e}")
        return False

    # =========================================================================
    # メッセージ送受信
    # =========================================================================

    async def send_prompt(self, prompt: str) -> None:
        """
        プロンプトを入力して送信

        Args:
            prompt: 送信するプロンプト
        """
        logger.info(f"Sending prompt ({len(prompt)} chars)...")

        # 入力エリアのセレクタを取得
        textarea = self._selectors.get("chatgpt.input.textarea", "#prompt-textarea")
        textarea_alt = self._selectors.get("chatgpt.input.textarea_alt")

        # 入力エリアを検索
        element = await self._page.query_selector(textarea)
        if element is None and textarea_alt:
            element = await self._page.query_selector(textarea_alt)

        if element is None:
            raise RuntimeError("Could not find input textarea")

        # プロンプトを入力
        await self._human.type_like_human(self._page, textarea, prompt)
        await self._human.random_delay(300, 600)

        # 送信ボタンをクリック
        send_button = self._selectors.get("chatgpt.input.send_button")
        send_button_alt = self._selectors.get("chatgpt.input.send_button_alt")

        button = await self._page.query_selector(send_button)
        if button is None and send_button_alt:
            button = await self._page.query_selector(send_button_alt)

        if button:
            await button.click()
        else:
            # Enterキーで送信
            await self._page.keyboard.press("Enter")

        logger.info("Prompt sent")

    async def wait_for_response(self, timeout_ms: Optional[int] = None) -> str:
        """
        ChatGPTのレスポンスを待機して取得

        Args:
            timeout_ms: タイムアウト（ミリ秒）

        Returns:
            レスポンステキスト
        """
        if timeout_ms is None:
            timeout_ms = int(
                self._selectors.get("chatgpt.timing.response_timeout", "120000")
            )

        poll_interval = int(
            self._selectors.get("chatgpt.timing.response_poll_interval", "500")
        )
        generating_selector = self._selectors.get("chatgpt.status.generating")

        logger.info("Waiting for response...")

        # 生成開始を待機
        await asyncio.sleep(poll_interval / 1000)

        # 生成完了を待機（ポーリング）
        elapsed = 0
        while elapsed < timeout_ms:
            generating = await self._page.query_selector(generating_selector)

            if generating is None:
                await asyncio.sleep(0.5)  # DOM安定待ち
                break

            await asyncio.sleep(poll_interval / 1000)
            elapsed += poll_interval

        if elapsed >= timeout_ms:
            raise TimeoutError("Response timeout exceeded")

        # レスポンスを取得
        response_elements = await self._page.query_selector_all(
            self._selectors.get("chatgpt.output.message_container", "")
        )

        if not response_elements:
            raise RuntimeError("No response found")

        # 最後のレスポンスを取得
        last_response = response_elements[-1]
        content_selector = self._selectors.get(
            "chatgpt.output.message_content", ".markdown"
        )
        content_element = await last_response.query_selector(content_selector)

        if content_element:
            text = await content_element.inner_text()
            logger.info(f"Response received ({len(text)} chars)")
            return text

        raise RuntimeError("Could not extract response text")

    # =========================================================================
    # セッション管理
    # =========================================================================

    async def new_chat(self) -> None:
        """新しいチャットを開始"""
        selector = self._selectors.get("chatgpt.navigation.new_chat")
        alt_selector = self._selectors.get("chatgpt.navigation.new_chat_alt")

        element = await self._page.query_selector(selector)
        if element is None and alt_selector:
            element = await self._page.query_selector(alt_selector)

        if element:
            await element.click()
            await self._human.action_delay()
            logger.info("Started new chat")
        else:
            # URLで直接移動
            base_url = self._selectors.get("chatgpt.base_url", "https://chatgpt.com")
            await self._page.goto(base_url, wait_until="networkidle")

    # =========================================================================
    # ユーティリティ
    # =========================================================================

    async def screenshot(self, path: Optional[str] = None) -> str:
        """
        スクリーンショットを保存

        Args:
            path: 保存先パス（省略時は自動生成）

        Returns:
            保存したファイルのパス
        """
        import time

        if path is None:
            screenshots_dir = Path("screenshots")
            screenshots_dir.mkdir(exist_ok=True)
            path = str(screenshots_dir / f"screenshot_{int(time.time())}.png")

        await self._page.screenshot(path=path)
        logger.info(f"Screenshot saved: {path}")
        return path

    async def get_page_content(self) -> str:
        """ページのHTMLコンテンツを取得"""
        return await self._page.content()

    async def evaluate_script(self, script: str) -> any:
        """JavaScriptを実行"""
        return await self._page.evaluate(script)
