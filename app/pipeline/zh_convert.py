"""中文繁简转换：保证流水线输出简体。"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List


@lru_cache(maxsize=1)
def _opencc_t2s():
    from opencc import OpenCC

    return OpenCC("t2s")


def to_simplified(text: str) -> str:
    """繁体 → 简体；空串原样返回。"""
    if not text:
        return text
    return _opencc_t2s().convert(text)


def segments_to_simplified(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """对 segment 列表中的 text 做繁转简，保留时间戳。"""
    result: List[Dict[str, Any]] = []
    for seg in segments:
        item = dict(seg)
        item["text"] = to_simplified(str(seg.get("text", "")))
        result.append(item)
    return result
