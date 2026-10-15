from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path

import yaml


@dataclass
class Show:
    name: str
    channel: str
    weekdays: list[int]
    start: time
    end: time


def load(path: Path) -> list[Show]:
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [Show(s["name"], s.get("channel", ""), s.get("weekdays", list(range(1, 8))),
                 time.fromisoformat(s["start"]), time.fromisoformat(s["end"])) for s in raw.get("shows", [])]


def on_air(shows: list[Show], now: datetime) -> Show | None:
    t = now.time()
    return next((s for s in shows if now.isoweekday() in s.weekdays and s.start <= t < s.end), None)


def events(shows: list[Show], now: datetime) -> list[str]:
    """開播或結束後 3 分鐘內回報（引擎每分鐘問一次、同一天同一事件只處理一次）。"""
    out = []
    mins = now.hour * 60 + now.minute
    for s in shows:
        if now.isoweekday() not in s.weekdays:
            continue
        if 0 <= mins - (s.start.hour * 60 + s.start.minute) < 3:
            out.append("tv.program_started")
        if 0 <= mins - (s.end.hour * 60 + s.end.minute) < 3:
            out.append("tv.program_ended")
    return out


def topics(shows: list[Show], now: datetime) -> list[str]:
    out = []
    for s in shows:
        if now.isoweekday() in s.weekdays and now.time() < s.end:
            when = f"{s.start.hour - 12 if s.start.hour > 12 else s.start.hour}點"
            out.append(f"今暗{when}{s.channel}{s.name}，欲做伙看無？")
    cur = on_air(shows, now)
    if cur:
        out.insert(0, f"這馬{cur.channel}咧演{cur.name}")
    return out
