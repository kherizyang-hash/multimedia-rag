"""对话 API 基础验收（依赖 PG / Milvus / DashScope）。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.milvus_client import get_collection  # noqa: E402
from app.db.postgres import init_db  # noqa: E402
from app.models.note import NoteCreate  # noqa: E402
from app.models.pipeline import TranscriptSegment  # noqa: E402
from app.notes import create_note, delete_note, permanentize_note  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _prepare():
    init_db()
    get_collection()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def _make_note(*, permanent: bool) -> tuple:
    text = (
        "差旅助手可以查询高铁与机票，也可以预订酒店并管理行程。"
        "本测试用于验证对话接口能否基于笔记内容回答。"
    )
    note = create_note(
        NoteCreate(
            title="对话测试笔记",
            summary="差旅助手功能简介。",
            full_text=text,
            cleaned_text=text,
            source_type="video",
            source_file_path="/data/uploads/chat_test.mp4",
            category="学习",
            is_permanent=False,
            mindmap="# 差旅\n- 交通\n- 酒店",
            source_segments=[
                TranscriptSegment(text=text, start_sec=0.0, end_sec=10.0),
            ],
        )
    )
    if permanent:
        note = permanentize_note(note.id)
    return note


def test_chat_on_temporary_note(client: TestClient):
    note = _make_note(permanent=False)
    try:
        resp = client.post(
            "/api/chat/note",
            json={
                "note_id": str(note.id),
                "query": "这个笔记里提到了哪些交通方式？",
                "history": [],
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["answer"]
        assert isinstance(data["sources"], list)
        assert len(data["sources"]) >= 1
        assert data["sources"][0]["note_id"] == str(note.id)
        assert data["sources"][0]["title"] == note.title
    finally:
        delete_note(note.id)


def test_chat_global_with_permanent_note(client: TestClient):
    note = _make_note(permanent=True)
    try:
        resp = client.post(
            "/api/chat/global",
            json={
                "query": "差旅助手能做什么？",
                "note_ids": [str(note.id)],
                "history": [],
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["answer"]
        assert isinstance(data["sources"], list)
        # 有检索命中时 sources 带 note_id；极端空库时也可能为空，但本用例刚入库应命中
        if data["sources"]:
            assert any(s["note_id"] == str(note.id) for s in data["sources"])

        empty_ids = client.post(
            "/api/chat/global",
            json={
                "query": "差旅助手能做什么？",
                "note_ids": [],
                "history": [],
            },
        )
        assert empty_ids.status_code == 200, empty_ids.text
        empty_data = empty_ids.json()
        assert empty_data["answer"]
        assert isinstance(empty_data["sources"], list)
        assert empty_data["sources"], "note_ids=[] 应检索全部永久笔记，sources 不应为空"
        assert any(s["note_id"] == str(note.id) for s in empty_data["sources"])
    finally:
        delete_note(note.id)


def test_chat_note_not_found(client: TestClient):
    resp = client.post(
        "/api/chat/note",
        json={
            "note_id": "00000000-0000-0000-0000-000000000099",
            "query": "你好",
            "history": [],
        },
    )
    assert resp.status_code == 404
