import 'dart:io';
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:google_mlkit_selfie_segmentation/google_mlkit_selfie_segmentation.dart';
import 'package:path_provider/path_provider.dart';

class PeopleMask {
  static bool get supported => Platform.isAndroid || Platform.isIOS;

  /// 回傳和照片同尺寸比例的遮罩圖：人的地方不透明，其他透明。
  static Future<ui.Image?> of(Uint8List photo) async {
    if (!supported) return null;
    final dir = await getTemporaryDirectory();
    final f = File('${dir.path}/seg_${DateTime.now().microsecondsSinceEpoch}.jpg');
    await f.writeAsBytes(photo);
    final seg = SelfieSegmenter(mode: SegmenterMode.single, enableRawSizeMask: true);
    try {
      final mask = await seg.processImage(InputImage.fromFilePath(f.path));
      if (mask == null) return null;
      final rgba = Uint8List(mask.width * mask.height * 4);
      for (var i = 0; i < mask.confidences.length; i++) {
        final a = (mask.confidences[i] * 255).round().clamp(0, 255);
        rgba[i * 4] = 255;
        rgba[i * 4 + 1] = 255;
        rgba[i * 4 + 2] = 255;
        rgba[i * 4 + 3] = a;
      }
      final buf = await ui.ImmutableBuffer.fromUint8List(rgba);
      final desc = ui.ImageDescriptor.raw(buf, width: mask.width, height: mask.height, pixelFormat: ui.PixelFormat.rgba8888);
      final frame = await (await desc.instantiateCodec()).getNextFrame();
      return frame.image;
    } finally {
      await seg.close();
      await f.delete().catchError((_) => f);
    }
  }
}
