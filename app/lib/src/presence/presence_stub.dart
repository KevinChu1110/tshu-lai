class Presence {
  static bool get supported => false;
  static Future<String?> registerHome(double lat, double lng, {double radius = 100}) async =>
      '這個平台不支援背景定位，請用手機 app';
}
