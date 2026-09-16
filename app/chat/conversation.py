"""会话历史占位（先不建表）。"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from app.models.chat import ConversationMeta, Message
from app.models.enums import ConversationType


def save_conversation(
    type: ConversationType,
    note_id: Optional[UUID],
    messages: List[Message],
    title: Optional[str] = None,
) -> ConversationMeta:
    raise NotImplementedError("chat.conversation.save_conversation 尚未实现")
