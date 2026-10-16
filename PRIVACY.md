# 隱私權政策 Privacy Policy

最後更新：2026-10-16

厝內（Tshù-lāi）是一個開源軟體，由每個家庭自己架設在家裡的電腦上。專案作者不經營任何伺服器，也收不到任何家庭的資料。

## 我們用 Google 帳號做什麼

家人用 Google 帳號登入厝內 app 時，app 只向 Google 取得**你的 email 與名字**（openid、email、profile 範圍），用途只有一個：
讓你家的家用主機確認你是不是家人名單上的人，以及阿嬤該怎麼稱呼你。

- 不讀取你的 Gmail、聯絡人、相簿或雲端硬碟。
- 不把 email 傳給任何第三方，不用於廣告。
- email 只存在你家家用主機的設定檔，由架設的家人管理。

## 素材放在哪裡

家人的錄音、照片放在家人自己共享的 Google Drive 資料夾，權限由家人在 Google Drive 管理。
家用主機用唯讀的 service account 同步一份到本機，用來產生聲音、影像與記憶。這些衍生資料只在家用主機。

## AI 服務

如果家庭選擇用雲端語言模型（例如 Claude），送出去的只有人格卡文字與對話內容，不含聲音與臉。

## 刪除

把共享資料夾取消分享、刪掉家用主機上的 `data/` 資料夾，資料就全部消失。
要移除 app 存取 Google 帳號的權限：https://myaccount.google.com/permissions

## 聯絡

https://github.com/KevinChu1110/tshu-lai/issues
