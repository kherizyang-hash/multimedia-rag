"""视频音频提取与 Whisper 转写。"""

from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from app.config import settings


def _ensure_ffmpeg() -> str:
    """优先系统 PATH 中的 ffmpeg；否则回退到 imageio-ffmpeg 自带静态二进制。"""
    path = shutil.which("ffmpeg")
    if path:
        return path
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "未找到 ffmpeg。可任选其一：\n"
            "  1) sudo apt-get install -y ffmpeg\n"
            "  2) pip install imageio-ffmpeg（本项目已支持自动回退）\n"
            f"底层错误: {exc}"
        ) from exc


def _ensure_ffmpeg_on_path() -> str:
    """
    保证 Whisper 子进程也能找到名为 ffmpeg 的可执行文件。
    imageio-ffmpeg 二进制名可能是 ffmpeg-linux-x86_64-...，需做同名软链。
    """
    ffmpeg = _ensure_ffmpeg()
    if os.path.basename(ffmpeg) == "ffmpeg" and shutil.which("ffmpeg"):
        return ffmpeg

    shim_dir = Path(settings.TEMP_DIR) / "ffmpeg_shim"
    shim_dir.mkdir(parents=True, exist_ok=True)
    link = shim_dir / "ffmpeg"
    target = os.path.abspath(ffmpeg)
    if link.is_symlink() or link.exists():
        if not (link.is_symlink() and os.path.realpath(link) == target):
            link.unlink()
            link.symlink_to(target)
    else:
        link.symlink_to(target)

    shim = str(shim_dir)
    path_parts = os.environ.get("PATH", "").split(os.pathsep)
    if shim not in path_parts:
        os.environ["PATH"] = shim + os.pathsep + os.environ.get("PATH", "")
    return str(link)


def extract_audio(video_path: str, output_audio_path: str) -> str:
    """
    使用 ffmpeg 从视频提取 16kHz 单声道 WAV（适配 Whisper）。

    Raises:
        FileNotFoundError: 视频不存在
        RuntimeError: ffmpeg 未安装或执行失败
    """
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"视频文件不存在: {video_path}")

    ffmpeg = _ensure_ffmpeg_on_path()
    os.makedirs(os.path.dirname(os.path.abspath(output_audio_path)) or ".", exist_ok=True)

    cmd = [
        ffmpeg,
        "-i",
        video_path,
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        "-y",
        output_audio_path,
    ]
    try:
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise RuntimeError(f"无法启动 ffmpeg: {exc}") from exc

    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            f"ffmpeg 提取音频失败 (code={result.returncode}): {err[-800:]}"
        )

    if not os.path.isfile(output_audio_path):
        raise RuntimeError(f"ffmpeg 未生成音频文件: {output_audio_path}")
    return output_audio_path


@lru_cache(maxsize=2)
def _load_whisper_model(model_name: str):
    """缓存已加载的 Whisper 模型，避免重复下载/加载。"""
    import whisper

    return whisper.load_model(model_name)


def transcribe_audio(
    audio_path: str,
    model_name: str | None = None,
) -> Dict[str, Any]:
    """
    Whisper 转写音频。

    Returns:
        {"text": str, "segments": [{"id", "start", "end", "text"}, ...]}
    """
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"音频文件不存在: {audio_path}")

    # Whisper 内部也会调用 ffmpeg，必须保证 PATH 中有名为 ffmpeg 的命令
    _ensure_ffmpeg_on_path()

    name = model_name or settings.WHISPER_MODEL
    model = _load_whisper_model(name)
    # language=zh；initial_prompt 引导简体；最终仍用 OpenCC 兜底转简
    result = model.transcribe(
        audio_path,
        language="zh",
        fp16=False,
        initial_prompt="以下是简体中文普通话的转写文稿。",
    )

    segments = []
    for i, seg in enumerate(result.get("segments") or []):
        segments.append(
            {
                "id": int(seg.get("id", i)),
                "start": float(seg.get("start", 0.0)),
                "end": float(seg.get("end", 0.0)),
                "text": str(seg.get("text", "")).strip(),
            }
        )

    return {
        "text": str(result.get("text", "")).strip(),
        "segments": segments,
    }
