"""笔记模块业务异常。"""


class NoteNotFoundError(Exception):
    """指定笔记不存在。"""


class NoteValidationError(Exception):
    """笔记业务校验失败。"""
