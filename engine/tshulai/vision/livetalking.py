from __future__ import annotations

import json
import urllib.request
import uuid


class LiveTalking:
    """LiveTalking 伺服器轉接。client 拿 webrtc_url 自己做 offer/answer，拿到 sessionid 回報給引擎。"""

    def __init__(self, url: str):
        self.url = url.rstrip("/")

    @property
    def webrtc_offer_url(self) -> str:
        return f"{self.url}/offer"

    def push_audio(self, sessionid: str | int, wav: bytes) -> None:
        boundary = uuid.uuid4().hex
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"sessionid\"\r\n\r\n{sessionid}\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"say.wav\"\r\n"
            "Content-Type: audio/wav\r\n\r\n"
        ).encode() + wav + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(f"{self.url}/humanaudio", data=body,
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        urllib.request.urlopen(req, timeout=30).read()

    def interrupt(self, sessionid: str | int) -> None:
        req = urllib.request.Request(f"{self.url}/interrupt_talk", data=json.dumps({"sessionid": sessionid}).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10).read()
