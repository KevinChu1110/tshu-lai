# 改進項目

三份研究（[voice](research/voice.md)、[vision](research/vision.md)、[drive-and-app](research/drive-and-app.md)）提出的改進項目，與目前狀態。

## 已完成

| 項目 | 來源 | 做法 |
| --- | --- | --- |
| 原版 GPT-SoVITS 不會台語 | voice | 改接 GPT-SoVITS-TW fork，加華語→白話字翻譯 |
| ASR 預設模型 | voice | Breeze-ASR-26 CTranslate2 版 |
| 台語 TTS 太慢 | voice | 常用句預先合成 `PhraseCache`、`warm-tts`；文字先出，語音逐句跟上 |
| 「Mac 30fps 嘴型」沒有出處 | vision | 架構改成即時嘴型需 NVIDIA，Mac 只播預先算好的影片 |
| 影像 plugin 分兩種介面 | vision | `LiveTalking`（串流）、`ComfyClient`（工作型） |
| 權重授權欄位 | vision | manifest 加 `weights_license`、`commercial_ok`，不可商用會警告 |
| RMBG-2.0 非商用 | vision | 姿勢庫只用 BiRefNet |
| 「資料留在家裡、沒有雲端帳號」的說法 | drive | 改寫原則 1：原始素材在家人 Drive，運算在家裡 |
| Drive 存取方式 | drive | service account 唯讀同步，不走 OAuth 審核 |
| 家人身分 | drive | Google 登入只取 ID token，引擎核對家人名單 |
| 旅行照片來源 | drive | Drive `trips/` 或 app 上傳；不用 Google Photos API |
| 阿嬤看板 | drive | `/frame` 網頁 + app 看板模式 |
| geofence 套件 | drive | native_geofence（不用已停維護的 geofence_service、付費的 flutter_background_geolocation） |
| 坐下偵測 | 原設計 | app 加速度計：進門後靜止 2 分鐘送 `motion.sit_down` |
| 手機合照遮擋 | vision | ML Kit 切出照片裡的人，「阿嬤徛佇大家後壁」開關 |
| 向量檢索 | 原設計 | sqlite-vec + fastembed 多語模型，與關鍵字混合；真實模型實測 3 題中 2 |
| 農曆節日 | 原設計 | calendar-tw plugin：過年、天公生、媽祖生、普渡、中秋、尾牙、清明、冬至、初一十五 |
| tv-taiwan plugin | 原設計 | 家人填節目表，開播切看電視 scene、阿嬤叫你來看 |
| plugin 事件輪詢 | 原設計 | 引擎每分鐘問 `poll_events`，同日同事件只處理一次，對連線中的家人主動開口 |
| 浮水印重採樣與訊息 | voice | 16 kHz 算浮水印再採樣回去；mp3 先轉 wav；16-bit 訊息 = persona id |
| 白話字逐字稿流程 | voice | `tshulai-capture poj-draft` → 人工校正 TSV → `poj-export` 訓練清單 |
| 使用節制、道別模式 | 倫理 | 一天超過 90 分鐘她會叫你去休息（一天一次）；安靜時段不主動開口；道別模式 |
| HEIC GPS | drive | 測試確認 pillow-heif 讀得到 iPhone HEIC 的時間與 GPS |
| Google 登入驗證 | drive | 模擬 Google 簽章測過：家人名單、audience、email 驗證、HTTP 與 WebSocket 都擋 |
| Android 建置 | 原設計 | 裝好 JDK 17 與 Android SDK，`flutter build apk` 成功（加 core library desugaring） |

## 待做

需要你的帳號或硬體，我這邊做不了：

1. **Google Cloud 設定**：建專案、service account、OAuth client（[google-drive.md](google-drive.md)）。之後才能用真的 Drive 資料夾跑 `drive check` 和真的 Google 帳號登入。
2. **iOS 建置**：需要 Xcode（App Store 用 Apple ID 安裝，約 15GB）。
3. **手機實機測試**：geofence、相機、錄音、ML Kit 遮擋、坐下偵測都要在真手機上確認。電腦硬碟只剩約 12GB，沒裝 Android 模擬器。
4. **台語管線實測**：拿阿嬤真實錄音量 Breeze-ASR-26 的錯誤率、GPT-SoVITS-TW 微調品質。這是整個專案最大的未知數。
5. **Picker 選資料夾後 `drive.file` 能否讀內容**：目前設計不依賴它。

可以再改進的：

6. **台語詞彙對應**：語意檢索遇到「爸爸小時候」對「恁阿爸細漢」會漏，可加台華詞彙對照或用台語語料微調的 embedding。
7. **道別模式的設計**需要哀傷照護專業意見。
8. **農曆生日、忌日**：人格卡 `dates` 目前是國曆，可改支援農曆。

