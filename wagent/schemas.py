"""
Pydantic Schemas - APIリクエスト/レスポンスのスキーマ定義
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """チャットリクエスト"""

    message: str = Field(..., description="送信するプロンプト", min_length=1)
    new_conversation: bool = Field(
        default=False, description="新しい会話を開始するかどうか"
    )
    timeout: Optional[int] = Field(
        default=None,
        description="レスポンス待機タイムアウト（ミリ秒）",
        ge=1000,
        le=300000,
    )


class ChatResponse(BaseModel):
    """チャットレスポンス"""

    success: bool = Field(..., description="リクエストの成功/失敗")
    message: Optional[str] = Field(None, description="ChatGPTからのレスポンス")
    error: Optional[str] = Field(None, description="エラーメッセージ")
    elapsed_time: float = Field(..., description="処理時間（秒）")
    timestamp: datetime = Field(default_factory=datetime.now)


class StatusResponse(BaseModel):
    """ステータスレスポンス"""

    status: str = Field(..., description="現在のステータス")
    browser_alive: bool = Field(..., description="ブラウザが起動しているか")
    logged_in: bool = Field(..., description="ログイン状態")
    timestamp: datetime = Field(default_factory=datetime.now)


class SessionResponse(BaseModel):
    """セッション操作レスポンス"""

    success: bool
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)


class ErrorResponse(BaseModel):
    """エラーレスポンス"""

    success: bool = False
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
