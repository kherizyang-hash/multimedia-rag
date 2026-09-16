"""API 路由聚合。"""

from fastapi import APIRouter

from app.api import chat, health, notes, pipeline, tasks

# 业务路由（由 main 挂到 /api 前缀）
api_router = APIRouter()
api_router.include_router(pipeline.router)
api_router.include_router(notes.router)
api_router.include_router(chat.router)
api_router.include_router(tasks.router)

__all__ = ["api_router", "health", "notes", "pipeline", "chat", "tasks"]
