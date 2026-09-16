"""统一配置：仅从环境变量 / .env 读取，密钥不硬编码进源码。"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Zilliz / Milvus — 必须通过 .env 配置
    MILVUS_URI: str = os.getenv("MILVUS_URI", "")
    MILVUS_TOKEN: str = os.getenv("MILVUS_TOKEN", "")

    # PostgreSQL — 密码只从 .env 读取，不硬编码进源码
    PG_HOST: str = os.getenv(
        "PG_HOST", "multimedia-rag-db-postgresql.ns-myfrr2v2.svc"
    )
    PG_PORT: int = int(os.getenv("PG_PORT", "5432"))
    PG_USER: str = os.getenv("PG_USER", "postgres")
    PG_PASSWORD: str = os.getenv("PG_PASSWORD", "")
    PG_DATABASE: str = os.getenv("PG_DATABASE", "postgres")

    # DashScope / 通义千问
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")
    QWEN_MODEL: str = os.getenv("QWEN_MODEL", "qwen-plus")
    QWEN_MAX_TOKENS: int = int(os.getenv("QWEN_MAX_TOKENS", "4000"))

    # Collection / embedding
    MILVUS_COLLECTION: str = os.getenv("MILVUS_COLLECTION", "note_chunks")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "1536"))

    # RAG 切片参数（单层：按句边界，默认 500 / 50）
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "500"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "50"))

    # DashScope 批量嵌入上限
    EMBEDDING_BATCH_SIZE: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "25"))

    # Whisper / 临时音频
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "small")
    TEMP_DIR: str = os.getenv("TEMP_DIR", "/tmp/rag_audio")

    # 哨兵：标量字段「无值」时写入 Milvus
    MISSING_FLOAT: float = -1.0
    MISSING_INT: int = -1

    @property
    def PG_DSN(self) -> str:
        return (
            f"postgresql://{self.PG_USER}:{self.PG_PASSWORD}"
            f"@{self.PG_HOST}:{self.PG_PORT}/{self.PG_DATABASE}"
        )


settings = Settings()
