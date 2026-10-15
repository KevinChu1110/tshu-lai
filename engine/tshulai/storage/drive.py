"""Google Drive 唯讀同步。

模式（見 docs/google-drive.md）：
  - 每個家庭在自己的 Google Cloud 專案建一個 service account，下載金鑰 JSON 放到 data/。
  - 擁有者把共享素材資料夾「以檢視者身分」分享給 service account 的 email。
  - 引擎每 5 分鐘把資料夾鏡像到 data/drive/，只下載新增或變更的檔案。

為什麼這樣做：
  - drive / drive.readonly 是 restricted scope。用個人 OAuth 的話，未驗證 app 在測試狀態下
    token 7 天就失效，家用主機沒辦法長期同步；送 Google 審核對開源專案不實際。
  - service account 不走 OAuth 同意畫面，不用審核，金鑰不會過期。
  - service account 沒有儲存配額，所以只讀不寫。上傳一律由家人用自己的 Drive app 丟進資料夾。
"""

from __future__ import annotations

import io
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from .layout import LAYOUT

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
FOLDER_MIME = "application/vnd.google-apps.folder"
FIELDS = "nextPageToken, files(id, name, mimeType, md5Checksum, modifiedTime, owners(emailAddress, displayName), imageMediaMetadata(time, location))"


def service_account_creds(key_file: Path):
    try:
        from google.oauth2 import service_account
    except ImportError as e:  # pragma: no cover
        raise SystemExit("需要 Google 套件：uv sync --extra drive") from e
    if not key_file.exists():
        raise SystemExit(f"找不到 service account 金鑰 {key_file}，步驟見 docs/google-drive.md")
    return service_account.Credentials.from_service_account_file(str(key_file), scopes=SCOPES)


@dataclass
class RemoteFile:
    id: str
    name: str
    mime: str
    md5: str | None
    modified: str
    owner: str | None
    photo_time: str | None
    lat: float | None
    lng: float | None


class DriveMirror:
    """把 Drive 資料夾樹鏡像到本機。狀態存在 <cache>/.drive_state.json。"""

    def __init__(self, creds, folder_id: str, cache: Path, service=None):
        if service is None:
            from googleapiclient.discovery import build

            service = build("drive", "v3", credentials=creds, cache_discovery=False)
        self.svc = service
        self.folder_id = folder_id
        self.cache = cache
        self.state_path = cache / ".drive_state.json"
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {"files": {}}

    def _walk(self, folder_id: str, rel: str = ""):
        page = None
        while True:
            res = self.svc.files().list(
                q=f"'{folder_id}' in parents and trashed = false", fields=FIELDS,
                pageToken=page, pageSize=1000, supportsAllDrives=True, includeItemsFromAllDrives=True,
            ).execute()
            for f in res.get("files", []):
                path = f"{rel}/{f['name']}" if rel else f["name"]
                if f["mimeType"] == FOLDER_MIME:
                    yield path, None
                    yield from self._walk(f["id"], path)
                elif not f["mimeType"].startswith("application/vnd.google-apps"):
                    meta = f.get("imageMediaMetadata") or {}
                    loc = meta.get("location") or {}
                    owner = (f.get("owners") or [{}])[0]
                    yield path, RemoteFile(
                        f["id"], f["name"], f["mimeType"], f.get("md5Checksum"), f["modifiedTime"],
                        owner.get("displayName") or owner.get("emailAddress"),
                        meta.get("time"), loc.get("latitude"), loc.get("longitude"),
                    )
            page = res.get("nextPageToken")
            if not page:
                break

    def missing_folders(self) -> list[str]:
        """標準結構裡 Drive 上還沒有的資料夾。service account 唯讀，不能幫你建。"""
        have = {p for p, rf in self._walk(self.folder_id) if rf is None}
        return [rel for rel in LAYOUT if rel not in have]

    def sync(self) -> list[str]:
        """比對一次，下載新增或變更的檔案，刪除 Drive 上已不存在的本機檔。回傳變更的相對路徑。"""
        changed, seen = [], set()
        for path, rf in self._walk(self.folder_id):
            if rf is None:
                (self.cache / path).mkdir(parents=True, exist_ok=True)
                continue
            seen.add(path)
            known = self.state["files"].get(path)
            local = self.cache / path
            if known and known.get("md5") == rf.md5 and known.get("modified") == rf.modified and local.exists():
                continue
            self._download(rf.id, local)
            self.state["files"][path] = {
                "id": rf.id, "md5": rf.md5, "modified": rf.modified, "owner": rf.owner,
                "photo_time": rf.photo_time, "lat": rf.lat, "lng": rf.lng,
            }
            changed.append(path)
        for path in list(self.state["files"]):
            if path not in seen:
                (self.cache / path).unlink(missing_ok=True)
                del self.state["files"][path]
                changed.append(path)
        self._save()
        log.info("Drive 同步完成，%d 個檔案變更", len(changed))
        return changed

    def file_meta(self, rel_path: str) -> dict:
        """Drive 端的中繼資料（擁有者、照片 GPS）。HEIC 讀不到 EXIF 時，旅行模組拿這個補。"""
        return self.state["files"].get(rel_path, {})

    def _download(self, file_id: str, dst: Path) -> None:
        from googleapiclient.http import MediaIoBaseDownload

        dst.parent.mkdir(parents=True, exist_ok=True)
        req = self.svc.files().get_media(fileId=file_id, supportsAllDrives=True)
        with io.FileIO(dst, "wb") as buf:
            dl = MediaIoBaseDownload(buf, req, chunksize=8 * 1024 * 1024)
            done = False
            while not done:
                _, done = dl.next_chunk()

    def _save(self) -> None:
        self.cache.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self.state, ensure_ascii=False, indent=1), encoding="utf-8")
