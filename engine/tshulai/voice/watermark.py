"""AudioSeal 浮水印嵌入。需要 torch + audioseal（uv sync --extra voice）。"""

from __future__ import annotations

import io

import torch
import torchaudio
from audioseal import AudioSeal

_gen = None


def embed(wav: bytes) -> bytes:
    global _gen
    if _gen is None:
        _gen = AudioSeal.load_generator("audioseal_wm_16bits")
    audio, sr = torchaudio.load(io.BytesIO(wav))
    if sr != 16000:
        audio16 = torchaudio.functional.resample(audio, sr, 16000)
    else:
        audio16 = audio
    with torch.no_grad():
        wm = _gen.get_watermark(audio16.unsqueeze(0), 16000).squeeze(0)
    if sr != 16000:
        wm = torchaudio.functional.resample(wm, 16000, sr)
    out = io.BytesIO()
    torchaudio.save(out, audio + wm[..., : audio.shape[-1]], sr, format="wav")
    return out.getvalue()
