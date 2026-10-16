/// 家庭專屬的 Google OAuth client ID，建置時用 --dart-define-from-file=config/google.json 帶入。
/// 不是祕密（會出現在 app 裡），但每個家庭不同，所以不寫死在原始碼。
const googleWebClientId = String.fromEnvironment('GOOGLE_WEB_CLIENT_ID');
const googleIosClientId = String.fromEnvironment('GOOGLE_IOS_CLIENT_ID');
