import 'dart:io';

import 'package:flutter/widgets.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:geolocator/geolocator.dart';
import 'package:native_geofence/native_geofence.dart';

import '../settings.dart';

const _homeId = 'ama-home';

/// geofence 觸發時在背景 isolate 跑：記下事件、跳通知。app 開起來時把事件送給阿嬤。
@pragma('vm:entry-point')
Future<void> onHomeGeofence(GeofenceCallbackParams params) async {
  WidgetsFlutterBinding.ensureInitialized();
  final enter = params.event == GeofenceEvent.enter;
  await AppSettings.addPendingEvent(enter ? 'geofence.enter:home' : 'geofence.exit:home');
  if (!enter) return;
  final n = FlutterLocalNotificationsPlugin();
  await n.initialize(
    settings: const InitializationSettings(
      android: AndroidInitializationSettings('@mipmap/ic_launcher'),
      iOS: DarwinInitializationSettings(),
    ),
  );
  await n.show(
    id: 1,
    title: '阿嬤',
    body: '轉來矣喔？食飽未？',
    notificationDetails: const NotificationDetails(
      android: AndroidNotificationDetails('ama', '阿嬤', importance: Importance.high, priority: Priority.high),
      iOS: DarwinNotificationDetails(),
    ),
  );
}

class Presence {
  static bool get supported => Platform.isAndroid || Platform.isIOS;

  /// 註冊阿嬤家。回傳 null 表示成功，否則是給人看的錯誤原因。
  static Future<String?> registerHome(double lat, double lng, {double radius = 100}) async {
    if (!supported) return '這個平台不支援背景定位，請用手機 app';
    var perm = await Geolocator.checkPermission();
    if (perm == LocationPermission.denied) perm = await Geolocator.requestPermission();
    if (perm == LocationPermission.denied || perm == LocationPermission.deniedForever) {
      return '需要定位權限';
    }
    if (perm != LocationPermission.always) {
      // iOS/Android 都要使用者自己到設定裡改成「永遠」，app 才能在背景知道你回到家
      perm = await Geolocator.requestPermission();
      if (perm != LocationPermission.always) {
        return '請到系統設定把定位權限改成「永遠允許」，不然 app 沒開時阿嬤不知道你回來';
      }
    }
    await NativeGeofenceManager.instance.initialize();
    await NativeGeofenceManager.instance.removeGeofenceById(_homeId).catchError((_) {});
    await NativeGeofenceManager.instance.createGeofence(
      Geofence(
        id: _homeId,
        location: Location(latitude: lat, longitude: lng),
        radiusMeters: radius,
        triggers: {GeofenceEvent.enter, GeofenceEvent.exit},
        iosSettings: const IosGeofenceSettings(initialTrigger: false),
        androidSettings: const AndroidGeofenceSettings(
          initialTriggers: {},
          notificationResponsiveness: Duration(minutes: 2),
        ),
      ),
      onHomeGeofence,
    );
    return null;
  }
}
