// 回到阿嬤家偵測。手機用原生 geofence（app 關掉也會觸發），網頁與桌面沒有。
export 'presence_stub.dart' if (dart.library.io) 'presence_native.dart';
