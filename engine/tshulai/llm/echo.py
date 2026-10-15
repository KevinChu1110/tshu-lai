from __future__ import annotations

from collections.abc import AsyncIterator

from .base import LLM, Turn


class EchoLLM(LLM):
    """不打網路。把對方講的話用阿嬤的方式反問回去，測試整條管線用。"""

    async def stream(self, system: str, history: list[Turn], user_text: str) -> AsyncIterator[str]:
        for chunk in ("你講", f"「{user_text}」", "喔？", "按呢喔，", "食飽未？"):
            yield chunk
