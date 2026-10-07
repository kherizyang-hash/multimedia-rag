"""map-reduce 切分逻辑（不调 API）。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.pipeline.summarizer import _find_soft_cut, _split_for_map  # noqa: E402


def test_find_soft_cut_prefers_sentence_end():
    text = "甲甲甲。" + ("乙" * 100) + "丙丙丙。丁丁丁"
    # target 落在乙中间偏后；应回退到「甲甲甲。」或前进到「丙丙丙。」
    cut = _find_soft_cut(text, 80)
    assert text[cut - 1] in "。！？\n" or cut == 80


def test_split_plain_respects_chunk_size():
    body = ("这是一句测试话。" * 200)
    chunks = _split_for_map(body, segments=None, chunk_size=350)
    assert len(chunks) >= 2
    # 软切可略低于阈值，不应远超（允许 +200 前瞻窗口）
    assert all(len(c["text"]) <= 550 for c in chunks)
    assert max(len(c["text"]) for c in chunks) <= 350 + 50
    rebuilt = "".join(c["text"] for c in chunks)
    assert abs(len(rebuilt) - len(body)) <= 5


def test_summarize_short_uses_single_path():
    from unittest.mock import patch

    from app.pipeline.summarizer import summarize_long_text

    with patch(
        "app.pipeline.summarizer.call_qwen",
        return_value={"title": "短", "summary": "摘要", "mindmap": "flowchart LR\n  root[\"短\"]"},
    ) as mocked:
        with patch("app.pipeline.summarizer._map_one_chunk") as map_mock:
            out = summarize_long_text("短稿" * 10, segments=None, task_id=None)
    assert out["title"] == "短"
    mocked.assert_called_once()
    map_mock.assert_not_called()


def test_summarize_long_runs_map_then_reduce():
    from unittest.mock import patch

    from app.config import settings
    from app.pipeline.summarizer import summarize_long_text

    long_text = ("长段内容。" * 1200)  # 5*1200=6000 > 5000
    assert len(long_text) > settings.QWEN_SINGLE_THRESHOLD

    with patch(
        "app.pipeline.summarizer._map_one_chunk",
        return_value="- 要点甲\n- 要点乙",
    ) as map_mock:
        with patch(
            "app.pipeline.summarizer.call_qwen",
            return_value={
                "title": "长片",
                "summary": "合并后的笔记",
                "mindmap": "flowchart LR\n  root[\"长片\"]",
            },
        ) as reduce_mock:
            out = summarize_long_text(long_text, segments=None, task_id=None)
    assert out["summary"] == "合并后的笔记"
    assert map_mock.call_count >= 2
    reduce_mock.assert_called_once()


def test_split_with_segments_keeps_timestamps():
    segs = []
    t = 0.0
    for i in range(20):
        piece = f"第{i}段内容。" + ("字" * 40)
        segs.append(
            {"text": piece, "start_sec": t, "end_sec": t + 10.0}
        )
        t += 10.0
    cleaned = "".join(s["text"] for s in segs)
    chunks = _split_for_map(cleaned, segs, chunk_size=200)
    assert len(chunks) >= 2
    assert chunks[0]["start_sec"] == 0.0
    assert chunks[0]["end_sec"] is not None
    assert chunks[-1]["end_sec"] == segs[-1]["end_sec"]
