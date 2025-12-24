"""
Client - Wagent APIクライアント

外部プログラムからWagent APIを呼び出すためのクライアントライブラリ。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

import requests
from loguru import logger

# =============================================================================
# 例外クラス
# =============================================================================


class WagentClientError(Exception):
    """Wagentクライアントの基底例外"""

    pass


class ConnectionError(WagentClientError):
    """接続エラー"""

    pass


class TimeoutError(WagentClientError):
    """タイムアウトエラー"""

    pass


class RateLimitError(WagentClientError):
    """レートリミットエラー"""

    pass


# =============================================================================
# レスポンスデータクラス
# =============================================================================


@dataclass
class ChatResult:
    """チャットの結果"""

    success: bool
    message: Optional[str]
    error: Optional[str]
    elapsed_seconds: float
    prompt_length: Optional[int] = None
    response_length: Optional[int] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChatResult:
        """辞書からChatResultを生成"""
        return cls(
            success=data.get("success", False),
            message=data.get("message"),
            error=data.get("error"),
            elapsed_seconds=data.get("elapsed_seconds", 0.0),
            prompt_length=data.get("prompt_length"),
            response_length=data.get("response_length"),
        )


@dataclass
class StatusResult:
    """ステータスの結果"""

    success: bool
    browser_status: str
    logged_in: bool
    headless: bool
    uptime_seconds: Optional[float] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StatusResult:
        """辞書からStatusResultを生成"""
        return cls(
            success=data.get("success", False),
            browser_status=data.get("browser_status", "unknown"),
            logged_in=data.get("logged_in", False),
            headless=data.get("headless", False),
            uptime_seconds=data.get("uptime_seconds"),
        )


# =============================================================================
# クライアントクラス
# =============================================================================


class WagentClient:
    """
    Wagent APIクライアント

    Wagentサーバーとの通信を行うクライアントライブラリ。

    Usage:
        client = WagentClient()

        # ステータス確認
        status = client.status()
        print(f"Logged in: {status.logged_in}")

        # メッセージ送信
        result = client.chat("Hello, ChatGPT!")
        print(result.message)

        # シンプルなインターフェース
        response = client.ask("What is Python?")
        print(response)
    """

    DEFAULT_BASE_URL = "http://127.0.0.1:8765"
    DEFAULT_TIMEOUT = 180

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
        auto_retry: bool = True,
        max_retries: int = 3,
    ) -> None:
        """
        Args:
            base_url: WagentサーバーのベースURL
            timeout: リクエストタイムアウト（秒）
            auto_retry: 失敗時に自動リトライするか
            max_retries: 最大リトライ回数
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.auto_retry = auto_retry
        self.max_retries = max_retries
        self._session = requests.Session()

    # =========================================================================
    # パブリックAPI
    # =========================================================================

    def chat(
        self,
        message: str,
        new_conversation: bool = False,
        timeout_ms: Optional[int] = None,
    ) -> ChatResult:
        """
        メッセージを送信し、レスポンスを取得

        Args:
            message: 送信するプロンプト
            new_conversation: 新しい会話を開始するかどうか
            timeout_ms: レスポンス待機タイムアウト（ミリ秒）

        Returns:
            ChatResult オブジェクト
        """
        payload = {
            "message": message,
            "new_conversation": new_conversation,
        }
        if timeout_ms is not None:
            payload["timeout_ms"] = timeout_ms

        response = self._request("POST", "/v1/chat", json=payload)
        return ChatResult.from_dict(response)

    def ask(self, message: str, new_conversation: bool = False) -> Optional[str]:
        """
        シンプルなインターフェース - メッセージを送信してテキストのみを返す

        Args:
            message: 送信するプロンプト
            new_conversation: 新しい会話を開始するかどうか

        Returns:
            レスポンステキスト、エラー時はNone
        """
        result = self.chat(message, new_conversation)
        if result.success:
            return result.message
        logger.error(f"Chat failed: {result.error}")
        return None

    def status(self) -> StatusResult:
        """
        サーバーのステータスを取得

        Returns:
            StatusResult オブジェクト
        """
        response = self._request("GET", "/v1/status")
        return StatusResult.from_dict(response)

    def reset_session(self) -> bool:
        """
        セッション（チャット履歴）をリセット

        Returns:
            成功した場合True
        """
        response = self._request("DELETE", "/v1/session")
        return response.get("success", False)

    def health(self) -> bool:
        """
        サーバーのヘルスチェック

        Returns:
            健全な場合True
        """
        try:
            response = self._session.get(
                f"{self.base_url}/health",
                timeout=5,
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    def wait_for_server(
        self,
        max_retries: int = 30,
        interval: float = 1.0,
    ) -> bool:
        """
        サーバーが起動するまで待機

        Args:
            max_retries: 最大リトライ回数
            interval: リトライ間隔（秒）

        Returns:
            サーバーが起動した場合True
        """
        for i in range(max_retries):
            if self.health():
                logger.info("Server is ready!")
                return True
            logger.debug(f"Waiting for server... ({i + 1}/{max_retries})")
            time.sleep(interval)

        logger.error("Server did not respond")
        return False

    # =========================================================================
    # 内部メソッド
    # =========================================================================

    def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """APIリクエストを実行"""
        url = f"{self.base_url}{path}"

        for attempt in range(self.max_retries if self.auto_retry else 1):
            try:
                response = self._session.request(
                    method,
                    url,
                    timeout=self.timeout,
                    **kwargs,
                )

                # レートリミット
                if response.status_code == 429:
                    raise RateLimitError("Rate limit exceeded")

                response.raise_for_status()
                return response.json()

            except requests.ConnectionError as e:
                if attempt == self.max_retries - 1:
                    raise ConnectionError(f"Failed to connect: {e}") from e
                time.sleep(1)

            except requests.Timeout as e:
                if attempt == self.max_retries - 1:
                    raise TimeoutError(f"Request timed out: {e}") from e
                time.sleep(1)

            except requests.RequestException as e:
                logger.error(f"Request failed: {e}")
                return {"success": False, "error": str(e)}

        return {"success": False, "error": "Max retries exceeded"}

    # =========================================================================
    # コンテキストマネージャー
    # =========================================================================

    def __enter__(self) -> WagentClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self._session.close()


# =============================================================================
# 便利関数
# =============================================================================


def ask_chatgpt(
    prompt: str,
    server_url: str = "http://127.0.0.1:8765",
) -> Optional[str]:
    """
    ワンショットでChatGPTに質問する便利関数

    Args:
        prompt: プロンプト
        server_url: WagentサーバーのURL

    Returns:
        レスポンステキスト
    """
    with WagentClient(server_url) as client:
        return client.ask(prompt)
