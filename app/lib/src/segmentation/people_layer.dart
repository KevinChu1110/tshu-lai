import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';

/// 只畫照片裡「人」的部分（用遮罩 dstIn），疊在阿嬤上面 → 阿嬤看起來站在大家後面。
class PeopleLayer extends StatefulWidget {
  const PeopleLayer({super.key, required this.photo, required this.mask});
  final Uint8List photo;
  final ui.Image mask;

  @override
  State<PeopleLayer> createState() => _PeopleLayerState();
}

class _PeopleLayerState extends State<PeopleLayer> {
  ui.Image? _img;

  @override
  void initState() {
    super.initState();
    ui.instantiateImageCodec(widget.photo).then((c) => c.getNextFrame()).then((f) {
      if (mounted) setState(() => _img = f.image);
    });
  }

  @override
  Widget build(BuildContext context) =>
      _img == null ? const SizedBox.shrink() : CustomPaint(painter: _Painter(_img!, widget.mask), size: Size.infinite);
}

class _Painter extends CustomPainter {
  _Painter(this.photo, this.mask);
  final ui.Image photo;
  final ui.Image mask;

  @override
  void paint(Canvas canvas, Size size) {
    // 和 Image(fit: contain) 一樣的擺法
    final src = Size(photo.width.toDouble(), photo.height.toDouble());
    final fitted = applyBoxFit(BoxFit.contain, src, size);
    final dst = Alignment.center.inscribe(fitted.destination, Offset.zero & size);
    canvas.saveLayer(dst, Paint());
    canvas.drawImageRect(photo, Offset.zero & src, dst, Paint());
    canvas.drawImageRect(mask, Offset.zero & Size(mask.width.toDouble(), mask.height.toDouble()), dst,
        Paint()..blendMode = BlendMode.dstIn);
    canvas.restore();
  }

  @override
  bool shouldRepaint(_Painter old) => old.photo != photo || old.mask != mask;
}
