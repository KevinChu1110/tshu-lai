"""把逐字稿與 notes/log.md 整理成記憶庫可以吃的 stories.jsonl。

log.md 每行格式（空白或 | 分隔皆可）：
    2026-10-18 | 20261018_阿公熟似_01.m4a | 阿公,媽祖廟 | 1960s | 懷念
欄位：日期、檔名、提到的人（逗號分隔）、年代、情緒。後三欄可省略。
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def parse_log(log_md: Path) -> dict[str, dict]:
    notes: dict[str, dict] = {}
    if not log_md.exists():
        return notes
    for line in log_md.read_text(encoding="utf-8").splitlines():
        line = line.strip().lstrip("-*| ").rstrip("| ")
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in re.split(r"\s*\|\s*|\s{2,}", line) if p.strip()]
        if len(parts) < 2:
            continue
        date, filename, *rest = parts
        people = [x.strip() for x in rest[0].split(",")] if len(rest) > 0 and rest[0] else []
        notes[Path(filename).stem] = {
            "date": date,
            "people": people,
            "era": rest[1] if len(rest) > 1 else None,
            "mood": rest[2] if len(rest) > 2 else None,
        }
    return notes


def build(root: Path, out: Path) -> int:
    notes = parse_log(root / "notes" / "log.md")
    transcripts_dir = root / "work" / "transcripts"
    count = 0
    with out.open("w", encoding="utf-8") as f:
        for tj in sorted(transcripts_dir.glob("*.json")) if transcripts_dir.exists() else []:
            data = json.loads(tj.read_text(encoding="utf-8"))
            stem = Path(data["source"]).stem
            # 切段檔名 xxx_seg001 -> 原檔 xxx
            base = re.sub(r"_seg\d{3}$", "", stem)
            meta = notes.get(base, {})
            for i, seg in enumerate(data["segments"]):
                rec = {
                    "id": f"{stem}#{i}",
                    "source": data["source"],
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": seg["text"],
                    "people": meta.get("people", []),
                    "era": meta.get("era"),
                    "mood": meta.get("mood"),
                    "recorded_on": meta.get("date"),
                    "asr_model": data.get("model"),
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                count += 1
    return count
