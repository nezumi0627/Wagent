"""
Config Loader - 設定ファイルの読み込みと管理
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from loguru import logger


class ConfigLoader:
    """YAMLベースの設定ローダー"""

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Args:
            config_dir: 設定ファイルのディレクトリパス
        """
        if config_dir is None:
            # デフォルトはプロジェクトルートの config ディレクトリ
            config_dir = Path(__file__).parent.parent / "config"
        self.config_dir = Path(config_dir)
        self._settings: Dict[str, Any] = {}
        self._selectors: Dict[str, Any] = {}
        self._loaded = False

    def load(self) -> None:
        """全ての設定ファイルを読み込む"""
        self._load_settings()
        self._load_selectors()
        self._loaded = True
        logger.info("Configuration loaded successfully")

    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        """YAMLファイルを読み込む"""
        filepath = self.config_dir / filename
        if not filepath.exists():
            logger.warning(f"Config file not found: {filepath}")
            return {}

        with open(filepath, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _load_settings(self) -> None:
        """settings.yaml を読み込む"""
        self._settings = self._load_yaml("settings.yaml")
        logger.debug(f"Settings loaded: {list(self._settings.keys())}")

    def _load_selectors(self) -> None:
        """selectors.yaml を読み込む"""
        self._selectors = self._load_yaml("selectors.yaml")
        logger.debug(f"Selectors loaded: {list(self._selectors.keys())}")

    @property
    def settings(self) -> Dict[str, Any]:
        """アプリケーション設定を取得"""
        if not self._loaded:
            self.load()
        return self._settings

    @property
    def selectors(self) -> Dict[str, Any]:
        """セレクタ設定を取得"""
        if not self._loaded:
            self.load()
        return self._selectors

    def get_selector(self, path: str, default: Optional[str] = None) -> Optional[str]:
        """
        ドット記法でセレクタを取得

        Args:
            path: "chatgpt.input.textarea" のようなドット区切りパス
            default: セレクタが見つからない場合のデフォルト値

        Returns:
            セレクタ文字列
        """
        if not self._loaded:
            self.load()

        keys = path.split(".")
        value = self._selectors

        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            logger.debug(f"Selector not found: {path}, using default")
            return default

    def get_setting(self, path: str, default: Any = None) -> Any:
        """
        ドット記法で設定値を取得

        Args:
            path: "browser.headless" のようなドット区切りパス
            default: 設定が見つからない場合のデフォルト値

        Returns:
            設定値
        """
        if not self._loaded:
            self.load()

        keys = path.split(".")
        value = self._settings

        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default


# シングルトンインスタンス
config = ConfigLoader()
