"""Application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import api_router, health
from app.db.postgres import init_db
from app.notes.exceptions import NoteNotFoundError, NoteValidationError


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.config import settings
    from app.llm_dashscope import configure_dashscope

    configure_dashscope()
    from app.llm_dashscope import compatible_base_url

    print(
        "[CONFIG] "
        f"vector_top_k={settings.RAG_VECTOR_TOP_K} "
        f"bm25_top_k={settings.RAG_BM25_TOP_K} "
        f"rrf_k={settings.RAG_RRF_K} "
        f"score_ratio={settings.RAG_SCORE_THRESHOLD_RATIO} "
        f"score_min={settings.RAG_SCORE_MIN} "
        f"max_results={settings.RAG_MAX_RESULTS} "
        f"vector_min={settings.RAG_VECTOR_MIN_SCORE} "
        f"bm25_min={settings.RAG_BM25_MIN_SCORE} "
        f"hyde={settings.RAG_USE_HYDE} bm25={settings.RAG_USE_BM25} "
        f"qwen_model={settings.QWEN_MODEL} "
        f"dashscope_compatible={compatible_base_url()}",
        flush=True,
    )
    try:
        init_db()
        print("[startup] database tables ready")
    except Exception as exc:  # noqa: BLE001
        print(f"[startup] init_db failed: {exc}")
    try:
        from app.rag.bm25_index import rebuild_all_bm25_indexes

        rebuild_all_bm25_indexes()
    except Exception as exc:  # noqa: BLE001
        print(f"[startup] BM25 rebuild skipped: {exc}")
    yield


app = FastAPI(
    title="多媒体学习资料智能知识库助手",
    description="Video/document → notes → optional RAG knowledge base",
    version="0.1.0",
    lifespan=lifespan,
)

# /health 在根路径；业务接口统一 /api/*
app.include_router(health.router)
app.include_router(api_router, prefix="/api")


@app.get("/")
def root():
    return {
        "name": "multimedia-knowledge-base",
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
    }


@app.exception_handler(NoteNotFoundError)
async def note_not_found_handler(
    _request: Request, exc: NoteNotFoundError
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(NoteValidationError)
async def note_validation_handler(
    _request: Request, exc: NoteValidationError
) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
