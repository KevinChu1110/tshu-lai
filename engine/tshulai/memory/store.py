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
CREATE TABLE IF NOT EXISTS usage (
  day TEXT NOT NULL, member TEXT NOT NULL, seconds REAL DEFAULT 0, reminded INTEGER DEFAULT 0,
  PRIMARY KEY (day, member)
);
CREATE TABLE IF NOT EXISTS handled_events (
  day TEXT NOT NULL, name TEXT NOT NULL, PRIMARY KEY (day, name)
);
CREATE TABLE IF NOT EXISTS trips (
  key TEXT PRIMARY KEY,            -- who:start
  who TEXT, start TEXT, "end" TEXT,
  title TEXT, places TEXT, lat REAL, lng REAL,
  photos TEXT,                     -- JSON array，相對素材根目錄
  told INTEGER DEFAULT 0           -- 數位阿嬤提過沒
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
    def __init__(self, path: Path, embedder=None, vectors: bool = False):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)  # 背景同步執行緒也會寫；寫入都很短，用 SQLite 自己的鎖
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.vec = None
        if vectors or embedder is not None:
            from .vectors import try_vector_index

            self.vec = try_vector_index(self.conn, embedder)

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
        """有向量索引就用語意檢索（「阿公以前做啥」找得到「伊少年時咧做木工」），否則關鍵字。"""
        hits = self.keyword_search(query, k)          # 精確命中（人名、地名）優先
        if self.vec is not None and len(hits) < k:
            try:
                self.vec.index_missing()
                hits += [h for h in self.vec.search(query, k) if h not in hits]
            except Exception:
                pass
        return hits[:k]

    def keyword_search(self, query: str, k: int = 5) -> list[str]:
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

    # --- trips -----------------------------------------------------------
    def upsert_trips(self, trips: list[dict]) -> list[dict]:
        """寫入旅行，回傳新出現的那幾趟。"""
        new = []
        with self.conn:
            for t in trips:
                key = f"{t['who']}:{t['start']}"
                exists = self.conn.execute("SELECT 1 FROM trips WHERE key = ?", (key,)).fetchone()
                self.conn.execute(
                    "INSERT INTO trips(key, who, start, \"end\", title, places, lat, lng, photos) VALUES (?,?,?,?,?,?,?,?,?)"
                    " ON CONFLICT(key) DO UPDATE SET \"end\"=excluded.\"end\", title=excluded.title, places=excluded.places,"
                    " lat=excluded.lat, lng=excluded.lng, photos=excluded.photos",
                    (key, t["who"], t["start"], t["end"], t["title"], json.dumps(t["places"], ensure_ascii=False),
                     t["lat"], t["lng"], json.dumps(t["photos"], ensure_ascii=False)),
                )
                if not exists:
                    new.append(t)
        return new

    def recent_trips(self, n: int = 10) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM trips ORDER BY \"end\" DESC LIMIT ?", (n,)).fetchall()
        return [{**dict(r), "places": json.loads(r["places"]), "photos": json.loads(r["photos"])} for r in rows]

    # --- future messages -----------------------------------------------
    def sync_future_messages(self, files: list[tuple[str, str, str]]) -> None:
        """files: (相對路徑, 給誰, 觸發) 。觸發是 MM-DD、YYYY-MM-DD 或 manual:<名稱>。"""
        with self.conn:
            for path, who, trig in files:
                if not self.conn.execute("SELECT 1 FROM future_messages WHERE path = ?", (path,)).fetchone():
                    self.conn.execute("INSERT INTO future_messages(for_whom, trigger, path) VALUES (?,?,?)", (who, trig, path))

    def due_future_messages(self, today: str, who: str | None = None) -> list[dict]:
        """今天該播的留言。MM-DD 每年播（生日），YYYY-MM-DD 播一次。"""
        rows = self.conn.execute(
            "SELECT * FROM future_messages WHERE (trigger = ? AND played_at IS NULL) OR trigger = ?",
            (today, today[5:]),
        ).fetchall()
        out = [dict(r) for r in rows]
        return [r for r in out if who is None or r["for_whom"] in (who, "全家")]

    def manual_future_messages(self, who: str | None = None) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM future_messages WHERE trigger LIKE 'manual:%'").fetchall()
        return [dict(r) for r in rows if who is None or r["for_whom"] in (who, "全家")]

    def mark_played(self, msg_id: int) -> None:
        with self.conn:
            self.conn.execute("UPDATE future_messages SET played_at = ? WHERE id = ?", (_now(), msg_id))

    # --- 使用節制 -------------------------------------------------------
    def add_usage(self, day: str, member: str, seconds: float) -> float:
        with self.conn:
            self.conn.execute(
                "INSERT INTO usage(day, member, seconds) VALUES (?,?,?) "
                "ON CONFLICT(day, member) DO UPDATE SET seconds = seconds + excluded.seconds", (day, member, seconds))
        return self.conn.execute("SELECT seconds FROM usage WHERE day=? AND member=?", (day, member)).fetchone()[0]

    def should_remind(self, day: str, member: str, limit_seconds: float) -> bool:
        """超過上限且今天還沒提醒過 → True，並記下已提醒。"""
        row = self.conn.execute("SELECT seconds, reminded FROM usage WHERE day=? AND member=?", (day, member)).fetchone()
        if not row or row["seconds"] < limit_seconds or row["reminded"]:
            return False
        with self.conn:
            self.conn.execute("UPDATE usage SET reminded = 1 WHERE day=? AND member=?", (day, member))
        return True

    def first_time_today(self, day: str, event: str) -> bool:
        """同一天同一事件只處理一次（plugin 每分鐘輪詢會重複回報）。"""
        with self.conn:
            cur = self.conn.execute("INSERT OR IGNORE INTO handled_events(day, name) VALUES (?, ?)", (day, event))
        return cur.rowcount == 1
