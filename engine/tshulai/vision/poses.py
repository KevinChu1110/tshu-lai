"""姿勢庫：照片 → 去背 PNG + 遮罩，供 app 合照快版預覽與 ComfyUI 好版參考。

去背用 BiRefNet（MIT）。不用 RMBG-2.0（CC BY-NC）。需要 uv sync --extra vision。
輸出放 <data>/poses/，index.json 記每張的姿勢標籤（從檔名：pose/20261019_全身坐_沙發_02.jpg → 坐）。
"""

from __future__ import annotations

import json
from pathlib import Path

POSE_WORDS = {"坐": "sit", "站": "stand", "半身": "half", "牽手": "hold_hands", "YA": "peace"}


def pose_tags(name: str) -> list[str]:
    return [tag for word, tag in POSE_WORDS.items() if word in name] or ["stand"]


class PoseLibrary:
    def __init__(self, out_dir: Path):
        self.out_dir = out_dir
        self.index_path = out_dir / "index.json"
        self.index: dict[str, dict] = json.loads(self.index_path.read_text()) if self.index_path.exists() else {}
        self._model = None

    def _matte(self, src: Path):
        import torch
        from PIL import Image
        from torchvision import transforms

        if self._model is None:
            from transformers import AutoModelForImageSegmentation

            self._model = AutoModelForImageSegmentation.from_pretrained("ZhengPeng7/BiRefNet-portrait", trust_remote_code=True)
            self._model.eval()
        im = Image.open(src).convert("RGB")
        tf = transforms.Compose([
            transforms.Resize((1024, 1024)), transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])
        with torch.no_grad():
            pred = self._model(tf(im).unsqueeze(0))[-1].sigmoid()[0, 0]
        mask = transforms.ToPILImage()(pred).resize(im.size)
        rgba = im.copy()
        rgba.putalpha(mask)
        bbox = mask.point(lambda v: 255 if v > 32 else 0).getbbox()
        return rgba.crop(bbox) if bbox else rgba

    def build(self, pose_dirs: list[Path]) -> int:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        n = 0
        for d in pose_dirs:
            for src in sorted(d.glob("*")) if d.exists() else []:
                if src.suffix.lower() not in (".jpg", ".jpeg", ".png", ".heic", ".webp") or src.name in self.index:
                    continue
                cut = self._matte(src)
                dst = self.out_dir / f"{src.stem}.png"
                cut.save(dst)
                self.index[src.name] = {"png": dst.name, "tags": pose_tags(src.stem), "w": cut.width, "h": cut.height}
                n += 1
        self.index_path.write_text(json.dumps(self.index, ensure_ascii=False, indent=1), encoding="utf-8")
        return n

    def list(self) -> list[dict]:
        return [{"source": k, **v} for k, v in self.index.items()]
