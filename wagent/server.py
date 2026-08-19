"""
Server - FastAPIベースのRESTサーバー

外部エージェントからのリクエストを受け付け、ChatGPT Web UIを操作。
セッション管理・チャットID指定・会話履歴のDB保存をサポート。
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
from wagent.database import Database
from wagent.schemas import (
    BrowserStatus,
    ChatInfo,
    ChatListResponse,
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    HealthResponse,
    MessageInfo,
    MessageListResponse,
    ResponseStatus,
    SessionInfo,
    SessionListResponse,
    SessionResponse,
    StatusResponse,
)
from wagent.session import SessionManager

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

        time_since_last = now - self._last_request_time
        if time_since_last < self.min_interval:
            wait_time = self.min_interval - time_since_last
            return False, f"Please wait {wait_time:.1f} seconds"

        if now - self._window_start > 60:
            self._window_start = now
            self._request_count = 0

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
    session_manager: Optional[SessionManager] = None
    db: Optional[Database] = None
    rate_limiter: Optional[RateLimiter] = None
    start_time: float = field(default_factory=time.time)

    @property
    def browser(self) -> Optional[BrowserController]:
        if self.session_manager and self.session_manager.browser:
            return self.session_manager.browser
        return None

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

    config = Config.load()
    selectors = Selectors.load()

    # データベース初期化
    db_path = config.database.path
    db = Database(db_path)

    rate_limiter = RateLimiter(
        requests_per_minute=config.rate_limit.requests_per_minute,
        min_interval=config.rate_limit.min_interval,
        burst_limit=config.rate_limit.burst_limit,
    )

    app_state.config = config
    app_state.selectors = selectors
    app_state.db = db
    app_state.rate_limiter = rate_limiter
    app_state.start_time = time.time()

    # セッションマネージャーを開始
    session_manager = SessionManager(
        config=config,
        selectors=selectors,
        db=db,
        sessions_dir=config.database.sessions_dir,
    )
    await session_manager.start()
    app_state.session_manager = session_manager

    logger.info(f"Wagent server ready (headless={config.browser.headless})")
    yield

    await session_manager.stop()
    db.close()
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
    - **chat_id**: 開くチャットID（指定時はそのチャットを開く）
    - **timeout_ms**: レスポンス待機タイムアウト（ミリ秒）
    """
    browser = app_state.browser
    if browser is None:
        raise HTTPException(status_code=503, detail="Browser not initialized")

    # レートリミットチェック
    if app_state.rate_limiter:
        allowed, error_msg = app_state.rate_limiter.check()
        if not allowed:
            raise HTTPException(status_code=429, detail=error_msg or "Rate limit exceeded")

    db = app_state.db
    session_id = app_state.session_manager.active_session_id if app_state.session_manager else None

    start_time = time.time()
    prompt_length = len(request.message)

    try:
        # チャットIDが指定されている場合は開く
        if request.chat_id:
            opened = await browser.open_chat(request.chat_id)
            if not opened:
                raise HTTPException(status_code=404, detail=f"Chat not found: {request.chat_id}")

        # 新しい会話を開始
        if request.new_conversation:
            await browser.new_chat()

        # ウェブ検索を有効化
        if request.web_search:
            await browser.toggle_web_search(True)

        # ファイルアップロード
        if request.files:
            await browser.upload_files(request.files)

        # プロンプト送信
        await browser.send_prompt(request.message)

        # レスポンス取得
        response_text = await browser.wait_for_response(timeout_ms=request.timeout_ms)

        # DBに保存
        if db and session_id:
            current_chat_id = await browser.get_current_chat_id()
            if current_chat_id:
                db.upsert_chat(current_chat_id, session_id)
                db.add_message(current_chat_id, "user", request.message)
                db.add_message(current_chat_id, "assistant", response_text)

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

    except HTTPException:
        raise

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
    browser = app_state.browser
    if browser is None:
        return StatusResponse(
            success=False,
            browser_status=BrowserStatus.NOT_INITIALIZED,
            logged_in=False,
            headless=False,
            uptime_seconds=app_state.uptime_seconds,
        )

    try:
        logged_in = await browser.is_logged_in()
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


# =============================================================================
# セッション管理エンドポイント
# =============================================================================


