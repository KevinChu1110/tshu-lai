"""給未來的留言。檔名 future_給誰_哪一天.ext：
  future_阿融_生日.m4a        -> 需要人格卡 people 裡有生日，否則當 manual
  future_阿融_2030-05-20.m4a  -> 那天播一次
  future_全家_過年.m4a        -> manual:過年（由 calendar plugin 觸發）
  future_阿融_心情不好.m4a    -> manual:心情不好（使用者自己按）
"""

from __future__ import annotations

import re
from pathlib import Path

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$|^\d{2}-\d{2}$")


def parse_future_dir(root: Path, birthdays: dict[str, str] | None = None) -> list[tuple[str, str, str]]:
    out = []
    d = root / "future"
    if not d.exists():
        return out
    birthdays = birthdays or {}
    for p in sorted(d.iterdir()):
        if not p.is_file() or p.name.startswith("."):
            continue
        parts = p.stem.split("_")
        if len(parts) < 3 or parts[0] != "future":
            continue
        who, when = parts[1], "_".join(parts[2:])
        if DATE_RE.match(when):
            trig = when
        elif when == "生日" and who in birthdays:
            trig = birthdays[who][5:] if len(birthdays[who]) == 10 else birthdays[who]
        else:
            trig = f"manual:{when}"
        out.append((str(p.relative_to(root)), who, trig))
    return out
