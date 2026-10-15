# 研究：共享 Google Drive、旅行相框、Flutter 套件

> 2026-10-16 調查。版本號取自 pub.dev / PyPI API 當天的 latest。

## 0. 先處理的設計衝突

`docs/architecture.md` 原則 1 寫「資料留在家裡、沒有雲端帳號」。改成以 Drive 為媒體來源後，這條要改寫成：
**原始媒體放在家人自己的 Google Drive；衍生資料（向量、聲音模型、人格卡）與 LLM 呼叫留在家用主機**。

## 1. Google Drive 存取

### Scope 分級（[Drive scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth)）

| Scope | 等級 | 能做什麼 |
| --- | --- | --- |
| `drive.file` | non-sensitive | 只碰 app 自己建立的檔案，或使用者用 Picker 選給 app 的檔案 |
| `drive.readonly`、`drive` | **restricted** | 讀整個 Drive。要過 restricted 審查（含示範影片），把資料存在伺服器上還要每年做安全評估（[驗證要求](https://support.google.com/cloud/answer/13464321)） |

未驗證的 app（[說明](https://support.google.com/cloud/answer/15549945)）：Testing 狀態最多 100 個測試使用者，**授權 7 天後失效，refresh token 也會一起失效**。正式發布但還沒驗證的 app，要求 sensitive 或 restricted scope 時整個專案一輩子最多 100 個新使用者。開源專案不可能讓每個家庭各自去過 restricted 審查。

### (b) Engine（家用主機）— 建議用 service account，唯讀

- 每個家庭各自建 GCP 專案和 service account，**把共享資料夾以「檢視者」權限分享給 service account 的 email**。這樣不用跑 OAuth 同意畫面，也不需要任何審查，token 也不會 7 天過期。
- Service account 沒有儲存配額，也不能擁有檔案（[討論](https://discuss.google.dev/t/storagequotaexceeded-the-users-drive-storage-quota-has-been-exceeded-for-service-account/104375)、[Fivetran](https://fivetran.com/docs/activations/destinations/available-destinations/google-drive/troubleshooting/service-accounts-storage-quota)）。要寫入只能用 Shared Drive，而 Shared Drive 需要 Workspace，所以 **engine 只讀不寫**，上傳交給家人自己的 Drive app。
- 增量同步（[manage changes](https://developers.google.com/workspace/drive/api/guides/manage-changes)）：先呼叫 `changes.getStartPageToken`，之後輪詢 `changes.list(pageToken=…, includeRemoved=True)`，最後一頁回來時存下 `newStartPageToken`。`changes.watch`（[push](https://developers.google.com/workspace/drive/api/guides/push)）需要公開 HTTPS 和有效憑證，channel 最長 7 天、要自己續訂。家用主機在 Tailscale 後面，**直接用每 5 分鐘輪詢**，不要用 watch。用 `files.list(q="'<folderId>' in parents")` 遞迴建立初始索引。
- 套件：`google-api-python-client 2.201.0`（2026-09-30）+ `google-auth`。
- 備案：一個家長用 installed-app OAuth（loopback redirect + PKCE，[文件](https://developers.google.com/identity/protocols/oauth2/native-app)）。但只要用到 `drive.readonly`，Testing 模式下 7 天就失效，不適合長期跑在家用主機上。

### (a) Flutter client — 只做身分驗證，不讀 Drive

- `google_sign_in 7.2.0`（[pub](https://pub.dev/packages/google_sign_in)）的寫法：`GoogleSignIn.instance.initialize(clientId:, serverClientId:)` → `attemptLightweightAuthentication()` / `authenticate()`，scope 用 `authorizationClient.authorizationForScopes()` / `authorizeScopes()` 取得。支援 Android、iOS、macOS、web。web 版的 access token 1 小時後過期且不會自動續期。
- Client **只要 openid/email**（non-sensitive）。Engine 驗證 ID token，再拿 email 去比對 `family.yaml` 的成員名單。
- 如果之後真的要讓 app 直接讀寫 Drive：`googleapis 17.0.0` + `extension_google_sign_in_as_googleapis_auth 3.0.0`（`authorization.authClient(scopes:)`）+ `drive.file`。手機和桌面的 Picker 只允許 `drive.file`，會開系統瀏覽器（`trigger_onepick=true`，回傳 `picked_file_ids`，[文件](https://developers.google.com/workspace/drive/picker/guides/desktop-mobile-picker)）。**選資料夾之後是否能存取裡面的檔案，官方文件沒寫，要先實測**，所以不要讓整個設計依賴這一點。

## 2. 旅行

- **Photos Library API**：2025-03-31 移除了 `photoslibrary.readonly`、`photoslibrary`、`photoslibrary.sharing`，現在只能存取 app 自己建立的內容（[updates](https://developers.google.com/photos/support/updates)）。不能用。
- **Photos Picker API**：scope 是 `photospicker.mediaitems.readonly`，流程是建 session → 使用者在 `pickerUri` 選照片 → 輪詢 → `mediaItems.list`。baseUrl 60 分鐘就過期，而且 **`=d` 下載時會拿掉位置 EXIF**（[media items](https://developers.google.com/photos/picker/guides/media-items)），所以拿不到地點，不適合這個用途。
- **建議：孫子把照片丟進 Drive 的 `trips/<YYYY-MM 地點>/`**。原檔放 Drive 不會被拿掉 EXIF。Engine 直接讀 `files.get(fields="imageMediaMetadata(location,time)")`（[files](https://developers.google.com/workspace/drive/api/reference/rest/v3/files)），連檔案都不用下載。缺值時（HEIC、影片）再下載用 `exiftool` / `pillow 12.3.0` + pillow-heif 補。
- **反查地名**：Nominatim 公用伺服器限制每秒最多 1 次、要帶可辨識的 User-Agent、結果必須快取、標示 OSM 出處，排程腳本限每分鐘 4 次（[policy](https://operations.osmfoundation.org/policies/nominatim/)）。座標四捨五入到約 1 km 當快取 key，一趟旅行只會打幾十次，完全夠用。透過 `geopy 2.5.0` 的 `Nominatim` + `RateLimiter` 呼叫。離線備案用 GeoNames cities 資料（`reverse_geocoder` 2016 年後就沒維護）。
- **流程**：照片依時間 + 距離分群成「一站」→ 反查地名 → 寫進 `trips` 表和 `life_events`（「冠融上禮拜去花蓮，有去太魯閣」）→ 對話腦檢索得到，阿嬤可以主動問。
- **阿嬤相框**：由 engine 提供一個唯讀 web 頁面（Flutter web 或純 HTML），平板開 Guided Access / 螢幕固定。畫面大字、只放一張照片、地名、日期，自動輪播，不需要任何操作。地圖用 `flutter_map 8.3.2`，OSM 圖磚要遵守使用政策，或改用靜態地圖圖片。

## 3. Flutter 套件（2026-10）

| 用途 | 建議 | 版本（發布日） | 平台 |
| --- | --- | --- | --- |
| Geofence | **`native_geofence`**（[pub](https://pub.dev/packages/native_geofence)）：iOS 用 CLLocationManager、Android 用 GeofencingClient，app 被殺掉也能觸發，MIT | 1.3.1（2026-06） | Android、iOS |
| 備選 | `polyfence`（多邊形、停留偵測） | 3.0.1（2026-10） | Android、iOS |
| 不要用 | `geofence_service` 已停止維護，而且是在 app 存活時輪詢位置，不是原生 geofence；`flutter_background_geolocation` 套件本身是 Apache-2.0，但 **iOS 和 Android 的 release build 都要付費授權**，開源專案不適合當預設 | 6.0.0+1 / 5.9.0 | — |
| 相機 + 疊圖 | `camera`，用 `Stack` 疊去背姿勢圖；macOS 用 `camera_macos` | 0.12.1 / 0.1.1 | Android、iOS、web / macOS |
| WebSocket | `web_socket_channel` | 3.0.3 | 全平台 |
| 錄音 | `record`（`startStream` 輸出 PCM16，可串流給 STT） | 7.1.2 | 全平台 |
| 播放 | `just_audio`（Windows 要另外加實作套件） | 0.10.6 | Android、iOS、macOS、web |
| 本機通知 | `flutter_local_notifications`（web 不支援排程通知） | 22.3.2 | 全平台 |
| 桌面小工具 | `home_widget`（可互動、可呼叫 Dart） | 0.10.0 | Android、iOS |
| 定位 | `geolocator` | 14.1.1 | 全平台 |
| EXIF（client 端） | `native_exif`（`exif` 套件 2023 年後就沒更新） | 0.8.0 | Android、iOS |

## 改善項目

1. 改寫 architecture 原則 1 與 README 的「沒有雲端帳號」，說明 Drive 只放原始媒體。
2. 新增 `docs/setup-google.md`：教家庭建 GCP 專案 → service account → 分享資料夾給它，附截圖。
3. `spec/` 新增 `family.yaml` schema（成員 email ↔ 人物關係圖）和 Drive 資料夾規範（`recordings/ photos/ videos/ notes/ trips/`）。
4. Engine 新增 `drive_sync`：初始掃描 + `changes.list` 輪詢，寫入 `media` 表（存 fileId、md5、EXIF 地點與時間），不在本機長期保留原檔副本，或設快取上限。
5. Memory 新增 `trips` 表，生活模擬器加「孫子旅行」事件來源。
6. 新增「阿嬤相框」模式：engine 提供 `/frame` 頁面，大字、自動輪播、零操作。
7. 架構文件的 geofence 段落指定用 `native_geofence`，並註明 iOS 最多 20 個 region、Android 最多 100 個。
8. 實測項目：用 Picker 選資料夾後 `drive.file` 能否讀到裡面的檔案；HEIC 檔是否有 `imageMediaMetadata.location`。
