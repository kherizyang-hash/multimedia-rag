"""笔记相关 Pydantic 模型。"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import SourceType
from app.models.pipeline import TranscriptSegment


class NoteBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    summary: str = Field(..., min_length=1, description="用户可见的总结笔记正文")
    full_text: str = Field(..., min_length=1, description="原始全文/转写文稿")
    cleaned_text: str = Field(..., min_length=1, description="清洗后文本，供RAG切片")
    source_type: SourceType
    source_url: Optional[str] = Field(default=None, max_length=500)
    source_file_path: Optional[str] = Field(default=None, max_length=500)
    category: str = Field(default="学习", max_length=50)
    is_permanent: bool = Field(
        default=False,
        description="False=临时速读；True=已入RAG向量库",
    )
    mindmap: Optional[str] = Field(
        default=None,
        description="思维导图 Markdown 文本（可持久化预览）",
    )
    source_segments: Optional[List[TranscriptSegment]] = Field(
        default=None,
        description="ASR 时间戳片段；永久化时挂载 chunk 的 start/end",
    )

    @field_validator("category")
    @classmethod
    def category_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("category 不能为空")
        return v

    @model_validator(mode="after")
    def source_must_exist(self) -> "NoteBase":
        if self.source_type == SourceType.LINK and not self.source_url:
            raise ValueError("source_type=link 时必须提供 source_url")
        if self.source_type in {SourceType.VIDEO, SourceType.DOCUMENT}:
            if not self.source_file_path and not self.source_url:
                raise ValueError(
                    "video/document 至少提供 source_file_path 或 source_url 之一"
                )
        return self


class NoteCreate(NoteBase):
    """创建入参；id / 时间戳由服务层生成。"""


class NoteUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    summary: Optional[str] = None
    category: Optional[str] = Field(default=None, max_length=50)
    mindmap: Optional[str] = None


class Note(NoteBase):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
