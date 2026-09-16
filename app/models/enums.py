"""跨模块共享枚举。"""

from enum import Enum


class SourceType(str, Enum):
    VIDEO = "video"
    DOCUMENT = "document"
    LINK = "link"


class ChunkLayer(str, Enum):
    """切片层级。阶段3·B 起采用单层；coarse/fine 保留兼容旧数据。"""

    SINGLE = "single"
    COARSE = "coarse"
    FINE = "fine"


class ConversationType(str, Enum):
    NOTE = "note"
    GLOBAL = "global"
