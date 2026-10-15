"""向量檢索：sqlite-vec（MIT/Apache）+ fastembed 多語模型，全部在家用主機跑。

沒裝 --extra memory 就退回 FTS5 關鍵字檢索，介面不變。
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Protocol

log = logging.getLogger(__name__)
DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"   # 384 維，約 220MB


class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FastEmbedder:
    def __init__(self, model: str = DEFAULT_MODEL):
        from fastembed import TextEmbedding

        self.model = TextEmbedding(model)
        self.dim = len(next(iter(self.model.embed(["測試"]))))

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [list(map(float, v)) for v in self.model.embed(texts)]


class VectorIndex:
    def __init__(self, conn: sqlite3.Connection, embedder: Embedder):
        import sqlite_vec

        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        self.conn = conn
        self.embedder = embedder
        self._ser = sqlite_vec.serialize_float32
        conn.execute(f"CREATE VIRTUAL TABLE IF NOT EXISTS stories_vec USING vec0(id TEXT PRIMARY KEY, embedding float[{embedder.dim}])")

    def index_missing(self, batch: int = 64) -> int:
        rows = self.conn.execute(
            "SELECT id, text FROM stories WHERE id NOT IN (SELECT id FROM stories_vec)").fetchall()
        for i in range(0, len(rows), batch):
            chunk = rows[i:i + batch]
            vecs = self.embedder.embed([r[1] for r in chunk])
            with self.conn:
                self.conn.executemany("INSERT INTO stories_vec(id, embedding) VALUES (?, ?)",
                                      [(r[0], self._ser(v)) for r, v in zip(chunk, vecs)])
        return len(rows)

    def search(self, query: str, k: int = 5) -> list[str]:
        v = self.embedder.embed([query])[0]
        rows = self.conn.execute(
            "SELECT s.text FROM stories_vec v JOIN stories s ON s.id = v.id "
            "WHERE v.embedding MATCH ? AND k = ? ORDER BY v.distance", (self._ser(v), k)).fetchall()
        return [r[0] for r in rows]


def try_vector_index(conn: sqlite3.Connection, embedder: Embedder | None = None) -> VectorIndex | None:
    try:
        return VectorIndex(conn, embedder or FastEmbedder())
    except ImportError:
        return None
    except Exception as e:
        log.warning("向量檢索無法啟用，改用關鍵字：%s", e)
        return None
