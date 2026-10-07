"""Embedding：经百炼 OpenAI 兼容接口调用 text-embedding-v1（1536 维）。"""

from __future__ import annotations

from typing import List

from app.config import settings
from app.llm_dashscope import embed_texts_openai


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    批量嵌入；按 EMBEDDING_BATCH_SIZE（默认 25）分批调用。
    失败抛出 RuntimeError，不吞异常。
    """
    if not texts:
        return []
    if not settings.DASHSCOPE_API_KEY:
        raise RuntimeError(
            "DASHSCOPE_API_KEY 未配置，请在 .env 中填写（参见 .env.example）"
        )

    batch_size = max(1, settings.EMBEDDING_BATCH_SIZE)
    vectors: List[List[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        vectors.extend(embed_texts_openai(batch, model="text-embedding-v1"))
    return vectors


def embed_text(text: str) -> List[float]:
    """单条嵌入。"""
    return embed_texts([text])[0]
