"""data/ 資料夾的標準結構與檔名規則。與 docs/data-collection.md 同步。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

AUDIO_EXT = {".wav", ".m4a", ".mp3", ".aac", ".flac", ".ogg", ".opus"}
VIDEO_EXT = {".mp4", ".mov", ".mkv"}
PHOTO_EXT = {".jpg", ".jpeg", ".png", ".heic", ".webp"}

# 相對路徑 -> (說明, 目標量, 單位)
LAYOUT: dict[str, tuple[str, float | None, str]] = {
    "consent": ("同意錄影", 1, "段"),
    "audio/story": ("講故事語音", 90, "分鐘"),
    "audio/chat": ("日常聊天語音", 30, "分鐘"),
    "audio/message": ("LINE 語音訊息", 20, "則"),
    "video/talking": ("正面說話影片", 3, "段"),
    "video/expression": ("表情影片", 6, "種"),
    "video/idle": ("待機動作影片", 4, "種"),
    "video/greeting": ("打招呼句", 10, "句"),
    "photo/face": ("正面與多角度照", 22, "張"),
    "photo/pose": ("全身站、坐照", 12, "張"),
    "photo/together": ("合照", None, "張"),
    "photo/outdoor": ("戶外照", 10, "張"),
    "photo/old": ("老照片", None, "張"),
    "future": ("給未來的留言", None, "則"),
    "notes": ("人物表、作息表、log", None, "份"),
}

# 20261018_阿公熟似_01.m4a  或  future_冠融_結婚.m4a
FILENAME_RE = re.compile(r"^(?:\d{8}_[^_]+(?:_[^_]+)*_\d{2}|future_[^_]+_[^_]+)\.[A-Za-z0-9]+$")


@dataclass
class Item:
    path: Path
    category: str  # LAYOUT 的 key
    kind: str  # audio / video / photo / other

    @property
    def name_ok(self) -> bool:
        return bool(FILENAME_RE.match(self.path.name))


def kind_of(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in AUDIO_EXT:
        return "audio"
    if ext in VIDEO_EXT:
        return "video"
    if ext in PHOTO_EXT:
        return "photo"
    return "other"


def scan(root: Path) -> list[Item]:
    items: list[Item] = []
    for category in LAYOUT:
        d = root / category
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*")):
            if p.is_file() and not p.name.startswith("."):
                items.append(Item(p, category, kind_of(p)))
    return items


def ensure_layout(root: Path) -> list[Path]:
    created = []
    for category in LAYOUT:
        d = root / category
        if not d.exists():
            d.mkdir(parents=True)
            created.append(d)
    return created
