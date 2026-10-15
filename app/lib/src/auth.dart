import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:google_sign_in/google_sign_in.dart';

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

  Future<void> init({String serverClientId = ''}) async {
    try {
      await GoogleSignIn.instance.initialize(
        serverClientId: serverClientId.isEmpty || kIsWeb ? null : serverClientId,
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
      await GoogleSignIn.instance.attemptLightweightAuthentication();
    } catch (e) {
      // 沒設定 OAuth client（開發模式）時會到這裡；引擎關掉 auth 也能用
      error = '$e';
      _ready = true;
    }
    notifyListeners();
  }

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
