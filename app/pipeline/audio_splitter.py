"""音频切段：ffmpeg 按固定时长切片，供串行 ASR。"""

from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path

from app.config import settings


def _ffmpeg_bin() -> str:
    path = shutil.which("ffmpeg")
    if path:
        return path
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"未找到 ffmpeg: {exc}") from exc


def _ffprobe_bin() -> str | None:
    path = shutil.which("ffprobe")
    if path:
        return path
    # imageio-ffmpeg 通常只有 ffmpeg；用 ffmpeg -i 解析时长作回退
    return None


def get_audio_duration(audio_path: str) -> float:
    """获取音频总时长（秒）。"""
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"音频文件不存在: {audio_path}")

    probe = _ffprobe_bin()
    if probe:
        cmd = [
            probe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            audio_path,
        ]
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if result.returncode == 0:
            try:
                return float((result.stdout or "").strip())
            except ValueError:
                pass

    # 回退：ffmpeg -i 解析 Duration
    ffmpeg = _ffmpeg_bin()
    result = subprocess.run(
        [ffmpeg, "-i", audio_path],
        check=False,
        capture_output=True,
        text=True,
    )
    err = result.stderr or ""
    # Duration: 00:01:17.04
    import re

    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", err)
    if not m:
        raise RuntimeError(f"无法获取音频时长: {audio_path}")
    h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return h * 3600 + mi * 60 + s


def split_audio(audio_path: str, segment_duration: int = 180) -> list[str]:
    """
    用 ffmpeg 将音频切成每段 segment_duration 秒的小文件（默认 180=3 分钟）。
    返回：小文件路径列表（按时间顺序）。
    """
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"音频文件不存在: {audio_path}")
    if segment_duration <= 0:
        raise ValueError("segment_duration 必须为正整数")

    duration = get_audio_duration(audio_path)
    if duration <= 0:
        raise RuntimeError("音频时长为 0")

    # 短于一段：不切，直接返回原文件
    if duration <= float(segment_duration):
        return [audio_path]

    out_dir = Path(settings.TEMP_DIR) / f"split_{uuid.uuid4().hex}"
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(out_dir / "seg_%03d.wav")

    ffmpeg = _ffmpeg_bin()
    cmd = [
        ffmpeg,
        "-i",
        audio_path,
        "-f",
        "segment",
        "-segment_time",
        str(int(segment_duration)),
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        "-reset_timestamps",
        "1",
        "-y",
        pattern,
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"ffmpeg 切段失败: {err[-800:]}")

    parts = sorted(out_dir.glob("seg_*.wav"))
    paths = [str(p) for p in parts if p.is_file() and p.stat().st_size > 0]
    if not paths:
        raise RuntimeError("ffmpeg 切段未生成有效文件")
    return paths


def cleanup_split_files(paths: list[str], original: str) -> None:
    """删除切段产生的临时目录（不删原始音频）。"""
    for p in paths:
        if not p or p == original:
            continue
        try:
            path = Path(p)
            if path.is_file():
                parent = path.parent
                path.unlink(missing_ok=True)
                # 若目录空了就删掉
                if parent.name.startswith("split_") and parent.is_dir():
                    try:
                        next(parent.iterdir())
                    except StopIteration:
                        parent.rmdir()
        except OSError:
            pass
