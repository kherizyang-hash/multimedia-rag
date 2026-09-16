"""通用音频处理：转写 → 清洗 → 千问摘要/导图。"""

from __future__ import annotations

import os
import time
from uuid import UUID

from app.config import settings
from app.models.pipeline import ProcessedVideo, TranscriptSegment
from app.pipeline.audio_splitter import (
    cleanup_split_files,
    get_audio_duration,
    split_audio,
)
from app.pipeline.cleaner import clean_segments, clean_text
from app.pipeline.note_generator import generate_summary_and_mindmap
from app.pipeline.transcriber import engine_name, transcribe
from app.pipeline.zh_convert import segments_to_simplified, to_simplified

# 默认切段时长（秒）；短于此时长不切段
_SEGMENT_SECONDS = int(os.getenv("ASR_SEGMENT_SECONDS", "180"))


def _format_elapsed_cn(seconds: float) -> str:
    """人类可读耗时，如「6分8秒」「45秒」。"""
    n = max(0, int(round(seconds)))
    m, s = divmod(n, 60)
    if m <= 0:
        return f"{s}秒"
    return f"{m}分{s}秒"


def _notify(task_id: str | None, progress: int, step: str) -> None:
    if not task_id:
        return
    try:
        from app.tasks import update_progress

        update_progress(UUID(str(task_id)), progress, step)
    except Exception as exc:  # noqa: BLE001
        print(f"[pipeline] update_progress failed: {exc}")


def process_audio_file(
    audio_path: str,
    title: str | None = None,
    task_id: str | None = None,
) -> ProcessedVideo:
    """
    处理音频文件，不关心来源。

    - 时长 < 3 分钟：整段转写
    - 时长 ≥ 3 分钟：切段串行转写，并修正时间戳偏移
    """
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"音频文件不存在: {audio_path}")

    t0 = time.perf_counter()
    split_paths: list[str] = []

    try:
        duration = get_audio_duration(audio_path)
    except Exception as exc:  # noqa: BLE001
        print(f"[pipeline] get_audio_duration failed, treat as short: {exc}")
        duration = 0.0

    try:
        t = time.perf_counter()
        _notify(task_id, 28, f"准备转写（引擎 {engine_name()}）…")

        if duration > 0 and duration >= float(_SEGMENT_SECONDS):
            split_paths = split_audio(audio_path, segment_duration=_SEGMENT_SECONDS)
        else:
            split_paths = [audio_path]

        total_parts = len(split_paths)
        all_raw_segments: list[dict] = []
        text_parts: list[str] = []

        for i, part in enumerate(split_paths):
            offset = float(i * _SEGMENT_SECONDS)
            step = (
                f"转写第{i + 1}/{total_parts}段"
                if total_parts > 1
                else "整段转写中…"
            )
            # 转写占约 28% → 88%
            pct = 28 + int((i / max(total_parts, 1)) * 60)
            _notify(task_id, pct, step)

            raw = transcribe(part, model_name=settings.WHISPER_MODEL)
            part_text = (raw.get("text") or "").strip()
            if part_text:
                text_parts.append(part_text)

            for seg in raw.get("segments") or []:
                all_raw_segments.append(
                    {
                        "id": len(all_raw_segments),
                        "start": float(seg.get("start", 0.0)) + offset,
                        "end": float(seg.get("end", 0.0)) + offset,
                        "text": str(seg.get("text", "")).strip(),
                    }
                )

            done_pct = 28 + int(((i + 1) / max(total_parts, 1)) * 60)
            _notify(
                task_id,
                min(done_pct, 88),
                f"转写第{i + 1}/{total_parts}段完成"
                if total_parts > 1
                else "转写完成",
            )

        t_asr = time.perf_counter() - t

        t = time.perf_counter()
        _notify(task_id, 90, "清洗文稿…")
        full_text = to_simplified(" ".join(text_parts).strip())
        raw_segments = segments_to_simplified(all_raw_segments)
        cleaned_segs = clean_segments(raw_segments)

        segments: list[TranscriptSegment] = []
        for seg in cleaned_segs:
            start = float(seg.get("start", 0.0))
            end = float(seg.get("end", 0.0))
            if end < start:
                end = start
            text = str(seg.get("text", "")).strip()
            if not text:
                continue
            segments.append(TranscriptSegment(text=text, start_sec=start, end_sec=end))

        cleaned_full = clean_text(full_text)
        if not cleaned_full and segments:
            cleaned_full = clean_text(" ".join(s.text for s in segments))
        cleaned_full = cleaned_full or full_text
        t_clean = time.perf_counter() - t

        t = time.perf_counter()
        _notify(task_id, 95, "生成摘要与思维导图…")
        ai_title, summary, mindmap = generate_summary_and_mindmap(cleaned_full)
        t_qwen = time.perf_counter() - t

        note_title = (title or "").strip() or ai_title

        total = time.perf_counter() - t0
        print(
            "[pipeline] process_audio_file done: "
            f"engine={engine_name()} parts={total_parts} "
            f"duration={duration:.1f}s asr={t_asr:.1f}s clean={t_clean:.1f}s "
            f"qwen={t_qwen:.1f}s total={total:.1f}s segments={len(segments)} "
            f"cleaned_chars={len(cleaned_full or '')}"
        )
        print(f"音视频已解析完成，用时{_format_elapsed_cn(total)}")

        return ProcessedVideo(
            full_text=full_text,
            cleaned_text=cleaned_full,
            segments=segments,
            title=note_title,
            summary=summary,
            mindmap_markdown=mindmap,
        )
    finally:
        if split_paths:
            cleanup_split_files(
                [p for p in split_paths if p != audio_path],
                audio_path,
            )
