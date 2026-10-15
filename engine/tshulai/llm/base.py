from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass
class Turn:
    role: str  # "user" | "persona"
    text: str


class LLM(ABC):
    """對話腦的介面。回傳文字串流，語音管線會一句一句接去合成。"""

    @abstractmethod
    def stream(self, system: str, history: list[Turn], user_text: str) -> AsyncIterator[str]: ...
