"""长文千问摘要：短文单次；超阈值则按字符 map-reduce（时间戳仅日志元数据）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

from app.config import settings
from app.llm_dashscope import chat_completions
from app.pipeline.note_generator import build_prompt, call_qwen

_SENT_END = "。！？\n"

_MAP_PROMPT = """你是一个耐心的学习助手。下面是视频转写稿的**其中一个片段**。
请提取本段的关键学习要点（简体中文），供后续合并成完整笔记。

### 关于转写稿（必读）
转写可能有同音错字。请结合上下文在脑中纠正后，**只输出纠正后的表述**。
硬性禁止：原转写/误听/应为/括号对照错词、编造本段未涉及的情节。

### 输出要求
- 用简短要点列出本段讲了什么（可用「-」列表，约 5～12 条）
- 保留专有名词与关键信息；不要写标题、不要写思维导图
- 不要写「本段」「片段」等元叙述；直接写要点正文

### 转写片段：
{chunk_text}
"""


def _format_ts(sec: Optional[float]) -> str:
    if sec is None:
        return "?"
    n = max(0, int(sec))
    m, s = divmod(n, 60)
    return f"{m}:{s:02d}"


def _notify(task_id: Optional[str], progress: int, step: str) -> None:
    if not task_id:
        return
    try:
        from app.tasks import update_progress

        update_progress(UUID(str(task_id)), progress, step)
    except Exception as exc:  # noqa: BLE001
        print(f"[QWEN] update_progress failed: {exc}")


def _normalize_segments(
    segments: Optional[Sequence[Any]],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not segments:
        return out
    for seg in segments:
        if hasattr(seg, "text"):
            text = str(getattr(seg, "text", "") or "").strip()
            start = getattr(seg, "start_sec", None)
            end = getattr(seg, "end_sec", None)
        elif isinstance(seg, dict):
            text = str(seg.get("text") or "").strip()
            start = seg.get("start_sec", seg.get("start"))
            end = seg.get("end_sec", seg.get("end"))
        else:
            continue
        if not text:
            continue
        try:
            start_f = float(start) if start is not None else None
        except (TypeError, ValueError):
            start_f = None
        try:
            end_f = float(end) if end is not None else None
        except (TypeError, ValueError):
            end_f = None
        out.append({"text": text, "start_sec": start_f, "end_sec": end_f})
    return out


def _find_soft_cut(text: str, target: int) -> int:
    """在 target 附近找句边界；找不到则硬切 target。"""
    n = len(text)
    if n <= target:
        return n
    lo = max(0, int(target * 0.7))
    for i in range(min(target, n - 1), lo - 1, -1):
        if text[i] in _SENT_END:
            return i + 1
    hi = min(n, target + 200)
    for i in range(target, hi):
        if text[i] in _SENT_END:
            return i + 1
    return min(target, n)


def _split_plain_text(cleaned_text: str, chunk_size: int) -> List[Dict[str, Any]]:
    text = cleaned_text.strip()
    if not text:
        return []
    chunks: List[Dict[str, Any]] = []
    pos = 0
    while pos < len(text):
        remain = text[pos:]
        if len(remain) <= chunk_size:
            chunks.append(
                {"text": remain, "start_sec": None, "end_sec": None}
            )
            break
        cut = _find_soft_cut(remain, chunk_size)
        piece = remain[:cut].strip()
        if not piece:
            cut = min(chunk_size, len(remain))
            piece = remain[:cut]
        chunks.append({"text": piece, "start_sec": None, "end_sec": None})
        pos += cut
        while pos < len(text) and text[pos].isspace():
            pos += 1
    return chunks


def _split_for_map(
    cleaned_text: str,
    segments: Optional[Sequence[Any]],
    chunk_size: int,
) -> List[Dict[str, Any]]:
    """
    按字符数切分；优先沿 ASR segments 累加以便带上 start/end。
    返回 [{'text', 'start_sec', 'end_sec'}, ...]。
    """
    size = max(200, int(chunk_size))
    segs = _normalize_segments(segments)
    if not segs:
        return _split_plain_text(cleaned_text or "", size)

    chunks: List[Dict[str, Any]] = []
    buf: List[str] = []
    buf_start: Optional[float] = None
    buf_end: Optional[float] = None
    buf_len = 0

    def _flush() -> None:
        nonlocal buf, buf_start, buf_end, buf_len
        if not buf:
            return
        text = "".join(buf).strip()
        if text:
            chunks.append(
                {
                    "text": text,
                    "start_sec": buf_start,
                    "end_sec": buf_end,
                }
            )
        buf = []
        buf_start = None
        buf_end = None
        buf_len = 0

    for seg in segs:
        t = seg["text"]
        # 单段过长：先按句界硬拆
        if not buf and len(t) > size:
            for piece in _split_plain_text(t, size):
                piece["start_sec"] = seg["start_sec"]
                piece["end_sec"] = seg["end_sec"]
                chunks.append(piece)
            continue

        add_len = len(t)
        if buf and buf_len + add_len > size:
            _flush()

        if not buf:
            buf = [t]
            buf_len = len(t)
            buf_start = seg["start_sec"]
        else:
            buf.append(t)
            buf_len += add_len
        if seg["end_sec"] is not None:
            buf_end = seg["end_sec"]
        elif seg["start_sec"] is not None:
            buf_end = seg["start_sec"]

        if buf_len >= size:
            _flush()

    _flush()

    # segments 拼出的正文若明显短于 cleaned_text，回退纯文本切分
    joined = "".join(c["text"] for c in chunks)
    cleaned = (cleaned_text or "").strip()
    if cleaned and len(joined) < int(len(cleaned) * 0.5):
        print(
            f"[QWEN] segments 覆盖不足（{len(joined)}/{len(cleaned)} 字），"
            "改用清洗稿按字切分"
        )
        return _split_plain_text(cleaned, size)
    return chunks or _split_plain_text(cleaned, size)


def _map_one_chunk(chunk_text: str) -> Optional[str]:
    if not settings.DASHSCOPE_API_KEY:
        print("[QWEN] DASHSCOPE_API_KEY 未配置，map 跳过")
        return None
    try:
        content = chat_completions(
            [
                {
                    "role": "user",
                    "content": _MAP_PROMPT.format(chunk_text=chunk_text),
                }
            ],
            max_tokens=min(1500, settings.QWEN_MAX_TOKENS),
            temperature=0.5,
        )
        text = (content or "").strip()
        return text or None
    except Exception as exc:  # noqa: BLE001
        print(f"[QWEN] map 调用失败: {exc}")
        return None


def _merge_map_points(points: List[str]) -> str:
    parts: List[str] = []
    for i, p in enumerate(points, start=1):
        parts.append(f"### 第 {i} 段要点\n{p.strip()}")
    return (
        "以下是长视频各段转写的要点汇总（已按时间顺序）。"
        "请据此生成完整学习笔记与思维导图，勿编造汇总中未出现的情节。\n\n"
        + "\n\n".join(parts)
    )


def summarize_long_text(
    cleaned_text: str,
    segments: Optional[Sequence[Any]] = None,
    task_id: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """
    长文本摘要：
    - ≤ QWEN_SINGLE_THRESHOLD：单次 build_prompt
    - 否则：先按字切完 → 串行 map → 一次 reduce
    返回 {'title', 'summary', 'mindmap'}。
    """
    empty: Dict[str, Optional[str]] = {
        "title": None,
        "summary": None,
        "mindmap": None,
    }
    text = (cleaned_text or "").strip()
    if not text:
        return empty

    threshold = max(1, int(settings.QWEN_SINGLE_THRESHOLD))
    chunk_size = max(200, int(settings.QWEN_MAP_CHUNK_SIZE))
    n_chars = len(text)

    if n_chars <= threshold:
        print(f"[QWEN] 文本 {n_chars} 字 ≤ {threshold}，走单次摘要")
        _notify(task_id, 95, "生成摘要与思维导图…")
        return call_qwen(build_prompt(text))

    print(f"[QWEN] 文本 {n_chars} 字 > {threshold}，走 map-reduce")
    chunks = _split_for_map(text, segments, chunk_size)
    total = len(chunks)
    print(f"[QWEN] map 切分为 {total} 块")
    if not chunks:
        return empty

    map_points: List[str] = []
    for i, ch in enumerate(chunks, start=1):
        t0 = _format_ts(ch.get("start_sec"))
        t1 = _format_ts(ch.get("end_sec"))
        pct = 92 + int((i - 1) / max(total, 1) * 5)
        _notify(task_id, min(pct, 96), f"摘要 map {i}/{total}…")
        point = _map_one_chunk(ch["text"])
        if point:
            map_points.append(point)
            print(
                f"[QWEN] map {i}/{total} chars={len(ch['text'])} "
                f"t={t0}-{t1} 完成"
            )
        else:
            # 失败时降级：截取原文前若干字作要点，避免整段丢失
            fallback = ch["text"][:800].strip()
            if fallback:
                map_points.append(fallback)
            print(
                f"[QWEN] map {i}/{total} chars={len(ch['text'])} "
                f"t={t0}-{t1} 失败，已用原文截断兜底"
            )

    if not map_points:
        print("[QWEN] map 全部失败，回退单次（可能仍失败）")
        return call_qwen(build_prompt(text[:threshold]))

    print(f"[QWEN] reduce 阶段：合并 {len(map_points)} 个要点")
    _notify(task_id, 97, "合并摘要（reduce）…")
    merged = _merge_map_points(map_points)
    result = call_qwen(build_prompt(merged))
    summary = result.get("summary") or ""
    print(f"[QWEN] reduce 完成，总摘要 {len(summary)} 字")
    return result
