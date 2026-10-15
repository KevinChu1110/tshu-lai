# 貢獻指南

謝謝你來。這個專案處理的是真人的聲音和臉，所以有幾件事比一般開源專案嚴格：

1. **絕對不要 commit 任何真人的錄音、照片、逐字稿。** `data/` 已在 `.gitignore`。測試用的範例一律虛構。
2. **人格卡範例不能是真人。** `spec/examples/` 下的東西是編的。
3. **生成內容一定帶標記。** 新的 TTS 或影像 plugin 要過浮水印與 EXIF 標記，PR 沒有這段不收。
4. **台語用字**：文件與題庫用教育部臺灣台語常用詞辭典的推薦漢字，不確定就附台羅。

## 最需要幫忙的

- 台語語音辨識與合成的實測與微調經驗
- Flutter 背景定位（iOS Region Monitoring、Android Geofencing）
- 哀傷照護、老人心理的專業意見，特別是「道別模式」該怎麼設計
- 訪談題庫：你家的長輩會講什麼？加主題，保留每個人都問的三題結構

## 流程

- Issue 先討論再動手，除了文件錯字
- commit 格式 `[TAG] scope: 描述`，TAG 為 ADD / FIX / IMP / REF / REM / DOC
- PR 要能跑 `cd engine && uv run pytest`
