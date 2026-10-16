#!/usr/bin/env bash
# 一鍵設定 Google：Cloud 專案、Drive API、service account、在你的 Drive 建素材資料夾並分享。
#
# 先登入一次（會開瀏覽器，用你自己的 Google 帳號）：
#   gcloud auth login --enable-gdrive-access
# 然後：
#   scripts/setup-google.sh [--project 專案ID] [--family a@gmail.com,b@gmail.com] [--folder-name 厝內-阿嬤]
#
# 會做的事（都在你的帳號下，可以隨時在 console 刪掉）：
#   1. 建 Cloud 專案（或用 --project 指定既有的），啟用 Drive API
#   2. 建 service account tshulai-engine，金鑰存到 data/service_account.json
#   3. 在你的 Drive 建「厝內-阿嬤」與全部子資料夾
#   4. 資料夾以「檢視者」分享給 service account，以「編輯者」分享給 --family 的家人
#   5. 寫好 data/config.yaml 的 drive 區段
# 不會做：Google 登入用的 OAuth client（Google 只開放在網頁上建），最後會印出連結。
set -euo pipefail
cd "$(dirname "$0")/.."
PROJECT="" ; FAMILY="" ; FOLDER_NAME="厝內-阿嬤"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project) PROJECT="$2"; shift 2 ;;
    --family) FAMILY="$2"; shift 2 ;;
    --folder-name) FOLDER_NAME="$2"; shift 2 ;;
    *) echo "不認識的參數 $1"; exit 1 ;;
  esac
done

ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -1)
[[ -z "$ACCOUNT" ]] && { echo "請先執行：gcloud auth login --enable-gdrive-access"; exit 1; }
echo "使用帳號：$ACCOUNT"

if [[ -z "$PROJECT" ]]; then
  PROJECT="tshulai-$(python3 -c 'import secrets,string; print("".join(secrets.choice(string.ascii_lowercase+string.digits) for _ in range(6)))')"
  echo "建立 Cloud 專案 $PROJECT"
  gcloud projects create "$PROJECT" --name="tshulai" --quiet
fi
gcloud config set project "$PROJECT" --quiet >/dev/null
echo "啟用 Drive API"
gcloud services enable drive.googleapis.com --project "$PROJECT" --quiet

SA="tshulai-engine@${PROJECT}.iam.gserviceaccount.com"
if ! gcloud iam service-accounts describe "$SA" --project "$PROJECT" >/dev/null 2>&1; then
  echo "建立 service account $SA"
  gcloud iam service-accounts create tshulai-engine --display-name="厝內 engine（唯讀 Drive）" --project "$PROJECT" --quiet
  sleep 5
fi
mkdir -p data
if [[ ! -f data/service_account.json ]]; then
  gcloud iam service-accounts keys create data/service_account.json --iam-account "$SA" --project "$PROJECT" --quiet
  chmod 600 data/service_account.json
fi

TOKEN=$(gcloud auth print-access-token)
FOLDER_ID=$(TOKEN="$TOKEN" SA="$SA" FAMILY="$FAMILY" FOLDER_NAME="$FOLDER_NAME" python3 scripts/drive_bootstrap.py)
echo "素材資料夾：https://drive.google.com/drive/folders/$FOLDER_ID"

python3 - "$FOLDER_ID" <<'PY'
import sys, re
from pathlib import Path
fid = sys.argv[1]
p = Path("data/config.yaml")
s = p.read_text(encoding="utf-8") if p.exists() else ""
block = f"drive:\n  enabled: true\n  folder_id: {fid}\n  service_account: service_account.json\n  poll_seconds: 300\n"
s = re.sub(r"(?ms)^drive:\n(?:[ \t]+.*\n?)*", "", s).rstrip()
p.write_text((s + "\n\n" if s else "") + block, encoding="utf-8")
print("已寫入 data/config.yaml")
PY

cat <<MSG

完成。接下來：
  cd engine && uv sync --extra drive && uv run tshulai-engine drive check

家人登入 app 用的 OAuth client 要在網頁建（Google 不開放指令建立）：
  https://console.cloud.google.com/auth/clients?project=$PROJECT
  步驟見 docs/google-drive.md 的「步驟三」，建好把 client ID 填進 data/config.yaml 的 auth.google_client_ids。
MSG
