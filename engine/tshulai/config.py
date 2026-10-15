"""引擎設定。來源依序：環境變數 > data/config.yaml > 預設值。

data/config.yaml 範例見 spec/examples/config.example.yaml。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]


@dataclass
class DriveConfig:
    enabled: bool = False
    folder_id: str = ""                 # 共享資料夾 ID（網址 folders/ 後面那串）
    service_account: str = "service_account.json"  # service account 金鑰，相對於 data/
    poll_seconds: int = 300


@dataclass
class AuthConfig:
    enabled: bool = False               # 關掉時任何人都能連（只在本機開發用）
    google_client_ids: list[str] = field(default_factory=list)   # 接受哪些 OAuth client 簽的 ID token
    family: dict[str, str] = field(default_factory=dict)          # email -> 稱呼（阿融、阿舅）


@dataclass
class WellbeingConfig:
    """使用節制與道別。數位亡者對生者的影響好壞參半，預設保守。"""
    daily_minutes: int = 90             # 一天跟阿嬤講超過這麼久，她會叫你去休息
    quiet_hours: list[int] = field(default_factory=lambda: [23, 7])  # 這段時間她不主動開口
    farewell: bool = False              # 道別模式：她不再主動找你，對話慢慢收尾


@dataclass
class Config:
    data_dir: Path
    llm: str = "echo"
    user_name: str = "使用者"
    tts: str = "none"                   # none / taigi（台語 fork）/ gptsovits（原版，只會華語）
    translator_url: str = ""            # Ollama，跑 Taigi 翻譯模型；空白就不翻譯
    livetalking_url: str = ""           # 即時嘴型伺服器（需 NVIDIA GPU）
    comfy_url: str = ""                 # ComfyUI，合照好版與待機影片
    tts_url: str = "http://127.0.0.1:9880"
    stt: str = "none"                   # none / whisper
    geocoder: str = "nominatim"         # nominatim / none
    geocoder_contact: str = ""          # Nominatim 使用規範要求聯絡方式
    drive: DriveConfig = field(default_factory=DriveConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    plugins: list[str] = field(default_factory=list)
    vector_memory: bool = True          # 有裝 --extra memory 才會生效
    wellbeing: WellbeingConfig = field(default_factory=WellbeingConfig)
    tts_ref: str = ""                   # 參考音檔，相對於素材根目錄
    tts_ref_text: str = ""

    @property
    def media_roots(self) -> list[Path]:
        """素材根目錄，依序：Drive 鏡像、app 直接上傳的、本機手動放的。"""
        roots = []
        if self.drive.enabled:
            roots.append(self.data_dir / "drive")
        roots += [self.data_dir / "uploads", self.data_dir / "local"]
        return roots


def load_config(data_dir: Path | None = None) -> Config:
    data_dir = Path(data_dir or os.environ.get("TSHULAI_DATA", REPO / "data"))
    raw: dict = {}
    cfg_file = data_dir / "config.yaml"
    if cfg_file.exists():
        raw = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {}
    cfg = Config(
        data_dir=data_dir,
        llm=raw.get("llm", "echo"),
        user_name=raw.get("user_name", "使用者"),
        tts=raw.get("tts", "none"),
        tts_url=raw.get("tts_url", "http://127.0.0.1:9880"),
        stt=raw.get("stt", "none"),
        geocoder=raw.get("geocoder", "nominatim"),
        geocoder_contact=raw.get("geocoder_contact", ""),
        drive=DriveConfig(**(raw.get("drive") or {})),
        auth=AuthConfig(**(raw.get("auth") or {})),
        plugins=(raw.get("plugins") or {}).get("enabled", []),
        vector_memory=raw.get("vector_memory", True),
        wellbeing=WellbeingConfig(**(raw.get("wellbeing") or {})),
        tts_ref=raw.get("tts_ref", ""),
        translator_url=raw.get("translator_url", ""),
        livetalking_url=raw.get("livetalking_url", ""),
        comfy_url=raw.get("comfy_url", ""),
        tts_ref_text=raw.get("tts_ref_text", ""),
    )
    env = os.environ
    cfg.llm = env.get("TSHULAI_LLM", cfg.llm)
    cfg.user_name = env.get("TSHULAI_USER", cfg.user_name)
    cfg.tts = env.get("TSHULAI_TTS", cfg.tts)
    cfg.stt = env.get("TSHULAI_STT", cfg.stt)
    if env.get("TSHULAI_DRIVE_FOLDER"):
        cfg.drive.enabled = True
        cfg.drive.folder_id = env["TSHULAI_DRIVE_FOLDER"]
    return cfg
