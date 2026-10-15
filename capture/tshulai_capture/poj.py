"""台語白話字逐字稿：聲音模型微調資料的準備流程。

1. transcribe 產出的是華語漢字草稿（Breeze-ASR 會把台語轉成華語字）。
2. draft：每一段送 Taigi 翻譯模型（Ollama）轉成白話字（POJ）草稿，連同漢字字幕寫成 TSV。
3. 人工校正：家人邊聽邊改 TSV 的 poj 欄，照阿嬤實際的發音與變調改。這一步最花時間，也最重要。
4. export：校正過（checked 欄填 1）的段落輸出成 GPT-SoVITS 訓練清單 `wav路徑|說話人|語言|文字`。
"""

from __future__ import annotations

import csv
import json
import urllib.request
from pathlib import Path

FIELDS = ["wav", "start", "end", "zh", "han", "poj", "checked", "note"]


def translate(text: str, target: str, url: str, model: str) -> str:
    prompt = f"[TRANS]\n{text}\n[/TRANS]\n[{target}]\n"
    body = json.dumps({"model": model, "prompt": prompt, "raw": True, "stream": False,
                       "options": {"temperature": 0, "stop": [f"[/{target}]"]}}).encode()
    req = urllib.request.Request(f"{url.rstrip('/')}/api/generate", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["response"].strip()


def draft(root: Path, url: str | None, model: str = "taigi-translator") -> list[Path]:
    """對每份逐字稿產生 work/poj/<名稱>.tsv。已存在的不覆蓋（避免蓋掉人工校正）。"""
    tdir, out_dir = root / "work" / "transcripts", root / "work" / "poj"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for tj in sorted(tdir.glob("*.json")) if tdir.exists() else []:
        out = out_dir / f"{tj.stem}.tsv"
        if out.exists():
            continue
        data = json.loads(tj.read_text(encoding="utf-8"))
        wav = _find_wav(root, data["source"])
        with out.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, FIELDS, delimiter="\t")
            w.writeheader()
            for seg in data["segments"]:
                zh = seg["text"]
                han = translate(zh, "HAN", url, model) if url else ""
                poj = translate(zh, "POJ", url, model) if url else ""
                w.writerow({"wav": wav, "start": f"{seg['start']:.2f}", "end": f"{seg['end']:.2f}",
                            "zh": zh, "han": han, "poj": poj, "checked": "0", "note": ""})
        written.append(out)
    return written


def _find_wav(root: Path, source: str) -> str:
    for p in (root / "work").rglob(Path(source).name):
        return str(p.relative_to(root))
    return source


def export(root: Path, speaker: str = "ama", lang: str = "tw") -> tuple[Path, int, int]:
    """輸出 checked=1 的段落。回傳 (清單路徑, 收錄段數, 未校正段數)。

    一份逐字稿對應一個已切好的 3 到 12 秒段落時直接用；整段長錄音的話依 start/end 用 ffmpeg 切出來。
    """
    import subprocess

    poj_dir, clips = root / "work" / "poj", root / "work" / "tts_clips"
    clips.mkdir(parents=True, exist_ok=True)
    lines, skipped = [], 0
    for tsv in sorted(poj_dir.glob("*.tsv")) if poj_dir.exists() else []:
        with tsv.open(encoding="utf-8") as f:
            for i, row in enumerate(csv.DictReader(f, delimiter="\t")):
                if row["checked"].strip() != "1" or not row["poj"].strip():
                    skipped += 1
                    continue
                start, end = float(row["start"]), float(row["end"])
                if not 1.0 <= end - start <= 15.0:
                    skipped += 1
                    continue
                clip = clips / f"{tsv.stem}_{i:03d}.wav"
                if not clip.exists():
                    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(root / row["wav"]),
                                    "-ss", f"{start:.2f}", "-to", f"{end:.2f}", "-ac", "1", str(clip)], check=True)
                lines.append(f"{clip.resolve()}|{speaker}|{lang}|{row['poj'].strip()}")
    out = root / "work" / "tts_train.list"
    out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return out, len(lines), skipped
