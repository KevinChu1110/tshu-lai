// 照片裡「現場的人」的遮罩，讓阿嬤可以站在大家後面。手機用 ML Kit，其他平台沒有。
export 'segmentation_stub.dart' if (dart.library.io) 'segmentation_native.dart';
