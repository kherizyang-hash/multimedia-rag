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

    # DashScope / 通义千问（百炼工作空间独立域名）
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")
    # 可选：原生 DashScope /api/v1（当前业务走 OpenAI 兼容端点）
    DASHSCOPE_BASE_URL: str = os.getenv("DASHSCOPE_BASE_URL", "")
    # 控制台「OpenAI 兼容」Base URL（Generation / Embedding 实际使用）
    DASHSCOPE_COMPATIBLE_BASE_URL: str = os.getenv(
        "DASHSCOPE_COMPATIBLE_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    QWEN_MODEL: str = os.getenv("QWEN_MODEL", "qwen-plus")
    QWEN_MAX_TOKENS: int = int(os.getenv("QWEN_MAX_TOKENS", "4000"))
    # 长文摘要：≤ 此字数走单次千问；超过则 map-reduce
    QWEN_SINGLE_THRESHOLD: int = int(os.getenv("QWEN_SINGLE_THRESHOLD", "5000"))
    # map 阶段每块目标字符数（在阈值附近找句边界）
    QWEN_MAP_CHUNK_SIZE: int = int(os.getenv("QWEN_MAP_CHUNK_SIZE", "3500"))

    # Collection / embedding
    MILVUS_COLLECTION: str = os.getenv("MILVUS_COLLECTION", "note_chunks")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "1536"))

    # RAG 切片参数（单层：按句边界，默认 500 / 50）
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "500"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "50"))

    # DashScope 批量嵌入上限
    EMBEDDING_BATCH_SIZE: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "25"))

    # RAG 混合检索：HyDE + 向量 + BM25 + RRF
    RAG_USE_HYDE: bool = os.getenv("RAG_USE_HYDE", "true").lower() == "true"
    RAG_USE_BM25: bool = os.getenv("RAG_USE_BM25", "true").lower() == "true"
    RAG_VECTOR_TOP_K: int = int(os.getenv("RAG_VECTOR_TOP_K", "15"))
    RAG_BM25_TOP_K: int = int(os.getenv("RAG_BM25_TOP_K", "15"))
    RAG_RRF_K: int = int(os.getenv("RAG_RRF_K", "60"))
    RAG_SCORE_THRESHOLD_RATIO: float = float(
        os.getenv("RAG_SCORE_THRESHOLD_RATIO", "0.5")
    )
    # RRF 绝对分数下限；低于此值直接丢弃（默认适配 k=60 的弱命中）
    RAG_SCORE_MIN: float = float(os.getenv("RAG_SCORE_MIN", "0.01"))
    # RRF 融合并分数过滤后，按排名最多保留条数（相对阈值对挤在一起的 RRF 分区分力弱）
    RAG_MAX_RESULTS: int = int(os.getenv("RAG_MAX_RESULTS", "3"))
    # 向量检索绝对相似度下限（Milvus COSINE，越高越相关；无关问句常见 <0.35）
    RAG_VECTOR_MIN_SCORE: float = float(
        os.getenv("RAG_VECTOR_MIN_SCORE", "0.35")
    )
    # BM25 原始分数绝对下限（rank-bm25；弱命中常接近 0）
    RAG_BM25_MIN_SCORE: float = float(os.getenv("RAG_BM25_MIN_SCORE", "1.0"))

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
