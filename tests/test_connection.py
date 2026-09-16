"""连通性测试：Zilliz Cloud 连接 + 列出 / 创建 note_chunks。

可直接运行:
  python tests/test_connection.py

或:
  python -m pytest tests/test_connection.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

# 保证从任意 cwd 运行都能 import app
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def run_connection_check() -> int:
    print("=== Zilliz / Milvus connectivity check ===")
    try:
        from app.config import settings
        from app.db.milvus_client import (
            create_chunks_collection,
            disconnect,
            get_milvus_connection,
            list_collections,
        )

        if not settings.MILVUS_URI or not settings.MILVUS_TOKEN:
            print("[FAIL] MILVUS_URI / MILVUS_TOKEN 未配置，请检查 .env")
            return 1

        print(f"URI: {settings.MILVUS_URI}")
        get_milvus_connection()
        print("[OK] connected")

        names = list_collections()
        print(f"[OK] collections: {names}")

        col = create_chunks_collection()
        print(f"[OK] collection ready: {col.name}")

        names_after = list_collections()
        print(f"[OK] collections after ensure: {names_after}")

        disconnect()
        print("=== SUCCESS ===")
        return 0
    except Exception as exc:  # noqa: BLE001 — 测试脚本需打印具体错误
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        return 1


def test_zilliz_connection():
    """pytest 入口。"""
    assert run_connection_check() == 0


if __name__ == "__main__":
    raise SystemExit(run_connection_check())
