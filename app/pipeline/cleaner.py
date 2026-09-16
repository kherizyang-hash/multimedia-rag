"""转写文本清洗：仅去除语气词，不做语义合并。"""

from __future__ import annotations

import re
from typing import Any, Dict, List

# 较长词优先匹配；含简繁常见口语变体
FILLER_WORDS = [
    "就是说呢",
    "然后呢",
    "然後呢",
    "那个呢",
    "那個呢",
    "就是说",
    "就是說",
    "基本上",
    "一个是",
    "一個是",
    "还有一个",
    "還有一個",
    "那个",
    "那個",
    "这个",
    "這個",
    "然后",
    "然後",
    "那么",
    "那麼",
    "所以",
    "其实",
    "其實",
    "就是",
    "嗯",
    "啊",
    "哦",
    "呃",
]

_FILLER_PATTERN = re.compile(
    "|".join(re.escape(w) for w in FILLER_WORDS),
)


def clean_text(text: str) -> str:
    """
    去除转写稿中的语气词和冗余口头禅。
    - 移除 FILLER_WORDS
    - 合并多余空白
    - 保留标点
    """
    if not text:
        return ""

    cleaned = _FILLER_PATTERN.sub("", text)
    # 合并连续空白，保留换行语义：先统一空格再压缩
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"[^\S\n]+", " ", cleaned)  # 非换行空白 -> 单空格
    cleaned = re.sub(r" *\n *", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    # 去掉标点前多余空格：如「 ，」->「，」
    cleaned = re.sub(r"\s+([，。！？；：、,.!?;:])", r"\1", cleaned)
    return cleaned.strip()


def clean_segments(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """对每个 segment 的 text 做清洗，保留时间戳字段。"""
    result: List[Dict[str, Any]] = []
    for seg in segments:
        item = dict(seg)
        item["text"] = clean_text(str(seg.get("text", "")))
        result.append(item)
    return result
