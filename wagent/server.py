"""
Wagent API Server - FastAPIベースのRESTサーバー
外部エージェントからのリクエストを受け付け、ChatGPT Web UIを操作
"""

import time
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from .browser import browser
from .config import config
from .schemas import (
    ChatRequest,
    ChatResponse,
    SessionResponse,
    StatusResponse,
)


# Rate Limiter (簡易実装)
class RateLimiter:
    """シンプルなレートリミッター"""

    def __init__(self):
        self.last_request_time: float = 0
        self.request_count: int = 0
        self.window_start: float = 0

    def check(self) -> bool:
        """リクエストが許可されるかチェック"""
        now = time.time()
        min_interval = config.get_setting("rate_limit.min_interval", 3)
        rpm_limit = config.get_setting("rate_limit.requests_per_minute", 10)

        # 最小間隔チェック
        if now - self.last_request_time < min_interval:
            return False

        # 1分間のリクエスト数チェック
        if now - self.window_start > 60:
            self.window_start = now
            self.request_count = 0

        if self.request_count >= rpm_limit:
            return False

        return True

    def record(self):
        """リクエストを記録"""
        self.last_request_time = time.time()
        self.request_count += 1


rate_limiter = RateLimiter()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションのライフサイクル管理"""
    # 起動時
    logger.info("Starting Wagent server...")
    await browser.initialize()
    await browser.navigate_to_chatgpt()

    yield

    # 終了時
    logger.info("Shutting down Wagent server...")
    await browser.close()


# FastAPIアプリケーション
app = FastAPI(
    title="Wagent API",
    description="Web版ChatGPTをAPIとして利用するためのブリッジサーバー",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/v1/chat", response_model=ChatResponse)
async def send_chat(request: ChatRequest) -> ChatResponse:
    """
    メッセージを送信し、ChatGPTからの回答を返す

    - **message**: 送信するプロンプト
    - **new_conversation**: 新しい会話を開始するかどうか
    - **timeout**: レスポンス待機タイムアウト（ミリ秒）
    """
    # レートリミットチェック
    if not rate_limiter.check():
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please wait before sending another request.",
        )

    start_time = time.time()

    try:
        # 新しい会話を開始
        if request.new_conversation:
            await browser.new_chat()

        # プロンプト送信
        await browser.send_prompt(request.message)

        # レスポンス取得
        response_text = await browser.wait_for_response(timeout=request.timeout)

        rate_limiter.record()
        elapsed = time.time() - start_time

        return ChatResponse(success=True, message=response_text, elapsed_time=elapsed)

    except TimeoutError as e:
        elapsed = time.time() - start_time
        logger.error(f"Timeout: {e}")
        return ChatResponse(
            success=False, error="Response timeout exceeded", elapsed_time=elapsed
        )

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Error in chat: {e}")
        return ChatResponse(success=False, error=str(e), elapsed_time=elapsed)


@app.get("/v1/status", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    """
    ブラウザの生存確認とログイン状態をチェック
    """
    try:
        logged_in = await browser.is_logged_in()
        return StatusResponse(status="ok", browser_alive=True, logged_in=logged_in)
    except Exception as e:
        logger.error(f"Status check error: {e}")
        return StatusResponse(status="error", browser_alive=False, logged_in=False)


@app.delete("/v1/session", response_model=SessionResponse)
async def reset_session() -> SessionResponse:
    """
    新しいチャットを開始してコンテキストをリセット
    """
    try:
        await browser.new_chat()
        return SessionResponse(success=True, message="Session reset. New chat started.")
    except Exception as e:
        logger.error(f"Session reset error: {e}")
        return SessionResponse(success=False, message=f"Failed to reset session: {e}")


@app.get("/v1/screenshot")
async def take_screenshot():
    """
    デバッグ用：現在のブラウザ画面のスクリーンショットを取得
    """
    try:
        path = await browser.screenshot(f"screenshots/debug_{int(time.time())}.png")
        return {"success": True, "path": path}
    except Exception as e:
        logger.error(f"Screenshot error: {e}")
        return {"success": False, "error": str(e)}


@app.get("/health")
async def health_check():
    """ヘルスチェック"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
