"""Chat 模块公共接口。"""

from app.chat.conversation import save_conversation
from app.chat.service import chat_global, chat_on_note

__all__ = ["chat_on_note", "chat_global", "save_conversation"]
