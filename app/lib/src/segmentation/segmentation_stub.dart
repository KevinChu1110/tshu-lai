import 'dart:typed_data';
import 'dart:ui' as ui;

class PeopleMask {
  static bool get supported => false;
  static Future<ui.Image?> of(Uint8List photo) async => null;
}
