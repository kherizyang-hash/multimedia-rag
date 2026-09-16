"""多媒体预处理流水线公共接口。"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

from app.config import settings
from app.models.pipeline import ProcessedDocument, ProcessedVideo
from app.pipeline.audio import process_audio_file
from app.pipeline.cleaner import clean_segments, clean_text
from app.pipeline.document import process_document
from app.pipeline.video import extract_audio, transcribe_audio

__all__ = [
    "process_video",
    "process_audio_file",
    "process_document",
    "extract_audio",
    "transcribe_audio",
    "clean_text",
    "clean_segments",
]


def _ensure_temp_dir() -> Path:
    path = Path(settings.TEMP_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def process_video(
    file_path: str,
    task_id: str | None = None,
) -> ProcessedVideo:
    """
    视频预处理完整流水线：
    提取音频 → process_audio_file（转写 / 清洗 / 千问）
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"视频文件不存在: {file_path}")

    temp_dir = _ensure_temp_dir()
    audio_path = temp_dir / f"{uuid.uuid4().hex}.wav"
    t0 = time.perf_counter()

    try:
        t = time.perf_counter()
        if task_id:
            try:
                from uuid import UUID

                from app.tasks import update_progress

                update_progress(UUID(str(task_id)), 12, "提取音频…")
            except Exception:  # noqa: BLE001
                pass
        extract_audio(file_path, str(audio_path))
        t_extract = time.perf_counter() - t

        processed = process_audio_file(str(audio_path), task_id=task_id)
        total = time.perf_counter() - t0
        print(
            "[pipeline] process_video done: "
            f"extract={t_extract:.1f}s total={total:.1f}s "
            f"segments={len(processed.segments)} "
            f"cleaned_chars={len(processed.cleaned_text or '')}"
        )
        return processed
    finally:
        try:
            if audio_path.exists():
                audio_path.unlink()
        except OSError:
            pass
