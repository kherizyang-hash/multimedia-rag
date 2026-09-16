"""RAG 模块公共接口。"""

from app.rag.chunker import chunk_text
from app.rag.embedder import embed_text, embed_texts
from app.rag.retriever import retrieve, search
from app.rag.store import count_chunks, delete_chunks, insert_chunks, search_chunks

__all__ = [
    "embed_text",
    "embed_texts",
    "chunk_text",
    "insert_chunks",
    "delete_chunks",
    "count_chunks",
    "search_chunks",
    "search",
    "retrieve",
]
