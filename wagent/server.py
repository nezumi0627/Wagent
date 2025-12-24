"""
Server - FastAPIベースのRESTサーバー

外部エージェントからのリクエストを受け付け、ChatGPT Web UIを操作。
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from wagent import __version__
from wagent.browser import BrowserController
from wagent.config import Config, Selectors
from wagent.schemas import (
    BrowserStatus,
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    HealthResponse,
    ResponseStatus,
    SessionResponse,
    StatusResponse,
)

# =============================================================================
# レートリミッター
# =============================================================================


@dataclass
class RateLimiter:
    """トークンバケット方式のレートリミッター"""

    requests_per_minute: int = 10
    min_interval: float = 3.0
    burst_limit: int = 3
    _last_request_time: float = field(default=0.0, init=False)
    _request_count: int = field(default=0, init=False)
    _window_start: float = field(default=0.0, init=False)

    def check(self) -> tuple[bool, Optional[str]]:
        """
        リクエストが許可されるかチェック

        Returns:
            (許可されるか, エラーメッセージ)
        """
        now = time.time()

        # 最小間隔チェック
        time_since_last = now - self._last_request_time
        if time_since_last < self.min_interval:
            wait_time = self.min_interval - time_since_last
            return False, f"Please wait {wait_time:.1f} seconds"

        # ウィンドウリセット
        if now - self._window_start > 60:
            self._window_start = now
            self._request_count = 0

        # RPMチェック
        if self._request_count >= self.requests_per_minute:
            return False, "Rate limit exceeded (requests per minute)"

        return True, None

    def record(self) -> None:
        """リクエストを記録"""
        self._last_request_time = time.time()
        self._request_count += 1


# =============================================================================
# アプリケーション状態
# =============================================================================


@dataclass
class AppState:
    """アプリケーション状態を管理"""

    config: Optional[Config] = None
    selectors: Optional[Selectors] = None
    browser: Optional[BrowserController] = None
    rate_limiter: Optional[RateLimiter] = None
    start_time: float = field(default_factory=time.time)

    @property
    def uptime_seconds(self) -> float:
        """起動からの経過時間"""
        return time.time() - self.start_time


# グローバル状態
app_state = AppState()


# =============================================================================
# ライフサイクル管理
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """アプリケーションのライフサイクル管理"""
    logger.info("Starting Wagent server...")

    # 設定読み込み
    config = Config.load()
    selectors = Selectors.load()

    # レートリミッター初期化
    rate_limiter = RateLimiter(
        requests_per_minute=config.rate_limit.requests_per_minute,
        min_interval=config.rate_limit.min_interval,
        burst_limit=config.rate_limit.burst_limit,
    )

    app_state.config = config
    app_state.selectors = selectors
    app_state.rate_limiter = rate_limiter
    app_state.start_time = time.time()

    # ブラウザコントローラーを開始
    async with BrowserController.create(config, selectors) as browser:
        app_state.browser = browser

        # ChatGPTに移動
        await browser.navigate_to_chatgpt()

        logger.info(f"Wagent server ready (headless={config.browser.headless})")
        yield

    logger.info("Wagent server shutdown complete")


# =============================================================================
# FastAPIアプリケーション
# =============================================================================


app = FastAPI(
    title="Wagent API",
    description="Web版ChatGPTをAPIとして利用するためのブリッジサーバー",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# エラーハンドラー
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """グローバル例外ハンドラー"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            success=False,
            error="Internal server error",
            detail=str(exc),
        ).model_dump(),
    )


# CORS設定（起動時に設定）
@app.on_event("startup")
async def setup_cors() -> None:
    """CORS設定を適用"""
    if app_state.config and app_state.config.server.cors.enabled:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(app_state.config.server.cors.origins),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )


# =============================================================================
# エンドポイント
# =============================================================================


