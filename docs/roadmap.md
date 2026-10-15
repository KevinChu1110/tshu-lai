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

## 待做（依優先序）

1. **實測台語管線**：拿阿嬤真實錄音跑 Breeze-ASR-26 的 CER、GPT-SoVITS-TW 微調品質。這是整個專案最大的未知數。
2. **capture 加白話字逐字稿流程**：ASR 出華語草稿 → 翻成白話字 → 人工照實際變調校正，產出 TTS 微調資料。
3. **錄音規格**：32 kHz 以上、單聲道、切段 3 到 12 秒（已寫進採集清單）。
4. **浮水印重採樣**：AudioSeal 只吃 16/24 kHz，TTS 輸出要先重採樣；16-bit 訊息對應 persona id。
5. **手機合照遮擋**：接 google_mlkit_selfie_segmentation，現場的人站在阿嬤前面時正確遮住。
6. **坐下偵測**：加速度計靜止 + 在家，觸發 sitting scene。
7. **向量檢索**：stories 換 sqlite-vec，介面不變。
8. **農曆節日**：calendar plugin（過年、中秋、拜拜日）。
9. **tv-taiwan plugin**：找節目表資料來源。
10. **實測兩個文件沒寫的行為**：Picker 選資料夾後 `drive.file` 能否讀內容；Drive 上 HEIC 是否有位置資訊。
11. **道別模式與使用節制提醒**：需要哀傷照護專業意見。
12. **iOS / Android 實機建置**：需要 Xcode 與 Android SDK，以及 Google OAuth client 設定。
