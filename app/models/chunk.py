"""切片与检索结果模型。"""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import ChunkLayer


class Chunk(BaseModel):
    id: str
    note_id: UUID
    text: str
    layer: ChunkLayer
    start_sec: Optional[float] = Field(
        default=None, description="视频起始秒；文档切片可为空"
    )
    end_sec: Optional[float] = Field(default=None, description="视频结束秒")
    page: Optional[int] = Field(default=None, description="文档页码")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SearchResult(BaseModel):
    note_id: UUID
    chunk_id: str
    chunk_text: str
    score: float
    layer: ChunkLayer
    start_sec: Optional[float] = None
    end_sec: Optional[float] = None
    page: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
