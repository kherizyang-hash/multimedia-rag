"""笔记模块公共接口。"""

from app.notes.exceptions import NoteNotFoundError, NoteValidationError
from app.notes.service import (
    create_note,
    delete_note,
    get_note,
    list_notes,
    permanentize_note,
    update_note,
)

__all__ = [
    "create_note",
    "get_note",
    "list_notes",
    "update_note",
    "delete_note",
    "permanentize_note",
    "NoteNotFoundError",
    "NoteValidationError",
]
