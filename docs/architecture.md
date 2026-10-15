# 架構設計

## 設計原則

1. **資料留在家裡**。家人的聲音、臉、故事不上傳到任何雲端。Engine 跑在家用主機，手機透過 Tailscale 私網連回來。
2. **她不只回答，會主動開口**。生活模擬器讓她每天「發生事情」，成為主動話題的來源。
3. **台語分三段處理**。LLM 不會寫台語，所以聽、想、說拆開，每段可以獨立換模型。
4. **先錄再說**。所有依賴 AI 模型的部分都可以晚點做，但資料採集現在就開始。
5. **可插拔**。LLM、STT、TTS、avatar 引擎、話題來源全部走 plugin。

## 三層

```
┌─────────────────────────────────────────────────────┐
│  Client（Flutter：iOS / Android / macOS / Windows）    │
│  情境感測：geofence、加速度計、時間、麥克風、相機         │
│  呈現：avatar 影片串流、語音播放、LINE 式對話時間軸        │
│  相機模式 + 分享延伸（合照）                              │
│  離線快取：預錄招呼語、小模型                             │
└───────────────┬─────────────────────────────────────┘
                │ WebSocket（Tailscale）
┌───────────────▼─────────────────────────────────────┐
│  Persona Engine（Python / FastAPI，家用主機）            │
│  Scene 狀態機      進門 → 坐下 → 看電視 → 道別 + 閒聊通道  │
│  對話腦            人格卡 + 記憶檢索 + LLM（可插拔）        │
│  生活模擬器        作息表 × 真實資訊 → 今天的事件           │
│  語音管線          台語 STT → LLM → 台語文本 → 聲音複製 TTS │
│  影像管線          姿勢庫 / 待機影片 / 即時嘴型 / 合照合成   │
│  Plugin Host       MCP server 管理、manifest 載入          │
└───────────────┬─────────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────────┐
│  Memory Store（SQLite + sqlite-vec）                    │
│  人格卡、人物關係圖、故事庫、對話日誌、生活事件、媒體索引     │
└─────────────────────────────────────────────────────┘
```

## Client：Flutter

選 Flutter 的理由：一套程式碼涵蓋六個平台，而且背景定位的原生插件成熟
（iOS Region Monitoring 最多 20 個 region、Android Geofencing API）。
Tauri 桌面好看但手機背景能力弱，React Native 桌面支援弱。

Client 刻意做得「笨」：不跑大模型，只感測、呈現、快取。所有生成在 Engine。

### 情境觸發（Presence）

| 觸發 | 感測 | 範例 |
| --- | --- | --- |
| 回到家 | geofence 半徑 100m 進入事件 | 「轉來矣？食飽未？」 |
| 坐下 | 加速度計靜止 2 分鐘 + 在家 | 進入聊天 scene |
| 看電視 | 使用者說、或電視模式讀節目表 | 問劇情 |
| 時間 | 節日、忌日、生日、傍晚 | 「今仔日是你阿公的忌日」 |
| 滑手機卡住 | 桌面版截圖理解；手機版靠生活模擬器讓她「不會用 LINE」 | 「這个貼圖按怎傳？」 |
| 拍照 | 使用者開相機模式或分享照片進來 | 「我坐中央好無？」 |

### 閒聊通道

永遠開著，不綁情境。形式像 LINE：她傳台語語音訊息附文字稿，早上傳早安圖。
進入方式：桌面小工具按住說話、鎖定畫面快捷、喚醒詞「阿嬤」（裝置端 openWakeWord）、通知。
主動頻率可調，預設一天最多 3 則，可設不要在上班時間、深夜。

## Engine：Python

### Scene 狀態機

每個 scene 是一個 YAML，社群可以貢獻：

```yaml
id: homecoming
enter_on: [geofence.enter:home]
greeting_pool: [greet.homecoming.*]      # 從記憶庫撈她真的說過的招呼語
topics: [today_events, ask_about_user_day]
exit_on: [scene.sit_down, idle:10m]
```

### 對話腦

System prompt = 人格卡 + 當前 scene + 今天的生活事件 + 檢索到的記憶（向量搜尋 top-k）
+ 近期對話摘要。每輪結束把新事實寫回記憶（「冠融講伊最近工作足忝」）。

LLM 可插拔。本機 Ollama（Qwen、Gemma）最省；雲端 Claude 品質最好，預設 `claude-opus-5-5`，
adaptive thinking，effort 設 low 以壓低延遲。LLM 收到的是人格卡和記憶，不是聲音和臉。

### 生活模擬器

