"""DashScope text-embedding-v1 嵌入调用（1536 维）。"""

from __future__ import annotations

from http import HTTPStatus
from typing import List

import dashscope
from dashscope import TextEmbedding

from app.config import settings


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

    dashscope.api_key = settings.DASHSCOPE_API_KEY
    batch_size = max(1, settings.EMBEDDING_BATCH_SIZE)
    vectors: List[List[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        resp = TextEmbedding.call(
            model=TextEmbedding.Models.text_embedding_v1,
            input=batch,
        )
        if getattr(resp, "status_code", None) != HTTPStatus.OK:
            code = getattr(resp, "code", None)
            message = getattr(resp, "message", None) or str(resp)
            raise RuntimeError(
                f"DashScope embedding 调用失败: status={getattr(resp, 'status_code', None)}, "
                f"code={code}, message={message}"
            )

        output = resp.output or {}
        items = output.get("embeddings") or []
        if len(items) != len(batch):
            raise RuntimeError(
                f"DashScope embedding 返回条数不符: expect={len(batch)}, got={len(items)}"
            )
        items = sorted(items, key=lambda x: x.get("text_index", 0))
        for item in items:
            emb = item.get("embedding") or []
            if len(emb) != settings.EMBEDDING_DIM:
                raise RuntimeError(
                    f"嵌入维度不符: expect={settings.EMBEDDING_DIM}, got={len(emb)}"
                )
            vectors.append(list(emb))

    return vectors


def embed_text(text: str) -> List[float]:
    """单条嵌入。"""
    return embed_texts([text])[0]
