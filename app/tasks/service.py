"""处理任务业务编排。"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from app.tasks import repository as repo


class TaskNotFoundError(Exception):
    pass


def create_task(task_type: str) -> dict:
    t = (task_type or "").strip().lower()
    if t not in {"video", "bilibili", "document"}:
        raise ValueError(f"不支持的 task_type: {task_type}")
    return repo.create_task(t)


def get_task(task_id: UUID) -> dict:
    row = repo.get_task(task_id)
    if not row:
        raise TaskNotFoundError(f"任务不存在: {task_id}")
    return row


def mark_running(task_id: UUID, current_step: str = "开始处理", progress: int = 1) -> dict:
    return repo.update_task(
        task_id,
        status="running",
        progress=progress,
        current_step=current_step,
    ) or get_task(task_id)


def update_progress(
    task_id: UUID,
    progress: int,
    current_step: str,
) -> dict:
    return repo.update_task(
        task_id,
        status="running",
        progress=progress,
        current_step=current_step,
    ) or get_task(task_id)


def complete_task(task_id: UUID, note_id: UUID) -> dict:
    return repo.update_task(
        task_id,
        status="done",
        progress=100,
        current_step="完成",
        note_id=note_id,
        error_message="",
    ) or get_task(task_id)


def fail_task(task_id: UUID, error_message: str) -> dict:
    return repo.update_task(
        task_id,
        status="failed",
        current_step="失败",
        error_message=(error_message or "未知错误")[:2000],
    ) or get_task(task_id)
