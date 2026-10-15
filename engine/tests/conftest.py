import pytest


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    """每個測試用自己的 data 目錄，不碰 repo 的 data/。"""
    monkeypatch.setenv("TSHULAI_DATA", str(tmp_path / "data"))
    monkeypatch.setenv("TSHULAI_LLM", "echo")
    for k in ("TSHULAI_DRIVE_FOLDER", "TSHULAI_TTS", "TSHULAI_STT"):
        monkeypatch.delenv(k, raising=False)
    yield tmp_path / "data"
