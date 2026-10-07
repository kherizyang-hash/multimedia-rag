"""验收摘要轻结构化格式（会真实调用千问，需 DASHSCOPE_API_KEY）。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.pipeline.summarizer import _split_for_map, summarize_long_text  # noqa: E402

CORPUS = ROOT / "data" / "test_cleaned_text.txt"


def test_empty_segments_still_splits_by_chars():
    """segments=[] 时应按字符切块，时间戳为 None。"""
    text = ("句号结尾的测试句。" * 400)
    chunks = _split_for_map(text, segments=[], chunk_size=500)
    assert len(chunks) >= 2
    assert all(c.get("start_sec") is None for c in chunks)
    assert all(c.get("text") for c in chunks)


@pytest.mark.skipif(
    not settings.DASHSCOPE_API_KEY,
    reason="需要 DASHSCOPE_API_KEY",
)
@pytest.mark.skipif(
    not CORPUS.is_file(),
    reason="缺少 data/test_cleaned_text.txt",
)
def test_summary_format():
    cleaned_text = CORPUS.read_text(encoding="utf-8").strip()
    assert len(cleaned_text) > 5000, "测试语料应足够长以覆盖 map-reduce 或长单次"

    segments: list = []  # 无时戳，验证空 segments 路径
    result = summarize_long_text(cleaned_text, segments)

    print("\n=== 标题 ===")
    print(result["title"])
    print("\n=== 摘要 ===")
    print(result["summary"])
    print("\n=== 思维导图 ===")
    print(result["mindmap"])

    assert result["title"], "应有标题"
    assert result["summary"], "应有摘要"
    summary = result["summary"] or ""
    assert "**" in summary, "摘要应包含加粗小标题"

    bold_heads = re.findall(r"\*\*[^*\n]+\*\*", summary)
    assert 3 <= len(bold_heads) <= 8, (
        f"期望约 3～6 个加粗小标题，实际 {len(bold_heads)}：{bold_heads}"
    )
    for h in bold_heads:
        bare = h.strip("*").strip()
        assert bare not in {"第一部分", "第二部分", "第一点", "第二点", "概述", "正文"}
        assert not re.match(r"^第[一二三四五六七八九十\d]+", bare), f"空泛标题: {bare}"
