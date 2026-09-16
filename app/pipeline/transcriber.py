"""统一转写入口：优先 faster-whisper，失败则回退 openai-whisper。"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict

from app.config import settings
from app.pipeline.video import _ensure_ffmpeg_on_path

_LAST_ENGINE = "openai-whisper"
_FASTER_DISABLED = False

# DevBox 常无法直连 huggingface.co；镜像 + 关 XET 便于首次下载
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")


@lru_cache(maxsize=2)
def _load_faster_whisper(model_name: str):
    from faster_whisper import WhisperModel

    # CPU / int8：适配 2C4G；优先本地路径（FASTER_WHISPER_MODEL）
    path = (os.getenv("FASTER_WHISPER_MODEL") or "").strip() or model_name
    return WhisperModel(path, device="cpu", compute_type="int8")


def _faster_whisper_importable() -> bool:
    try:
        import faster_whisper  # noqa: F401

        return True
    except Exception:  # noqa: BLE001
        return False


def _transcribe_faster(audio_path: str, model_name: str) -> Dict[str, Any]:
    model = _load_faster_whisper(model_name)
    segments_iter, _info = model.transcribe(
        audio_path,
        language="zh",
        vad_filter=True,
        initial_prompt="以下是简体中文普通话的转写文稿。",
    )
    segments = []
    texts = []
    for i, seg in enumerate(segments_iter):
        text = (seg.text or "").strip()
        segments.append(
            {
                "id": i,
                "start": float(seg.start or 0.0),
                "end": float(seg.end or 0.0),
                "text": text,
            }
        )
        if text:
            texts.append(text)
    return {"text": " ".join(texts).strip(), "segments": segments}


def _transcribe_openai(audio_path: str, model_name: str) -> Dict[str, Any]:
    from app.pipeline.video import transcribe_audio

    return transcribe_audio(audio_path, model_name=model_name)


def transcribe(audio_path: str, model_name: str | None = None) -> Dict[str, Any]:
    """
    统一的转写入口，内部自动选择引擎。

    Returns:
        {"text": str, "segments": [{"id","start","end","text"}, ...]}
    """
    global _LAST_ENGINE, _FASTER_DISABLED
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"音频文件不存在: {audio_path}")

    _ensure_ffmpeg_on_path()
    name = model_name or settings.WHISPER_MODEL

    if not _FASTER_DISABLED and _faster_whisper_importable():
        try:
            result = _transcribe_faster(audio_path, name)
            _LAST_ENGINE = "faster-whisper"
            return result
        except Exception as exc:  # noqa: BLE001
            print(f"[transcriber] faster-whisper 失败，回退 openai-whisper: {exc}")
            _FASTER_DISABLED = True

    _LAST_ENGINE = "openai-whisper"
    return _transcribe_openai(audio_path, name)


def engine_name() -> str:
    return _LAST_ENGINE
