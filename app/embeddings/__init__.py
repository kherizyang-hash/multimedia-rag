"""嵌入层公共导出。"""

from app.embeddings.dashscope_embedder import embed_text, embed_texts

__all__ = ["embed_text", "embed_texts"]
