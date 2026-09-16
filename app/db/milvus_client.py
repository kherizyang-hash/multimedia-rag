"""Milvus / Zilliz Cloud 连接与 note_chunks Collection 初始化。

本模块仅负责基础设施连通，不含切片/入库/搜索业务逻辑。
"""

from __future__ import annotations

from typing import Optional

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from app.config import settings

_ALIAS = "default"


def get_milvus_connection(alias: str = _ALIAS) -> str:
    """连接 Zilliz Cloud；已连接则复用。返回连接 alias。"""
    if not settings.MILVUS_URI or not settings.MILVUS_TOKEN:
        raise RuntimeError(
            "MILVUS_URI / MILVUS_TOKEN 未配置，请在 .env 中填写（参见 .env.example）"
        )

    try:
        if connections.has_connection(alias):
            return alias
    except Exception:
        # 部分版本无 has_connection，继续尝试 connect
        pass

    connections.connect(
        alias=alias,
        uri=settings.MILVUS_URI,
        token=settings.MILVUS_TOKEN,
    )
    return alias


def _build_schema() -> CollectionSchema:
    fields = [
        FieldSchema(
            name="id",
            dtype=DataType.VARCHAR,
            is_primary=True,
            max_length=64,
            description="chunk id",
        ),
        FieldSchema(
            name="embedding",
            dtype=DataType.FLOAT_VECTOR,
            dim=settings.EMBEDDING_DIM,
            description="DashScope text-embedding-v1 vector",
        ),
        FieldSchema(
            name="note_id",
            dtype=DataType.VARCHAR,
            max_length=36,
            description="UUID string of notes.id",
        ),
        FieldSchema(
            name="text",
            dtype=DataType.VARCHAR,
            max_length=65535,
            description="chunk text",
        ),
        FieldSchema(
            name="layer",
            dtype=DataType.VARCHAR,
            max_length=16,
            description="single | coarse | fine",
        ),
        # 无时间戳/页码时使用哨兵值（见 settings.MISSING_*）
        FieldSchema(
            name="start_sec",
            dtype=DataType.FLOAT,
            description="video start second; -1 if N/A",
        ),
        FieldSchema(
            name="end_sec",
            dtype=DataType.FLOAT,
            description="video end second; -1 if N/A",
        ),
        FieldSchema(
            name="page",
            dtype=DataType.INT64,
            description="document page; -1 if N/A",
        ),
        FieldSchema(
            name="metadata",
            dtype=DataType.JSON,
            description="extensible metadata",
        ),
    ]
    return CollectionSchema(
        fields=fields,
        description="Note chunks for multimedia knowledge base",
        enable_dynamic_field=False,
    )


def create_chunks_collection(
    collection_name: Optional[str] = None,
    alias: str = _ALIAS,
) -> Collection:
    """创建 note_chunks 集合（已存在则跳过创建，直接返回）。"""
    get_milvus_connection(alias=alias)
    name = collection_name or settings.MILVUS_COLLECTION

    if utility.has_collection(name, using=alias):
        return Collection(name, using=alias)

    schema = _build_schema()
    collection = Collection(name=name, schema=schema, using=alias)

    # HNSW 索引（Demo 友好）
    index_params = {
        "metric_type": "COSINE",
        "index_type": "HNSW",
        "params": {"M": 16, "efConstruction": 200},
    }
    collection.create_index(field_name="embedding", index_params=index_params)
    return collection


def get_collection(
    collection_name: Optional[str] = None,
    alias: str = _ALIAS,
) -> Collection:
    """返回 note_chunks 集合；不存在则创建。"""
    return create_chunks_collection(collection_name=collection_name, alias=alias)


def list_collections(alias: str = _ALIAS) -> list[str]:
    """列出当前库全部 collection 名称。"""
    get_milvus_connection(alias=alias)
    return utility.list_collections(using=alias)


def disconnect(alias: str = _ALIAS) -> None:
    """断开连接（测试收尾用）。"""
    try:
        connections.disconnect(alias)
    except Exception:
        pass
