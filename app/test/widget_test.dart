import 'package:flutter_test/flutter_test.dart';
import 'package:sensors_plus/sensors_plus.dart';
import 'package:tshulai/src/sit_detector.dart';
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

  test('坐下偵測：靜止兩分鐘觸發一次，中途晃動重算', () {
    var sat = 0;
    final d = SitDetector(onSit: () => sat++);
    final t0 = DateTime(2026, 10, 16, 18);
    UserAccelerometerEvent ev(double v) => UserAccelerometerEvent(v, 0, 0, t0);
    d.feed(ev(0.05), t0);
    d.feed(ev(0.05), t0.add(const Duration(seconds: 90)));
    d.feed(ev(2.0), t0.add(const Duration(seconds: 100)));      // 起身走動
    d.feed(ev(0.05), t0.add(const Duration(seconds: 110)));
    d.feed(ev(0.05), t0.add(const Duration(seconds: 200)));
    expect(sat, 0);
    d.feed(ev(0.05), t0.add(const Duration(seconds: 231)));
    d.feed(ev(0.05), t0.add(const Duration(seconds: 400)));
    expect(sat, 1);
  });
}
