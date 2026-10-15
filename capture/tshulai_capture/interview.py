"""載入並印出訪談題庫。"""

from __future__ import annotations

from pathlib import Path

import yaml

DEFAULT_QUESTIONS = Path(__file__).resolve().parents[2] / "docs" / "interview" / "questions.yaml"


def load(path: Path = DEFAULT_QUESTIONS) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)["topics"]


def find_topic(topics: list[dict], key: str) -> dict | None:
    for t in topics:
        if key in (t["id"], t["name"]):
            return t
    return None
