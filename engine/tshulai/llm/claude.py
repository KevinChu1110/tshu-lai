"""Claude adapter。預設 claude-opus-5-5，adaptive thinking，effort low 壓延遲。

API key 從環境變數 ANTHROPIC_API_KEY 或 `ant auth login` 的 profile 來，不寫在設定檔。
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from .base import LLM, Turn


class ClaudeLLM(LLM):
    def __init__(self, model: str = "claude-opus-5-5", effort: str = "low", max_tokens: int = 1024):
        import anthropic

        self.client = anthropic.AsyncAnthropic()
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens

    async def stream(self, system: str, history: list[Turn], user_text: str) -> AsyncIterator[str]:
        messages = [{"role": "assistant" if t.role == "persona" else "user", "content": t.text} for t in history]
        # 連續同角色的訊息合併，API 要求 user/assistant 交替
        merged: list[dict] = []
        for m in messages:
            if merged and merged[-1]["role"] == m["role"]:
                merged[-1]["content"] += "\n" + m["content"]
            else:
                merged.append(dict(m))
        if merged and merged[0]["role"] == "assistant":
            merged.insert(0, {"role": "user", "content": "（進門）"})
        merged.append({"role": "user", "content": user_text})

        async with self.client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            thinking={"type": "adaptive"},
            output_config={"effort": self.effort},
            messages=merged,
        ) as stream:
            async for text in stream.text_stream:
                yield text
