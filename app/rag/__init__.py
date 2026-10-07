"""RAG 模块公共接口。"""

from app.rag.chunker import chunk_text
from app.rag.embedder import embed_text, embed_texts
from app.rag.retriever import retrieve, search
from app.rag.bm25_index import (
    build_bm25_index,
    delete_bm25_index,
    rebuild_all_bm25_indexes,
    search_bm25,
)
from app.rag.store import count_chunks, delete_chunks, insert_chunks, list_chunks, search_chunks

__all__ = [
    "embed_text",
    "embed_texts",
    "chunk_text",
    "insert_chunks",
    "delete_chunks",
    "count_chunks",
    "search_chunks",
    "list_chunks",
    "search",
    "retrieve",
    "build_bm25_index",
    "delete_bm25_index",
    "rebuild_all_bm25_indexes",
    "search_bm25",
]
