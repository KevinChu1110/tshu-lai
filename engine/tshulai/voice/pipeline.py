from __future__ import annotations

import io
import logging
from abc import ABC, abstractmethod
from pathlib import Path

log = logging.getLogger(__name__)

HARD_END = set("。！？!?…～~\n")
SOFT_END = set("，,；;、")


class SentenceSplitter:
    """LLM 串流進來邊收邊切，切出完整句子就交給 TTS，首句延遲壓到最低。

    句號問號驚嘆號：累積到 min_chars 字以上就切（太短的「啦！」併到下一句）。
    逗號：累積到 soft_chars 字以上才切，避免一個「啦，」就送去合成。
    """

    def __init__(self, min_chars: int = 4, soft_chars: int = 12):
        self.buf = ""
        self.min_chars = min_chars
        self.soft_chars = soft_chars

    def feed(self, delta: str) -> list[str]:
        out = []
        for ch in delta:
            self.buf += ch
            n = len(self.buf.strip())
            if (ch in HARD_END and n >= self.min_chars) or (ch in SOFT_END and n >= self.soft_chars):
                out.append(self.buf.strip())
                self.buf = ""
        return out

    def flush(self) -> list[str]:
        rest, self.buf = self.buf.strip(), ""
        return [rest] if rest else []


# --- STT -------------------------------------------------------------------
class STT(ABC):
    @abstractmethod
    def transcribe(self, audio: bytes) -> str: ...


class NoSTT(STT):
    def transcribe(self, audio: bytes) -> str:
        raise RuntimeError("沒有設定語音辨識（config stt）")


class WhisperSTT(STT):
    """faster-whisper。預設 Breeze-ASR-26 的 CTranslate2 版（Apache-2.0，台華混講），
    輸出華語漢字，直接餵給用華語思考的 LLM。見 docs/research/voice.md。"""

    def __init__(self, model: str = "weemed/Breeze-ASR-26-ct2", language: str = "zh"):
        from faster_whisper import WhisperModel

        self.model = WhisperModel(model, device="auto", compute_type="auto")
        self.language = language

    def transcribe(self, audio: bytes) -> str:
        segs, _ = self.model.transcribe(io.BytesIO(audio), language=self.language, vad_filter=True)
        return "".join(s.text for s in segs).strip()


# --- TTS -------------------------------------------------------------------
class TTS(ABC):
    media_type = "audio/wav"

    @abstractmethod
    def synth(self, text: str) -> bytes: ...


class NoTTS(TTS):
    def synth(self, text: str) -> bytes:
        return b""


