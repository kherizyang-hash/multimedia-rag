"""PostgreSQL 连接与 notes 表初始化。"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg2
from psycopg2.extensions import connection as PgConnection

from app.config import settings

_NOTES_DDL = """
CREATE TABLE IF NOT EXISTS notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    summary TEXT NOT NULL,
    full_text TEXT NOT NULL,
    cleaned_text TEXT NOT NULL,
    source_type VARCHAR(20) NOT NULL,
    source_url VARCHAR(500),
    source_file_path VARCHAR(500),
    category VARCHAR(50) NOT NULL DEFAULT '学习',
    is_permanent BOOLEAN NOT NULL DEFAULT FALSE,
    mindmap TEXT,
    source_segments JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_TASKS_DDL = """
CREATE TABLE IF NOT EXISTS processing_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    progress INT NOT NULL DEFAULT 0,
    current_step VARCHAR(255),
    error_message TEXT,
    note_id UUID,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_INDEX_DDL = [
    "CREATE INDEX IF NOT EXISTS idx_notes_category ON notes(category);",
    "CREATE INDEX IF NOT EXISTS idx_notes_is_permanent ON notes(is_permanent);",
    "CREATE INDEX IF NOT EXISTS idx_notes_created_at ON notes(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_tasks_status ON processing_tasks(status);",
]

# 已有库增量迁移（幂等）
_MIGRATE_DDL = [
    "ALTER TABLE notes ADD COLUMN IF NOT EXISTS source_segments JSONB;",
]


def get_db_connection() -> PgConnection:
    """每次调用新建一个 psycopg2 连接。"""
    if not settings.PG_HOST:
        raise RuntimeError("PG_HOST 未配置，请在 .env 中填写（参见 .env.example）")
    return psycopg2.connect(
        host=settings.PG_HOST,
        port=settings.PG_PORT,
        user=settings.PG_USER,
        password=settings.PG_PASSWORD,
        dbname=settings.PG_DATABASE,
    )


@contextmanager
def db_cursor(*, commit: bool = True) -> Iterator:
    """短生命周期连接 + cursor；成功则 commit，异常 rollback。"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            yield cur
            if commit:
                conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """创建 notes / processing_tasks 表及索引（幂等）；并对旧表补齐新列。"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # PG13+ 内置 gen_random_uuid；旧版可依赖 pgcrypto
            cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
            cur.execute(_NOTES_DDL)
            cur.execute(_TASKS_DDL)
            for stmt in _MIGRATE_DDL:
                cur.execute(stmt)
            for stmt in _INDEX_DDL:
                cur.execute(stmt)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
