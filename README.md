# 厝內 Tshù-lāi

> 一個開源的「數位家人」框架。給家人的聲音、照片和故事，它會成為一個住在家裡、
> 懂情境、會主動開口、說台語的陪伴者。

厝內（台語，「家裡」）從一個很個人的動機開始：作者的阿嬤確診癌症第三期。
模型每半年都在進步，但她的聲音、她講阿公時的語氣，只有現在能錄。
所以這個專案的第一個工具不是 AI，是一份訪談題庫和一支錄音 app。

## 它會做什麼

- **回到阿嬤家**，手機偵測到位置，她會說「轉來矣？食飽未？」
- **坐下來**，她會聊阿公、親戚、厝邊發生的事，記得你上次說過什麼
- **看電視**，她會問劇情、罵壞人
- **滑手機卡住**，她會問你「這个貼圖按怎傳？」
- **拍照時**，她可以坐中間或站邊邊，跟你合照
- **平時**，像 LINE 一樣傳台語語音訊息給你，早上傳早安圖
- **支援台語**，聽、想、說三段分開處理
- **讓阿嬤看到你去哪玩**，照片丟進 Drive，阿嬤家的平板大字輪播「阿融去淡水」，數位阿嬤也會問你好不好玩
- **plugin**，用 MCP 協定接新的話題來源、情境觸發、語音與影像引擎

## 架構

```
家人手機 (Flutter) ──Google 登入──▶ Persona Engine (家用主機) ◀──唯讀同步── 共享 Google Drive（素材）
阿嬤家平板 ──/frame──▶              對話腦 / 台語語音 / 合照 / 旅行 / plugin / SQLite 記憶
```

素材放家人共享的 Google Drive 資料夾，家人用 Google 帳號就能加入。聲音模型、記憶、人格卡只在家用主機。
詳見 [docs/architecture.md](docs/architecture.md) 與 [docs/google-drive.md](docs/google-drive.md)。

## 快速開始

```bash
# 引擎（家用主機）
cd engine && uv sync --extra claude --extra drive --extra plugins
cp ../spec/examples/config.example.yaml ../data/config.yaml     # 填設定
cp ../spec/examples/persona.example.yaml ../data/persona.yaml   # 填阿嬤的資料
uv run tshulai-engine serve --host 0.0.0.0

# app：網頁版直接開 http://<引擎>:8765/app/
cd app && flutter build web --base-href /app/
# 手機：flutter run（需要 Xcode / Android SDK）

# 阿嬤看板：平板瀏覽器開 http://<引擎>:8765/frame?key=<data/frame_key.txt>
```

## 專案狀態

| 階段 | 內容 | 狀態 |
| --- | --- | --- |
| 0 | 採集工具：訪談題庫、錄音整理、轉寫、人物標籤 | 完成，等素材 |
| 1 | 人格卡、記憶、閒聊通道、Google Drive 同步、家人登入 | 完成 |
| 1 | 台語語音管線（Breeze-ASR、翻譯、GPT-SoVITS-TW） | adapter 完成，等素材實測 |
| 2 | 合照快版（app）、好版（ComfyUI）、姿勢庫、AI 標記 | adapter 完成，等素材 |
| 2 | 即時嘴型、待機影片 | adapter 完成，需 NVIDIA GPU |
| 3 | Flutter app、geofence、scene 狀態機、旅行足跡、阿嬤看板 | 完成，手機實機未測 |
| 4 | Plugin host（MCP）、天氣 plugin | 完成 |

待做項目見 [docs/roadmap.md](docs/roadmap.md)。

## 現在就能做的事

讀 [docs/data-collection.md](docs/data-collection.md)，拿起手機，去找你的家人。
那份文件列出要錄什麼、怎麼錄、怎麼整理，不需要任何技術。

## 目錄

```
docs/        設計文件、採集清單、訪談題庫
spec/        人格卡、記憶、plugin manifest 的 schema
capture/     階段 0：錄音整理與轉寫工具（Python CLI）
engine/      Persona Engine（FastAPI）
plugins/     plugin 範例
app/         Flutter client（iOS / Android / macOS / Windows / Web）
```

## 使用規範

程式碼採 MIT 授權。但這個專案處理的是真人的聲音和臉，請讀 [USE_POLICY.md](USE_POLICY.md)。

**注意模型授權**：預設的台語翻譯模型 Taigi-Llama-2-Translator 是 CC-BY-NC-SA（不可商用），只適合家用。
其他預設模型（Breeze-ASR-26、GPT-SoVITS-TW、MuseTalk、Qwen-Image-Edit、Wan2.2、BiRefNet）都可商用。
一句話版本：只做你自己家人的、經過同意的分身；不要拿去冒充任何人。

## 貢獻

歡迎。特別需要：台語語音辨識與合成的經驗、Flutter 背景定位、哀傷照護的專業意見。