class GPTSoVITS(TTS):
    """GPT-SoVITS api_v2.py（`python api_v2.py -a 127.0.0.1 -p 9880`）。

    參考音檔與其逐字稿從素材 audio/story 挑一段 3 到 10 秒、情緒平穩的，
    寫在 data/config.yaml 的 tts_ref / tts_ref_text。
    """

    def __init__(self, url: str, ref_audio: Path, ref_text: str, text_lang: str = "zh", prompt_lang: str = "zh"):
        self.url = url.rstrip("/")
        self.ref_audio = ref_audio
        self.ref_text = ref_text
        self.text_lang = text_lang
        self.prompt_lang = prompt_lang

    def synth(self, text: str) -> bytes:
        import json
        import urllib.request

        body = json.dumps({
            "text": text, "text_lang": self.text_lang,
            "ref_audio_path": str(self.ref_audio), "prompt_text": self.ref_text, "prompt_lang": self.prompt_lang,
            "text_split_method": "cut0", "media_type": "wav", "streaming_mode": False,
        }).encode()
        req = urllib.request.Request(f"{self.url}/tts", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return watermark(r.read())


class TaigiTranslator:
    """華語 → 台語。Taigi-Llama-2-Translator-7B（CC-BY-NC-SA，不可商用）的 GGUF 跑在 Ollama。

    同一句跑兩次：POJ 給 TTS 唸，漢字（HAN）給畫面當字幕。結果快取，常用句只翻一次。
    """

    def __init__(self, url: str = "http://127.0.0.1:11434", model: str = "taigi-translator"):
        self.url = url.rstrip("/")
        self.model = model
        self.cache: dict[tuple[str, str], str] = {}

    def translate(self, text: str, target: str = "POJ") -> str:
        import json
        import urllib.request

        key = (text, target)
        if key in self.cache:
            return self.cache[key]
        prompt = f"[TRANS]\n{text}\n[/TRANS]\n[{target}]\n"
        body = json.dumps({"model": self.model, "prompt": prompt, "raw": True, "stream": False,
                           "options": {"temperature": 0, "stop": [f"[/{target}]"]}}).encode()
        req = urllib.request.Request(f"{self.url}/api/generate", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            out = json.loads(r.read())["response"].strip()
        self.cache[key] = out
        return out


class TaigiSoVITS(TTS):
    """KaedeTai/GPT-SoVITS-TW fork（MIT）的 webui 伺服器（`python -m tw_inference.webui`，預設 127.0.0.1:5557）。
    吃 POJ／台羅，不吃漢字；內建連讀變調。不支援串流，所以搭配 PhraseCache。"""

    media_type = "audio/mpeg"

    def __init__(self, url: str, ref_audio: Path | None, translator: TaigiTranslator | None = None):
        self.url = url.rstrip("/")
        self.ref_audio = ref_audio
        self.translator = translator

    def synth(self, text: str) -> bytes:
        import json
        import urllib.request

        poj = self.translator.translate(text, "POJ") if self.translator else text
        body = {"text": poj, "seed": 42, "apply_sandhi": True}
        if self.ref_audio:
            body["ref"] = str(self.ref_audio.resolve())
        req = urllib.request.Request(f"{self.url}/api/synthesize", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            res = json.loads(r.read())
        with urllib.request.urlopen(f"{self.url}{res['url']}", timeout=60) as r:
            return r.read()


class PhraseCache(TTS):
    """常用句預先合成存檔。台語 TTS 在 Mac 上一句 10 到 30 秒，招呼語、口頭禪、離線備援靠這個。"""

    def __init__(self, inner: TTS, cache_dir: Path):
        self.inner = inner
        self.dir = cache_dir
        self.media_type = inner.media_type

    def _path(self, text: str) -> Path:
        import hashlib

        ext = ".mp3" if self.media_type == "audio/mpeg" else ".wav"
        return self.dir / (hashlib.sha1(text.encode()).hexdigest()[:16] + ext)

    def synth(self, text: str) -> bytes:
        p = self._path(text)
        if p.exists():
            return p.read_bytes()
        audio = self.inner.synth(text)
        if audio:
            self.dir.mkdir(parents=True, exist_ok=True)
            p.write_bytes(audio)
        return audio

    def warm(self, phrases: list[str]) -> int:
        return sum(1 for t in phrases if not self._path(t).exists() and self.synth(t))


def watermark(wav: bytes) -> bytes:
    """AudioSeal 浮水印。沒裝就原樣回傳並記一次警告（使用規範要求正式使用時必須開）。"""
    try:
        from .watermark import embed
    except ImportError:
        if not getattr(watermark, "_warned", False):
            log.warning("沒裝 audioseal，生成語音沒有浮水印：uv sync --extra voice")
            watermark._warned = True  # type: ignore[attr-defined]
        return wav
    return embed(wav)


def get_stt(name: str) -> STT:
    if name == "whisper":
        import os

        return WhisperSTT(os.environ.get("TSHULAI_ASR_MODEL", "weemed/Breeze-ASR-26-ct2"))
    return NoSTT()


def get_tts(name: str, *, url: str = "", ref_audio: Path | None = None, ref_text: str = "",
            translator_url: str = "", cache_dir: Path | None = None) -> TTS:
    if name == "taigi":
        tr = TaigiTranslator(translator_url) if translator_url else None
        inner = TaigiSoVITS(url or "http://127.0.0.1:5557", ref_audio, tr)
        return PhraseCache(inner, cache_dir) if cache_dir else inner
    if name == "gptsovits":
        if not ref_audio:
            raise ValueError("gptsovits 需要 tts_ref 參考音檔")
        return GPTSoVITS(url, ref_audio, ref_text)
    return NoTTS()