@app.post("/v1/chat", response_model=ChatResponse)
async def send_chat(request: ChatRequest) -> ChatResponse:
    """
    メッセージを送信し、ChatGPTからの回答を返す

    - **message**: 送信するプロンプト
    - **new_conversation**: 新しい会話を開始するかどうか
    - **timeout_ms**: レスポンス待機タイムアウト（ミリ秒）
    """
    # レートリミットチェック
    if app_state.rate_limiter:
        allowed, error_msg = app_state.rate_limiter.check()
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=error_msg or "Rate limit exceeded",
            )

    if app_state.browser is None:
        raise HTTPException(
            status_code=503,
            detail="Browser not initialized",
        )

    start_time = time.time()
    prompt_length = len(request.message)

    try:
        # 新しい会話を開始
        if request.new_conversation:
            await app_state.browser.new_chat()

        # プロンプト送信
        await app_state.browser.send_prompt(request.message)

        # レスポンス取得
        response_text = await app_state.browser.wait_for_response(
            timeout_ms=request.timeout_ms
        )

        # レートリミッター記録
        if app_state.rate_limiter:
            app_state.rate_limiter.record()

        elapsed = time.time() - start_time

        return ChatResponse(
            success=True,
            message=response_text,
            status=ResponseStatus.SUCCESS,
            elapsed_seconds=elapsed,
            prompt_length=prompt_length,
            response_length=len(response_text),
        )

    except TimeoutError:
        elapsed = time.time() - start_time
        logger.error("Response timeout")
        return ChatResponse(
            success=False,
            error="Response timeout exceeded",
            status=ResponseStatus.TIMEOUT,
            elapsed_seconds=elapsed,
            prompt_length=prompt_length,
        )

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Chat error: {e}")
        return ChatResponse(
            success=False,
            error=str(e),
            status=ResponseStatus.ERROR,
            elapsed_seconds=elapsed,
            prompt_length=prompt_length,
        )


@app.get("/v1/status", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    """ブラウザの生存確認とログイン状態をチェック"""
    if app_state.browser is None:
        return StatusResponse(
            success=False,
            browser_status=BrowserStatus.NOT_INITIALIZED,
            logged_in=False,
            headless=False,
            uptime_seconds=app_state.uptime_seconds,
        )

    try:
        logged_in = await app_state.browser.is_logged_in()
        headless = app_state.config.browser.headless if app_state.config else False

        return StatusResponse(
            success=True,
            browser_status=BrowserStatus.READY,
            logged_in=logged_in,
            headless=headless,
            uptime_seconds=app_state.uptime_seconds,
        )

    except Exception as e:
        logger.error(f"Status check error: {e}")
        return StatusResponse(
            success=False,
            browser_status=BrowserStatus.ERROR,
            logged_in=False,
            headless=False,
            uptime_seconds=app_state.uptime_seconds,
        )


@app.delete("/v1/session", response_model=SessionResponse)
async def reset_session() -> SessionResponse:
    """新しいチャットを開始してコンテキストをリセット"""
    if app_state.browser is None:
        return SessionResponse(
            success=False,
            message="Browser not initialized",
        )

    try:
        await app_state.browser.new_chat()
        return SessionResponse(
            success=True,
            message="Session reset. New chat started.",
        )

    except Exception as e:
        logger.error(f"Session reset error: {e}")
        return SessionResponse(
            success=False,
            message=f"Failed to reset session: {e}",
        )


@app.get("/v1/screenshot")
async def take_screenshot() -> dict:
    """デバッグ用：現在のブラウザ画面のスクリーンショットを取得"""
    if app_state.browser is None:
        return {"success": False, "error": "Browser not initialized"}

    try:
        path = await app_state.browser.screenshot()
        return {"success": True, "path": path}

    except Exception as e:
        logger.error(f"Screenshot error: {e}")
        return {"success": False, "error": str(e)}


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """ヘルスチェック"""
    return HealthResponse(
        status="healthy",
        version=__version__,
        timestamp=datetime.now(),
    )


# =============================================================================
# サーバー起動ヘルパー
# =============================================================================


def run_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    reload: bool = False,
) -> None:
    """サーバーを起動"""
    import uvicorn

    logger.info(f"Starting Wagent server on {host}:{port}")
    uvicorn.run(
        "wagent.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
