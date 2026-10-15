# 影像管線技術調研（2026-10）

> 範圍：即時嘴型、待機影片、合照、去背、C2PA。資料來自下列連結的 README／文件（2026-10-16 讀取）。
> 沒寫在 README 的數字（例如 Mac 上的 fps）一律標「未記載」，要自己實測。

## 1. 即時嘴型／talking head

**預設：MuseTalk 1.5，透過 [LiveTalking](https://github.com/lipku/LiveTalking) 提供服務**
- [MuseTalk](https://github.com/TMElyralab/MuseTalk)：程式碼 MIT，權重**可商用**；V100 上 30fps 以上。只重繪嘴部，所以拿「待機影片」當底片剛好合用。README 沒提到 MPS／Mac。
- LiveTalking（Apache-2.0）：WebRTC 串流服務，musetalk 實測 3090 45fps、4090 72fps；可中途打斷。
  啟動：`python app.py --transport webrtc --model musetalk --avatar_id <id>`
  介面（[docs/api.md](https://raw.githubusercontent.com/lipku/LiveTalking/main/docs/api.md)）：
  - `POST /offer` `{sdp, type:"offer", avatar?}` → `{sdp, type:"answer", sessionid}`（也支援 `POST /whep`）
  - `POST /humanaudio`（multipart：`sessionid`, `file`）← 接我們自己的台語 TTS 音檔
  - `POST /human` `{sessionid, text, type:"echo"|"chat", interrupt}`、`POST /interrupt_talk`、`POST /is_speaking`、`GET /sse?sessionid=`

**備選**
| 模型 | 授權 | 適合 | 備註 |
|---|---|---|---|
| [Ditto](https://github.com/antgroup/ditto-talkinghead) | Apache-2.0 | 照片 → 整顆頭動，可串流 | 有 `stream_pipeline_online.py`；TensorRT 預建引擎限 Ampere 以上，2025-07 起有 PyTorch 版。`python inference.py --data_root … --cfg_pkl … --audio_path a.wav --source_path img.png --output_path o.mp4` |
| [LivePortrait](https://github.com/KwaiVGI/LivePortrait) / [FasterLivePortrait](https://github.com/warmshao/FasterLivePortrait) | MIT，但 [InsightFace 模型僅限非商用](https://raw.githubusercontent.com/KwaiVGI/LivePortrait/main/LICENSE) | 表情、點頭 | Faster 版 3090+TensorRT 30fps 以上；macOS 可用 `--mode onnx` 但「仍相當慢」；JoyVASA 可用音訊驅動；`python api.py` 跑在 9871 port，路由沒寫在文件裡（看 `tests/test_api.py`） |
| [LatentSync 1.6](https://github.com/bytedance/LatentSync) | Apache-2.0 | **離線**把真實錄影對上新台詞 | 只吃影片；需 18GB VRAM；`./inference.sh` |
| [EchoMimicV3](https://github.com/antgroup/echomimic_v3) | Apache-2.0 | 離線半身影片 | 1.3B（基於 Wan2.1），12GB；2026-01 推出 Flash 版；`bash run_flash.sh` |
| [Hallo3](https://github.com/fudan-generative-vision/hallo3) | MIT＋CogVideo 授權 | — | 測試用 H100，不合用 |
| [Sonic](https://github.com/jixiaozhong/Sonic) | **CC BY-NC-SA** | — | 非商用，不當預設 |

## 2. 待機影片（image-to-video）

**預設：[Wan2.2](https://github.com/Wan-Video/Wan2.2) TI2V-5B**（Apache-2.0，24GB／4090，720p 5 秒影片不到 9 分鐘；已整合進 ComfyUI 和 Diffusers）
`python generate.py --task ti2v-5B --size 1280*704 --ckpt_dir ./Wan2.2-TI2V-5B --offload_model True --convert_model_dtype --t5_cpu --image grandma.jpg --prompt "…"`
（I2V-A14B 品質更好，但單卡要 80GB。）

| 模型 | VRAM | 授權 | Mac |
|---|---|---|---|
| [HunyuanVideo 1.5](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5) | 8.3B，開 offload 14GB；4090 跑 480p 蒸餾版約 75 秒 | [Community License](https://raw.githubusercontent.com/Tencent-Hunyuan/HunyuanVideo-1.5/main/LICENSE) **不適用於歐盟／英國／南韓** | 未記載 |
| [HunyuanVideo-I2V](https://github.com/Tencent-Hunyuan/HunyuanVideo-I2V) | 720p 要 60GB | 同上 | 否 |
| [FramePack](https://github.com/lllyasviel/FramePack) | 6GB；4090 每幀 1.5–2.5 秒 | Apache-2.0 | 只支援 NVIDIA |
| [LTX-Video 0.9.8](https://github.com/Lightricks/LTX-Video) / [LTX-2](https://github.com/Lightricks/LTX-2) | 有蒸餾版和 FP8 版；LTX-2 還會產生音訊 | 商用條款要逐一核對 LICENSE 檔 | MPS 支援有限 |

結論：Mac 上沒有正式支援的選項，照架構文件的規劃「租 GPU 跑一次，把影片帶回家」。

## 3. 把阿嬤放進合照

**預設：[Qwen-Image-Edit-2511](https://huggingface.co/Qwen/Qwen-Image-Edit-2511)**（Apache-2.0）
- 支援多張輸入圖；2511 版大幅改善角色一致性，可以把兩張人物照合成一張自然的團體照，也內建打光 LoRA。
- Adapter（[Qwen-Image](https://github.com/QwenLM/Qwen-Image)）：`QwenImageEditPlusPipeline.from_pretrained("Qwen/Qwen-Image-Edit-2511")`，呼叫時帶 `image=[scene, grandma_pose]`、`prompt`、`true_cfg_scale=4.0`、`num_inference_steps=40`。官方提醒：不先改寫 prompt，結果會不穩定。

**要精準控制位置和比例時：[InsertAnything](https://github.com/song-wensong/insert-anything)**
- 吃遮罩，構圖助手算出來的人框可以直接當遮罩。走 Nunchaku 約 10GB，有 ComfyUI 節點。
- 程式碼 MIT，但它建在 FLUX.1-Fill-dev 上，**權重不能商用**。

**其他選項**
- [FLUX.2 klein 4B](https://github.com/black-forest-labs/flux2)：Apache-2.0，約 8GB，可多參考圖編輯，適合當快速版。
- [FLUX.1 Kontext dev](https://github.com/black-forest-labs/flux)、FLUX.2 dev、klein 9B：都是非商用授權。
- [OmniGen2](https://github.com/VectorSpaceLab/OmniGen2)：Apache、17GB；README 承認插入的物件會走樣。
- [PuLID](https://github.com/ToTheBeginning/PuLID)：是生成新圖，不是插進既有照片，不合用。

**自動化介面**：一律包成 ComfyUI workflow，透過它的 [server routes](https://docs.comfy.org/development/comfyui-server/comms_routes) 操作：`POST /upload/image` → `POST /prompt`（回傳 `prompt_id`）→ 監聽 `WS /ws` 的進度 → `GET /history/{prompt_id}` → `GET /view` 取圖。

## 4. 去背／人像分割

- **姿勢庫的遮罩（Engine 端，事先算好）**：[BiRefNet](https://github.com/ZhengPeng7/BiRefNet)（MIT），用 Portrait 或 HR-matting 權重，有 ONNX；4090 FP16 約 58ms。**不要用 [RMBG-2.0](https://huggingface.co/briaai/RMBG-2.0)**，它是 CC BY-NC，而且本身就是 BiRefNet 架構。
- **手機即時預覽（偵測遮擋、找空位）**：[google_mlkit_selfie_segmentation 0.12.1](https://pub.dev/packages/google_mlkit_selfie_segmentation)，Android 和 iOS 都能用，`SelfieSegmenter(mode: SegmenterMode.stream, enableRawSizeMask: true)`。
- **iOS 加強版**：透過 platform channel 呼叫 Vision 的 `VNGeneratePersonSegmentationRequest`，品質分 fast／balanced／accurate；iOS 17 起的 `VNGeneratePersonInstanceMaskRequest` 能把每個人分開。[Apple 文件頁](https://developer.apple.com/documentation/vision/vngeneratepersonsegmentationrequest)內容沒抓到，這兩點是依我的既有知識，要再確認。
- 阿嬤自己的去背圖已經事先算好，手機只需要分割「現場的人」。

## 5. C2PA 簽章

[c2pa-python](https://github.com/contentauth/c2pa-python)（Apache/MIT）：`pip install c2pa-python`，寫法照 [examples/sign.py](https://raw.githubusercontent.com/contentauth/c2pa-python/main/examples/sign.py)。
```python
manifest = {"claim_generator_info":[{"name":"tshu-lai","version":"0.1"}],
  "format":"image/jpeg","title":"合照","assertions":[{"label":"c2pa.actions","data":{"actions":[
   {"action":"c2pa.created","digitalSourceType":
    "http://cv.iptc.org/newscodes/digitalsourcetype/compositeWithTrainedAlgorithmicMedia"}]}}]}
with c2pa.Context() as ctx, c2pa.Signer.from_callback(sign_es256, c2pa.C2paSigningAlg.ES256,
        certs_pem, "http://timestamp.digicert.com") as signer, c2pa.Builder(manifest, ctx) as b:
    b.sign_file("in.jpg", "out.jpg", signer)
```
- [IPTC](https://cv.iptc.org/newscodes/digitalsourcetype/) 標記怎麼選：合照用 `compositeWithTrainedAlgorithmicMedia`（拿 AI 編輯過真實照片）；早安圖和待機影片用 `trainedAlgorithmicMedia`（整張由 AI 生成）。
- 用自簽憑證時，沒有載入 trust 設定的驗證器會顯示 Invalid，但標記照樣嵌在檔案裡。
- 時間戳那行會連外部的 digicert 伺服器，跟「資料留在家裡」衝突；隱私優先就拿掉或設成可關閉。

## 給 repo 的改進項目

1. `architecture.md` 寫「MuseTalk/LivePortrait 在 Apple Silicon 上 30fps」，沒有任何來源支持。改成：即時嘴型需要 NVIDIA GPU（≥3080Ti 級）；Mac 只做離線預渲染，或退回 FasterLivePortrait 的 ONNX 模式。
2. 把 vision／camera plugin 分成兩種介面：**串流型**（WebRTC offer＋送音檔＋打斷，直接對應 LiveTalking）和**工作型**（submit／poll／fetch，對應 ComfyUI）。
3. plugin manifest 加 `weights_license` 和 `commercial_ok` 欄位，非商用權重（InsightFace、FLUX dev、RMBG-2.0、Sonic）預設不載入，或載入時明確警告。
4. 合照表格把「BiRefNet / RMBG」改成只寫 BiRefNet。
5. `data-collection.md` 加一項：錄 1–2 分鐘正面、光線均勻、自然講話的影片。MuseTalk 和 LatentSync 拿真實影片當底，效果比單張照片好很多；這段錄影也能當 Ditto 和 LivePortrait 的參考。
6. HunyuanVideo 的地區限制寫進文件，避免當成預設。
7. C2PA 簽章金鑰放 `data/keys/`，設定檔加「是否連外部時間戳伺服器」的選項。
