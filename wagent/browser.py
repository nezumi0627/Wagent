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
    """playwright-stealth v2を使用したステルス機能"""

    def __init__(self) -> None:
        self._stealth_available = False
        self._stealth_class = None

        try:
            from playwright_stealth.stealth import Stealth

            self._stealth_class = Stealth
            self._stealth_available = True
            logger.debug("playwright-stealth v2 is available")
        except ImportError:
            logger.warning(
                "playwright-stealth not installed. "
                "Install it with: pip install playwright-stealth"
            )

    @property
    def is_available(self) -> bool:
        return self._stealth_available

    async def apply(self, page: Page) -> None:
        if self._stealth_available and self._stealth_class:
            stealth = self._stealth_class()
            await stealth.apply_stealth_async(page)
            logger.debug("Stealth mode applied via playwright-stealth v2")


class CustomStealthModule(StealthModule):
    """強化カスタムステルススクリプト"""

    STEALTH_SCRIPTS: list[str] = [
        # WebDriver全般を隠す
        """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        """,
        # documentElement の webdriver を隠す
        """
        Object.defineProperty(document, 'documentElement', {
            get: () => undefined
        });
        """,
        # Chrome runtime を完全に偽装
        """
        window.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {},
            webstore: {},
            platform: 'Win32'
        };
        """,
        # Plugins を実際に近い形で偽装
        """
        Object.defineProperty(navigator, 'plugins', {
            get: () => [
                { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                { name: 'Native Client', filename: 'internal-nacl-plugin' },
                { name: 'Widevine Content Decryption Module', filename: 'widevinecdmadapter.plugin' },
                { name: 'Chromium PDF Plugin', filename: 'internal-pdf-viewer' }
            ]
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
        # HardwareConcurrency を設定
        """
        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: () => 8
        });
        """,
        # DeviceMemory を設定
        """
        Object.defineProperty(navigator, 'deviceMemory', {
            get: () => 8
        });
        """,
        # Platform を設定
        """
        Object.defineProperty(navigator, 'platform', {
            get: () => 'Win32'
        });
        """,
        # Vendor を設定
        """
        Object.defineProperty(navigator, 'vendor', {
            get: () => 'Google Inc.'
        });
        """,
        # User Agent Data を設定
        """
        if (navigator.userAgentData) {
            Object.defineProperty(navigator, 'userAgentData', {
                get: () => ({
                    brands: [
                        { brand: 'Chromium', version: '120' },
                        { brand: 'Google Chrome', version: '120' }
                    ],
                    mobile: false,
                    platform: 'Windows'
                })
            });
        }
        """,
        # iframe contentWindow アクセスを許可
        """
        Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
            get: function() {
                return this.contentWindow;
            }
        });
        """,
        # WebGL の debug 情報を隠す
        """
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) return 'Google Inc. (NVIDIA)';
            if (parameter === 37446) return 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3080 Direct3D11 vs_5_0 ps_5_0, D3D11)';
            return getParameter.apply(this, [parameter]);
        };
        """,
        # Permission status を上書き
        """
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
            Promise.resolve({ state: 'default' }) :
            originalQuery(parameters)
        );
        """,
        # Notification permission を設定
        """
        Object.defineProperty(Notification, 'permission', {
            get: () => 'default'
        });
        """,
        # toString を上書き（一部検出回避）
        """
        const originalToString = Function.prototype.toString;
        Function.prototype.toString = function() {
            if (this === window.navigator.permissions.query) {
                return 'function query() { [native code] }';
            }
            return originalToString.call(this);
        };
        """,
    ]

    async def apply(self, page: Page) -> None:
        for script in self.STEALTH_SCRIPTS:
            await page.add_init_script(script)
        logger.debug("Enhanced custom stealth scripts applied")


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
        context = None

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
            if context is not None:
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
        """ログイン状態を確認（複数指標で判定）"""
        current_url = self._page.url

        # URLベース判定: ログイン後は /c/ や /d/ で始まる
        if "/c/" in current_url or "/d/" in current_url:
            return True

        # チャット入力エリアの存在確認
        chat_input_selectors = [
            "#prompt-textarea",
            "[data-id='root'] textarea",
            "textarea[placeholder*='Message']",
            "textarea[placeholder*='Send a message']",
        ]
        for selector in chat_input_selectors:
            try:
                element = await self._page.query_selector(selector)
                if element:
                    return True
            except Exception:
                continue

        # ログインページの要素が存在しないか確認
        login_indicators = [
            "[data-testid='login-button']",
            "button:has-text('Log in')",
            "a[href*='/login']",
            "a[href*='/auth']",
        ]
        for selector in login_indicators:
            try:
                element = await self._page.query_selector(selector)
                if element:
                    return False
            except Exception:
                continue

        # プロファイルボタンの存在確認
        profile_selectors = [
            "[data-testid='profile-button']",
            "[data-testid='account-menu-button']",
            "nav [class*='user']",
            "aside [class*='profile']",
            "[class*='sidebar'] button[aria-label*='profile']",
            "[class*='sidebar'] button[aria-label*='Account']",
        ]
        for selector in profile_selectors:
            try:
                element = await self._page.query_selector(selector)
                if element:
                    return True
            except Exception:
                continue

        # モデルセレクターの存在確認
        try:
            model_selector = await self._page.query_selector(
                "[data-testid='model-switcher'], [class*='model-selector']"
            )
            if model_selector:
                return True
        except Exception:
            pass

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
    # ファイルアップロード
    # =========================================================================

    async def upload_files(self, file_paths: list[str]) -> bool:
        """
        ファイルをアップロード

        Args:
            file_paths: アップロードするファイルパスのリスト

        Returns:
            成功した場合True
        """
        if not file_paths:
            return True

        if not self.is_logged_in():
            raise RuntimeError("Not logged in. Please log in to ChatGPT first.")

        logger.info(f"Uploading {len(file_paths)} files...")

        # ファイルの存在確認
        import os
        for path in file_paths:
            if not os.path.exists(path):
                raise FileNotFoundError(f"File not found: {path}")

        # 画像ファイルと一般ファイルを分類
        image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".bmp", ".heic", ".heif"}
        image_files = []
        other_files = []

        for path in file_paths:
            ext = os.path.splitext(path)[1].lower()
            if ext in image_extensions:
                image_files.append(path)
            else:
                other_files.append(path)

        # 画像をアップロード
        if image_files:
            photo_input = self._selectors.get("chatgpt.upload.photo_input")
            if photo_input:
                await self._page.set_input_files(photo_input, image_files)
                logger.info(f"Uploaded {len(image_files)} image(s)")
                await self._human.action_delay()

        # 一般ファイルをアップロード
        if other_files:
            file_input = self._selectors.get("chatgpt.upload.file_input")
            if file_input:
                await self._page.set_input_files(file_input, other_files)
                logger.info(f"Uploaded {len(other_files)} file(s)")
                await self._human.action_delay()

        return True

    async def toggle_web_search(self, enabled: bool = True) -> bool:
        """
        ウェブ検索をオン/オフ

        Args:
            enabled: オンにする場合True

        Returns:
            成功した場合True
        """
        try:
            web_search_button = self._selectors.get("chatgpt.upload.web_search_button")
            if not web_search_button:
                return False

            button = await self._page.query_selector(web_search_button)
            if not button:
                return False

            # 現在の状態を確認
            aria_pressed = await button.get_attribute("aria-pressed")
            is_active = aria_pressed == "true"

            if is_active != enabled:
                await button.click()
                await self._human.action_delay()
                logger.info(f"Web search {'enabled' if enabled else 'disabled'}")

            return True

        except Exception as e:
            logger.error(f"Toggle web search failed: {e}")
            return False

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

    async def get_username(self) -> Optional[str]:
        """
        ログインユーザー名を取得

        Returns:
            ユーザー名（メールアドレス等）、取得不可時はNone
        """
        username_selectors = self._selectors.get("chatgpt.auth.username", "").split(",")
        
        for selector in username_selectors:
            selector = selector.strip()
            if not selector:
                continue
            try:
                element = await self._page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                    if text and text.strip():
                        return text.strip()
            except Exception:
                continue

        # JavaScriptで直接取得を試みる
        try:
            username = await self._page.evaluate("""
                () => {
                    const selectors = [
                        '[data-testid="profile-button"]',
                        'nav [class*="user"]',
                        '[class*="sidebar"] [class*="user"]',
                        'aside [class*="profile"]'
                    ];
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el && el.textContent.trim()) {
                            return el.textContent.trim();
                        }
                    }
                    return null;
                }
            """)
            if username:
                return username
        except Exception:
            pass

        return None
