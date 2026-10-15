# ComfyUI workflows

工作型影像任務的 workflow，用 ComfyUI 的「Export (API)」匯出後放這裡。輸入用 `{{佔位符}}` 標記。

| 檔案 | 用途 | 佔位符 | 建議模型 |
| --- | --- | --- | --- |
| insert_person.json | 合照好版 | scene_image, person_image, instruction | Qwen-Image-Edit-2511（Apache-2.0） |
| idle_video.json | 待機影片 | image, prompt | Wan2.2 TI2V-5B（Apache-2.0） |

授權注意：FLUX.1 Kontext dev、FLUX.2 dev、InsertAnything、RMBG-2.0 都是非商用權重，不要放進預設 workflow。
詳見 [docs/research/vision.md](../../docs/research/vision.md)。
