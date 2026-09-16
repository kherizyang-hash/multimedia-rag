"""Milvus 向量存储：写入 / 删除 / 检索。"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from app.config import settings
from app.db.milvus_client import get_collection
from app.models.chunk import Chunk, SearchResult
from app.models.enums import ChunkLayer
from app.rag.embedder import embed_text, embed_texts


def insert_chunks(note_id: UUID, chunks: List[Chunk]) -> None:
    """
    批量向量化并写入 Milvus。
    chunks 为空则直接返回；失败抛异常（由调用方保证不翻转 is_permanent）。
    """
    if not chunks:
        return

    texts = [c.text for c in chunks]
    vectors = embed_texts(texts)
    if len(vectors) != len(chunks):
        raise RuntimeError(
            f"嵌入数量与切片不一致: chunks={len(chunks)}, vectors={len(vectors)}"
        )

    note_id_str = str(note_id)
    ids = [c.id for c in chunks]
    note_ids = [note_id_str] * len(chunks)
    layers = [
        c.layer.value if isinstance(c.layer, ChunkLayer) else str(c.layer)
        for c in chunks
    ]
    start_secs = [
        float(c.start_sec)
        if c.start_sec is not None
        else settings.MISSING_FLOAT
        for c in chunks
    ]
    end_secs = [
        float(c.end_sec) if c.end_sec is not None else settings.MISSING_FLOAT
        for c in chunks
    ]
    pages = [
        int(c.page) if c.page is not None else settings.MISSING_INT for c in chunks
    ]
    metadatas = [dict(c.metadata or {}) for c in chunks]

    collection = get_collection()
    collection.insert(
        [
            ids,
            vectors,
            note_ids,
            texts,
            layers,
            start_secs,
            end_secs,
            pages,
            metadatas,
        ]
    )
    collection.flush()


def delete_chunks(note_id: UUID) -> None:
    """按 note_id 删除该笔记全部向量。"""
    collection = get_collection()
    collection.delete(expr=f'note_id == "{note_id}"')
    collection.flush()


def count_chunks(note_id: UUID) -> int:
    """统计某笔记在向量库中的 chunk 数（测试/验收用）。"""
    collection = get_collection()
    collection.load()
    results = collection.query(
        expr=f'note_id == "{note_id}"',
        output_fields=["id"],
        limit=16384,
    )
    return len(results)


def search_chunks(
    query: str,
    note_ids: Optional[List[str]] = None,
    top_k: int = 5,
) -> List[SearchResult]:
    """
    向量检索；可选按 note_id 过滤。
    返回 SearchResult 列表（含时间戳与 score）。
    """
    if not query or not query.strip():
        return []

    vector = embed_text(query.strip())
    collection = get_collection()
    collection.load()

    expr = None
    if note_ids:
        quoted = ", ".join(f'"{nid}"' for nid in note_ids)
        expr = f"note_id in [{quoted}]"

    hits = collection.search(
        data=[vector],
        anns_field="embedding",
        param={"metric_type": "COSINE", "params": {"ef": 64}},
        limit=top_k,
        expr=expr,
        output_fields=[
            "note_id",
            "text",
            "layer",
            "start_sec",
            "end_sec",
            "page",
            "metadata",
        ],
    )

    results: List[SearchResult] = []
    if not hits:
        return results

    for hit in hits[0]:
        entity = hit.entity
        start = entity.get("start_sec")
        end = entity.get("end_sec")
        page = entity.get("page")
        # 哨兵值还原为 None，便于上层使用
        if start is not None and float(start) == settings.MISSING_FLOAT:
            start = None
        if end is not None and float(end) == settings.MISSING_FLOAT:
            end = None
        if page is not None and int(page) == settings.MISSING_INT:
            page = None

        layer_raw = entity.get("layer") or ChunkLayer.SINGLE.value
        try:
            layer = ChunkLayer(layer_raw)
        except ValueError:
            layer = ChunkLayer.SINGLE

        meta = entity.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}

        results.append(
            SearchResult(
                note_id=UUID(str(entity.get("note_id"))),
                chunk_id=str(hit.id),
                chunk_text=str(entity.get("text") or ""),
                score=float(hit.score),
                layer=layer,
                start_sec=float(start) if start is not None else None,
                end_sec=float(end) if end is not None else None,
                page=int(page) if page is not None else None,
                metadata=meta,
            )
        )
    return results
