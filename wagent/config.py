"""
Config - 設定管理モジュール

型安全な設定クラスとYAMLローダーを提供。
Pydanticを使用したバリデーション付き。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Optional

import yaml
from loguru import logger

# =============================================================================
# 設定データクラス
# =============================================================================


@dataclass(frozen=True)
class ViewportConfig:
    """ビューポート設定"""

    width: int = 1280
    height: int = 800


@dataclass(frozen=True)
class CorsConfig:
    """CORS設定"""

    enabled: bool = True
    origins: tuple[str, ...] = ("*",)


@dataclass(frozen=True)
class ServerConfig:
    """サーバー設定"""

    host: str = "127.0.0.1"
    port: int = 8765
    debug: bool = True
    cors: CorsConfig = field(default_factory=CorsConfig)


@dataclass(frozen=True)
class BrowserConfig:
    """ブラウザ設定"""

    headless: bool = False
    user_data_dir: str = "./browser_data"
    viewport: ViewportConfig = field(default_factory=ViewportConfig)
    slow_mo: int = 0
    timeout: int = 30000
    wait_until: str = "networkidle"


@dataclass(frozen=True)
class UserAgentConfig:
    """ユーザーエージェント設定"""

    custom: Optional[str] = None
    random: bool = False
    preset: str = "chrome_windows"


@dataclass(frozen=True)
class FingerprintConfig:
    """フィンガープリント偽装設定"""

    enabled: bool = True
    webgl_vendor: str = "Google Inc. (NVIDIA)"
    webgl_renderer: str = "ANGLE (NVIDIA, NVIDIA GeForce RTX 3080)"


@dataclass(frozen=True)
class PluginsConfig:
    """プラグイン偽装設定"""

    enabled: bool = True
    count: int = 5


@dataclass(frozen=True)
class StealthConfig:
    """ステルス設定"""

    enabled: bool = True
    hide_webdriver: bool = True
    user_agent: UserAgentConfig = field(default_factory=UserAgentConfig)
    locale: str = "ja-JP"
    timezone: str = "Asia/Tokyo"
    fingerprint: FingerprintConfig = field(default_factory=FingerprintConfig)
    plugins: PluginsConfig = field(default_factory=PluginsConfig)


@dataclass(frozen=True)
class TypingConfig:
    """タイピング設定"""

    min_delay: int = 30
    max_delay: int = 120
    word_pause_probability: float = 0.1
    word_pause_min: int = 100
    word_pause_max: int = 300


@dataclass(frozen=True)
class MouseConfig:
    """マウス設定"""

    natural_movement: bool = True
    speed: int = 10


@dataclass(frozen=True)
class ActionDelayConfig:
    """アクション遅延設定"""

    min: int = 500
    max: int = 1500


@dataclass(frozen=True)
class RandomPauseConfig:
    """ランダム休憩設定"""

    enabled: bool = False
    interval_min: int = 60000
    interval_max: int = 300000
    duration_min: int = 1000
    duration_max: int = 3000


@dataclass(frozen=True)
class HumanBehaviorConfig:
    """人間らしい挙動設定"""

    typing: TypingConfig = field(default_factory=TypingConfig)
    mouse: MouseConfig = field(default_factory=MouseConfig)
    action_delay: ActionDelayConfig = field(default_factory=ActionDelayConfig)
    random_pause: RandomPauseConfig = field(default_factory=RandomPauseConfig)


@dataclass(frozen=True)
class RateLimitConfig:
    """レートリミット設定"""

    enabled: bool = True
    requests_per_minute: int = 10
    min_interval: int = 3
    burst_limit: int = 3


@dataclass(frozen=True)
class SessionConfig:
    """セッション設定"""

    keepalive_interval: int = 300
    timeout: int = 3600
    auto_recovery: bool = True


@dataclass(frozen=True)
class LoggingConfig:
    """ログ設定"""

    level: str = "DEBUG"
    file: str = "./logs/wagent.log"
    rotation: str = "10 MB"
    retention: int = 5
    format: str = (
        "<green>{time:HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan> - <level>{message}</level>"
    )


# =============================================================================
# ユーザーエージェントプリセット
# =============================================================================


class UserAgentPresets:
    """ユーザーエージェントのプリセット集"""

    CHROME_WINDOWS: ClassVar[str] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    CHROME_MAC: ClassVar[str] = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    EDGE_WINDOWS: ClassVar[str] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
    )
    FIREFOX_WINDOWS: ClassVar[str] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
        "Gecko/20100101 Firefox/121.0"
    )
    SAFARI_MAC: ClassVar[str] = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.2 Safari/605.1.15"
    )

    _PRESETS: ClassVar[dict[str, str]] = {
        "chrome_windows": CHROME_WINDOWS,
        "chrome_mac": CHROME_MAC,
        "edge_windows": EDGE_WINDOWS,
        "firefox_windows": FIREFOX_WINDOWS,
        "safari_mac": SAFARI_MAC,
    }

    @classmethod
    def get(cls, name: str) -> str:
        """プリセット名からUAを取得"""
        return cls._PRESETS.get(name, cls.CHROME_WINDOWS)

    @classmethod
    def random(cls) -> str:
        """ランダムなUAを取得"""
        import random

        return random.choice(list(cls._PRESETS.values()))


# =============================================================================
# メイン設定クラス
# =============================================================================


class Config:
    """
    設定管理クラス

    YAMLファイルから設定を読み込み、型安全なデータクラスとして提供。
    シングルトンパターンを採用。

    Usage:
        config = Config.load()
        print(config.browser.headless)
        print(config.stealth.user_agent.preset)
    """

    _instance: ClassVar[Optional[Config]] = None
    _config_dir: ClassVar[Path] = Path(__file__).parent.parent / "config"

    def __init__(
        self,
        server: ServerConfig,
        browser: BrowserConfig,
        stealth: StealthConfig,
        human_behavior: HumanBehaviorConfig,
        rate_limit: RateLimitConfig,
        session: SessionConfig,
        logging: LoggingConfig,
    ) -> None:
        self.server = server
        self.browser = browser
        self.stealth = stealth
        self.human_behavior = human_behavior
        self.rate_limit = rate_limit
        self.session = session
        self.logging = logging

    @classmethod
    def load(cls, config_dir: Optional[Path] = None) -> Config:
        """
        設定ファイルを読み込んでConfigインスタンスを返す

        Args:
            config_dir: 設定ディレクトリのパス（省略時はデフォルト）

        Returns:
            Config インスタンス（シングルトン）
        """
        if cls._instance is not None:
            return cls._instance

        if config_dir is not None:
            cls._config_dir = Path(config_dir)

        settings = cls._load_yaml("settings.yaml")
        cls._instance = cls._parse_settings(settings)

        logger.info(f"Configuration loaded from {cls._config_dir}")
        return cls._instance

    @classmethod
    def reload(cls) -> Config:
        """設定をリロード"""
        cls._instance = None
        return cls.load()

    @classmethod
    def _load_yaml(cls, filename: str) -> dict[str, Any]:
        """YAMLファイルを読み込む"""
        filepath = cls._config_dir / filename
        if not filepath.exists():
            logger.warning(f"Config file not found: {filepath}")
            return {}

        with open(filepath, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    @classmethod
    def _parse_settings(cls, data: dict[str, Any]) -> Config:
        """設定データをパースしてConfigインスタンスを生成"""
        return Config(
            server=cls._parse_server(data.get("server", {})),
            browser=cls._parse_browser(data.get("browser", {})),
            stealth=cls._parse_stealth(data.get("stealth", {})),
            human_behavior=cls._parse_human_behavior(data.get("human_behavior", {})),
            rate_limit=cls._parse_rate_limit(data.get("rate_limit", {})),
            session=cls._parse_session(data.get("session", {})),
            logging=cls._parse_logging(data.get("logging", {})),
        )

    @staticmethod
    def _parse_server(data: dict[str, Any]) -> ServerConfig:
        cors_data = data.get("cors", {})
        return ServerConfig(
            host=data.get("host", "127.0.0.1"),
            port=data.get("port", 8765),
            debug=data.get("debug", True),
            cors=CorsConfig(
                enabled=cors_data.get("enabled", True),
                origins=tuple(cors_data.get("origins", ["*"])),
            ),
        )

    @staticmethod
    def _parse_browser(data: dict[str, Any]) -> BrowserConfig:
        viewport_data = data.get("viewport", {})
        return BrowserConfig(
            headless=data.get("headless", False),
            user_data_dir=data.get("user_data_dir", "./browser_data"),
            viewport=ViewportConfig(
                width=viewport_data.get("width", 1280),
                height=viewport_data.get("height", 800),
            ),
            slow_mo=data.get("slow_mo", 0),
            timeout=data.get("timeout", 30000),
            wait_until=data.get("wait_until", "networkidle"),
        )

    @staticmethod
    def _parse_stealth(data: dict[str, Any]) -> StealthConfig:
        ua_data = data.get("user_agent", {})
        fp_data = data.get("fingerprint", {})
        plugins_data = data.get("plugins", {})

        return StealthConfig(
            enabled=data.get("enabled", True),
            hide_webdriver=data.get("hide_webdriver", True),
            user_agent=UserAgentConfig(
                custom=ua_data.get("custom"),
                random=ua_data.get("random", False),
                preset=ua_data.get("preset", "chrome_windows"),
            ),
            locale=data.get("locale", "ja-JP"),
            timezone=data.get("timezone", "Asia/Tokyo"),
            fingerprint=FingerprintConfig(
                enabled=fp_data.get("enabled", True),
                webgl_vendor=fp_data.get("webgl_vendor", "Google Inc. (NVIDIA)"),
                webgl_renderer=fp_data.get(
                    "webgl_renderer", "ANGLE (NVIDIA, NVIDIA GeForce RTX 3080)"
                ),
            ),
            plugins=PluginsConfig(
                enabled=plugins_data.get("enabled", True),
                count=plugins_data.get("count", 5),
            ),
        )

    @staticmethod
    def _parse_human_behavior(data: dict[str, Any]) -> HumanBehaviorConfig:
        typing_data = data.get("typing", {})
        mouse_data = data.get("mouse", {})
        action_data = data.get("action_delay", {})
        pause_data = data.get("random_pause", {})

        return HumanBehaviorConfig(
            typing=TypingConfig(
                min_delay=typing_data.get("min_delay", 30),
                max_delay=typing_data.get("max_delay", 120),
                word_pause_probability=typing_data.get("word_pause_probability", 0.1),
                word_pause_min=typing_data.get("word_pause_min", 100),
                word_pause_max=typing_data.get("word_pause_max", 300),
            ),
            mouse=MouseConfig(
                natural_movement=mouse_data.get("natural_movement", True),
                speed=mouse_data.get("speed", 10),
            ),
            action_delay=ActionDelayConfig(
                min=action_data.get("min", 500),
                max=action_data.get("max", 1500),
            ),
            random_pause=RandomPauseConfig(
                enabled=pause_data.get("enabled", False),
                interval_min=pause_data.get("interval_min", 60000),
                interval_max=pause_data.get("interval_max", 300000),
                duration_min=pause_data.get("duration_min", 1000),
                duration_max=pause_data.get("duration_max", 3000),
            ),
        )

    @staticmethod
    def _parse_rate_limit(data: dict[str, Any]) -> RateLimitConfig:
        return RateLimitConfig(
            enabled=data.get("enabled", True),
            requests_per_minute=data.get("requests_per_minute", 10),
            min_interval=data.get("min_interval", 3),
            burst_limit=data.get("burst_limit", 3),
        )

    @staticmethod
    def _parse_session(data: dict[str, Any]) -> SessionConfig:
        return SessionConfig(
            keepalive_interval=data.get("keepalive_interval", 300),
            timeout=data.get("timeout", 3600),
            auto_recovery=data.get("auto_recovery", True),
        )

    @staticmethod
    def _parse_logging(data: dict[str, Any]) -> LoggingConfig:
        return LoggingConfig(
            level=data.get("level", "DEBUG"),
            file=data.get("file", "./logs/wagent.log"),
            rotation=data.get("rotation", "10 MB"),
            retention=data.get("retention", 5),
            format=data.get(
                "format",
                "<green>{time:HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan> - <level>{message}</level>",
            ),
        )

    def get_user_agent(self) -> str:
        """設定に基づいてユーザーエージェントを取得"""
        ua_config = self.stealth.user_agent

        if ua_config.custom:
            return ua_config.custom
        if ua_config.random:
            return UserAgentPresets.random()
        return UserAgentPresets.get(ua_config.preset)


# =============================================================================
# セレクタ設定（別クラス）
# =============================================================================


class Selectors:
    """
    CSSセレクタ管理クラス

    Web UIのセレクタを外部ファイルで管理し、UI変更に対応しやすくする。
    """

    _instance: ClassVar[Optional[Selectors]] = None
    _data: dict[str, Any]

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    @classmethod
    def load(cls, config_dir: Optional[Path] = None) -> Selectors:
        """セレクタファイルを読み込む"""
        if cls._instance is not None:
            return cls._instance

        config_dir = config_dir or Path(__file__).parent.parent / "config"
        filepath = config_dir / "selectors.yaml"

        if not filepath.exists():
            logger.warning(f"Selectors file not found: {filepath}")
            cls._instance = cls({})
            return cls._instance

        with open(filepath, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        cls._instance = cls(data)
        logger.debug("Selectors loaded")
        return cls._instance

    def get(self, path: str, default: Optional[str] = None) -> Optional[str]:
        """
        ドット記法でセレクタを取得

        Args:
            path: "chatgpt.input.textarea" のようなパス
            default: デフォルト値

        Returns:
            セレクタ文字列
        """
        keys = path.split(".")
        value: Any = self._data

        try:
            for key in keys:
                value = value[key]
            return str(value) if value is not None else default
        except (KeyError, TypeError):
            return default

    def __getitem__(self, path: str) -> str:
        """角括弧記法でのアクセス"""
        result = self.get(path)
        if result is None:
            raise KeyError(f"Selector not found: {path}")
        return result
