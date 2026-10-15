# 厝內 app

Flutter：iOS、Android、macOS、Windows、Web。

```bash
flutter pub get
flutter analyze && flutter test
flutter build web --base-href /app/   # 引擎會在 /app/ 提供
flutter run -d chrome                 # 開發
flutter run                           # 手機（需要 Xcode / Android SDK）
```

| 分頁 | 功能 |
| --- | --- |
| 阿嬤 | 聊天、語音、按住講話、給未來的留言 |
| 合照 | 相機疊阿嬤去背圖，站倒爿 / 坐中央 / 站正爿，快版存檔、好版送引擎 |
| 去佗位 | 傳旅行照片給阿嬤看 |
| 設定 | 引擎位址、Google 登入、註冊阿嬤家、阿嬤看板模式 |

Google 登入要先照 [docs/google-drive.md](../docs/google-drive.md) 步驟三建 OAuth client：
- iOS：把 iOS client 的 `GIDClientID` 與反轉的 client ID URL scheme 加進 `ios/Runner/Info.plist`。
- Android：在設定頁填 Web client ID（serverClientId）；Firebase 不需要。
- Web：在 `web/index.html` 加 `<meta name="google-signin-client_id" content="...">`。

沒設定 OAuth 時，引擎把 `auth.enabled` 關掉就能在家裡網路先用。