每天早上依作息表產生「今天的事件」：去市場遇到誰、八點檔演了什麼、天氣如何、
廟會快到了。真實資訊從 knowledge plugin 來（天氣、新聞、節目表），虛構部分受人格卡約束。
事件寫入記憶庫，成為她主動開口的話題。這是讓她「活著」而不只是「回答」的關鍵。

### 語音管線

| 段 | 做法 | 候選 |
| --- | --- | --- |
| 聽 | 台語語音辨識 | Whisper 台語微調版（TAT 語料系列）、意傳科技 ASR；不夠就用她的錄音再微調 |
| 想 | LLM 用華語生成，帶台語語感指示 | 任何 LLM |
| 譯 | 華語 → 台語漢字 / 台羅 | 意傳科技臺灣言語工具、TAIDE |
| 說 | 聲音複製 TTS | GPT-SoVITS（首選，微調幾分鐘錄音）、CosyVoice、F5-TTS、Fish Speech |
| 標記 | 音訊浮水印 | AudioSeal |

串流式：STT 邊聽邊轉，LLM 邊生邊切句，TTS 一句一句合成。目標首句語音 1.5 秒內。

### 影像管線

不追求即時生成影片。兩段式：

- **離線**：照片 → image-to-video（Wan 2.x、HunyuanVideo）產生待機影片：坐著、點頭、看電視、笑。
  真的有錄到的待機影片優先用，生成的補不足。
- **即時**：對話時 MuseTalk 或 LivePortrait 驅動嘴型與表情，30fps，Apple Silicon 或一張消費級 GPU。

### 合照

| | 快版（即時預覽） | 好版（拍完後） |
| --- | --- | --- |
| 做法 | 姿勢庫去背圖貼進畫面 | 身分保持的圖像編輯模型把她畫進場景 |
| 跑在哪 | 手機 | Engine GPU |
| 候選 | BiRefNet / RMBG 去背 | Flux Kontext、Qwen-Image-Edit，實測哪個最像 |

姿勢庫：事先從照片生成幾十張不同姿勢，附去背遮罩。預覽與好版用同一張當參考，前後一致。
構圖助手：姿勢偵測找人和空位，給「中間 / 左 / 右」三個建議位；比例從其他人身高推算，
有深度感測再修正；有人站她前面用深度做遮擋。
合成照寫入 EXIF 與 C2PA 標記。

## Plugin 系統

採 MCP 協定。一個 plugin 是一個 MCP server 加一份 manifest：

```yaml
name: tv-taiwan
version: 0.1.0
kind: [knowledge, trigger]      # knowledge / trigger / tool / voice / vision / camera
languages: [nan-TW, zh-TW]
server:
  command: uvx
  args: [tshulai-plugin-tv-taiwan]
provides:
  triggers:
    - event: tv.program_started
  tools:
    - get_tonight_drama_summary
  topics:
    - 八點檔劇情
```

| kind | 做什麼 |
| --- | --- |
| knowledge | 餵話題：節目表、鄰里新聞、年代記憶 |
| trigger | 新的情境來源：智慧門鎖、電視盒、行事曆 |
| tool | 她能幫你做的事：打給舅舅、查公車 |
| voice | 換 STT / TTS 引擎 |
| vision | 換 avatar 引擎 |
| camera | 換合照合成模型 |

Schema 在 `spec/plugin-manifest.schema.json`。

## 記憶

SQLite 單檔，`data/persona.db`，sqlite-vec 做向量索引。表：

- `persona`：人格卡（JSON，schema 在 `spec/persona-card.schema.json`）
- `people`：人物關係圖
- `stories`：訪談逐字稿分段，附人物、年代、情緒標籤與 embedding
- `media`：照片影片索引，附標籤（姿勢、表情、場景）
- `life_events`：生活模擬器產生的事件
- `conversations`：對話日誌與摘要
- `future_messages`：給未來的留言，附觸發日期

## 倫理與保護

見 [USE_POLICY.md](../USE_POLICY.md)。設計上的硬性保護：

- 聲音訓練前檢查 `data/consent/` 下有同意錄音
- 所有生成語音過 AudioSeal
- 所有合成照寫 AI 標記
- 人格卡的 `taboo_topics` 優先於任何對話指令
- 使用節制提醒、道別模式

## 硬體

- 開發與 Engine：Apple Silicon Mac 可跑 GPT-SoVITS 推論、LivePortrait、MuseTalk
- 聲音微調、影像生成：一張 24GB 以上 GPU，或租雲端 GPU 跑一次後把模型拿回家
- 手機：任何能跑 Flutter 的即可；有 LiDAR 的 iPhone 合照深度更準
