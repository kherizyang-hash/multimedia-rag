"""处理任务仓储：processing_tasks 表 CRUD。"""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from psycopg2.extras import RealDictCursor

from app.db.postgres import get_db_connection

_COLUMNS = (
    "id, task_type, status, progress, current_step, "
    "error_message, note_id, created_at, updated_at"
)


def _row(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return dict(row) if row else None


def create_task(task_type: str) -> dict:
    sql = f"""
        INSERT INTO processing_tasks (task_type, status, progress, current_step)
        VALUES (%(task_type)s, 'pending', 0, '排队中')
        RETURNING {_COLUMNS}
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, {"task_type": task_type})
            row = cur.fetchone()
        conn.commit()
        return _row(row)  # type: ignore[return-value]
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_task(task_id: UUID) -> Optional[dict]:
    sql = f"SELECT {_COLUMNS} FROM processing_tasks WHERE id = %s"
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (str(task_id),))
            return _row(cur.fetchone())
    finally:
        conn.close()


def update_task(
    task_id: UUID,
    *,
    status: Optional[str] = None,
    progress: Optional[int] = None,
    current_step: Optional[str] = None,
    error_message: Optional[str] = None,
    note_id: Optional[UUID] = None,
) -> Optional[dict]:
    fields = ["updated_at = CURRENT_TIMESTAMP"]
    params: Dict[str, Any] = {"id": str(task_id)}
    if status is not None:
        fields.append("status = %(status)s")
        params["status"] = status
    if progress is not None:
        fields.append("progress = %(progress)s")
        params["progress"] = max(0, min(100, int(progress)))
    if current_step is not None:
        fields.append("current_step = %(current_step)s")
        params["current_step"] = current_step
    if error_message is not None:
        fields.append("error_message = %(error_message)s")
        params["error_message"] = error_message
    if note_id is not None:
        fields.append("note_id = %(note_id)s")
        params["note_id"] = str(note_id)

    sql = f"""
        UPDATE processing_tasks
        SET {", ".join(fields)}
        WHERE id = %(id)s
        RETURNING {_COLUMNS}
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        conn.commit()
        return _row(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
