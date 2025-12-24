"""
Browser Controller - Playwrightを使用したブラウザ自動操作
Stealth機能によるボット検知回避を含む
"""

import asyncio
import random
from pathlib import Path
from typing import Optional

from loguru import logger
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

try:
    from playwright_stealth import stealth_async

    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False
    logger.warning("playwright-stealth not installed. Stealth mode disabled.")

from .config import config


class BrowserController:
    """
    Playwrightベースのブラウザコントローラー
    ChatGPT Web UIの自動操作とステルス機能を提供
    """

    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._is_initialized = False

    async def initialize(self) -> None:
        """ブラウザを初期化して起動"""
        if self._is_initialized:
            logger.debug("Browser already initialized")
            return

        logger.info("Initializing browser...")

        self._playwright = await async_playwright().start()

        # ブラウザ設定
        headless = config.get_setting("browser.headless", False)
        slow_mo = config.get_setting("browser.slow_mo", 0)
        user_data_dir = config.get_setting("browser.user_data_dir", "./browser_data")

        # ユーザーデータディレクトリを絶対パスに変換
        user_data_path = Path(user_data_dir).absolute()
        user_data_path.mkdir(parents=True, exist_ok=True)

        # 永続的なコンテキストでブラウザを起動（ログイン状態を維持）
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_path),
            headless=headless,
            slow_mo=slow_mo,
            viewport={
                "width": config.get_setting("browser.viewport.width", 1280),
                "height": config.get_setting("browser.viewport.height", 800),
            },
            # 人間らしいブラウザ設定
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
            ignore_default_args=["--enable-automation"],
        )

        # 新しいページを取得または作成
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = await self._context.new_page()

        # Stealth機能を適用
        if STEALTH_AVAILABLE and config.get_setting("stealth.enabled", True):
            await stealth_async(self._page)
            logger.info("Stealth mode enabled")

        self._is_initialized = True
        logger.info("Browser initialized successfully")

    async def close(self) -> None:
        """ブラウザを終了"""
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()
        self._is_initialized = False
        logger.info("Browser closed")

    @property
    def page(self) -> Page:
        """現在のページを取得"""
        if not self._page:
            raise RuntimeError("Browser not initialized. Call initialize() first.")
        return self._page

    async def navigate_to_chatgpt(self) -> None:
        """ChatGPTのページに移動"""
        base_url = config.get_selector("chatgpt.base_url", "https://chatgpt.com")
        logger.info(f"Navigating to {base_url}")
        await self.page.goto(base_url, wait_until="networkidle")
        await self._random_delay(1000, 2000)

    async def is_logged_in(self) -> bool:
        """ログイン状態を確認"""
        try:
            indicator = config.get_selector("chatgpt.auth.logged_in_indicator")
            if indicator:
                element = await self.page.query_selector(indicator)
                return element is not None
        except Exception as e:
            logger.error(f"Error checking login status: {e}")
        return False

    async def type_human_like(self, selector: str, text: str) -> None:
        """
        人間らしいタイピング速度でテキストを入力

        Args:
            selector: 入力先のセレクタ
            text: 入力するテキスト
        """
        element = await self.page.wait_for_selector(selector, timeout=10000)

        # 要素をクリックしてフォーカス
        await element.click()
        await self._random_delay(100, 300)

        # 一文字ずつ入力（遅延付き）
        min_delay = config.get_selector("chatgpt.timing.typing_delay_min", 30)
        max_delay = config.get_selector("chatgpt.timing.typing_delay_max", 100)

        for char in text:
            await element.type(char, delay=random.randint(min_delay, max_delay))

        logger.debug(f"Typed {len(text)} characters")

    async def send_prompt(self, prompt: str) -> None:
        """
        プロンプトを入力して送信

        Args:
            prompt: 送信するプロンプト
        """
        logger.info(f"Sending prompt ({len(prompt)} chars)...")

        # 入力エリアのセレクタ
        textarea = config.get_selector("chatgpt.input.textarea", "#prompt-textarea")
        textarea_alt = config.get_selector("chatgpt.input.textarea_alt")

        # 入力エリアを取得
        element = await self.page.query_selector(textarea)
        if not element and textarea_alt:
            element = await self.page.query_selector(textarea_alt)

        if not element:
            raise RuntimeError("Could not find input textarea")

        # プロンプトを入力
        await self.type_human_like(textarea, prompt)
        await self._random_delay(300, 600)

        # 送信ボタンをクリック
        send_button = config.get_selector("chatgpt.input.send_button")
        send_button_alt = config.get_selector("chatgpt.input.send_button_alt")

        button = await self.page.query_selector(send_button)
        if not button and send_button_alt:
            button = await self.page.query_selector(send_button_alt)

        if button:
            await button.click()
        else:
            # ボタンが見つからない場合はEnterキーで送信
            await self.page.keyboard.press("Enter")

        logger.info("Prompt sent")

    async def wait_for_response(self, timeout: Optional[int] = None) -> str:
        """
        ChatGPTのレスポンスを待機して取得

        Args:
            timeout: タイムアウト（ミリ秒）

        Returns:
            レスポンステキスト
        """
        if timeout is None:
            timeout = config.get_selector("chatgpt.timing.response_timeout", 120000)

        poll_interval = config.get_selector(
            "chatgpt.timing.response_poll_interval", 500
        )
        generating_selector = config.get_selector("chatgpt.status.generating")
        config.get_selector("chatgpt.output.latest_response")

        logger.info("Waiting for response...")

        # 生成開始を待機
        await asyncio.sleep(poll_interval / 1000)

        # 生成完了を待機
        elapsed = 0
        while elapsed < timeout:
            # 生成中かどうかをチェック
            generating = await self.page.query_selector(generating_selector)

            if not generating:
                # 生成完了
                await asyncio.sleep(0.5)  # 少し待ってDOMが安定するのを待つ
                break

            await asyncio.sleep(poll_interval / 1000)
            elapsed += poll_interval

        if elapsed >= timeout:
            raise TimeoutError("Response timeout exceeded")

        # レスポンスを取得
        response_elements = await self.page.query_selector_all(
            config.get_selector("chatgpt.output.message_container")
        )

        if not response_elements:
            raise RuntimeError("No response found")

        # 最後のレスポンスを取得
        last_response = response_elements[-1]
        content_element = await last_response.query_selector(
            config.get_selector("chatgpt.output.message_content", ".markdown")
        )

        if content_element:
            text = await content_element.inner_text()
            logger.info(f"Response received ({len(text)} chars)")
            return text

        raise RuntimeError("Could not extract response text")

    async def new_chat(self) -> None:
        """新しいチャットを開始"""
        selector = config.get_selector("chatgpt.navigation.new_chat")
        alt_selector = config.get_selector("chatgpt.navigation.new_chat_alt")

        element = await self.page.query_selector(selector)
        if not element and alt_selector:
            element = await self.page.query_selector(alt_selector)

        if element:
            await element.click()
            await self._random_delay(500, 1000)
            logger.info("Started new chat")
        else:
            # URLで直接移動
            await self.page.goto(
                config.get_selector("chatgpt.base_url", "https://chatgpt.com"),
                wait_until="networkidle",
            )

    async def screenshot(self, path: str = "screenshot.png") -> str:
        """
        スクリーンショットを保存

        Args:
            path: 保存先パス

        Returns:
            保存したファイルのパス
        """
        await self.page.screenshot(path=path)
        logger.info(f"Screenshot saved: {path}")
        return path

    async def _random_delay(self, min_ms: int, max_ms: int) -> None:
        """ランダムな遅延を追加"""
        delay = random.randint(min_ms, max_ms) / 1000
        await asyncio.sleep(delay)


# シングルトンインスタンス
browser = BrowserController()
