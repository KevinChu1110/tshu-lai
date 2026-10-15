"""用擁有者的 access token 在 Drive 建素材資料夾樹並分享。只用標準函式庫，給 setup-google.sh 呼叫。

環境變數：TOKEN、SA（service account email）、FAMILY（逗號分隔 email，可空）、FOLDER_NAME。
已存在同名資料夾就沿用，可重複執行。stdout 只印 folder id。
"""

import json
import os
import sys
import urllib.parse
import urllib.request

API = os.environ.get("DRIVE_API", "https://www.googleapis.com/drive/v3")
FOLDER = "application/vnd.google-apps.folder"
LAYOUT = [
    "consent", "audio/story", "audio/chat", "audio/message",
    "video/talking", "video/expression", "video/idle", "video/greeting",
    "photo/face", "photo/pose", "photo/together", "photo/outdoor", "photo/old",
    "future", "notes", "trips",
]
TOKEN = os.environ["TOKEN"]


def call(method, path, body=None, query=None):
    url = f"{API}/{path}" + ("?" + urllib.parse.urlencode(query) if query else "")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        msg = e.read().decode()
        if e.code == 403 and "insufficient" in msg.lower():
            sys.exit("gcloud 登入時沒給 Drive 權限，請重跑：gcloud auth login --enable-gdrive-access")
        sys.exit(f"Drive API {e.code}：{msg[:300]}")


def folder(name, parent=None):
    q = f"name = '{name}' and mimeType = '{FOLDER}' and trashed = false"
    q += f" and '{parent}' in parents" if parent else " and 'root' in parents"
    found = call("GET", "files", query={"q": q, "fields": "files(id)"})["files"]
    if found:
        return found[0]["id"]
    body = {"name": name, "mimeType": FOLDER, "parents": [parent or "root"]}
    return call("POST", "files", body, {"fields": "id"})["id"]


def share(file_id, email, role):
    call("POST", f"files/{file_id}/permissions", {"type": "user", "role": role, "emailAddress": email},
         {"sendNotificationEmail": "false" if role == "reader" else "true", "fields": "id"})


root = folder(os.environ.get("FOLDER_NAME", "厝內-阿嬤"))
ids = {"": root}
for rel in LAYOUT:
    parent = ""
    for part in rel.split("/"):
        path = f"{parent}/{part}" if parent else part
        if path not in ids:
            ids[path] = folder(part, ids[parent])
        parent = path
share(root, os.environ["SA"], "reader")
for email in filter(None, (e.strip() for e in os.environ.get("FAMILY", "").split(","))):
    share(root, email, "writer")
    print(f"已分享給 {email}（編輯者）", file=sys.stderr)
print(root)
