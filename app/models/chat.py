"""对话相关模型（会话存储实现后置）。"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import ConversationType


class Message(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class ConversationMeta(BaseModel):
    id: UUID
    type: ConversationType
    note_id: Optional[UUID] = None
    title: str
    created_at: datetime
    updated_at: datetime


class ChatSource(BaseModel):
    note_id: UUID
    title: str
    start_sec: Optional[float] = None
    hit_count: int = Field(
        default=1,
        ge=1,
        description="该笔记在本轮检索中命中的片段数（按 note_id 去重后保留）",
    )


class ChatResponse(BaseModel):
    answer: str
    sources: List[ChatSource] = Field(default_factory=list)


class NoteChatRequest(BaseModel):
    note_id: UUID
    query: str = Field(..., min_length=1)
    history: List[Message] = Field(default_factory=list)


class GlobalChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    note_ids: Optional[List[UUID]] = None
    history: List[Message] = Field(default_factory=list)
