"""单层切片：按句子边界切分，挂载 ASR 时间戳。"""

from __future__ import annotations

import re
from typing import List, Optional, Sequence, Tuple, Union
from uuid import UUID

from app.config import settings
from app.models.chunk import Chunk
from app.models.enums import ChunkLayer
from app.models.pipeline import TranscriptSegment

# 句号/问号/感叹号/换行后切分，分隔符保留在前一句末尾
_SENTENCE_SPLIT = re.compile(r"(?<=[。！？\n])")

SegmentLike = Union[TranscriptSegment, dict]


def _as_segment(item: SegmentLike) -> TranscriptSegment:
    if isinstance(item, TranscriptSegment):
        return item
    return TranscriptSegment.model_validate(item)


def _split_sentences(text: str) -> List[str]:
    """按中文句子边界切分；空串丢弃。"""
    parts = _SENTENCE_SPLIT.split(text)
    return [p for p in parts if p and not p.isspace()]


def _build_segment_spans(
    text: str,
    segments: Sequence[SegmentLike],
) -> List[Tuple[int, int, float, float]]:
    """在全文中顺序定位各 segment 的字符区间 → 时间戳。"""
    spans: List[Tuple[int, int, float, float]] = []
    cursor = 0
    for raw in segments:
        seg = _as_segment(raw)
        seg_text = (seg.text or "").strip()
        if not seg_text:
            continue
        idx = text.find(seg_text, cursor)
        if idx < 0:
            idx = text.find(seg_text)
        if idx < 0:
            continue
        end = idx + len(seg_text)
        spans.append((idx, end, float(seg.start_sec), float(seg.end_sec)))
        cursor = end
    return spans


def _assign_timestamp(
    start: int,
    end: int,
    spans: Sequence[Tuple[int, int, float, float]],
) -> Tuple[Optional[float], Optional[float]]:
    """取与 [start, end) 有重叠的 segments 的时间并集。"""
    overlapping = [s for s in spans if s[0] < end and s[1] > start]
    if not overlapping:
        return None, None
    return min(s[2] for s in overlapping), max(s[3] for s in overlapping)


def chunk_text(
    text: str,
    note_id: Union[str, UUID],
    segments: Optional[Sequence[SegmentLike]] = None,
    chunk_size: Optional[int] = None,
    overlap: Optional[int] = None,
) -> List[Chunk]:
    """
    按句子边界切分文本，生成单层 Chunk 列表。

    - 累积句子直至接近 chunk_size
    - 下一块保留约 overlap 字符的上下文（按整句回退）
    - 根据字符区间匹配 segments，写入 start_sec / end_sec
    - id 形如 ``{note_id}:{index:04d}``
    """
    source = text or ""
    if not source.strip():
        return []

    size = chunk_size if chunk_size is not None else settings.CHUNK_SIZE
    ov = overlap if overlap is not None else settings.CHUNK_OVERLAP
    note_id_str = str(note_id)
    segs = list(segments or [])
    spans = _build_segment_spans(source, segs)

    sentences = _split_sentences(source)
    if not sentences:
        sentences = [source]

    raw_bodies: List[str] = []
    buf: List[str] = []
    buf_len = 0

    for sent in sentences:
        sent_len = len(sent)
        if buf and buf_len + sent_len > size:
            raw_bodies.append("".join(buf))
            if ov > 0:
                keep: List[str] = []
                keep_len = 0
                for s in reversed(buf):
                    if keep_len >= ov:
                        break
                    keep.insert(0, s)
                    keep_len += len(s)
                buf = keep
                buf_len = keep_len
            else:
                buf = []
                buf_len = 0
        buf.append(sent)
        buf_len += sent_len

    if buf:
        piece = "".join(buf)
        if not raw_bodies or piece != raw_bodies[-1]:
            raw_bodies.append(piece)

    note_uuid = note_id if isinstance(note_id, UUID) else UUID(note_id_str)
    chunks: List[Chunk] = []
    search_from = 0
    for index, body in enumerate(raw_bodies):
        body_stripped = body.strip()
        if not body_stripped:
            continue

        idx = source.find(body, search_from)
        if idx < 0:
            idx = source.find(body_stripped, search_from)
        if idx < 0:
            idx = source.find(body_stripped)
        if idx >= 0:
            matched = (
                body
                if source[idx : idx + len(body)] == body
                else body_stripped
            )
            pos_start = idx
            pos_end = idx + len(matched)
            search_from = max(pos_start + 1, pos_end - max(ov, 0))
            start_sec, end_sec = _assign_timestamp(pos_start, pos_end, spans)
        else:
            start_sec, end_sec = None, None

        chunks.append(
            Chunk(
                id=f"{note_id_str}:{index:04d}",
                note_id=note_uuid,
                text=body_stripped,
                layer=ChunkLayer.SINGLE,
                start_sec=start_sec,
                end_sec=end_sec,
                metadata={"char_start": idx if idx >= 0 else None},
            )
        )
    return chunks
