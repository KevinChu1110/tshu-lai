# 語音管線選型研究（2026-10）

> 所有連結都在 2026-10-16 實際打開過。CER 與品質數字都是作者自報，沒有在阿嬤的錄音上實測。

## 結論：預設組合

| 段 | 預設 | 備案 |
| --- | --- | --- |
| 聽 | [Breeze-ASR-26](https://huggingface.co/MediaTek-Research/Breeze-ASR-26)（Apache-2.0） | [NUTN-KWS/Whisper-Taiwanese-model-v0.5](https://huggingface.co/NUTN-KWS/Whisper-Taiwanese-model-v0.5)（CC BY-NC 4.0） |
| 想 | LLM 用華語生成（不變） | — |
| 譯 | [Bohanlu/Taigi-Llama-2-Translator-7B](https://huggingface.co/Bohanlu/Taigi-Llama-2-Translator-7B)，華語 → POJ 加漢字 | 先產生台語漢字，再用 [taibun](https://github.com/andreihar/taibun)（MIT）轉台羅 |
| 說 | [KaedeTai/GPT-SoVITS](https://github.com/KaedeTai/GPT-SoVITS) 台語 fork 加 [gpt-sovits-tw](https://huggingface.co/kaedetai/gpt-sovits-tw) 權重（MIT） | [Fun-CosyVoice3-0.5B-2512](https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512)（Apache-2.0，有列「Minnan」） |
| 標記 | [AudioSeal](https://github.com/facebookresearch/audioseal) 0.2 串流版（MIT，包含權重） | — |

## 1. 台語 ASR

- **Breeze-ASR-26**：以 Whisper-large-v2 微調，用了約 1 萬小時合成台語語料，支援台華混講，授權 Apache-2.0。在作者的 Taigi benchmark（30 句台華混講）上平均 CER 30.13%，教育部輸入法 30.70%、雅婷 32.11%、Gemini 3 Flash 32.52%、Breeze-ASR-25 49.99%。**輸出是華語漢字**，不是台文也不是台羅，剛好可以直接餵給「華語思考」的 LLM。
  - 已有的轉檔（Apache-2.0）：[weemed/Breeze-ASR-26-ct2](https://huggingface.co/weemed/Breeze-ASR-26-ct2)，給 faster-whisper 用，RTF 0.21（4 核 CPU）；[weemed/Breeze-ASR-26-GGML](https://huggingface.co/weemed/Breeze-ASR-26-GGML)，給 whisper.cpp 用，Q5_0 1.1 GB；[doggy8088/Breeze-ASR-26-MLX-4bit](https://huggingface.co/doggy8088/Breeze-ASR-26-MLX-4bit)，給 Apple Silicon 用。Mac 上建議跑 MLX 或 whisper.cpp（Metal）。
- **NUTN-KWS v0.5**：以 large-v3-turbo 微調，約 90 小時，沒有報 CER，授權不可商用，可以當備案或當微調起點。
- 社群的 TAT 微調模型很多（[搜尋結果](https://huggingface.co/models?search=whisper%20taiwanese)），大多是 small 或 tiny，沒有評測。論文數據：Whisper-small 在 TAT-MOE test 上 CER 18.68%，large 加 AdaLoRA 13.89%（[arXiv 2609.18194](https://arxiv.org/pdf/2609.18194)）。
- 長輩口音、慢速、含糊的語音一定會掉準確率。真正的解法是拿她的錄音加上人工校正的逐字稿，對 Breeze-ASR-26 做 LoRA 微調。

## 2. 華語 → 台語文本

- **Taigi-Llama-2-Translator-7B/13B**：可以互譯華語、英語和台語漢字（HAN）、POJ、漢羅（HL），授權 CC-BY-NC-SA-4.0，論文在 [arXiv 2403.12024](https://arxiv.org/abs/2403.12024)。有 GGUF 版（[搜尋結果](https://huggingface.co/models?search=taigi)），可以用 Ollama 或 llama.cpp 起 OpenAI 相容的 HTTP 服務。
  - Prompt 格式：`{BOS}[TRANS]\n{原文}\n[/TRANS]\n[POJ]\n`。目標可以是 `ZH`、`EN`、`POJ`、`HL`、`HAN`。
  - 一句話跑兩次：`[POJ]` 的結果餵給 TTS，`[HAN]` 的結果當畫面上的字幕。
- **taibun**：把漢字轉成台羅、POJ、IPA 等，可以設定連讀變調（none/auto…）。程式 MIT，資料 CC BY-SA 4.0。
- **意傳**：[臺灣言語工具](https://github.com/i3thuan5/tai5-uan5_gian5-gi2_kang1-ku7) 採 CPAL 授權，[KeSi](https://github.com/i3thuan5/KeSi) 是 MIT，兩個都是 Python 函式庫，**沒有公開的 HTTP API 文件**。實測 `hokbu.ithuan.tw` 回 404 或 500，不要依賴。
- **TAIDE**：沒有找到專門做台語翻譯的模型。目前的實際做法還是「LLM 寫華語，再交給 Taigi 翻譯模型」。

## 3. 聲音複製 TTS

| 引擎 | 台語 | 授權 | Apple Silicon |
| --- | --- | --- | --- |
| GPT-SoVITS 上游（v2Pro/v4/v5） | **不支援**。語言白名單只有 `zh/en/ja/ko/yue`（含 `all_*`、`auto*` 變體），用 `zh` 會唸成華語 | MIT | 可推論（MPS 或 CPU）；官方說 Mac 只能用 CPU 訓練 |
| **KaedeTai fork** | 支援。輸入 POJ 或台羅，內建變調前處理，用約 15–25 小時台語資料訓練 | MIT | 作者在 M1 Max 上訓練；一句 10–30 秒；MPS 輸出無法完全重現 |
| Fun-CosyVoice3 | 有列「Minnan」，但沒說是不是台灣腔，也沒寫怎麼呼叫 | Apache-2.0 | 部署範例只有 NVIDIA |
| [MERaLiON OmniVoice Hokkien](https://huggingface.co/MERaLiON/MERaLiON-OmniVoice-Hokkien-TTS) | 新加坡福建話，不是台語 | 自訂授權 | 範例用 CUDA |
| BreezyVoice 26 | 台語，以 CosyVoice2 為基礎 | **權重未公開**（[聯發科文章](https://www.mediatek.com/zh-tw/tek-talk-blogs/mediatek-research-breeze-3)） | — |
| F5-TTS | 不支援 | 程式 MIT，權重 CC-BY-NC | — |
| Fish Speech / OpenAudio | 不支援 | Fish Audio Community License | — |
| IndexTTS2 | 不支援 | bilibili 自訂授權 | — |

**微調她的聲音**：從 gpt-sovits-tw 權重出發，用她 10 分鐘到 2 小時的錄音做微調。逐字稿要用 POJ，而且要照「實際唸出來的變調」標，不是本調。先微調 S2（SoVITS），S1 可以只微調少量步數。這段**我們還沒驗證**，fork 作者只示範過單一說話人。訓練建議租 CUDA GPU，推論放在家裡的 Mac。

## 推薦 TTS 伺服器的 HTTP 介面

**A. KaedeTai fork 的 `python -m tw_inference.webui`**（Flask，綁 `127.0.0.1:5557`，不支援串流）

```
POST /api/synthesize
  {"text": "Lí tsia̍h-pá--bē?", "seed": 42, "apply_sandhi": true, "ref": "/abs/ref.wav"}
  → 200 {"mp3": "/abs/cache/<key>.mp3", "key": "<key>", "url": "/audio/<key>.mp3"}
  → 400 {"error": "text is empty"} | 500 {"error": "<repr>"}
GET  /audio/<key>.mp3   → audio/mpeg
GET  /api/refs          → {"refs": [...], "default": "..."}
```

`text` 可以用 `{tw:...}{zh:...}` 分段標語言。`ref` 是 3–10 秒的單聲道 wav。

**B. 上游 `api_v2.py`**（fork 裡也有，但不接受台語）：`python api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer.yaml`

```
GET|POST /tts  JSON: text*, text_lang*, ref_audio_path*, prompt_lang*, prompt_text="",
  aux_ref_audio_paths=[], top_k=15, top_p=1, temperature=1, text_split_method="cut5",
  batch_size=1, batch_threshold=0.75, split_bucket=true, speed_factor=1.0,
  fragment_interval=0.3, seed=-1, media_type="wav|raw|ogg|aac", streaming_mode=false|0-3,
  parallel_infer=true, repetition_penalty=1.35, sample_steps, super_sampling=false,
  overlap_length=2, min_chunk_length=16
  → 200 audio/<media_type>（串流時先送 wav header，之後是 raw PCM）
  → 400 {"message": ..., "Exception"?: ...}
GET /set_gpt_weights?weights_path=…  /set_sovits_weights?weights_path=…
GET /set_refer_audio?refer_audio_path=…  GET /control?command=restart|exit
```

## 4. 浮水印

AudioSeal 0.2（2024-12）新增串流版的產生器 `audioseal_wm_streaming` 和偵測器 `audioseal_detector_streaming`，標準版是 `audioseal_wm_16bits`，可以嵌 16-bit 訊息。適用 16 或 24 kHz，GPT-SoVITS 的 32 或 48 kHz 輸出要先重採樣。沒有找到更新的替代品。

## 給這個 repo 的改進項目

1. `docs/architecture.md` 語音管線表要改：GPT-SoVITS 上游**不會說台語**，首選改成 KaedeTai fork；意傳沒有可用的 HTTP API；BreezyVoice 26 還沒開源；ASR 首選改成 Breeze-ASR-26。
2. TTS plugin 介面要能吃 `{poj, han, zh}` 三種文字，而且串流和非串流都要支援（fork 目前只能整句合成）。延遲目標要重新估：在 Mac 上一句 10–30 秒，1.5 秒首句做不到，需要預先合成常用句加快取。
3. `capture/` 要加 POJ 逐字稿流程：ASR 出華語草稿 → 翻譯成 POJ → 人工校正（照實際變調標）。這份資料同時用在 ASR 和 TTS 的微調。
4. 錄音規格寫進 `data-collection.md`：32 kHz 以上、單聲道、每段 3–12 秒、音量正規化、安靜環境。
5. 授權表：Taigi Translator 和 NUTN ASR 都是 NC 授權，在 README 標成「可選、不可商用」。
6. 浮水印模組要先重採樣，並且把 16-bit 訊息對應到 persona id。
