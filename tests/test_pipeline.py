"""阶段2/3：视频预处理 + 千问摘要测试。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.pipeline import process_video  # noqa: E402
from app.pipeline.cleaner import clean_segments, clean_text  # noqa: E402
from app.pipeline.note_generator import build_prompt, parse_response  # noqa: E402
from app.pipeline.video import extract_audio  # noqa: E402
from app.pipeline.zh_convert import to_simplified  # noqa: E402

SHORT_VIDEO = ROOT / "data" / "uploads" / "sample_short.mp4"
FULL_VIDEO = ROOT / "data" / "uploads" / "sample.mp4"


def test_to_simplified():
    assert to_simplified("這是繁體字簡歷項目") == "这是繁体字简历项目"


def test_clean_text_removes_fillers():
    raw = "嗯 那个 我们今天就是说 学习 RAG，然后 再实践啊。"
    cleaned = clean_text(raw)
    assert cleaned
    for word in ("嗯", "那个", "就是说", "然后", "啊"):
        assert word not in cleaned
    assert "学习" in cleaned or "RAG" in cleaned


def test_clean_segments_keeps_timestamps():
    segs = clean_segments(
        [{"id": 0, "start": 0.0, "end": 1.5, "text": "嗯 你好啊"}]
    )
    assert len(segs) == 1
    assert segs[0]["start"] == 0.0
    assert segs[0]["end"] == 1.5
    assert "嗯" not in segs[0]["text"]
    assert "你好" in segs[0]["text"]


def test_extract_audio(tmp_path):
    if not SHORT_VIDEO.is_file():
        pytest.skip(f"缺少短视频: {SHORT_VIDEO}")
    out = tmp_path / "out.wav"
    path = extract_audio(str(SHORT_VIDEO), str(out))
    assert Path(path).is_file()
    assert Path(path).stat().st_size > 1000


def test_parse_response():
    content = """【标题】
智能差旅助手概览

【总结笔记】
这是一段测试摘要，包含若干要点。

【思维导图】
mindmap
  root((差旅助手))
    交通
    酒店
"""
    parsed = parse_response(content)
    assert parsed["title"] and "差旅" in parsed["title"]
    assert parsed["summary"] and "测试摘要" in parsed["summary"]
    assert parsed["mindmap"] and "mindmap" in parsed["mindmap"]


def test_build_prompt_contains_text():
    prompt = build_prompt("转写稿内容ABC")
    assert "转写稿内容ABC" in prompt
    assert "【标题】" in prompt
    assert "【总结笔记】" in prompt
    assert "【思维导图】" in prompt
    # Prompt：段落与列表穿插，导图用 Mermaid
    assert "1. / 1.1 / 1.2" in prompt or "厚大纲" in prompt
    assert "该分则分" in prompt or "列表" in prompt
    assert "flowchart LR" in prompt or "mindmap" in prompt


def test_process_video_with_qwen():
    """短视频全链路：简体文稿 + 千问摘要/导图。"""
    video = SHORT_VIDEO if SHORT_VIDEO.is_file() else FULL_VIDEO
    if not video.is_file():
        pytest.skip("缺少测试视频 data/uploads/sample_short.mp4 或 sample.mp4")
    if not settings.DASHSCOPE_API_KEY:
        pytest.skip("未配置 DASHSCOPE_API_KEY，跳过千问联调")

    result = process_video(str(video))

    print("\n========== full_text ==========")
    print(result.full_text)
    print("========== cleaned_text ==========")
    print(result.cleaned_text)
    print("========== summary ==========")
    print(result.summary)
    print("========== mindmap ==========")
    print(result.mindmap_markdown)
    print(f"========== segments: {len(result.segments)} ==========")
    for i, seg in enumerate(result.segments):
        print(f"[{i}] {seg.start_sec:.1f}s-{seg.end_sec:.1f}s | {seg.text}")
    print("================================\n")

    assert result.full_text and len(result.full_text) > 10
    assert result.cleaned_text and len(result.cleaned_text) > 0
    assert len(result.segments) > 0

    # 简体：不应残留常见繁体字形
    for trad in ("講", "個", "項", "這", "後"):
        assert trad not in result.full_text
        assert trad not in result.cleaned_text

    for seg in result.segments:
        assert seg.start_sec >= 0
        assert seg.end_sec >= seg.start_sec
        assert seg.text

    assert result.summary is not None
    assert len(result.summary) > 50
    assert result.mindmap_markdown is not None
    assert len(result.mindmap_markdown) > 20
    mm = result.mindmap_markdown
    assert "mindmap" in mm or "-" in mm or "*" in mm
