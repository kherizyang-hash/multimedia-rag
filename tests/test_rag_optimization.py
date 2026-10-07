"""HyDE + BM25 + RRF 混合检索验收。"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.milvus_client import get_collection  # noqa: E402
from app.db.postgres import init_db  # noqa: E402
from app.models.note import NoteCreate  # noqa: E402
from app.models.pipeline import TranscriptSegment  # noqa: E402
from app.notes import create_note, delete_note, permanentize_note  # noqa: E402
from app.rag.fusion import rrf_fusion  # noqa: E402
from app.rag.retriever import retrieve  # noqa: E402

UNIQUE_PHRASE = "紫檀木向量仓"
EXPECTED_SNIPPET = "紫檀木向量仓采用 HNSW 索引存储差旅助手的会话记录。"


@pytest.fixture(scope="module", autouse=True)
def _prepare():
    init_db()
    get_collection()
    yield


def test_empty_note_ids_means_unscoped():
    from app.rag.retriever import _normalize_note_ids

    assert _normalize_note_ids(None) is None
    assert _normalize_note_ids([]) is None


def test_filter_by_score_ratio_keeps_relative_hits():
    from app.models.chunk import SearchResult
    from app.models.enums import ChunkLayer
    from app.rag.retriever import _filter_by_score_ratio

    nid = uuid4()

    def hit(cid: str, score: float) -> SearchResult:
        return SearchResult(
            note_id=nid,
            chunk_id=cid,
            chunk_text=cid,
            score=score,
            layer=ChunkLayer.SINGLE,
        )

    ranked = [hit("high", 0.04), hit("mid", 0.02), hit("low", 0.005)]
    kept = _filter_by_score_ratio(ranked, 0.3, min_score=0.0)
    assert [h.chunk_id for h in kept] == ["high", "mid"]

    kept_ratio = _filter_by_score_ratio(ranked, 0.5, min_score=0.0)
    assert [h.chunk_id for h in kept_ratio] == ["high", "mid"]

    kept_min = _filter_by_score_ratio(ranked, 0.0, min_score=0.01)
    assert [h.chunk_id for h in kept_min] == ["high", "mid"]

    empty = _filter_by_score_ratio(ranked, 0.5, min_score=0.05)
    assert empty == []


def test_rank_cap_after_score_filter():
    from app.models.chunk import SearchResult
    from app.models.enums import ChunkLayer
    from app.rag.retriever import _filter_by_score_ratio

    nid = uuid4()

    def hit(cid: str, score: float) -> SearchResult:
        return SearchResult(
            note_id=nid,
            chunk_id=cid,
            chunk_text=cid,
            score=score,
            layer=ChunkLayer.SINGLE,
        )

    ranked = [
        hit("a", 0.031),
        hit("b", 0.028),
        hit("c", 0.022),
        hit("d", 0.016),
        hit("e", 0.013),
        hit("f", 0.005),
    ]
    scored = _filter_by_score_ratio(ranked, 0.5, min_score=0.01)
    assert all(float(h.score) >= 0.01 for h in scored)
    capped = scored[:3]
    assert [h.chunk_id for h in capped] == ["a", "b", "c"]


def test_clear_sources_when_kb_miss_phrase():
    from unittest.mock import patch

    from app.chat.service import _run_chat
    from app.models.chat import ChatSource

    src = [
        ChatSource(note_id=uuid4(), title="t", start_sec=None, hit_count=2)
    ]
    with patch(
        "app.chat.service.chat_completion",
        return_value="个人知识库中没有找到相关内容。今天天气需看当地预报。",
    ):
        resp = _run_chat(
            query="今天天气怎么样？",
            context="（无）",
            history=None,
            sources=src,
        )
    assert resp.sources == []
    assert "个人知识库中没有找到相关内容" in resp.answer


def test_sources_dedup_by_note_id():
    from unittest.mock import patch

    from app.chat.service import _sources_from_hits
    from app.models.chunk import SearchResult
    from app.models.enums import ChunkLayer
    from app.notes.exceptions import NoteNotFoundError

    n1, n2 = uuid4(), uuid4()

    def hit(nid, cid: str, score: float) -> SearchResult:
        return SearchResult(
            note_id=nid,
            chunk_id=cid,
            chunk_text=cid,
            score=score,
            layer=ChunkLayer.SINGLE,
            start_sec=1.0 if cid.endswith("a") else 9.0,
        )

    hits = [
        hit(n1, "n1a", 0.02),
        hit(n1, "n1b", 0.08),
        hit(n2, "n2a", 0.05),
        hit(n1, "n1c", 0.03),
    ]
    with patch(
        "app.chat.service.get_note",
        side_effect=NoteNotFoundError("skip db"),
    ):
        sources = _sources_from_hits(hits)
    assert len(sources) == 2
    by_id = {s.note_id: s for s in sources}
    assert by_id[n1].hit_count == 3
    assert by_id[n1].start_sec == 9.0
    assert by_id[n2].hit_count == 1


def test_rrf_fusion_prefers_agreement():
    vector = [
        {"chunk_id": "a", "note_id": "n", "text": "A", "score": 0.9},
        {"chunk_id": "b", "note_id": "n", "text": "B", "score": 0.8},
    ]
    bm25 = [
        {"chunk_id": "b", "note_id": "n", "text": "B", "score": 12.0},
        {"chunk_id": "c", "note_id": "n", "text": "C", "score": 3.0},
    ]
    fused = rrf_fusion(vector, bm25, k=60)
    assert fused[0]["chunk_id"] == "b"
    ids = [x["chunk_id"] for x in fused]
    assert ids == ["b", "a", "c"]


def _corpus_text() -> str:
    filler_a = (
        "高铁查询模块负责时刻表与余票展示，用户可以按出发地和到达地筛选车次。"
        "机票模块对接多家航司，展示仓位价格，不涉及向量数据库实现细节。"
    )
    filler_b = (
        "酒店预订支持按星级和商圈过滤，行程管理把交通与住宿排进同一时间轴。"
        "这些功能面向差旅助手的日程视图，与会话持久化方案无关。"
    )
    unique = (
        f"{EXPECTED_SNIPPET}"
        "当用户询问会话存在哪里时，应明确回答采用紫檀木向量仓而不是普通关系表。"
    )
    filler_c = (
        "思维导图用于展示差旅助手的功能分支：交通、酒店、行程、提醒。"
        "摘要应当写得自然，避免说明书体。本节不含任何向量仓专有名词。"
    )
    return filler_a + filler_b + unique + filler_c


def test_hybrid_retrieve_modes_and_top1():
    cleaned = _corpus_text()
    segments = [
        TranscriptSegment(text=cleaned[:80], start_sec=0.0, end_sec=8.0),
        TranscriptSegment(text=EXPECTED_SNIPPET, start_sec=8.0, end_sec=16.0),
        TranscriptSegment(text=cleaned[-80:], start_sec=16.0, end_sec=24.0),
    ]
    note = create_note(
        NoteCreate(
            title="混合检索验收笔记",
            summary="差旅助手会话存储于紫檀木向量仓。",
            full_text=cleaned,
            cleaned_text=cleaned,
            source_type="video",
            source_file_path=f"/data/uploads/rag_opt_{uuid4().hex}.mp4",
            category="学习",
            is_permanent=False,
            mindmap="flowchart LR\n  root[\"差旅助手\"]",
            source_segments=segments,
        )
    )
    note_id = note.id
    query = "差旅助手的会话存在哪种向量仓？"

    try:
        permanentize_note(note_id)

        vector_hits = retrieve(
            query, note_ids=[note_id], top_k=3, use_hyde=False, use_bm25=False
        )
        hyde_hits = retrieve(
            query, note_ids=[note_id], top_k=3, use_hyde=True, use_bm25=False
        )
        bm25_hits = retrieve(
            query, note_ids=[note_id], top_k=3, use_hyde=False, use_bm25=True
        )
        hybrid_hits = retrieve(
            query, note_ids=[note_id], top_k=3, use_hyde=True, use_bm25=True
        )

        print("[test] vector", [h.chunk_text[:40] for h in vector_hits])
        print("[test] hyde", [h.chunk_text[:40] for h in hyde_hits])
        print("[test] bm25", [h.chunk_text[:40] for h in bm25_hits])
        print("[test] hybrid", [h.chunk_text[:40] for h in hybrid_hits])

        assert len(vector_hits) >= 1
        assert len(hyde_hits) >= 1
        assert len(bm25_hits) >= 1
        assert len(hybrid_hits) >= 1
        assert UNIQUE_PHRASE in hybrid_hits[0].chunk_text
    finally:
        try:
            delete_note(note_id)
        except Exception:
            pass
