import json
from pathlib import Path

from tshulai.memory import MemoryStore


def test_import_and_search(tmp_path: Path):
    jsonl = tmp_path / "stories.jsonl"
    jsonl.write_text(
        json.dumps({"id": "a#0", "text": "阮佮你阿公是佇媽祖廟熟似的", "people": ["阿公"]}, ensure_ascii=False) + "\n"
        + json.dumps({"id": "a#1", "text": "細漢的時陣厝邊有一隻狗", "people": []}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    m = MemoryStore(tmp_path / "p.db")
    assert m.import_stories_jsonl(jsonl) == 2
    hits = m.search_stories("阿公")
    assert any("阿公" in h for h in hits)


def test_turns_and_facts(tmp_path: Path):
    m = MemoryStore(tmp_path / "p.db")
    m.log_turn("user", "我最近足忝", "chat")
    m.log_turn("persona", "毋通傷忝啦", "chat")
    assert m.recent_turns() == [("user", "我最近足忝"), ("persona", "毋通傷忝啦")]
    m.add_fact("冠融最近工作足忝")
    assert m.recent_facts() == ["冠融最近工作足忝"]


class BagOfCharsEmbedder:
    """測試用：字元出現向量。讓「阿公」和「你阿公」接近，不用下載模型。"""
    dim = 64

    def embed(self, texts):
        out = []
        for t in texts:
            v = [0.0] * self.dim
            for ch in t:
                v[hash(ch) % self.dim] += 1.0
            n = sum(x * x for x in v) ** 0.5 or 1.0
            out.append([x / n for x in v])
        return out


def test_vector_search(tmp_path: Path):
    import pytest

    pytest.importorskip("sqlite_vec")
    jsonl = tmp_path / "s.jsonl"
    rows = [("a#0", "阮佮你阿公是佇媽祖廟熟似的"), ("a#1", "細漢的時陣厝邊有一隻狗"), ("a#2", "菜市仔的阿春足愛講話")]
    jsonl.write_text("".join(json.dumps({"id": i, "text": t}, ensure_ascii=False) + "\n" for i, t in rows), encoding="utf-8")
    m = MemoryStore(tmp_path / "p.db", embedder=BagOfCharsEmbedder())
    assert m.vec is not None
    m.import_stories_jsonl(jsonl)
    assert m.search_stories("你阿公佇佗位熟似", k=1) == ["阮佮你阿公是佇媽祖廟熟似的"]
