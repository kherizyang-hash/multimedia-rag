"""Notes 表仓储：纯 SQL，返回 dict（字段名与 Note 模型一致）。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from psycopg2.extras import Json, RealDictCursor

from app.db.postgres import get_db_connection

_COLUMNS = (
    "id, title, summary, full_text, cleaned_text, source_type, "
    "source_url, source_file_path, category, is_permanent, mindmap, "
    "source_segments, created_at, updated_at"
)


def _serialize_segments(value: Any) -> Any:
    """将 segments 转为可写入 JSONB 的结构。"""
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return Json(value.model_dump(mode="json"))
    if isinstance(value, list):
        items = []
        for item in value:
            if hasattr(item, "model_dump"):
                items.append(item.model_dump(mode="json"))
            else:
                items.append(item)
        return Json(items)
    if isinstance(value, str):
        return Json(json.loads(value))
    return Json(value)


def _row_to_dict(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    return dict(row)


def create_note(note_data: dict) -> dict:
    """插入 notes 表，返回完整记录（含 id、时间戳）。调用方传入的 id 被忽略。"""
    sql = f"""
        INSERT INTO notes (
            title, summary, full_text, cleaned_text,
            source_type, source_url, source_file_path,
            category, is_permanent, mindmap, source_segments
        ) VALUES (
            %(title)s, %(summary)s, %(full_text)s, %(cleaned_text)s,
            %(source_type)s, %(source_url)s, %(source_file_path)s,
            %(category)s, %(is_permanent)s, %(mindmap)s, %(source_segments)s
        )
        RETURNING {_COLUMNS}
    """
    payload = {
        "title": note_data["title"],
        "summary": note_data["summary"],
        "full_text": note_data["full_text"],
        "cleaned_text": note_data["cleaned_text"],
        "source_type": note_data["source_type"],
        "source_url": note_data.get("source_url"),
        "source_file_path": note_data.get("source_file_path"),
        "category": note_data.get("category") or "学习",
        "is_permanent": bool(note_data.get("is_permanent", False)),
        "mindmap": note_data.get("mindmap"),
        "source_segments": _serialize_segments(note_data.get("source_segments")),
    }
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, payload)
            row = cur.fetchone()
        conn.commit()
        return _row_to_dict(row)  # type: ignore[return-value]
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_note(note_id: str) -> dict | None:
    """根据 UUID 查询单条笔记。"""
    sql = f"SELECT {_COLUMNS} FROM notes WHERE id = %s"
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (str(note_id),))
            return _row_to_dict(cur.fetchone())
    finally:
        conn.close()


def list_notes(
    category: str | None = None,
    is_permanent: bool | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """列表查询；按 created_at DESC。"""
    clauses: List[str] = []
    params: List[Any] = []
    if category is not None:
        clauses.append("category = %s")
        params.append(category)
    if is_permanent is not None:
        clauses.append("is_permanent = %s")
        params.append(is_permanent)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT {_COLUMNS} FROM notes
        {where}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows]  # type: ignore[misc]
    finally:
        conn.close()


def update_note(note_id: str, updates: dict) -> dict | None:
    """更新传入的非空字段，并刷新 updated_at。"""
    allowed = {
        "title",
        "summary",
        "full_text",
        "cleaned_text",
        "source_type",
        "source_url",
        "source_file_path",
        "category",
        "is_permanent",
        "mindmap",
        "source_segments",
    }
    fields = {k: v for k, v in updates.items() if k in allowed and v is not None}
    if not fields:
        return get_note(note_id)

    if "source_segments" in fields:
        fields["source_segments"] = _serialize_segments(fields["source_segments"])

    fields["updated_at"] = datetime.utcnow()
    set_clause = ", ".join(f"{k} = %({k})s" for k in fields)
    sql = f"""
        UPDATE notes SET {set_clause}
        WHERE id = %(id)s
        RETURNING {_COLUMNS}
    """
    params = {**fields, "id": str(note_id)}
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        conn.commit()
        return _row_to_dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_note(note_id: str) -> bool:
    """仅删除 PG 记录；向量级联由 service 调用 rag。"""
    sql = "DELETE FROM notes WHERE id = %s RETURNING id"
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (str(note_id),))
            deleted = cur.fetchone() is not None
        conn.commit()
        return deleted
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def count_notes(
    category: str | None = None,
    is_permanent: bool | None = None,
) -> int:
    clauses: List[str] = []
    params: List[Any] = []
    if category is not None:
        clauses.append("category = %s")
        params.append(category)
    if is_permanent is not None:
        clauses.append("is_permanent = %s")
        params.append(is_permanent)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT COUNT(*) FROM notes {where}"
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return int(row[0]) if row else 0
    finally:
        conn.close()
