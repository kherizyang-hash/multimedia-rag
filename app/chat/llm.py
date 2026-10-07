"""通义千问对话补全（百炼 OpenAI 兼容接口）。"""

from __future__ import annotations

from typing import List

from app.config import settings
from app.llm_dashscope import chat_completions
from app.models.chat import Message


def chat_completion(messages: List[Message]) -> str:
    """
    调用通义千问生成回复。失败抛出 RuntimeError（对话路径需要明确错误）。
    """
    if not messages:
        raise ValueError("messages 不能为空")
    if not settings.DASHSCOPE_API_KEY:
        raise RuntimeError(
            "DASHSCOPE_API_KEY 未配置，请在 .env 中填写（参见 .env.example）"
        )

    payload = [{"role": m.role, "content": m.content} for m in messages]
    print(f"[LLM] 调用通义千问 model={settings.QWEN_MODEL} messages={len(payload)}")
    text = chat_completions(
        payload,
        max_tokens=settings.QWEN_MAX_TOKENS,
        temperature=0.7,
    )
    print(f"[LLM] 通义千问返回 {len(text)} 字")
    return text
