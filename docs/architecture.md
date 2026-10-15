# 架構設計

## 設計原則

1. **原始素材在家人自己的 Google Drive，運算和衍生資料在家裡**。錄音、照片放共享 Drive 資料夾，家人用自己的帳號管；
   聲音模型、向量、人格卡、對話紀錄只在家用主機。手機透過 Tailscale 私網連回家用主機。
   LLM 若選雲端（Claude），送出去的只有人格卡文字與對話，不含聲音和臉。
2. **她不只回答，會主動開口**。生活模擬器讓她每天「發生事情」：家人的旅行、天氣、節日、日常小事。
3. **台語分段處理**。聽（ASR，輸出華語漢字）→ 想（LLM 用華語）→ 譯（華語→台語白話字）→ 說（台語聲音複製）。每段可換。
4. **先錄再說**。所有依賴模型的部分都可以晚點做，素材現在就開始蒐集。
5. **可插拔，授權寫清楚**。LLM、STT、TTS、影像引擎、話題來源都走 plugin；非商用權重一律標明，不放進預設。

## 全貌

```
 家人手機（Flutter）                    共享 Google Drive「厝內-阿嬤」          阿嬤家平板
 聊天 / 合照 / 去佗位 / 設定            consent audio video photo           /frame?key=…
 geofence 回到阿嬤家                    future notes trips                  大字輪播「阿融去淡水」
        │  Google 登入（只取身分）                │ service account 唯讀同步           │
        ▼                                         ▼                                    ▼
 ┌──────────────────────────── Persona Engine（家用主機，Python / FastAPI）─────────────────────────────┐
 │ auth：驗 Google ID token，對照家人名單          storage：Drive 鏡像 data/drive + uploads + local      │
 │ scene 狀態機：閒聊 進門 坐下 看電視 手機卡住 合照  trips：EXIF/Drive GPS → 鄉鎮名 → 分趟 → 記憶 + 看板 │
 │ 對話腦：人格卡 + 記憶 + 今天的事件 → LLM         simulator：旅行、節日、plugin 話題、日常小事         │
 │ voice：Breeze-ASR → LLM → 斷句 → 台語翻譯 → 台語 TTS → 浮水印（常用句預先合成）                     │
 │ vision：姿勢庫（BiRefNet）、合照好版（ComfyUI）、即時嘴型（LiveTalking，需 NVIDIA）、AI 標記         │
 │ plugins：MCP host，topics / poll_events 約定                future：給未來的留言排程               │
 └──────────────────────────────────── memory：SQLite（stories trips facts …）─────────────────────────┘
```

## Client：Flutter

一套程式碼：iOS、Android、macOS、Windows、Web。網頁版由引擎直接提供（`<引擎>/app/`），家人不裝 app 也能用。
Client 不跑大模型，只感測、呈現、快取。

| 分頁 | 做什麼 |
| --- | --- |
| 阿嬤 | LINE 式聊天，阿嬤的每一句有語音就依序播；按住講話（手機/桌面）；收到給未來的留言 |
| 合照 | 相機預覽疊上阿嬤去背圖，拖曳縮放、一鍵「站倒爿 / 坐中央 / 站正爿」；存快版或送回家做好版 |
| 去佗位 | 傳旅行照片給阿嬤看；列出每一趟 |
| 設定 | 引擎位址、Google 登入、註冊阿嬤家 geofence、阿嬤看板模式 |

套件（版本見 `app/pubspec.yaml`，選型理由見 [research/drive-and-app.md](research/drive-and-app.md)）：

| 用途 | 套件 | 備註 |
| --- | --- | --- |
| 回到阿嬤家 | native_geofence | 原生 CLLocationManager / GeofencingClient，app 關掉也觸發。iOS 最多 20 個 region、Android 100 個 |
| 身分 | google_sign_in 7 | 只取 ID token，不要 Drive scope |
| 相機 | camera | macOS 沒有，改用相簿 |
| 錄音 / 播放 | record / just_audio | |
| 通知 | flutter_local_notifications | geofence 背景觸發時跳「轉來矣喔？」 |

背景 geofence 觸發時 app 可能沒開：事件存在本機，下次開 app 時送給阿嬤；登入過的話也會用 HTTP `/events` 回報。

### 情境觸發

| 觸發 | 感測 | 範例 |
| --- | --- | --- |
| 回到家 | geofence 半徑 100m | 「轉來矣？食飽未？」 |
| 坐下 | 加速度計靜止 2 分鐘 + 在家（待做） | 進入聊天 |
| 看電視 | tv plugin 事件、或使用者說 | 問劇情 |
| 時間 | 節日、生日、忌日（人格卡 `dates`） | 「今仔日是你阿公的忌日」 |
| 天氣 | weather-tw plugin | 「欲落雨矣，紮雨傘」 |
| 手機卡住 | 生活模擬器 | 「這个貼圖按怎傳？」 |
| 拍照 | 打開合照分頁 | 「我坐中央好無？」 |

## Engine

### 對話腦

System prompt = 人格卡 + 當前 scene + 今天的生活事件 + 記憶（故事檢索、最近學到的事實、家人最近的旅行）。
禁忌話題放最後、語氣最強。被問是不是 AI 要誠實。記憶檢索目前是 SQLite FTS5 trigram，之後換 sqlite-vec 向量，介面不變。

