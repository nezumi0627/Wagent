"""
Wagent Client - エージェントからWagent APIを呼び出すためのクライアント
"""

import time
from typing import Any, Dict, Optional

import requests
from loguru import logger


class WagentClient:
    """
    Wagent APIクライアント

    使用例:
        client = WagentClient()
        response = client.chat("Hello, how are you?")
        print(response)
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8765", timeout: int = 180):
        """
        Args:
            base_url: WagentサーバーのURL
            timeout: リクエストタイムアウト（秒）
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def chat(
        self,
        message: str,
        new_conversation: bool = False,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        メッセージを送信し、レスポンスを取得

        Args:
            message: 送信するプロンプト
            new_conversation: 新しい会話を開始するかどうか
            timeout: レスポンス待機タイムアウト（ミリ秒）

        Returns:
            APIレスポンス
        """
        payload = {"message": message, "new_conversation": new_conversation}
        if timeout:
            payload["timeout"] = timeout

        try:
            response = self.session.post(
                f"{self.base_url}/v1/chat", json=payload, timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Chat request failed: {e}")
            return {"success": False, "error": str(e), "message": None}

    def get_response(self, message: str) -> Optional[str]:
        """
        シンプルなインターフェース - メッセージを送信してテキストのみを返す

        Args:
            message: 送信するプロンプト

        Returns:
            ChatGPTからのレスポンステキスト、エラー時はNone
        """
        result = self.chat(message)
        if result.get("success"):
            return result.get("message")
        else:
            logger.error(f"Failed: {result.get('error')}")
            return None

    def status(self) -> Dict[str, Any]:
        """
        サーバーのステータスを取得

        Returns:
            ステータス情報
        """
        try:
            response = self.session.get(f"{self.base_url}/v1/status", timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Status request failed: {e}")
            return {
                "status": "error",
                "browser_alive": False,
                "logged_in": False,
                "error": str(e),
            }

    def reset_session(self) -> bool:
        """
        セッション（チャット履歴）をリセット

        Returns:
            成功した場合True
        """
        try:
            response = self.session.delete(f"{self.base_url}/v1/session", timeout=30)
            response.raise_for_status()
            result = response.json()
            return result.get("success", False)
        except requests.RequestException as e:
            logger.error(f"Reset session failed: {e}")
            return False

    def health(self) -> bool:
        """
        サーバーのヘルスチェック

        Returns:
            健全な場合True
        """
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def wait_for_server(self, max_retries: int = 30, interval: float = 1.0) -> bool:
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


# 便利関数
def ask_chatgpt(
    prompt: str, server_url: str = "http://127.0.0.1:8765"
) -> Optional[str]:
    """
    ワンショットでChatGPTに質問する便利関数

    Args:
        prompt: プロンプト
        server_url: WagentサーバーのURL

    Returns:
        レスポンステキスト
    """
    client = WagentClient(server_url)
    return client.get_response(prompt)
