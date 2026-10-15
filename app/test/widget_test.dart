import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:tshulai/src/screens/trips_screen.dart';
import 'package:tshulai/src/settings.dart';

void main() {
  test('台語相對日期', () {
    final now = DateTime.now();
    expect(agoTaigi(now), '今仔日');
    expect(agoTaigi(now.subtract(const Duration(days: 1))), '昨昏');
    expect(agoTaigi(now.subtract(const Duration(days: 3))), '3 工前');
    expect(agoTaigi(now.subtract(const Duration(days: 10))), '頂禮拜');
  });

  test('背景 geofence 事件留到下次開 app', () async {
    SharedPreferences.setMockInitialValues({});
    await AppSettings.addPendingEvent('geofence.enter:home');
    final s = await AppSettings.load();
    expect(s.takePendingEvents(), ['geofence.enter:home']);
    expect(s.takePendingEvents(), isEmpty);
  });

  test('引擎位址去掉結尾斜線', () async {
    SharedPreferences.setMockInitialValues({});
    final s = await AppSettings.load();
    s.engineUrl = 'http://100.64.0.2:8765/ ';
    expect(s.engineUrl, 'http://100.64.0.2:8765');
  });
}