LLM 可插拔：`echo`（測試）、`claude`（預設 `claude-opus-5-5`，effort low 壓延遲，system prompt 開 prompt cache）。

### 生活模擬器

每天產生一次，同一天結果固定。來源依可信度：家人的旅行與節日（真的）→ plugin 話題（半真的）→ 作息裡的小事（編的，只用人格卡裡已有的人與地點）。

### 語音管線

| 段 | 預設 | 授權 | 備案 |
| --- | --- | --- | --- |
| 聽 | Breeze-ASR-26（`weemed/Breeze-ASR-26-ct2`），台華混講，輸出華語漢字 | Apache-2.0 | NUTN Whisper 台語（不可商用） |
| 想 | LLM 用華語 | | |
| 譯 | Taigi-Llama-2-Translator-7B（GGUF on Ollama），同一句出白話字給 TTS、漢字給字幕 | **CC-BY-NC-SA，不可商用** | 先出台語漢字再用 taibun 轉台羅 |
| 說 | GPT-SoVITS-TW fork（KaedeTai）+ `KaedeTai/gpt-sovits-tw`，吃白話字/台羅，內建變調 | MIT | CosyVoice3（有 Minnan，未確認台灣腔） |
| 標記 | AudioSeal | MIT | |

**原版 GPT-SoVITS 不會說台語**，丟台語漢字會唸成華語。研究細節見 [research/voice.md](research/voice.md)。

延遲：台語 TTS 在 M1 Max 一句 10 到 30 秒，達不到「首句 1.5 秒」。對策：
1. 招呼語、口頭禪、離線備援句預先合成（`tshulai-engine warm-tts`，`PhraseCache`）。
2. 文字先出，語音一句一句跟上（`SentenceSplitter` 邊收邊切）。
3. 有 CUDA GPU 時把 TTS 伺服器放那台。

聲音微調建議租 CUDA GPU 跑一次，推論放家裡。用 10 分鐘到 2 小時長者錄音微調台語，目前沒有公開驗證，要實測。

### 影像管線

兩種介面：

- **串流型（即時嘴型）**：LiveTalking 包 MuseTalk 1.5（MIT，權重可商用），3090 約 45fps。client 用 WebRTC 直連，
  引擎把 TTS 音檔推給 `/humanaudio`。**需要 NVIDIA GPU，Mac 不做即時嘴型**，只播預先算好的影片。
- **工作型（ComfyUI）**：合照好版用 Qwen-Image-Edit-2511（Apache-2.0）、待機影片用 Wan2.2 TI2V-5B（Apache-2.0，24GB）。
  workflow 放 `engine/workflows/`。

| 項目 | 預設 | 不要用（非商用） |
| --- | --- | --- |
| 姿勢庫去背 | BiRefNet（MIT） | RMBG-2.0 |
| 手機預覽分割 | google_mlkit_selfie_segmentation（待接，用於遮擋） | |
| 合照好版 | Qwen-Image-Edit-2511 | FLUX.1 Kontext dev、FLUX.2 dev、InsertAnything |
| 嘴型 | MuseTalk 1.5 / Ditto | Sonic、LivePortrait（InsightFace 權重） |
| 標記 | EXIF + c2pa-python（合照 compositeWithTrainedAlgorithmicMedia） | |

採集時多錄 1 到 2 分鐘正面、光線均勻、自然講話的影片，MuseTalk 拿真實影片當底效果比單張照片好很多。

### 旅行足跡（讓阿嬤看到你去哪玩）

1. 家人把照片丟進 Drive `trips/`，或在 app 上傳（存家用主機 `uploads/trips/`）。
2. 讀 EXIF 時間與 GPS（HEIC 用 pillow-heif；讀不到用 Drive 的 imageMediaMetadata）。
3. 同一人、日期相連的算一趟；每趟最多查 5 個點，OpenStreetMap Nominatim 反查成鄉鎮名（淡水、安平），結果快取。
4. 寫進記憶：數位阿嬤會問「你頂禮拜去淡水，好耍無？」；寫進生活事件：當月的旅行是她主動開口的話題。
5. 阿嬤看板：`/frame?key=…` 全螢幕大字輪播，平板開 Guided Access 或螢幕固定；app 也有看板模式。

### Plugin

一個 plugin = MCP server（mcp 2.x）+ `manifest.yaml`。約定 tool：`topics`、`poll_events`。
人格卡的阿嬤家座標以環境變數傳給 plugin。見 [plugins/README.md](../plugins/README.md)。

### 記憶

SQLite 單檔 `data/persona.db`：`people`、`stories`（FTS5 trigram）、`media`、`life_events`、`conversations`、`facts`、`trips`、`future_messages`。

## 倫理與保護

見 [USE_POLICY.md](../USE_POLICY.md)。硬性保護：同意錄音、語音浮水印、合照 AI 標記（畫面角落 + EXIF + C2PA）、禁忌話題優先、
被問是不是 AI 要誠實、看板鑰匙與家人名單。

## 硬體

| 角色 | 最低 | 建議 |
| --- | --- | --- |
| 引擎、聊天、看板、旅行 | 任何能跑 Python 的電腦 | Mac mini |
| 台語 TTS 推論 | Apple Silicon（慢，靠預先合成） | NVIDIA GPU |
| 即時嘴型 | NVIDIA 3090 | 4090 |
| 聲音微調、待機影片 | 租 CUDA GPU 跑一次 | |
