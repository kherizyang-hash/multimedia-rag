"""RAG 侧嵌入封装：委托 embeddings.dashscope_embedder。"""

from __future__ import annotations

from typing import List

from app.embeddings.dashscope_embedder import embed_text as _embed_text
from app.embeddings.dashscope_embedder import embed_texts as _embed_texts


def embed_texts(texts: List[str]) -> List[List[float]]:
    """批量调用 DashScope text-embedding-v1，返回 1536 维向量列表。"""
    return _embed_texts(texts)


def embed_text(text: str) -> List[float]:
    """单个文本向量化。"""
    return _embed_text(text)
