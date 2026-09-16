"""Notes CRUD 验收测试（依赖真实 PostgreSQL；永久化会写 Milvus）。"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.postgres import init_db  # noqa: E402
from app.models.note import NoteCreate, NoteUpdate  # noqa: E402
from app.models.pipeline import TranscriptSegment  # noqa: E402
from app.notes import (  # noqa: E402
    NoteNotFoundError,
    create_note,
    delete_note,
    get_note,
    list_notes,
    permanentize_note,
    update_note,
)
from app.rag import count_chunks  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _prepare_db():
    init_db()
    yield


@pytest.fixture
def sample_create() -> NoteCreate:
    text = "清洗后的测试全文，用于验证笔记 CRUD 与永久化入库。"
    return NoteCreate(
        title="测试笔记",
        summary="这是一条测试摘要",
        full_text="完整的测试全文内容...",
        cleaned_text=text,
        source_type="video",
        source_file_path="/data/uploads/demo.mp4",
        category="学习",
        is_permanent=False,
        mindmap="# 测试导图\n- 节点1\n- 节点2",
        source_segments=[
            TranscriptSegment(text=text, start_sec=0.0, end_sec=3.5),
        ],
    )


def test_notes_crud_and_permanentize(sample_create: NoteCreate):
    note = create_note(sample_create)
    assert isinstance(note.id, UUID)
    assert note.is_permanent is False
    assert note.title == "测试笔记"
    assert note.mindmap is not None and "节点1" in note.mindmap
    assert note.source_segments is not None and len(note.source_segments) == 1
    note_id = note.id

    try:
        fetched = get_note(note_id)
        assert fetched.id == note_id
        assert fetched.summary == sample_create.summary
        assert fetched.cleaned_text == sample_create.cleaned_text

        all_notes = list_notes()
        assert any(n.id == note_id for n in all_notes)

        by_cat = list_notes(category="学习")
        assert any(n.id == note_id for n in by_cat)

        temps = list_notes(is_permanent=False)
        assert any(n.id == note_id for n in temps)

        permanents = list_notes(is_permanent=True)
        assert all(n.id != note_id for n in permanents)

        updated = update_note(
            note_id,
            NoteUpdate(title="测试笔记-已改", category="工作"),
        )
        assert updated.title == "测试笔记-已改"
        assert updated.category == "工作"

        permanent = permanentize_note(note_id)
        assert permanent.is_permanent is True
        assert count_chunks(note_id) >= 1

        again = permanentize_note(note_id)
        assert again.is_permanent is True
        assert again.id == note_id

        delete_note(note_id)
        assert count_chunks(note_id) == 0

        with pytest.raises(NoteNotFoundError):
            get_note(note_id)

    except Exception:
        try:
            delete_note(note_id)
        except Exception:
            pass
        raise
