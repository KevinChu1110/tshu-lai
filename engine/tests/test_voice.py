import io
import json
import threading
import wave
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from tshulai.voice.pipeline import PhraseCache, TaigiSoVITS, TaigiTranslator, to_wav


def _wav(seconds=0.2, sr=16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"\x00\x00" * int(sr * seconds))
    return buf.getvalue()


class FakeServers(BaseHTTPRequestHandler):
    """同時假裝 Ollama（/api/generate）和 GPT-SoVITS-TW（/api/synthesize、/audio/x.mp3）。"""
    calls: list = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeServers.calls.append((self.path, body))
        if self.path == "/api/generate":
            out = {"response": "Lí tńg--lâi ah ho͘h? " if "[POJ]" in body["prompt"] else "你轉來矣喔？"}
        else:
            out = {"mp3": "/x.mp3", "key": "k", "url": "/audio/k.wav"}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        data = _wav()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(data)


def _serve():
    srv = HTTPServer(("127.0.0.1", 0), FakeServers)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"


def test_taigi_pipeline_translates_then_synthesizes(tmp_path: Path):
    srv, url = _serve()
    try:
        tr = TaigiTranslator(url, "taigi")
        tts = PhraseCache(TaigiSoVITS(url, tmp_path / "ref.wav", tr, "ama"), tmp_path / "cache")
        audio = tts.synth("你回來了嗎？")
        assert audio[:4] == b"RIFF"
        paths = [p for p, _ in FakeServers.calls]
        assert paths == ["/api/generate", "/api/synthesize"]
        assert FakeServers.calls[0][1]["prompt"].endswith("[POJ]\n")
        assert FakeServers.calls[1][1]["text"].startswith("Lí tńg")          # TTS 收到白話字，不是漢字
        assert FakeServers.calls[1][1]["apply_sandhi"] is True
        tts.synth("你回來了嗎？")                                               # 第二次走快取
        assert len(FakeServers.calls) == 2
        assert tr.translate("你回來了嗎？", "HAN") == "你轉來矣喔？"            # 字幕用漢字
    finally:
        srv.shutdown()


def test_to_wav_passthrough_and_convert(tmp_path: Path):
    import shutil
    import subprocess

    import pytest

    w = _wav()
    assert to_wav(w) is w
    if not shutil.which("ffmpeg"):
        pytest.skip("no ffmpeg")
    mp3 = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "wav", "-i", "pipe:0", "-f", "mp3", "pipe:1"],
                         input=w, capture_output=True, check=True).stdout
    assert to_wav(mp3)[:4] == b"RIFF"
