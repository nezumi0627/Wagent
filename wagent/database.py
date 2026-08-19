"""
Database - セッション・チャット・メッセージの永続化

SQLiteを使用した軽量データベース層。
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


@dataclass
class SessionRecord:
    session_id: str
    name: str
    user_data_dir: str
    created_at: str
    last_used: str
    is_active: bool = False


@dataclass
class ChatRecord:
    chat_id: str
    session_id: str
    title: Optional[str]
    created_at: str
    updated_at: str


@dataclass
class MessageRecord:
    id: int
    chat_id: str
    role: str
    content: str
    timestamp: str


class Database:
    """SQLiteベースのデータベース管理"""

    def __init__(self, db_path: str = "./data/wagent.db") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        cursor = self._conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                user_data_dir TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_used TEXT NOT NULL,
                is_active INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS chats (
                chat_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                title TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (chat_id) REFERENCES chats(chat_id)
            );

            CREATE INDEX IF NOT EXISTS idx_chats_session ON chats(session_id);
            CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id);
        """)
        self._conn.commit()

    def close(self) -> None:
        """接続を閉じる"""
        self._conn.close()

    # =========================================================================
    # セッション操作
    # =========================================================================

    def create_session(self, session_id: str, name: str, user_data_dir: str) -> SessionRecord:
        """新しいセッションを作成"""
        now = datetime.now().isoformat()
        cursor = self._conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO sessions (session_id, name, user_data_dir, created_at, last_used, is_active) VALUES (?, ?, ?, ?, ?, 0)",
            (session_id, name, user_data_dir, now, now),
        )
        self._conn.commit()
        return SessionRecord(session_id=session_id, name=name, user_data_dir=user_data_dir, created_at=now, last_used=now)

    def get_session(self, session_id: str) -> Optional[SessionRecord]:
        """セッションを取得"""
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return SessionRecord(
            session_id=row["session_id"],
            name=row["name"],
            user_data_dir=row["user_data_dir"],
            created_at=row["created_at"],
            last_used=row["last_used"],
            is_active=bool(row["is_active"]),
        )

    def list_sessions(self) -> list[SessionRecord]:
        """全セッションを取得"""
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM sessions ORDER BY last_used DESC")
        return [
            SessionRecord(
                session_id=row["session_id"],
                name=row["name"],
                user_data_dir=row["user_data_dir"],
                created_at=row["created_at"],
                last_used=row["last_used"],
                is_active=bool(row["is_active"]),
            )
            for row in cursor.fetchall()
        ]

    def update_session_last_used(self, session_id: str) -> None:
        """最終使用日時を更新"""
        now = datetime.now().isoformat()
        cursor = self._conn.cursor()
        cursor.execute("UPDATE sessions SET last_used = ? WHERE session_id = ?", (now, session_id))
        self._conn.commit()

    def set_active_session(self, session_id: str) -> None:
        """アクティブセッションを設定"""
        cursor = self._conn.cursor()
        cursor.execute("UPDATE sessions SET is_active = 0")
        cursor.execute("UPDATE sessions SET is_active = 1 WHERE session_id = ?", (session_id,))
        self._conn.commit()

    def get_active_session(self) -> Optional[SessionRecord]:
        """アクティブセッションを取得"""
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE is_active = 1 LIMIT 1")
        row = cursor.fetchone()
        if row is None:
            return None
        return SessionRecord(
            session_id=row["session_id"],
            name=row["name"],
            user_data_dir=row["user_data_dir"],
            created_at=row["created_at"],
            last_used=row["last_used"],
            is_active=bool(row["is_active"]),
        )

    def delete_session(self, session_id: str) -> bool:
        """セッションを削除"""
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM messages WHERE chat_id IN (SELECT chat_id FROM chats WHERE session_id = ?)", (session_id,))
        cursor.execute("DELETE FROM chats WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    # =========================================================================
    # チャット操作
    # =========================================================================

    def upsert_chat(self, chat_id: str, session_id: str, title: Optional[str] = None) -> ChatRecord:
        """チャットを追加または更新"""
        now = datetime.now().isoformat()
        cursor = self._conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO chats (chat_id, session_id, title, created_at, updated_at) VALUES (?, ?, COALESCE(?, (SELECT title FROM chats WHERE chat_id = ?)), COALESCE(?, (SELECT created_at FROM chats WHERE chat_id = ?)), ?)",
            (chat_id, session_id, title, chat_id, title, chat_id, now),
        )
        self._conn.commit()
        return ChatRecord(chat_id=chat_id, session_id=session_id, title=title, created_at=now, updated_at=now)

    def get_chat(self, chat_id: str) -> Optional[ChatRecord]:
        """チャットを取得"""
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM chats WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return ChatRecord(chat_id=row["chat_id"], session_id=row["session_id"], title=row["title"], created_at=row["created_at"], updated_at=row["updated_at"])

    def list_chats(self, session_id: str) -> list[ChatRecord]:
        """セッションのチャット一覧を取得"""
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM chats WHERE session_id = ? ORDER BY updated_at DESC", (session_id,))
        return [
            ChatRecord(
                chat_id=row["chat_id"],
                session_id=row["session_id"],
                title=row["title"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in cursor.fetchall()
        ]

    def update_chat_title(self, chat_id: str, title: str) -> None:
        """チャットタイトルを更新"""
        now = datetime.now().isoformat()
        cursor = self._conn.cursor()
        cursor.execute("UPDATE chats SET title = ?, updated_at = ? WHERE chat_id = ?", (title, now, chat_id))
        self._conn.commit()

    # =========================================================================
    # メッセージ操作
    # =========================================================================

    def add_message(self, chat_id: str, role: str, content: str) -> MessageRecord:
        """メッセージを追加"""
        now = datetime.now().isoformat()
        cursor = self._conn.cursor()
        cursor.execute(
            "INSERT INTO messages (chat_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (chat_id, role, content, now),
        )
        self._conn.commit()
        return MessageRecord(id=cursor.lastrowid, chat_id=chat_id, role=role, content=content, timestamp=now)

    def get_messages(self, chat_id: str, limit: int = 100) -> list[MessageRecord]:
        """チャットのメッセージ一覧を取得"""
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM messages WHERE chat_id = ? ORDER BY timestamp ASC LIMIT ?",
            (chat_id, limit),
        )
        return [
            MessageRecord(
                id=row["id"],
                chat_id=row["chat_id"],
                role=row["role"],
                content=row["content"],
                timestamp=row["timestamp"],
            )
            for row in cursor.fetchall()
        ]
