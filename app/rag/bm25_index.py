"""按笔记维护的内存 BM25 索引（服务重启后需重建）。"""

from __future__ import annotations

from threading import Lock
from typing import Any, Dict, List, Optional
from uuid import UUID

import jieba
from rank_bm25 import BM25Okapi

from app.config import settings
from app.rag.store import list_chunks

_LOCK = Lock()
# note_id -> {"bm25": BM25Okapi, "docs": list[dict]}
_INDEX: Dict[str, Dict[str, Any]] = {}


def _tokenize(text: str) -> List[str]:
    tokens = [t.strip() for t in jieba.lcut_for_search(text or "") if t.strip()]
    return tokens or [text.strip()] if (text or "").strip() else []


def build_bm25_index(note_id: str) -> None:
    """
    为指定笔记构建 BM25 索引。
    从 Milvus 读取该 note_id 的所有 chunk。
    """
    nid = str(note_id)
    docs = [d for d in list_chunks(nid) if (d.get("text") or "").strip()]
    if not docs:
        with _LOCK:
            _INDEX.pop(nid, None)
        print(f"[BM25] skip empty note_id={nid}")
        return

    corpus = [_tokenize(d["text"]) for d in docs]
    # 至少保证每篇有一个 token，避免 BM25 空文档
    corpus = [toks if toks else ["_"] for toks in corpus]
    bm25 = BM25Okapi(corpus)
    with _LOCK:
        _INDEX[nid] = {"bm25": bm25, "docs": docs}
    print(f"[BM25] indexed note_id={nid} chunks={len(docs)}")


def delete_bm25_index(note_id: str) -> None:
    """删除笔记时同步清理 BM25 索引。"""
    nid = str(note_id)
    with _LOCK:
        existed = _INDEX.pop(nid, None) is not None
    if existed:
        print(f"[BM25] deleted note_id={nid}")


def rebuild_all_bm25_indexes() -> int:
    """启动时按永久笔记重建内存索引。失败单条跳过。"""
    from app.notes.repository import list_notes

    rows = list_notes(is_permanent=True)
    built = 0
    for row in rows:
        nid = str(row.get("id") or "")
        if not nid:
            continue
        try:
            build_bm25_index(nid)
            built += 1
        except Exception as exc:  # noqa: BLE001
            print(f"[BM25] rebuild failed note_id={nid}: {exc}")
    print(f"[BM25] rebuild done notes={built}/{len(rows)}")
    return built


def search_bm25(
    query: str,
    note_ids: Optional[List[str]] = None,
    top_k: int = 10,
) -> List[dict]:
    """
    BM25 关键词检索。
    返回：{chunk_id, note_id, text, score, start_sec, end_sec, ...}
    """
    q = (query or "").strip()
    if not q or top_k <= 0:
        return []

    tokens = _tokenize(q)
    if not tokens:
        return []

    with _LOCK:
        if note_ids:
            targets = [str(n) for n in note_ids if str(n) in _INDEX]
            missing = [str(n) for n in note_ids if str(n) not in _INDEX]
        else:
            # None 或 []：搜全部已建索引的永久笔记
            targets = list(_INDEX.keys())
            missing = []

    for nid in missing:
        try:
            build_bm25_index(nid)
            targets.append(nid)
        except Exception as exc:  # noqa: BLE001
            print(f"[BM25] lazy build failed note_id={nid}: {exc}")

    scored: List[dict] = []
    with _LOCK:
        for nid in targets:
            pack = _INDEX.get(nid)
            if not pack:
                continue
            bm25: BM25Okapi = pack["bm25"]
            docs: List[dict] = pack["docs"]
            scores = bm25.get_scores(tokens)
            for doc, score in zip(docs, scores):
                item = dict(doc)
                item["score"] = float(score)
                scored.append(item)

    scored.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    raw_hits = scored[:top_k]
    floor = float(settings.RAG_BM25_MIN_SCORE)
    hits = [h for h in raw_hits if float(h.get("score") or 0.0) >= floor]
    print(
        f"[BM25] 原始 {len(raw_hits)} 条 → 分数过滤后 {len(hits)} 条"
        f"（min_score={floor}，索引笔记 {len(targets)} 篇）"
    )
    return hits


def indexed_note_ids() -> List[str]:
    with _LOCK:
        return list(_INDEX.keys())
