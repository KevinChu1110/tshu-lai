"""記憶庫：SQLite 單檔。向量索引之後接 sqlite-vec，現在先用 FTS5 關鍵字檢索撐著。"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS people (
  id TEXT PRIMARY KEY,
  called TEXT NOT NULL,            -- 她怎麼叫這個人（JSON array）
  relation TEXT,
  attitude TEXT,
  status TEXT,                     -- alive / passed / unknown
  notes TEXT
);
CREATE TABLE IF NOT EXISTS stories (
  id TEXT PRIMARY KEY,
  source TEXT,                     -- 原始錄音檔名
  start REAL, "end" REAL,
  text TEXT NOT NULL,
  people TEXT,                     -- JSON array of people.id 或稱呼
  era TEXT,
  mood TEXT,
  recorded_on TEXT
);
CREATE VIRTUAL TABLE IF NOT EXISTS stories_fts USING fts5(text, content='stories', content_rowid='rowid', tokenize='trigram');
CREATE TRIGGER IF NOT EXISTS stories_ai AFTER INSERT ON stories BEGIN
  INSERT INTO stories_fts(rowid, text) VALUES (new.rowid, new.text);
END;
CREATE TABLE IF NOT EXISTS media (
  path TEXT PRIMARY KEY,
  kind TEXT,                       -- photo / video / audio
  category TEXT,                   -- data/ 下的分類
  tags TEXT                        -- JSON
);
CREATE TABLE IF NOT EXISTS life_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  day TEXT NOT NULL,               -- YYYY-MM-DD
  text TEXT NOT NULL,
  source TEXT,                     -- 哪個 plugin 或 simulator
  mentioned INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS conversations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at TEXT NOT NULL,
  scene TEXT,
  role TEXT NOT NULL,              -- user / persona
  text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS facts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at TEXT NOT NULL,
  text TEXT NOT NULL,              -- 對話中學到的新事實，如「冠融最近工作足忝」
  expires TEXT
);
CREATE TABLE IF NOT EXISTS future_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  for_whom TEXT, trigger TEXT NOT NULL,   -- 日期 YYYY-MM-DD 或 manual:<key>
  path TEXT NOT NULL, played_at TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class MemoryStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    # --- stories -------------------------------------------------------
    def import_stories_jsonl(self, jsonl: Path) -> int:
        n = 0
        with jsonl.open(encoding="utf-8") as f, self.conn:
            for line in f:
                if not line.strip():
                    continue
                r = json.loads(line)
                self.conn.execute(
                    "INSERT OR REPLACE INTO stories(id, source, start, \"end\", text, people, era, mood, recorded_on)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    (r["id"], r.get("source"), r.get("start"), r.get("end"), r["text"],
                     json.dumps(r.get("people", []), ensure_ascii=False), r.get("era"), r.get("mood"), r.get("recorded_on")),
                )
                n += 1
        return n

    def search_stories(self, query: str, k: int = 5) -> list[str]:
        """關鍵字檢索。之後換成向量檢索，介面不變。

        FTS5 預設 tokenizer 不切中文，所以用 trigram；trigram 查詢要三個字以上，
        一兩個字的詞改用 LIKE。
        """
        terms = [t for t in query.replace("　", " ").split() if t]
        if not terms:
            return []
        long_terms = [t for t in terms if len(t) >= 3]
        short_terms = [t for t in terms if len(t) < 3]
        found: list[str] = []
        if long_terms:
            match = " OR ".join('"' + t.replace('"', '""') + '"' for t in long_terms)
            rows = self.conn.execute(
                "SELECT s.text FROM stories_fts f JOIN stories s ON s.rowid = f.rowid WHERE stories_fts MATCH ? LIMIT ?",
                (match, k),
            ).fetchall()
            found.extend(r["text"] for r in rows)
        if short_terms and len(found) < k:
            where = " OR ".join("text LIKE ?" for _ in short_terms)
            rows = self.conn.execute(
                f"SELECT text FROM stories WHERE {where} LIMIT ?",
                tuple(f"%{t}%" for t in short_terms) + (k - len(found),),
            ).fetchall()
            found.extend(r["text"] for r in rows if r["text"] not in found)
        return found[:k]

    # --- conversations & facts ----------------------------------------
    def log_turn(self, role: str, text: str, scene: str | None = None) -> None:
        with self.conn:
            self.conn.execute("INSERT INTO conversations(at, scene, role, text) VALUES (?,?,?,?)", (_now(), scene, role, text))

    def recent_turns(self, n: int = 12) -> list[tuple[str, str]]:
        rows = self.conn.execute("SELECT role, text FROM conversations ORDER BY id DESC LIMIT ?", (n,)).fetchall()
        return [(r["role"], r["text"]) for r in reversed(rows)]

    def add_fact(self, text: str, expires: str | None = None) -> None:
        with self.conn:
            self.conn.execute("INSERT INTO facts(at, text, expires) VALUES (?,?,?)", (_now(), text, expires))

    def recent_facts(self, n: int = 10) -> list[str]:
        rows = self.conn.execute("SELECT text FROM facts ORDER BY id DESC LIMIT ?", (n,)).fetchall()
        return [r["text"] for r in rows]

    # --- life events ---------------------------------------------------
    def add_life_event(self, day: str, text: str, source: str) -> None:
        with self.conn:
            self.conn.execute("INSERT INTO life_events(day, text, source) VALUES (?,?,?)", (day, text, source))

    def todays_events(self, day: str, unmentioned_only: bool = True) -> list[str]:
        sql = "SELECT text FROM life_events WHERE day = ?" + (" AND mentioned = 0" if unmentioned_only else "")
        return [r["text"] for r in self.conn.execute(sql, (day,)).fetchall()]
