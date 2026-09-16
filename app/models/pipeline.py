"""预处理流水线输出模型。"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    text: str
    start_sec: float = Field(..., ge=0)
    end_sec: float = Field(..., ge=0)


class ProcessedVideo(BaseModel):
    full_text: str
    cleaned_text: str
    segments: List[TranscriptSegment]
    title: Optional[str] = None
    summary: Optional[str] = None
    mindmap_markdown: Optional[str] = None


class ProcessedDocument(BaseModel):
    full_text: str
    cleaned_text: str
    title: Optional[str] = None
    summary: Optional[str] = None
    mindmap_markdown: Optional[str] = None


class BilibiliRequest(BaseModel):
    """B 站公开视频链接解析请求。"""

    url: str = Field(..., min_length=1, description="B 站视频链接或 BV 号")
    title: Optional[str] = Field(default=None, description="可选自定义标题")
