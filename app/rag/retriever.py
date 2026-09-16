"""检索编排（首版直连向量检索；HyDE/BM25/RRF 后续在此内部演进）。"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from app.models.chunk import SearchResult
from app.rag.store import search_chunks


def search(
    query: str,
    note_ids: Optional[List[UUID]] = None,
    top_k: int = 5,
) -> List[SearchResult]:
    """对外统一检索接口。"""
    id_strs = [str(n) for n in note_ids] if note_ids else None
    return search_chunks(query=query, note_ids=id_strs, top_k=top_k)


def retrieve(
    query: str,
    note_ids: Optional[List[UUID]] = None,
    top_k: int = 5,
) -> List[SearchResult]:
    """search 的别名（兼容提示词命名）。"""
    return search(query=query, note_ids=note_ids, top_k=top_k)
