from .base import LLM, Turn
from .echo import EchoLLM

__all__ = ["LLM", "Turn", "EchoLLM", "get_llm"]


def get_llm(name: str = "echo", **kwargs) -> LLM:
    """依名字拿 adapter。echo 不打網路，給測試和沒有 API key 的人用。"""
    if name == "echo":
        return EchoLLM()
    if name == "claude":
        from .claude import ClaudeLLM

        return ClaudeLLM(**kwargs)
    raise ValueError(f"不認識的 LLM：{name}")
