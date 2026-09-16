"""文档预处理占位。"""

from __future__ import annotations

from app.models.pipeline import ProcessedDocument


def process_document(file_path: str) -> ProcessedDocument:
    raise NotImplementedError("pipeline.document.process_document 尚未实现")
