import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:google_sign_in/google_sign_in.dart';

import 'google_config.dart';

/// 家人身分：只用 Google 帳號登入取 ID token，不要任何 Drive 權限。
/// 素材權限由共享 Drive 資料夾管，引擎用 service account 讀。
class FamilyAuth extends ChangeNotifier {
  GoogleSignInAccount? _account;
  String? error;
  bool _ready = false;
  StreamSubscription<GoogleSignInAuthenticationEvent>? _sub;

  GoogleSignInAccount? get account => _account;
  String? get idToken => _account?.authentication.idToken;
  bool get signedIn => _account != null;
  bool get canSignInHere => _ready && GoogleSignIn.instance.supportsAuthenticate();

  /// 有帶入家庭的 client ID 才算設定好；沒設定時 app 仍能在引擎關掉 auth 的情況下使用。
  bool get configured => googleWebClientId.isNotEmpty || _serverClientId.isNotEmpty;
  String _serverClientId = '';

  Future<void> init({String serverClientId = ''}) async {
    _serverClientId = serverClientId.isNotEmpty ? serverClientId : googleWebClientId;
    final ios = defaultTargetPlatform == TargetPlatform.iOS || defaultTargetPlatform == TargetPlatform.macOS;
    try {
      await GoogleSignIn.instance.initialize(
        // 網頁用 Web client；iOS 用 iOS client；Android 不給 clientId，靠 serverClientId 拿到 aud=Web client 的 ID token
        clientId: kIsWeb ? _nullIfEmpty(googleWebClientId) : (ios && !kIsWeb ? _nullIfEmpty(googleIosClientId) : null),
        serverClientId: kIsWeb ? null : _nullIfEmpty(_serverClientId),
      );
      _sub = GoogleSignIn.instance.authenticationEvents.listen((e) {
        _account = switch (e) {
          GoogleSignInAuthenticationEventSignIn() => e.user,
          GoogleSignInAuthenticationEventSignOut() => null,
        };
        notifyListeners();
      }, onError: (Object e) {
        error = '$e';
        notifyListeners();
      });
      _ready = true;
      // 不 await：網頁版會一直等 One Tap，等下去 app 就畫不出來。結果走 authenticationEvents。
      unawaited(Future(() async => GoogleSignIn.instance.attemptLightweightAuthentication())
          .catchError((Object _) => null));
    } catch (e) {
      // 沒設定 OAuth client（開發模式）時會到這裡；引擎關掉 auth 也能用
      error = '$e';
      _ready = true;
    }
    notifyListeners();
  }

  static String? _nullIfEmpty(String s) => s.isEmpty ? null : s;

  Future<void> signIn() async {
    error = null;
    try {
      _account = await GoogleSignIn.instance.authenticate();
    } on GoogleSignInException catch (e) {
      error = e.description ?? e.code.name;
    } catch (e) {
      error = '$e';
    }
    notifyListeners();
  }

  Future<void> signOut() async {
    await GoogleSignIn.instance.signOut();
    _account = null;
    notifyListeners();
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }
}
