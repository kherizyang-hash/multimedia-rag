"""混合检索：HyDE 查询改写 + 向量 + BM25 + RRF。对外签名保持兼容。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional
from uuid import UUID

from app.config import settings
from app.models.chunk import SearchResult
from app.models.enums import ChunkLayer
from app.rag.bm25_index import search_bm25
from app.rag.fusion import rrf_fusion
from app.rag.hyde import generate_hypothetical_answer
from app.rag.store import search_chunks


def _normalize_note_ids(
    note_ids: Optional[List[UUID]],
) -> Optional[List[UUID]]:
    """None 或空列表 = 不限定笔记范围。"""
    if not note_ids:
        return None
    return list(note_ids)


def _filter_by_score_ratio(
    results: List[SearchResult],
    ratio: float,
    min_score: Optional[float] = None,
) -> List[SearchResult]:
    """
    先按绝对下限 RAG_SCORE_MIN 丢弃，再按最高分 * ratio 相对过滤。
    全部不达标则返回空列表（不再强留 1 条，避免无关问题仍被引用）。
    """
    if not results:
        return []
    floor = (
        float(settings.RAG_SCORE_MIN) if min_score is None else float(min_score)
    )
    kept = [r for r in results if float(r.score or 0.0) >= floor]
    dropped_min = len(results) - len(kept)
    if dropped_min:
        print(
            f"[FILTER] 绝对下限 score_min={floor:.4f} 丢弃 {dropped_min} 条，"
            f"剩余 {len(kept)} 条"
        )
    if not kept:
        return []

    ratio = max(0.0, float(ratio))
    max_score = max(float(r.score or 0.0) for r in kept)
    if max_score <= 0:
        return []
    threshold = max_score * ratio
    relative = [r for r in kept if float(r.score or 0.0) >= threshold]
    print(
        f"[FILTER] 相对阈值 max={max_score:.4f} × {ratio} = {threshold:.4f}，"
        f"保留 {len(relative)} 条"
    )
    return relative


def _vector_search(
    query: str,
    note_ids: Optional[List[UUID]] = None,
    top_k: int = 5,
) -> List[SearchResult]:
    """纯向量检索（原 retriever.search 实现）。"""
    scoped = _normalize_note_ids(note_ids)
    id_strs = [str(n) for n in scoped] if scoped else None
    return search_chunks(query=query, note_ids=id_strs, top_k=top_k)


def _result_to_dict(item: SearchResult) -> dict:
    return {
        "chunk_id": item.chunk_id,
        "note_id": str(item.note_id),
        "text": item.chunk_text,
        "score": item.score,
        "start_sec": item.start_sec,
        "end_sec": item.end_sec,
        "page": item.page,
        "layer": item.layer,
        "metadata": dict(item.metadata or {}),
    }


def _dict_to_result(item: dict) -> SearchResult:
    layer_raw = item.get("layer") or ChunkLayer.SINGLE
    if isinstance(layer_raw, ChunkLayer):
        layer = layer_raw
    else:
        try:
            layer = ChunkLayer(str(layer_raw))
        except ValueError:
            layer = ChunkLayer.SINGLE
    meta = item.get("metadata") or {}
    if not isinstance(meta, dict):
        meta = {}
    return SearchResult(
        note_id=UUID(str(item["note_id"])),
        chunk_id=str(item.get("chunk_id") or ""),
        chunk_text=str(item.get("text") or item.get("chunk_text") or ""),
        score=float(item.get("score") or 0.0),
        layer=layer,
        start_sec=item.get("start_sec"),
        end_sec=item.get("end_sec"),
        page=item.get("page"),
        metadata=meta,
    )


def retrieve(
    query: str,
    note_ids: Optional[List[UUID]] = None,
    top_k: int = 5,
    use_hyde: bool = True,
    use_bm25: bool = True,
) -> List[SearchResult]:
    """
    混合检索主入口。

    1. HyDE：语义关键词扩展（use_hyde=True；失败回退原 query）
    2. 并行：向量检索（HyDE 文本或原 query）+ BM25（原 query）
    3. RRF 融合 → 分数过滤（SCORE_MIN + 相对阈值）→ 排名截断 RAG_MAX_RESULTS → 再截 top_k
    """
    q = (query or "").strip()
    if not q:
        return []

    print(f"[RAG] 开始检索：{q[:80]}")
    scoped_ids = _normalize_note_ids(note_ids)
    vector_query = generate_hypothetical_answer(q) if use_hyde else q
    id_strs = [str(n) for n in scoped_ids] if scoped_ids else None
    vector_k = max(settings.RAG_VECTOR_TOP_K, top_k)
    bm25_k = max(settings.RAG_BM25_TOP_K, top_k)

    vector_hits: List[SearchResult] = []
    bm25_hits: List[dict] = []

    def _run_vector() -> List[SearchResult]:
        return _vector_search(vector_query, note_ids=scoped_ids, top_k=vector_k)

    def _run_bm25() -> List[dict]:
        return search_bm25(q, note_ids=id_strs, top_k=bm25_k)

    if use_bm25:
        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_v = pool.submit(_run_vector)
            fut_b = pool.submit(_run_bm25)
            vector_hits = fut_v.result()
            bm25_hits = fut_b.result()
    else:
        vector_hits = _run_vector()

    print(
        f"[RAG] 向量命中 {len(vector_hits)} 条，BM25 命中 {len(bm25_hits)} 条"
    )

    vector_dicts = [_result_to_dict(h) for h in vector_hits]

    if use_bm25 and bm25_hits:
        fused = rrf_fusion(vector_dicts, bm25_hits, k=settings.RAG_RRF_K)
        ranked = [_dict_to_result(x) for x in fused]
        fused_n = len(fused)
    else:
        ranked = list(vector_hits)
        fused_n = len(ranked)

    print(f"[RRF] 融合后 {fused_n} 条")
    if ranked:
        top_s = float(ranked[0].score or 0.0)
        bot_s = float(ranked[-1].score or 0.0)
        print(f"[RRF] 分数区间 {bot_s:.4f} ～ {top_s:.4f}")

    scored = _filter_by_score_ratio(
        ranked, settings.RAG_SCORE_THRESHOLD_RATIO
    )
    cap = max(0, int(settings.RAG_MAX_RESULTS))
    if cap <= 0:
        truncated = list(scored)
    else:
        truncated = scored[:cap]
    print(
        f"[FILTER] 分数过滤后 {len(scored)} 条 → 排名截断后 {len(truncated)} 条 "
        f"（max_results={cap}）"
    )
    results = truncated[:top_k]

    preview = q.replace("\n", " ")[:80]
    print(
        f'[RAG] query="{preview}" hyde={use_hyde} bm25={use_bm25} '
        f"vector_hits={len(vector_hits)}/{vector_k} "
        f"bm25_hits={len(bm25_hits)}/{bm25_k} "
        f"fused={fused_n} filtered={len(results)} "
        f"score_kept={len(scored)} rank_cap={len(truncated)} "
        f"top_k={top_k} max_results={cap} "
        f"score_ratio={settings.RAG_SCORE_THRESHOLD_RATIO} "
        f"score_min={settings.RAG_SCORE_MIN}"
    )
    return results


def search(
    query: str,
    note_ids: Optional[List[UUID]] = None,
    top_k: int = 5,
) -> List[SearchResult]:
    """对外统一检索接口（走配置默认的混合策略）。"""
    return retrieve(
        query,
        note_ids=note_ids,
        top_k=top_k,
        use_hyde=settings.RAG_USE_HYDE,
        use_bm25=settings.RAG_USE_BM25,
    )
