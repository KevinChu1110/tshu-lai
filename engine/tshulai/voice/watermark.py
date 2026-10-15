"""AudioSeal 浮水印（MIT）。需要 torch + audioseal（uv sync --extra voice）。

- AudioSeal 只吃 16 kHz：先重採樣到 16k 算浮水印，再採樣回原取樣率疊回去。
- 16-bit 訊息 = persona id 的雜湊，事後用 detector 讀得出是哪個分身產生的。
"""

from __future__ import annotations

import hashlib
import io

import torch
import torchaudio
from audioseal import AudioSeal

_gen = None


def message_bits(persona_id: str) -> torch.Tensor:
    n = int.from_bytes(hashlib.sha256(persona_id.encode()).digest()[:2], "big")
    return torch.tensor([[(n >> i) & 1 for i in range(16)]], dtype=torch.int32)


def embed(wav: bytes, persona_id: str = "") -> bytes:
    global _gen
    if _gen is None:
        _gen = AudioSeal.load_generator("audioseal_wm_16bits")
    audio, sr = torchaudio.load(io.BytesIO(wav))
    mono = audio.mean(0, keepdim=True)
    a16 = torchaudio.functional.resample(mono, sr, 16000) if sr != 16000 else mono
    with torch.no_grad():
        wm = _gen.get_watermark(a16.unsqueeze(0), 16000, message=message_bits(persona_id) if persona_id else None).squeeze(0)
    if sr != 16000:
        wm = torchaudio.functional.resample(wm, 16000, sr)
    out = io.BytesIO()
    torchaudio.save(out, (audio + wm[..., : audio.shape[-1]]).clamp(-1, 1), sr, format="wav")
    return out.getvalue()
