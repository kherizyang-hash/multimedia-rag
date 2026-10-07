"""预处理相关 HTTP 路由（异步任务：立刻返回 job_id）。"""

from __future__ import annotations

import os
import shutil
import traceback
import uuid
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.config import settings
from app.models.enums import SourceType
from app.models.note import NoteCreate
from app.models.pipeline import BilibiliRequest
from app.notes import create_note
from app.pipeline import process_audio_file, process_video
from app.pipeline.bilibili import download_audio, extract_bvid, get_audio_url
from app.tasks import complete_task, create_task, fail_task, mark_running, update_progress

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_UPLOAD_DIR = _PROJECT_ROOT / "data" / "uploads"
_ALLOWED_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


class JobSubmitResponse(BaseModel):
    job_id: UUID
    message: str = Field(default="任务已提交，请轮询 /api/tasks/{job_id}")


def _safe_suffix(filename: Optional[str]) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix in _ALLOWED_SUFFIXES:
        return suffix
    return ".mp4"


def _run_video_job(
    task_id: UUID,
    saved_path: str,
    original_filename: str,
    form_title: Optional[str],
    category: str,
) -> None:
    try:
        mark_running(task_id, "提取音频与转写中", progress=5)
        update_progress(task_id, 10, "视频预处理中…")
        processed = process_video(saved_path, task_id=str(task_id))

        update_progress(task_id, 92, "创建笔记…")
        file_stem = Path(original_filename).stem or "未命名视频笔记"
        title_in = (form_title or "").strip()
        ai_title = (processed.title or "").strip()
        if not title_in or title_in == file_stem:
            note_title = ai_title or title_in or file_stem
        else:
            note_title = title_in

        summary = (processed.summary or "").strip()
        if not summary:
            summary = (processed.cleaned_text or processed.full_text or "（暂无摘要）")[:800]

        cleaned = (processed.cleaned_text or processed.full_text or "").strip()
        full_text = (processed.full_text or cleaned).strip()
        if not cleaned or not full_text:
            raise RuntimeError("视频转写结果为空，无法创建笔记")

        note = create_note(
            NoteCreate(
                title=note_title,
                summary=summary,
                full_text=full_text,
                cleaned_text=cleaned,
                source_type="video",
                source_file_path=saved_path,
                category=(category or "学习").strip() or "学习",
                is_permanent=False,
                mindmap=processed.mindmap_markdown,
                source_segments=processed.segments,
            )
        )
        complete_task(task_id, note.id)
    except Exception as exc:  # noqa: BLE001
        print(f"[pipeline] video job failed: {exc}\n{traceback.format_exc()}")
        fail_task(task_id, str(exc))


def _run_bilibili_job(
    task_id: UUID,
    url: str,
    custom_title: Optional[str],
) -> None:
    temp_path: Optional[str] = None
    try:
        mark_running(task_id, "解析 B 站链接…", progress=3)
        bvid = extract_bvid(url)
        update_progress(task_id, 8, "获取音频地址…")
        bili_title, audio_url = get_audio_url(bvid)

        temp_dir = Path(settings.TEMP_DIR)
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = str(temp_dir / f"bili_{uuid.uuid4().hex}.m4s")

        update_progress(task_id, 15, "下载音频…")
        download_audio(audio_url, temp_path)

        update_progress(task_id, 25, "开始转写…")
        processed = process_audio_file(
            temp_path,
            title=custom_title,
            task_id=str(task_id),
        )

        update_progress(task_id, 92, "创建笔记…")
        if custom_title:
            note_title = custom_title
        else:
            note_title = (processed.title or "").strip() or bili_title or bvid

        summary = (processed.summary or "").strip()
        if not summary:
            summary = (processed.cleaned_text or processed.full_text or "（暂无摘要）")[:800]

        cleaned = (processed.cleaned_text or processed.full_text or "").strip()
        full_text = (processed.full_text or cleaned).strip()
        if not cleaned or not full_text:
            raise RuntimeError("音频转写结果为空，无法创建笔记")

        note = create_note(
            NoteCreate(
                title=note_title,
                summary=summary,
                full_text=full_text,
                cleaned_text=cleaned,
                source_type=SourceType.LINK,
                source_url=(url or "").strip()[:500],
                category="学习",
                is_permanent=False,
                mindmap=processed.mindmap_markdown,
                source_segments=processed.segments,
            )
        )
        complete_task(task_id, note.id)
    except Exception as exc:  # noqa: BLE001
        print(f"[pipeline] bilibili job failed: {exc}\n{traceback.format_exc()}")
        fail_task(task_id, str(exc))
    finally:
        if temp_path and os.path.isfile(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


@router.post("/video", response_model=JobSubmitResponse)
async def api_process_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="视频文件"),
    title: Optional[str] = Form(default=None, description="笔记标题，默认用文件名"),
    category: str = Form(default="学习", description="笔记分类"),
) -> JobSubmitResponse:
    """上传视频 → 后台处理 → 轮询 /api/tasks/{job_id}。"""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少上传文件名",
        )

    suffix = Path(file.filename).suffix.lower()
    if suffix and suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的视频格式: {suffix}，允许: {sorted(_ALLOWED_SUFFIXES)}",
        )

    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved_name = f"{uuid.uuid4().hex}{_safe_suffix(file.filename)}"
    saved_path = _UPLOAD_DIR / saved_name

    try:
        with saved_path.open("wb") as out:
            shutil.copyfileobj(file.file, out)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"保存上传文件失败: {exc}",
        ) from exc
    finally:
        await file.close()

    if saved_path.stat().st_size <= 0:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="上传文件为空",
        )

    task = create_task("video")
    task_id = task["id"]
    print(f"[API] 提交视频任务 job_id={task_id} file={file.filename}")
    background_tasks.add_task(
        _run_video_job,
        task_id,
        str(saved_path),
        file.filename,
        title,
        category,
    )
    return JobSubmitResponse(job_id=task_id)


@router.post("/bilibili", response_model=JobSubmitResponse)
async def api_process_bilibili(
    body: BilibiliRequest,
    background_tasks: BackgroundTasks,
) -> JobSubmitResponse:
    """B 站链接 → 后台处理 → 轮询 /api/tasks/{job_id}。"""
    try:
        extract_bvid(body.url)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    task = create_task("bilibili")
    task_id = task["id"]
    print(f"[API] 提交 B 站任务 job_id={task_id} url={body.url[:80]}")
    custom_title = (body.title or "").strip() or None
    background_tasks.add_task(
        _run_bilibili_job,
        task_id,
        body.url.strip(),
        custom_title,
    )
    return JobSubmitResponse(job_id=task_id)
