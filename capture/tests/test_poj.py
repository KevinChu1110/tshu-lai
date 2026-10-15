import csv
import json
import subprocess
from pathlib import Path

import pytest

from tshulai_capture import poj


def test_draft_then_export(tmp_path: Path, monkeypatch):
    if subprocess.run(["which", "ffmpeg"], capture_output=True).returncode:
        pytest.skip("no ffmpeg")
    root = tmp_path
    wav = root / "work" / "wav" / "audio" / "story" / "20261018_阿公熟似_01.wav"
    wav.parent.mkdir(parents=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono", "-t", "8", str(wav)], check=True)
    t = root / "work" / "transcripts"
    t.mkdir(parents=True)
    (t / "20261018_阿公熟似_01.json").write_text(json.dumps({"source": wav.name, "segments": [
        {"start": 0.0, "end": 3.5, "text": "我跟你阿公是在媽祖廟認識的"},
        {"start": 3.5, "end": 7.9, "text": "那時候他很瘦"},
    ]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(poj, "translate", lambda text, target, url, model: f"{target}:{text}")
    [tsv] = poj.draft(root, "http://fake")
    rows = list(csv.DictReader(tsv.open(encoding="utf-8"), delimiter="\t"))
    assert rows[0]["poj"].startswith("POJ:") and rows[0]["han"].startswith("HAN:")
    assert poj.draft(root, "http://fake") == []                      # 不覆蓋人工校正
    rows[0]["poj"], rows[0]["checked"] = "Goán kap lí a-kong sī tī Má-tsó͘-biō bat--ê", "1"
    with tsv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, poj.FIELDS, delimiter="\t")
        w.writeheader()
        w.writerows(rows)
    out, n, skipped = poj.export(root)
    assert (n, skipped) == (1, 1)
    line = out.read_text(encoding="utf-8").strip()
    assert line.endswith("|ama|tw|Goán kap lí a-kong sī tī Má-tsó͘-biō bat--ê")
    assert Path(line.split("|")[0]).exists()
