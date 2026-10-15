import json
from datetime import date
from pathlib import Path

from tshulai.future import parse_future_dir
from tshulai.memory import MemoryStore
from tshulai.persona import load_persona
from tshulai.plugins import load_manifests
from tshulai.simulator import LifeSimulator
from tshulai.storage.drive import DriveMirror
from tshulai.voice import SentenceSplitter

REPO = Path(__file__).resolve().parents[2]


def test_splitter_streams_sentences():
    sp = SentenceSplitter()
    out = []
    for ch in "轉來矣喔？食飽未？阿嬤今仔日煮滷肉，你緊來食啦":
        out += sp.feed(ch)
    out += sp.flush()
    assert out[:2] == ["轉來矣喔？", "食飽未？"]
    assert out[2] == "阿嬤今仔日煮滷肉，你緊來食啦"
    assert "".join(out) == "轉來矣喔？食飽未？阿嬤今仔日煮滷肉，你緊來食啦"


def test_future_parse(tmp_path: Path):
    d = tmp_path / "future"
    d.mkdir()
    for n in ("future_阿融_2030-05-20.m4a", "future_阿融_生日.m4a", "future_全家_過年.m4a", "notes.txt"):
        (d / n).write_bytes(b"x")
    got = {p.split("/")[-1]: t for p, _, t in parse_future_dir(tmp_path, {"阿融": "1995-11-10"})}
    assert got["future_阿融_2030-05-20.m4a"] == "2030-05-20"
    assert got["future_阿融_生日.m4a"] == "11-10"
    assert got["future_全家_過年.m4a"] == "manual:過年"
    m = MemoryStore(tmp_path / "p.db")
    m.sync_future_messages(parse_future_dir(tmp_path, {"阿融": "1995-11-10"}))
    assert len(m.due_future_messages("2030-11-10", "阿融")) == 1   # 生日每年
    assert len(m.due_future_messages("2030-05-20", "阿融")) == 1
    assert len(m.manual_future_messages("阿舅")) == 1               # 全家的大家都有


def test_simulator_deterministic_and_uses_trips(tmp_path: Path):
    card = load_persona(REPO / "spec" / "examples" / "persona.example.yaml")
    m = MemoryStore(tmp_path / "p.db")
    sim = LifeSimulator(card, m)
    a = sim.generate(date(2026, 10, 10), trips_facts=["阿融去淡水"])
    b = sim.generate(date(2026, 10, 10))
    assert a == b and any("淡水" in e for e in a)
    assert any("國慶" in e for e in a)


def test_plugin_manifests_load():
    plugins = load_manifests([REPO / "plugins", REPO / "plugins" / "examples"])
    names = {p.name for p in plugins}
    assert {"weather-tw", "tv-taiwan"} <= names


class _Req:
    def __init__(self, v):
        self.v = v

    def execute(self):
        return self.v


class FakeFiles:
    """模擬 Drive：root -> trips/ -> 阿融_1.jpg"""

    def list(self, q, **kw):
        if "'ROOT' in parents" in q:
            return _Req({"files": [{"id": "T", "name": "trips", "mimeType": "application/vnd.google-apps.folder", "modifiedTime": "x"}]})
        if "'T' in parents" in q:
            return _Req({"files": [{"id": "F1", "name": "阿融_1.jpg", "mimeType": "image/jpeg", "md5Checksum": "abc",
                                    "modifiedTime": "2026-10-12T00:00:00Z", "owners": [{"displayName": "阿融"}],
                                    "imageMediaMetadata": {"location": {"latitude": 25.1, "longitude": 121.4}}}]})
        return _Req({"files": []})


class FakeService:
    def files(self):
        return FakeFiles()


def test_drive_mirror_sync(tmp_path: Path, monkeypatch):
    mirror = DriveMirror(None, "ROOT", tmp_path / "drive", service=FakeService())
    downloads = []
    monkeypatch.setattr(mirror, "_download", lambda fid, dst: (downloads.append(fid), dst.parent.mkdir(parents=True, exist_ok=True), dst.write_bytes(b"jpg")))
    assert mirror.sync() == ["trips/阿融_1.jpg"]
    assert mirror.sync() == []                       # 沒變就不重下載
    assert downloads == ["F1"]
    assert mirror.file_meta("trips/阿融_1.jpg")["lat"] == 25.1
    assert "audio/story" in mirror.missing_folders()
    state = json.loads((tmp_path / "drive" / ".drive_state.json").read_text())
    assert "trips/阿融_1.jpg" in state["files"]
