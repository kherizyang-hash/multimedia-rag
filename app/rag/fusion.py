"""RRF（Reciprocal Rank Fusion）融合多路检索结果。"""

from __future__ import annotations

from typing import Dict, List


def rrf_fusion(
    vector_results: List[dict],
    bm25_results: List[dict],
    k: int = 60,
) -> List[dict]:
    """
    RRF 融合两路已排序结果。

    公式：score(d) = Σ 1 / (k + rank_i(d))
    """
    k = max(int(k), 1)
    scores: Dict[str, float] = {}
    docs: Dict[str, dict] = {}

    for rank, item in enumerate(vector_results or [], start=1):
        cid = str(item.get("chunk_id") or "")
        if not cid:
            continue
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
        docs[cid] = dict(item)

    for rank, item in enumerate(bm25_results or [], start=1):
        cid = str(item.get("chunk_id") or "")
        if not cid:
            continue
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
        if cid not in docs:
            docs[cid] = dict(item)

    fused: List[dict] = []
    for cid, score in scores.items():
        row = dict(docs[cid])
        row["score"] = float(score)
        fused.append(row)
    fused.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    return fused
