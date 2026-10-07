"""笔记业务编排。"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from app.config import settings
from app.models.note import Note, NoteCreate, NoteUpdate
from app.notes import repository
from app.notes.exceptions import NoteNotFoundError
from app.rag import (
    build_bm25_index,
    chunk_text,
    delete_bm25_index,
    delete_chunks,
    insert_chunks,
)


def _to_note(row: dict) -> Note:
    return Note.model_validate(row)


def create_note(data: NoteCreate) -> Note:
    """校验后写入 repository，返回 Note（id 由 DB 生成）。"""
    payload = data.model_dump(mode="json")
    print(f"[NOTES] 创建笔记 title={payload.get('title')!r}")
    row = repository.create_note(payload)
    note = _to_note(row)
    print(f"[NOTES] 已创建笔记 id={note.id}")
    return note


def get_note(note_id: UUID) -> Note:
    row = repository.get_note(str(note_id))
    if row is None:
        raise NoteNotFoundError(f"note not found: {note_id}")
    return _to_note(row)


def list_notes(
    category: Optional[str] = None,
    is_permanent: Optional[bool] = None,
) -> List[Note]:
    rows = repository.list_notes(category=category, is_permanent=is_permanent)
    return [_to_note(r) for r in rows]


def update_note(note_id: UUID, data: NoteUpdate) -> Note:
    updates = data.model_dump(exclude_unset=True, mode="json")
    if not repository.get_note(str(note_id)):
        raise NoteNotFoundError(f"note not found: {note_id}")
    row = repository.update_note(str(note_id), updates)
    if row is None:
        raise NoteNotFoundError(f"note not found: {note_id}")
    return _to_note(row)


def delete_note(note_id: UUID) -> None:
    """先清理向量，再删 PG 记录。"""
    if not repository.get_note(str(note_id)):
        raise NoteNotFoundError(f"note not found: {note_id}")
    print(f"[NOTES] 删除笔记 {note_id}（级联清向量）")
    delete_chunks(note_id)
    delete_bm25_index(str(note_id))
    repository.delete_note(str(note_id))
    print(f"[NOTES] 已删除笔记 {note_id}")


def permanentize_note(note_id: UUID) -> Note:
    """
    将临时笔记转为永久：切片 → 向量化 → 写入 Milvus → 翻转 is_permanent。

    幂等：已永久则直接返回，不重新切片/入库。
    任一步失败不翻转 is_permanent，异常向上抛出。
    """
    note = get_note(note_id)
    if note.is_permanent:
        print(f"[NOTES] 已永久，跳过重新入库 id={note_id}")
        try:
            build_bm25_index(str(note_id))
        except Exception as exc:  # noqa: BLE001
            print(f"[RAG] BM25 rebuild on permanent note skipped: {exc}")
        return note

    print(f"[NOTES] 开始永久化 id={note_id}")
    chunks = chunk_text(
        note.cleaned_text,
        note_id=note.id,
        segments=note.source_segments or [],
        chunk_size=settings.CHUNK_SIZE,
        overlap=settings.CHUNK_OVERLAP,
    )
    insert_chunks(note_id, chunks)

    row = repository.update_note(
        str(note_id),
        {"is_permanent": True},
    )
    if row is None:
        raise NoteNotFoundError(f"note not found: {note_id}")
    try:
        build_bm25_index(str(note_id))
    except Exception as exc:  # noqa: BLE001
        print(f"[RAG] BM25 index after permanentize failed: {exc}")
    print(f"[NOTES] 永久化完成 id={note_id} chunks={len(chunks)}")
    return _to_note(row)
