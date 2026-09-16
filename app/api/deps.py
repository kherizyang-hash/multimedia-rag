"""FastAPI 依赖注入占位。"""

from __future__ import annotations


def get_settings():
    from app.config import settings

    return settings
