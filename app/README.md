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

Google 登入要先照 [docs/google-drive.md](../docs/google-drive.md) 步驟三建 OAuth client，然後：

```bash
cp config/google.example.json config/google.json                    # 填 Web 與 iOS client ID
cp ios/Flutter/Google.example.xcconfig ios/Flutter/Google.xcconfig  # 填反轉的 iOS client ID
flutter build web --base-href /app/ --dart-define-from-file=config/google.json
flutter build apk --dart-define-from-file=config/google.json
```

這兩個檔案是每個家庭自己的，已在 `.gitignore`。Android 的 SHA-1 要和 OAuth Android client 登記的一樣（debug 版用 `~/.android/debug.keystore`）。
網頁版的 JavaScript 來源要在 OAuth Web client 登記（如 `http://localhost:8765`）；Google 只接受 https 或 localhost。

沒設定 OAuth 時，引擎把 `auth.enabled` 關掉就能在家裡網路先用。
