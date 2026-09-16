"""B 站公开视频：提取 BV 号、获取音频流、下载到本地。"""

from __future__ import annotations

import os
import re
from typing import Tuple

import requests
from bilibili_api import HEADERS, sync, video

_BV_RE = re.compile(r"(BV[a-zA-Z0-9]+)")


def extract_bvid(url: str) -> str:
    """从 B 站 URL（或纯 BV 号）中提取 BV 号。"""
    text = (url or "").strip()
    if not text:
        raise ValueError("请提供 B 站视频链接")
    m = _BV_RE.search(text)
    if not m:
        raise ValueError("无效的 B 站链接，未找到 BV 号")
    return m.group(1)


async def _fetch_title_and_audio(bvid: str) -> Tuple[str, str]:
    v = video.Video(bvid=bvid)
    try:
        info = await v.get_info()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("目前仅支持解析公开视频哦~") from exc

    title = str(info.get("title") or bvid).strip() or bvid

    try:
        download_data = await v.get_download_url(page_index=0)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("目前仅支持解析公开视频哦~") from exc

    detecter = video.VideoDownloadURLDataDetecter(data=download_data)
    streams = detecter.detect_best_streams()

    audio_url: str | None = None
    for s in streams:
        if isinstance(s, video.AudioStreamDownloadURL) and getattr(s, "url", None):
            audio_url = s.url
            break

    # dash 无独立音轨时：FLV/MP4 合流也可交给 Whisper（内部走 ffmpeg）
    if not audio_url:
        for s in streams:
            if isinstance(
                s,
                (video.FLVStreamDownloadURL, video.MP4StreamDownloadURL),
            ) and getattr(s, "url", None):
                audio_url = s.url
                break

    if not audio_url and streams and getattr(streams[0], "url", None):
        audio_url = streams[0].url

    if not audio_url:
        # 再试 html5 移动端 MP4（部分公开视频仅此路径）
        try:
            html5_data = await v.get_download_url(page_index=0, html5=True)
            durl = (html5_data or {}).get("durl") or []
            if durl and durl[0].get("url"):
                audio_url = durl[0]["url"]
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("目前仅支持解析公开视频哦~") from exc

    if not audio_url:
        raise RuntimeError("目前仅支持解析公开视频哦~")

    return title, audio_url


def get_audio_url(bvid: str) -> tuple[str, str]:
    """
    获取音频流下载地址和视频标题。

    Returns:
        (title, audio_url)
    """
    bvid = (bvid or "").strip()
    if not bvid:
        raise ValueError("BV 号不能为空")
    try:
        return sync(_fetch_title_and_audio(bvid))
    except RuntimeError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("目前仅支持解析公开视频哦~") from exc


def download_audio(audio_url: str, output_path: str) -> str:
    """流式下载音频到本地临时文件；需带 B 站 Referer。"""
    if not audio_url:
        raise ValueError("音频地址为空")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)

    try:
        with requests.get(
            audio_url,
            headers=HEADERS,
            stream=True,
            timeout=120,
        ) as resp:
            resp.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        f.write(chunk)
    except requests.RequestException as exc:
        raise RuntimeError(f"下载音频失败: {exc}") from exc

    if not os.path.isfile(output_path) or os.path.getsize(output_path) <= 0:
        raise RuntimeError("下载音频失败：文件为空")
    return output_path
