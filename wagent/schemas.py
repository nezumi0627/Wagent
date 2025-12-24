"""
Schemas - APIリクエスト/レスポンスのスキーマ定義

Pydanticを使用した型安全なデータモデル。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

# =============================================================================
# 列挙型
# =============================================================================


class ResponseStatus(str, Enum):
    """レスポンスステータス"""

    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"


class BrowserStatus(str, Enum):
    """ブラウザステータス"""

    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    NOT_INITIALIZED = "not_initialized"


# =============================================================================
# リクエストスキーマ
# =============================================================================


class ChatRequest(BaseModel):
    """チャットリクエスト"""

    message: str = Field(
        ...,
        min_length=1,
        max_length=100000,
        description="送信するプロンプト",
    )
    new_conversation: bool = Field(
        default=False,
        description="新しい会話を開始するかどうか",
    )
    timeout_ms: Optional[int] = Field(
        default=None,
        ge=1000,
        le=300000,
        description="レスポンス待機タイムアウト（ミリ秒）",
    )

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        """メッセージが空でないことを確認"""
        if not v.strip():
            raise ValueError("Message cannot be empty or whitespace only")
        return v.strip()

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Pythonでフィボナッチ数列を計算するコードを書いてください",
                "new_conversation": False,
                "timeout_ms": 60000,
            }
        }


# =============================================================================
# レスポンススキーマ
# =============================================================================


class BaseResponse(BaseModel):
    """レスポンスの基底クラス"""

    success: bool = Field(..., description="リクエストの成功/失敗")
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="レスポンス生成時刻",
    )


class ChatResponse(BaseResponse):
    """チャットレスポンス"""

    message: Optional[str] = Field(
        None,
        description="ChatGPTからのレスポンス",
    )
    error: Optional[str] = Field(
        None,
        description="エラーメッセージ",
    )
    status: ResponseStatus = Field(
        default=ResponseStatus.SUCCESS,
        description="レスポンスステータス",
    )
    elapsed_seconds: float = Field(
        ...,
        description="処理時間（秒）",
    )
    prompt_length: Optional[int] = Field(
        None,
        description="送信したプロンプトの長さ",
    )
    response_length: Optional[int] = Field(
        None,
        description="レスポンスの長さ",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "以下はPythonでフィボナッチ数列を計算するコードです...",
                "status": "success",
                "elapsed_seconds": 5.23,
                "prompt_length": 45,
                "response_length": 350,
                "timestamp": "2024-12-24T12:00:00",
            }
        }


class StatusResponse(BaseResponse):
    """ステータスレスポンス"""

    browser_status: BrowserStatus = Field(
        ...,
        description="ブラウザのステータス",
    )
    logged_in: bool = Field(
        ...,
        description="ChatGPTにログインしているか",
    )
    headless: bool = Field(
        ...,
        description="ヘッドレスモードか",
    )
    uptime_seconds: Optional[float] = Field(
        None,
        description="サーバー起動からの経過時間（秒）",
    )


class SessionResponse(BaseResponse):
    """セッション操作レスポンス"""

    message: str = Field(..., description="操作結果メッセージ")


class HealthResponse(BaseModel):
    """ヘルスチェックレスポンス"""

    status: str = Field(default="healthy")
    version: str = Field(...)
    timestamp: datetime = Field(default_factory=datetime.now)


class ErrorResponse(BaseResponse):
    """エラーレスポンス"""

    success: bool = False
    error: str = Field(..., description="エラーメッセージ")
    detail: Optional[str] = Field(None, description="詳細情報")
    error_code: Optional[str] = Field(None, description="エラーコード")
