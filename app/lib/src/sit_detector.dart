import 'dart:async';
import 'dart:math';

import 'package:sensors_plus/sensors_plus.dart';

/// 坐下偵測：在阿嬤家（進門 scene 之後），手機連續 [still] 沒什麼動就算坐下來了。
/// 用 userAccelerometer（已扣掉重力），晃動小於 [threshold] m/s² 算靜止。
class SitDetector {
  SitDetector({required this.onSit, this.still = const Duration(minutes: 2), this.threshold = 0.35});

  final void Function() onSit;
  final Duration still;
  final double threshold;
  StreamSubscription<UserAccelerometerEvent>? _sub;
  DateTime? _stillSince;
  bool _fired = false;

  /// 進門後開始看；離開阿嬤家或已經坐下就停。
  void start() {
    if (_sub != null) return;
    _fired = false;
    _stillSince = null;
    try {
      _sub = userAccelerometerEventStream(samplingPeriod: SensorInterval.normalInterval).listen(feed, onError: (_) => stop());
    } catch (_) {
      // 桌面沒有感測器
    }
  }

  void stop() {
    _sub?.cancel();
    _sub = null;
  }

  /// 抽出來方便測試。
  void feed(UserAccelerometerEvent e, [DateTime? now]) {
    final t = now ?? DateTime.now();
    final mag = sqrt(e.x * e.x + e.y * e.y + e.z * e.z);
    if (mag > threshold) {
      _stillSince = null;
      return;
    }
    _stillSince ??= t;
    if (!_fired && t.difference(_stillSince!) >= still) {
      _fired = true;
      onSit();
      stop();
    }
  }
}
