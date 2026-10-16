# 用 Google Drive 放素材、用 Google 帳號當家人身分

一句話：**素材放在家人共享的 Google Drive 資料夾，家用主機的引擎用 service account 唯讀同步；家人用 Google 帳號登入 app 只是為了表明身分。**

```
家人的手機 ──Google Drive app 丟檔案──▶ 共享資料夾「厝內-阿嬤」 ◀──唯讀同步── 家用主機引擎（service account）
家人的手機 ──厝內 app（Google 登入取得身分）──▶ 家用主機引擎（核對家人名單）
阿嬤家的平板 ──/frame?key=…（不用登入）──▶ 家用主機引擎
```

## 快速設定（一個指令）

步驟一、二、四可以全部自動做完，只剩步驟三要在網頁點：

```bash
gcloud auth login --enable-gdrive-access          # 開瀏覽器，用你自己的 Google 帳號登入一次
scripts/setup-google.sh --family 家人1@gmail.com,家人2@gmail.com
cd engine && uv sync --extra drive && uv run tshulai-engine drive check
```

腳本會建 Cloud 專案、啟用 Drive API、建 service account 並下載金鑰，在你的 Drive 建好「厝內-阿嬤」整套資料夾，
分享給 service account（檢視者）和家人（編輯者），最後寫好 `data/config.yaml`。重跑不會重複建立。
想手動做或看懂每一步，往下看。

## 為什麼這樣設計

| 選項 | 問題 |
| --- | --- |
| 擁有者個人 OAuth 授權引擎讀 Drive | `drive` 是 restricted scope。未送審的 app 在「測試」狀態下 token 7 天就失效，家用主機沒辦法長期同步 |
| 送 Google 審核 | 要示範影片、每年安全評估，開源專案每個家庭各自送審不實際 |
| app 直接讀寫 Drive | 手機上只能用 `drive.file`，看不到別人放的檔案 |
| **service account + 共享資料夾（採用）** | 不走 OAuth 同意畫面、不用審核、金鑰不過期。缺點：service account 沒有儲存空間，所以只讀不寫，上傳交給家人自己的 Drive app |

研究細節見 [research/drive-and-app.md](research/drive-and-app.md)。

## 步驟一：建共享資料夾（擁有者，5 分鐘）

1. 在自己的 Google Drive 建一個資料夾，例如「厝內-阿嬤」。
2. 在裡面建這些子資料夾（或在電腦跑 `tshulai-capture init 厝內-阿嬤` 建好，整個拖進 Drive）：

   ```
   consent/  audio/story/  audio/chat/  audio/message/
   video/talking/  video/expression/  video/idle/  video/greeting/
   photo/face/  photo/pose/  photo/together/  photo/outdoor/  photo/old/
   future/  notes/  trips/
   ```

3. 把資料夾分享給家人（編輯者）。家人用手機的 Google Drive app 就能把錄音、照片丟進對應資料夾。
4. 資料夾網址 `https://drive.google.com/drive/folders/XXXX` 的 `XXXX` 是 folder ID，等一下要用。

## 步驟二：建 service account（擁有者，10 分鐘，免費）

1. 到 [Google Cloud Console](https://console.cloud.google.com/) 建一個新專案，例如 `tshulai-ama`。
2. 「API 和服務 → 程式庫」搜尋 **Google Drive API**，啟用。
3. 「IAM 與管理 → 服務帳戶 → 建立服務帳戶」，名稱 `tshulai-engine`，角色不用給。
4. 進入剛建的服務帳戶 →「金鑰 → 新增金鑰 → JSON」，下載的檔案改名 `service_account.json`，放到家用主機的 `data/`。
   **這個檔案等於鑰匙，不要傳到任何地方、不要進 git**（`.gitignore` 已擋 `data/`）。
5. 複製服務帳戶的 email（像 `tshulai-engine@tshulai-ama.iam.gserviceaccount.com`），
   回到 Drive 把「厝內-阿嬤」資料夾**以檢視者身分**分享給這個 email。

## 步驟三：家人登入用的 OAuth client（擁有者，10 分鐘）

這只用來讓 app 拿到「你是誰」（openid、email），不要任何 Drive 權限，所以不需要審核。

1. 同一個專案，「Google Auth Platform」：目標對象選「外部」，填 app 名稱「厝內」、你的 email。
   範圍不用加。「品牌」頁填首頁與隱私權政策連結（可用本 repo 的 PRIVACY.md），授權網域加 `github.com`，
   然後到「目標對象」按「發布應用程式」。只用到非敏感範圍、沒有上傳標誌，不需要送審。
2. 「憑證 → 建立憑證 → OAuth 用戶端 ID」建這幾個：
   - **網頁應用程式**：這個的 client ID 是引擎驗證用的 audience，也是 Android app 要填的 Web client ID。
     「已授權的 JavaScript 來源」加 `http://localhost:8765`（網頁版登入用）。
   - **iOS**：bundle ID `io.github.kevinchu1110.tshulai`（自己 fork 的請改成你的）。
   - **Android**：package `io.github.kevinchu1110.tshulai`，填 debug 與 release 的 SHA-1。

## 步驟四：設定引擎

`data/config.yaml`：

```yaml
user_name: 阿融
drive:
  enabled: true
  folder_id: XXXX                         # 步驟一的 folder ID
  service_account: service_account.json   # 步驟二的金鑰
auth:
  enabled: true
  google_client_ids:
    - 123-abc.apps.googleusercontent.com  # 步驟三的網頁 client ID
    - 123-ios.apps.googleusercontent.com  # iOS client ID
  family:                                 # 誰可以用，阿嬤怎麼叫他
    guanrong1110@gmail.com: 阿融
    uncle@example.com: 阿舅
```

檢查：

```bash
cd engine
uv sync --extra drive --extra plugins
uv run tshulai-engine drive check     # 讀得到資料夾嗎、缺哪些子資料夾
uv run tshulai-engine drive sync      # 先同步一次
uv run tshulai-engine serve --host 0.0.0.0
```

引擎每 5 分鐘同步一次，新的旅行照片會出現在阿嬤看板，數位阿嬤也會知道。

## 家人要做的事

- 被加進共享資料夾，用 Google Drive app 丟檔案。
- 裝厝內 app（或開 `<引擎位址>/app/`），在設定填引擎位址，用 Google 登入。
- 想讓阿嬤看到去哪玩：照片開定位拍，丟進 `trips/`，或在 app「去佗位」按「傳相片」。
  檔名前面加稱呼（`阿融_IMG_1234.jpg`）阿嬤看板就會寫「阿融去淡水」；沒加的話用 Drive 擁有者名字。

## 已知限制

- iPhone 的 HEIC 照片在 Drive 上不一定有位置資訊。引擎會下載原檔用 pillow-heif 讀 EXIF。
- Google Photos 的 API 從 2025 年 3 月起不能讀使用者相簿，所以旅行照片一律走 Drive 或 app 上傳。
- 反查地名用 OpenStreetMap Nominatim，限制每秒 1 次、要帶聯絡方式。在 config 填 `geocoder_contact`。
