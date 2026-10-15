"""素材資料夾結構。Drive 和本機鏡像共用，與 docs/data-collection.md、capture 工具一致。"""

from __future__ import annotations

from pathlib import Path

LAYOUT = [
    "consent",
    "audio/story", "audio/chat", "audio/message",
    "video/talking", "video/expression", "video/idle", "video/greeting",
    "photo/face", "photo/pose", "photo/together", "photo/outdoor", "photo/old",
    "future",
    "notes",
    "trips",            # 家人出去玩的照片，阿嬤看板與記憶都從這裡來
]


def ensure_local_layout(root: Path) -> list[Path]:
    created = []
    for rel in LAYOUT:
        d = root / rel
        if not d.exists():
            d.mkdir(parents=True)
            created.append(d)
    return created
