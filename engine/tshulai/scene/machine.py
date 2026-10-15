"""Scene 狀態機。每個 scene 一個 YAML，見 engine/scenes/。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

SCENES_DIR = Path(__file__).resolve().parents[2] / "scenes"


@dataclass
class Scene:
    id: str
    name: str
    description: str
    enter_on: list[str] = field(default_factory=list)   # 事件名，如 geofence.enter:home
    exit_on: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    greeting_pool: str | None = None                     # 從 video/greeting 撈真的錄音的 tag
    always_available: bool = False                       # 閒聊通道這種不綁情境的


def load_scenes(d: Path = SCENES_DIR) -> dict[str, Scene]:
    scenes: dict[str, Scene] = {}
    for p in sorted(d.glob("*.yaml")):
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        s = Scene(**data)
        scenes[s.id] = s
    return scenes


class SceneMachine:
    def __init__(self, scenes: dict[str, Scene], initial: str = "chat"):
        self.scenes = scenes
        self.current = scenes[initial]

    def on_event(self, event: str) -> Scene | None:
        """收到事件，決定要不要換 scene。回傳新 scene（有換才回）。

        先看有沒有 scene 想進來，沒有才看目前 scene 要不要退回閒聊通道。
        """
        for s in self.scenes.values():
            if s is not self.current and event in s.enter_on:
                self.current = s
                return s
        if event in self.current.exit_on:
            fallback = next((s for s in self.scenes.values() if s.always_available), self.current)
            if fallback is not self.current:
                self.current = fallback
                return fallback
        return None
