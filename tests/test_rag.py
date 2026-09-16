"""阶段3·B：切片 / 嵌入 / 入库 / 永久化 / 检索 验收。"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.db.milvus_client import get_collection  # noqa: E402
from app.db.postgres import init_db  # noqa: E402
from app.models.note import NoteCreate  # noqa: E402
from app.models.pipeline import TranscriptSegment  # noqa: E402
from app.notes import create_note, delete_note, permanentize_note  # noqa: E402
from app.rag import (  # noqa: E402
    chunk_text,
    count_chunks,
    embed_texts,
    retrieve,
)


@pytest.fixture(scope="module", autouse=True)
def _prepare():
    init_db()
    get_collection()
    yield


def _long_cleaned_text() -> str:
    # 足够长以产生多个 chunk（约 500 字一块）
    sentences = [
        f"这是第{i}句关于差旅助手的说明，涵盖高铁机票酒店预订与行程管理。"
        for i in range(1, 40)
    ]
    return "".join(sentences)


def test_chunk_text_sentence_boundary_and_timestamps():
    note_id = uuid4()
    text = (
        "欢迎使用差旅助手。"
        "它可以查询高铁与机票。"
        "也可以预订酒店并管理行程。"
    )
    segments = [
        TranscriptSegment(text="欢迎使用差旅助手。", start_sec=0.0, end_sec=2.0),
        TranscriptSegment(text="它可以查询高铁与机票。", start_sec=2.0, end_sec=5.0),
        TranscriptSegment(
            text="也可以预订酒店并管理行程。", start_sec=5.0, end_sec=8.5
        ),
    ]
    chunks = chunk_text(
        text,
        note_id=note_id,
        segments=segments,
        chunk_size=40,
        overlap=10,
    )
    assert len(chunks) >= 1
    assert all(c.layer.value == "single" for c in chunks)
    assert all(c.id.startswith(f"{note_id}:") for c in chunks)
    # 短文应挂上时间戳
    assert chunks[0].start_sec is not None
    assert chunks[-1].end_sec is not None
    assert chunks[0].start_sec <= chunks[-1].end_sec


def test_embed_texts_dimension():
    vectors = embed_texts(["差旅助手测试嵌入"])
    assert len(vectors) == 1
    assert len(vectors[0]) == settings.EMBEDDING_DIM


def test_permanentize_and_search():
    cleaned = _long_cleaned_text()
    segments = [
        TranscriptSegment(
            text=cleaned[i : i + 40],
            start_sec=float(i),
            end_sec=float(i + 40),
        )
        for i in range(0, min(200, len(cleaned)), 40)
    ]
    note = create_note(
        NoteCreate(
            title="RAG入库测试笔记",
            summary="差旅助手功能摘要：高铁机票酒店与行程管理。",
            full_text=cleaned,
            cleaned_text=cleaned,
            source_type="video",
            source_file_path="/data/uploads/rag_test.mp4",
            category="学习",
            is_permanent=False,
            mindmap="# 差旅助手\n- 交通\n- 酒店",
            source_segments=segments,
        )
    )
    note_id = note.id

    try:
        assert note.is_permanent is False

        permanent = permanentize_note(note_id)
        assert permanent.is_permanent is True

        n = count_chunks(note_id)
        assert n > 0

        hits = retrieve("差旅助手 高铁 机票 酒店", note_ids=[note_id], top_k=3)
        assert len(hits) >= 1
        assert all(h.note_id == note_id for h in hits)
        assert any("差旅" in h.chunk_text or "高铁" in h.chunk_text for h in hits)

        # 幂等：再次永久化不重复写入（count 不增加）
        again = permanentize_note(note_id)
        assert again.is_permanent is True
        assert count_chunks(note_id) == n

        delete_note(note_id)
        assert count_chunks(note_id) == 0
    except Exception:
        try:
            delete_note(note_id)
        except Exception:
            pass
        raise
