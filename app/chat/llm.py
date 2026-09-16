"""通义千问对话补全。"""

from __future__ import annotations

from typing import List

import dashscope
from dashscope import Generation

from app.config import settings
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

    dashscope.api_key = settings.DASHSCOPE_API_KEY
    payload = [{"role": m.role, "content": m.content} for m in messages]

    try:
        response = Generation.call(
            model=settings.QWEN_MODEL,
            messages=payload,
            max_tokens=settings.QWEN_MAX_TOKENS,
            temperature=0.7,
            result_format="message",
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"通义千问调用异常: {exc}") from exc

    status = getattr(response, "status_code", None)
    if status != 200:
        message = getattr(response, "message", response)
        raise RuntimeError(f"通义千问调用失败: status={status}, message={message}")

    try:
        content = response.output.choices[0].message.content
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"通义千问返回解析失败: {exc}") from exc

    text = str(content or "").strip()
    if not text:
        raise RuntimeError("通义千问返回空内容")
    return text
