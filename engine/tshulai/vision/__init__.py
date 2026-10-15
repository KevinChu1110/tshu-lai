"""影像管線。兩種介面（見 docs/research/vision.md）：

- 串流型：即時嘴型。LiveTalking（MuseTalk 1.5）跑在有 NVIDIA GPU 的機器上，client 直接用 WebRTC 連它，
  引擎把 TTS 產生的音檔推給它（/humanaudio）。Mac 不做即時嘴型。
- 工作型：合照好版、待機影片。ComfyUI workflow：上傳 → /prompt → 輪詢 /history → /view 取結果。
"""

from .comfy import ComfyClient
from .label import mark_ai_image
from .livetalking import LiveTalking
from .poses import PoseLibrary

__all__ = ["ComfyClient", "LiveTalking", "PoseLibrary", "mark_ai_image"]
