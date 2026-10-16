import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'google_config.dart';

/// App 設定。存在本機，換手機要重設。
class AppSettings extends ChangeNotifier {
  AppSettings._(this._prefs);

  final SharedPreferences _prefs;

  static Future<AppSettings> load() async =>
      AppSettings._(await SharedPreferences.getInstance());

  /// 家用主機的引擎位址，通常是 Tailscale 位址，如 http://100.64.0.2:8765
  /// 網頁版通常就是引擎自己提供的（<引擎>/app/），預設用同一個來源。
  String get engineUrl =>
      _prefs.getString('engineUrl') ?? (kIsWeb ? Uri.base.origin : 'http://127.0.0.1:8765');
  set engineUrl(String v) {
    _prefs.setString('engineUrl', v.trim().replaceAll(RegExp(r'/+$'), ''));
    notifyListeners();
  }

  /// Google OAuth Web client ID（引擎用它驗 ID token 的 audience）。Android 需要它當 serverClientId。
  String get googleServerClientId => _prefs.getString('googleServerClientId') ?? googleWebClientId;
  set googleServerClientId(String v) {
    _prefs.setString('googleServerClientId', v.trim());
    notifyListeners();
  }

  /// 阿嬤看板的鑰匙（平板不用登入）
  String get frameKey => _prefs.getString('frameKey') ?? '';
  set frameKey(String v) {
    _prefs.setString('frameKey', v.trim());
    notifyListeners();
  }

  /// 這台裝置是阿嬤的看板：開機直接進看板
  bool get frameMode => _prefs.getBool('frameMode') ?? false;
  set frameMode(bool v) {
    _prefs.setBool('frameMode', v);
    notifyListeners();
  }

  bool get voiceReplies => _prefs.getBool('voiceReplies') ?? true;
  set voiceReplies(bool v) {
    _prefs.setBool('voiceReplies', v);
    notifyListeners();
  }

  /// geofence 在背景觸發、app 沒開時記下來，下次開 app 時送給阿嬤
  List<String> takePendingEvents() {
    final list = _prefs.getStringList('pendingEvents') ?? [];
    _prefs.remove('pendingEvents');
    return list;
  }

  static Future<void> addPendingEvent(String name) async {
    final p = await SharedPreferences.getInstance();
    final list = p.getStringList('pendingEvents') ?? [];
    await p.setStringList('pendingEvents', [...list, name]);
  }
}
