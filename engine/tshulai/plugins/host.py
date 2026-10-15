"""Plugin host。一個 plugin = 一個 MCP server + 一份 manifest.yaml（schema 在 spec/）。

約定（knowledge / trigger plugin 用）：
  - tool `topics`       → 回傳今天可以聊的話題，每行一個。生活模擬器每天早上收一次。
  - tool `poll_events`  → 回傳待觸發事件，每行一個事件名（如 tv.program_started）。引擎每分鐘問一次。
其他 tool 由 manifest provides.tools 列出，對話腦可以呼叫。
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

log = logging.getLogger(__name__)
SCHEMA = Path(__file__).resolve().parents[3] / "spec" / "plugin-manifest.schema.json"


@dataclass
class LoadedPlugin:
    manifest: dict
    root: Path
    session: object | None = None
    tools: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.manifest["name"]


def load_manifests(dirs: list[Path], enabled: list[str] | None = None) -> list[LoadedPlugin]:
    validator = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    out = []
    for d in dirs:
        for mf in sorted(d.glob("*/manifest.yaml")) if d.exists() else []:
            m = yaml.safe_load(mf.read_text(encoding="utf-8"))
            errs = list(validator.iter_errors(m))
            if errs:
                log.warning("plugin %s manifest 不合規格，略過：%s", mf.parent.name, errs[0].message)
                continue
            if enabled is not None and m["name"] not in enabled:
                continue
            if m.get("commercial_ok") is False:
                log.warning("plugin %s 的模型權重不可商用（%s），只能個人家用", m["name"], m.get("weights_license", "?"))
            out.append(LoadedPlugin(m, mf.parent))
    return out


class PluginHost:
    def __init__(self, plugins: list[LoadedPlugin], extra_env: dict[str, str] | None = None):
        self.plugins = {p.name: p for p in plugins}
        self.extra_env = extra_env or {}
        self._stack = AsyncExitStack()

    async def start(self) -> None:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        for p in self.plugins.values():
            srv = p.manifest["server"]
            try:
                if "url" in srv:
                    from mcp.client.streamable_http import streamable_http_client

                    streams = await self._stack.enter_async_context(streamable_http_client(srv["url"]))
                    read, write = streams[0], streams[1]
                else:
                    params = StdioServerParameters(
                        command=srv["command"], args=srv.get("args", []),
                        env={**os.environ, **(srv.get("env") or {}), **self.extra_env}, cwd=str(p.root),
                    )
                    read, write = await self._stack.enter_async_context(stdio_client(params))
                session = await self._stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                p.session = session
                p.tools = [t.name for t in (await session.list_tools()).tools]
                log.info("plugin %s 啟動，tools=%s", p.name, p.tools)
            except Exception as e:
                log.warning("plugin %s 啟動失敗：%s", p.name, e)

    async def stop(self) -> None:
        await self._stack.aclose()

    async def call(self, plugin: str, tool: str, args: dict | None = None) -> str:
        p = self.plugins[plugin]
        if not p.session or tool not in p.tools:
            raise KeyError(f"{plugin} 沒有 {tool}")
        res = await p.session.call_tool(tool, args or {})
        return "\n".join(c.text for c in res.content if getattr(c, "type", "") == "text")

    async def _collect(self, tool: str, kind: str) -> list[str]:
        out = []
        for p in self.plugins.values():
            if kind in p.manifest["kind"] and tool in p.tools:
                try:
                    text = await self.call(p.name, tool)
                    out.extend(line.strip() for line in text.splitlines() if line.strip())
                except Exception as e:
                    log.warning("plugin %s.%s 失敗：%s", p.name, tool, e)
        return out

    async def topics(self) -> list[str]:
        return await self._collect("topics", "knowledge")

    async def poll_events(self) -> list[str]:
        return await self._collect("poll_events", "trigger")
