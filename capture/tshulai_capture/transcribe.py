"""語音辨識草稿。預設 faster-whisper；台語辨識率看模型，先當草稿。

模型可換：環境變數 TSHULAI_ASR_MODEL 指定 HuggingFace 上的 CTranslate2 模型，
例如台語微調版。沒設就用 large-v3，language 設 zh 讓它至少把華語夾雜的部分抓到。
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Segment:
    start: float
    end: float
    text: str


def transcribe(wav: Path, out_json: Path, *, language: str | None = None) -> list[Segment]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:  # pragma: no cover
        raise SystemExit("需要 faster-whisper：uv sync --extra asr") from e

    model_name = os.environ.get("TSHULAI_ASR_MODEL", "weemed/Breeze-ASR-26-ct2")
    model = WhisperModel(model_name, device="auto", compute_type="auto")
    segments, info = model.transcribe(
        str(wav),
        language=language or os.environ.get("TSHULAI_ASR_LANG", "zh"),
        vad_filter=True,
        beam_size=5,
    )
    result = [Segment(s.start, s.end, s.text.strip()) for s in segments]
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(
            {"source": wav.name, "model": model_name, "language": info.language,
             "segments": [asdict(s) for s in result]},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    return result
