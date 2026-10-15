# tshulai-capture

階段 0 的工具。手機錄完丟進 `data/`，這支 CLI 幫你：

1. 檢查資料夾結構和檔名是否照規則（`check`）
2. 把音訊轉成訓練用的 16kHz 單聲道 WAV，順便依靜音切段（`normalize`）
3. 跑語音辨識產生逐字稿草稿（`transcribe`，台語辨識率看模型，先當草稿）
4. 把 `notes/log.md` 和逐字稿整理成記憶庫可以吃的 JSONL（`index`）
5. 印出今天建議的訪談題目（`interview`）
6. 統計採集進度（`progress`）

```bash
cd capture
uv sync --extra asr
uv run tshulai-capture --help
uv run tshulai-capture interview --topic 阿公
uv run tshulai-capture progress ../data
```

需要 ffmpeg 在 PATH 上。

資料夾結構見 `docs/data-collection.md`。真人的錄音永遠不要進 git，`.gitignore` 已擋 `data/`。
