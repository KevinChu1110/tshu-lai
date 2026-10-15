"""音訊正規化：轉 16kHz 單聲道 WAV，依靜音切段。只依賴 ffmpeg。"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def duration_seconds(path: Path) -> float:
    out = _run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "json", str(path),
    ]).stdout
    return float(json.loads(out)["format"]["duration"])


def to_wav16k(src: Path, dst: Path) -> Path:
    """轉成訓練用格式。保留原檔，不覆蓋。"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    _run([
        "ffmpeg", "-y", "-i", str(src),
        "-ac", "1", "-ar", "16000", "-sample_fmt", "s16",
        "-af", "highpass=f=60",  # 去掉冷氣低頻嗡嗡聲
        str(dst),
    ])
    return dst


_SILENCE_RE = re.compile(r"silence_(start|end): ([\d.]+)")


def split_on_silence(
    wav: Path,
    out_dir: Path,
    *,
    min_silence: float = 1.2,
    noise_db: int = -35,
    min_segment: float = 3.0,
    max_segment: float = 15.0,
) -> list[Path]:
    """依靜音把長錄音切成 3 到 15 秒的段落。聲音複製訓練喜歡這個長度。

    回傳切出來的檔案清單。切不出來（整段沒有靜音）就整檔一段。
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    probe = subprocess.run(
        [
            "ffmpeg", "-i", str(wav), "-af",
            f"silencedetect=noise={noise_db}dB:d={min_silence}", "-f", "null", "-",
        ],
        capture_output=True, text=True,
    ).stderr

    total = duration_seconds(wav)
    marks = [(m.group(1), float(m.group(2))) for m in _SILENCE_RE.finditer(probe)]

    # 把 silence_start/end 配對成「有聲音」的區間
    speech: list[tuple[float, float]] = []
    cursor = 0.0
    for kind, t in marks:
        if kind == "start":
            if t - cursor >= 0.3:
                speech.append((cursor, t))
        else:
            cursor = t
    if total - cursor >= 0.3:
        speech.append((cursor, total))
    if not speech:
        speech = [(0.0, total)]

    # 合併太短的、拆開太長的
    merged: list[tuple[float, float]] = []
    for s, e in speech:
        if merged and (e - merged[-1][0]) <= max_segment and (merged[-1][1] - merged[-1][0]) < min_segment:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    final: list[tuple[float, float]] = []
    for s, e in merged:
        while e - s > max_segment:
            final.append((s, s + max_segment))
            s += max_segment
        if e - s >= 1.0:
            final.append((s, e))

    outputs = []
    for i, (s, e) in enumerate(final, 1):
        dst = out_dir / f"{wav.stem}_seg{i:03d}.wav"
        _run(["ffmpeg", "-y", "-i", str(wav), "-ss", f"{s:.3f}", "-to", f"{e:.3f}", "-c", "copy", str(dst)])
        outputs.append(dst)
    return outputs
