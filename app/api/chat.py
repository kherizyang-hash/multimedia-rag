"""对话相关 HTTP 路由。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.chat.service import chat_global, chat_on_note
from app.models.chat import ChatResponse, GlobalChatRequest, NoteChatRequest
from app.notes.exceptions import NoteNotFoundError

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/note", response_model=ChatResponse)
def api_chat_on_note(body: NoteChatRequest) -> ChatResponse:
    print(f"[API] POST /api/chat/note note_id={body.note_id}")
    try:
        return chat_on_note(
            note_id=body.note_id,
            user_query=body.query,
            history=body.history,
        )
    except NoteNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"笔记内讨论失败: {exc}",
        ) from exc


@router.post("/global", response_model=ChatResponse)
def api_chat_global(body: GlobalChatRequest) -> ChatResponse:
    print(f"[API] POST /api/chat/global query={body.query[:80]!r}")
    try:
        return chat_global(
            user_query=body.query,
            note_ids=body.note_ids,
            history=body.history,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"全局问答失败: {exc}",
        ) from exc
