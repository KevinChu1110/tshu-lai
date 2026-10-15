from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


class ComfyClient:
    """ComfyUI HTTP 介面。workflow 是用 ComfyUI「Export (API)」存下的 JSON，
    放在 engine/workflows/。節點裡的輸入用 {{佔位符}} 標，跑之前替換。"""

    def __init__(self, url: str = "http://127.0.0.1:8188"):
        self.url = url.rstrip("/")
        self.client_id = uuid.uuid4().hex

    def upload_image(self, path: Path) -> str:
        boundary = uuid.uuid4().hex
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{path.name}\"\r\n"
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode() + path.read_bytes() + f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(f"{self.url}/upload/image", data=body,
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())["name"]

    @staticmethod
    def fill(workflow: dict, values: dict[str, object]) -> dict:
        text = json.dumps(workflow, ensure_ascii=False)
        for k, v in values.items():
            text = text.replace(f'"{{{{{k}}}}}"', json.dumps(v, ensure_ascii=False)).replace(f"{{{{{k}}}}}", str(v))
        return json.loads(text)

    def run(self, workflow: dict, timeout: float = 600) -> list[bytes]:
        req = urllib.request.Request(f"{self.url}/prompt",
                                     data=json.dumps({"prompt": workflow, "client_id": self.client_id}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            pid = json.loads(r.read())["prompt_id"]
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with urllib.request.urlopen(f"{self.url}/history/{pid}", timeout=30) as r:
                hist = json.loads(r.read())
            if pid in hist and hist[pid].get("outputs"):
                images = []
                for node in hist[pid]["outputs"].values():
                    for img in node.get("images", []):
                        q = urllib.parse.urlencode({k: img[k] for k in ("filename", "subfolder", "type")})
                        with urllib.request.urlopen(f"{self.url}/view?{q}", timeout=60) as r:
                            images.append(r.read())
                return images
            time.sleep(2)
        raise TimeoutError(f"ComfyUI 工作 {pid} 超過 {timeout} 秒")


WORKFLOWS = Path(__file__).resolve().parents[2] / "workflows"


def insert_person(client: ComfyClient, scene_photo: Path, person_ref: Path, position: str) -> bytes:
    """合照好版：把阿嬤（姿勢庫參考圖）放進照片。position: left / center / right。"""
    wf = json.loads((WORKFLOWS / "insert_person.json").read_text(encoding="utf-8"))
    pos_text = {"left": "站在最左邊", "center": "坐在正中間", "right": "站在最右邊"}[position]
    wf = ComfyClient.fill(wf, {
        "scene_image": client.upload_image(scene_photo),
        "person_image": client.upload_image(person_ref),
        "instruction": f"把第二張圖的老太太自然地加進第一張照片，{pos_text}，光線、陰影、大小和其他人一致，其他人保持不變",
    })
    return client.run(wf)[0]
