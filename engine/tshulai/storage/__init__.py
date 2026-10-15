"""素材儲存。素材的唯一真實來源是共享 Google Drive 資料夾；本機只是鏡像快取。"""

from .layout import LAYOUT, ensure_local_layout

__all__ = ["LAYOUT", "ensure_local_layout"]
