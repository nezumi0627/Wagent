"""
Session Manager - 複数アカウント/セッションの管理

ブラウザコンテキストをセッション単位で管理し、
アカウントの保存・切り替え・破棄を提供する。
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Optional

from loguru import logger
from playwright.async_api import Page

from wagent.browser import BrowserController
from wagent.config import Config, Selectors
from wagent.database import Database, SessionRecord


class SessionManager:
    """ブラウザセッション管理"""

    def __init__(self, config: Config, selectors: Selectors, db: Database, sessions_dir: str = "./sessions") -> None:
        self._config = config
        self._selectors = selectors
        self._db = db
        self._sessions_dir = Path(sessions_dir)
        self._sessions_dir.mkdir(parents=True, exist_ok=True)

        self._browser: Optional[BrowserController] = None
        self._active_session_id: Optional[str] = None

    @property
    def active_session_id(self) -> Optional[str]:
        return self._active_session_id

    @property
    def browser(self) -> Optional[BrowserController]:
        return self._browser

    @property
    def page(self) -> Optional[Page]:
        return self._browser.page if self._browser else None

    # =========================================================================
    # ライフサイクル
    # =========================================================================

    async def start(self) -> None:
        """セッションマネージャーを開始"""
        active = self._db.get_active_session()
        if active:
            await self.switch_session(active.session_id)
        else:
            sessions = self._db.list_sessions()
            if sessions:
                await self.switch_session(sessions[0].session_id)
            else:
                await self.create_session("Default", "Default")

    async def stop(self) -> None:
        """セッションマネージャーを停止"""
        if self._browser:
            await self._browser.stop()
            self._browser = None
        logger.info("Session manager stopped")

    # =========================================================================
    # セッション作成・取得
    # =========================================================================

    async def create_session(self, name: str, account_label: str = "") -> SessionRecord:
        """新しいセッション（アカウント）を作成"""
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        profile_name = f"profile_{session_id}"
        user_data_dir = str(self._sessions_dir / profile_name)

        Path(user_data_dir).mkdir(parents=True, exist_ok=True)

        display_name = account_label or name or f"Account {len(self._db.list_sessions()) + 1}"
        session = self._db.create_session(session_id, display_name, user_data_dir)

        await self.switch_session(session_id)

        session = self._db.get_session(session_id)
        if session:
            logger.info(f"Created session: {session_id} ({session.name})")
            return session
        return session

    async def switch_session(self, session_id: str) -> bool:
        """セッションを切り替え"""
        session = self._db.get_session(session_id)
        if session is None:
            logger.error(f"Session not found: {session_id}")
            return False

        # 現在のブラウザを閉じる
        if self._browser:
            await self._browser.stop()
            self._browser = None

        # 新しいブラウザを作成
        try:
            self._browser = await BrowserController.create_instance(
                config=self._config,
                selectors=self._selectors,
                user_data_dir=session.user_data_dir,
            )
            self._active_session_id = session_id
            self._db.set_active_session(session_id)
            self._db.update_session_last_used(session_id)

            logger.info(f"Switched to session: {session_id} ({session.name})")
            return True

        except Exception as e:
            logger.error(f"Failed to switch session {session_id}: {e}")
            self._browser = None
            return False

    async def delete_session(self, session_id: str) -> bool:
        """セッションを削除"""
        if session_id == self._active_session_id and self._browser:
            await self._browser.stop()
            self._browser = None
            self._active_session_id = None

        session = self._db.get_session(session_id)
        if session:
            try:
                shutil.rmtree(session.user_data_dir, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Failed to remove profile dir: {e}")

        result = self._db.delete_session(session_id)
        if result:
            logger.info(f"Deleted session: {session_id}")

            # 別のセッションに切り替え
            sessions = self._db.list_sessions()
            if sessions and not self._active_session_id:
                await self.switch_session(sessions[0].session_id)

        return result

    def get_session(self, session_id: str) -> Optional[SessionRecord]:
        """セッション情報を取得"""
        return self._db.get_session(session_id)

    def list_sessions(self) -> list[SessionRecord]:
        """全セッション一覧を取得"""
        return self._db.list_sessions()

    # =========================================================================
    # チャット操作
    # =========================================================================

    async def open_chat(self, chat_id: str) -> bool:
        """特定のチャットを開く"""
        if self._browser:
            return await self._browser.open_chat(chat_id)
        return False

    async def get_current_chat_id(self) -> Optional[str]:
        """現在のチャットIDを取得"""
        if self._browser:
            return await self._browser.get_current_chat_id()
        return None
