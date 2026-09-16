"""异步处理任务 HTTP 路由。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.tasks import TaskNotFoundError, get_task

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskStatusResponse(BaseModel):
    job_id: UUID
    status: str
    progress: int = Field(ge=0, le=100)
    current_step: Optional[str] = None
    note_id: Optional[UUID] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@router.get("/{job_id}", response_model=TaskStatusResponse)
def api_get_task(job_id: UUID) -> TaskStatusResponse:
    try:
        row = get_task(job_id)
    except TaskNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return TaskStatusResponse(
        job_id=row["id"],
        status=row["status"],
        progress=int(row.get("progress") or 0),
        current_step=row.get("current_step"),
        note_id=row.get("note_id"),
        error_message=row.get("error_message") or None,
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )
