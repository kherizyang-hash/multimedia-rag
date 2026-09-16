"""笔记管理 HTTP 路由。"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.models.note import Note
from app.notes import (
    NoteNotFoundError,
    delete_note,
    get_note,
    list_notes,
    permanentize_note,
)

router = APIRouter(prefix="/notes", tags=["notes"])


class NoteListResponse(BaseModel):
    items: List[Note]
    total: int = Field(..., description="当前过滤条件下的返回条数")


class DeleteResponse(BaseModel):
    note_id: UUID
    deleted: bool = True


@router.get("", response_model=NoteListResponse)
def api_list_notes(
    category: Optional[str] = Query(default=None, description="按分类过滤"),
    is_permanent: Optional[bool] = Query(
        default=None, description="True=已入库；False=临时速读"
    ),
) -> NoteListResponse:
    items = list_notes(category=category, is_permanent=is_permanent)
    return NoteListResponse(items=items, total=len(items))


@router.get("/{note_id}", response_model=Note)
def api_get_note(note_id: UUID) -> Note:
    try:
        return get_note(note_id)
    except NoteNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("/{note_id}/permanentize", response_model=Note)
def api_permanentize_note(note_id: UUID) -> Note:
    try:
        return permanentize_note(note_id)
    except NoteNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"永久化失败: {exc}",
        ) from exc


@router.delete("/{note_id}", response_model=DeleteResponse)
def api_delete_note(note_id: UUID) -> DeleteResponse:
    try:
        delete_note(note_id)
    except NoteNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除失败: {exc}",
        ) from exc
    return DeleteResponse(note_id=note_id, deleted=True)