@app.post("/v1/sessions", response_model=SessionInfo)
async def create_session(name: str = "New Account", account_label: str = "") -> SessionInfo:
    """新しいセッション（アカウント）を作成"""
    if app_state.session_manager is None:
        raise HTTPException(status_code=503, detail="Session manager not initialized")

    session = await app_state.session_manager.create_session(name, account_label)
    return SessionInfo(
        session_id=session.session_id,
        name=session.name,
        user_data_dir=session.user_data_dir,
        created_at=session.created_at,
        last_used=session.last_used,
        is_active=session.is_active,
    )


@app.get("/v1/sessions", response_model=SessionListResponse)
async def list_sessions() -> SessionListResponse:
    """全セッション一覧を取得"""
    if app_state.session_manager is None:
        raise HTTPException(status_code=503, detail="Session manager not initialized")

    sessions = app_state.session_manager.list_sessions()
    return SessionListResponse(
        success=True,
        sessions=[
            SessionInfo(
                session_id=s.session_id,
                name=s.name,
                user_data_dir=s.user_data_dir,
                created_at=s.created_at,
                last_used=s.last_used,
                is_active=s.is_active,
            )
            for s in sessions
        ],
    )


@app.post("/v1/sessions/{session_id}/switch", response_model=SessionResponse)
async def switch_session(session_id: str) -> SessionResponse:
    """セッションを切り替え"""
    if app_state.session_manager is None:
        raise HTTPException(status_code=503, detail="Session manager not initialized")

    result = await app_state.session_manager.switch_session(session_id)
    if result:
        return SessionResponse(success=True, message=f"Switched to session: {session_id}")
    return SessionResponse(success=False, message=f"Failed to switch session: {session_id}")


@app.delete("/v1/sessions/{session_id}", response_model=SessionResponse)
async def delete_session(session_id: str) -> SessionResponse:
    """セッションを削除"""
    if app_state.session_manager is None:
        raise HTTPException(status_code=503, detail="Session manager not initialized")

    result = await app_state.session_manager.delete_session(session_id)
    if result:
        return SessionResponse(success=True, message=f"Deleted session: {session_id}")
    return SessionResponse(success=False, message=f"Failed to delete session: {session_id}")


# =============================================================================
# チャット管理エンドポイント
# =============================================================================


@app.get("/v1/chats", response_model=ChatListResponse)
async def list_chats() -> ChatListResponse:
    """現在のセッションのチャット一覧を取得"""
    if app_state.session_manager is None or app_state.db is None:
        raise HTTPException(status_code=503, detail="Not available")

    session_id = app_state.session_manager.active_session_id
    if not session_id:
        return ChatListResponse(success=True, chats=[])

    chats = app_state.db.list_chats(session_id)
    return ChatListResponse(
        success=True,
        chats=[
            ChatInfo(
                chat_id=c.chat_id,
                session_id=c.session_id,
                title=c.title,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in chats
        ],
    )


@app.get("/v1/chats/{chat_id}/messages", response_model=MessageListResponse)
async def get_chat_messages(chat_id: str, limit: int = 100) -> MessageListResponse:
    """チャットのメッセージ一覧を取得"""
    if app_state.db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    messages = app_state.db.get_messages(chat_id, limit)
    return MessageListResponse(
        success=True,
        messages=[
            MessageInfo(
                id=m.id,
                chat_id=m.chat_id,
                role=m.role,
                content=m.content,
                timestamp=m.timestamp,
            )
            for m in messages
        ],
    )


@app.delete("/v1/session", response_model=SessionResponse)
async def reset_session() -> SessionResponse:
    """新しいチャットを開始してコンテキストをリセット"""
    browser = app_state.browser
    if browser is None:
        return SessionResponse(success=False, message="Browser not initialized")

    try:
        await browser.new_chat()
        return SessionResponse(success=True, message="Session reset. New chat started.")

    except Exception as e:
        logger.error(f"Session reset error: {e}")
        return SessionResponse(success=False, message=f"Failed to reset session: {e}")


@app.get("/v1/screenshot")
async def take_screenshot() -> dict:
    """デバッグ用：現在のブラウザ画面のスクリーンショットを取得"""
    browser = app_state.browser
    if browser is None:
        return {"success": False, "error": "Browser not initialized"}

    try:
        path = await browser.screenshot()
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
