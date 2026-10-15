import 'dart:ui' as ui;

import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:image_picker/image_picker.dart';

import '../engine_client.dart';
import '../io_helper.dart';
import '../segmentation/people_layer.dart';
import '../segmentation/segmentation.dart';

/// 阿嬤在畫面上的位置，用比例存，預覽和拍好的照片共用。
class _Placement {
  double cx = 0.5; // 中心 x（0..1）
  double bottom = 0.98; // 腳底 y（0..1）
  double height = 0.62; // 佔畫面高度比例

  void preset(String pos, Pose pose) {
    final sitting = pose.tags.contains('sit');
    height = sitting ? 0.48 : 0.62;
    bottom = 0.98;
    cx = switch (pos) { 'left' => 0.16, 'right' => 0.84, _ => 0.5 };
  }

  String get position => cx < 0.33 ? 'left' : (cx > 0.67 ? 'right' : 'center');
}

/// 合照：坐中間或站邊邊。快版在手機上直接疊；好版送回家用主機重畫光影。
class PhotoScreen extends StatefulWidget {
  const PhotoScreen({super.key, required this.client});
  final EngineClient client;

  @override
  State<PhotoScreen> createState() => _PhotoScreenState();
}

class _PhotoScreenState extends State<PhotoScreen> {
  final _boundary = GlobalKey();
  final _place = _Placement();
  List<Pose> _poses = [];
  Pose? _pose;
  String? _error;
  CameraController? _cam;
  Uint8List? _photo;
  Uint8List? _good;
  bool _busy = false;
  double _scaleStart = 1;
  ui.Image? _peopleMask;
  bool _behind = false; // 阿嬤徛佇大家後壁

  @override
  void initState() {
    super.initState();
    _loadPoses();
    _initCamera();
    widget.client.postEvent('camera.opened').catchError((_) {});
  }

  Future<void> _loadPoses() async {
    try {
      final p = await widget.client.poses();
      setState(() {
        _poses = p;
        _pose = p.isEmpty ? null : p.first;
        if (p.isEmpty) _error = '姿勢庫還是空的：先把阿嬤的全身照放進 photo/pose，在引擎跑 tshulai-engine poses';
      });
    } catch (e) {
      setState(() => _error = '$e');
    }
  }

  Future<void> _initCamera() async {
    try {
      final cams = await availableCameras();
      if (cams.isEmpty) return;
      final back = cams.firstWhere((c) => c.lensDirection == CameraLensDirection.back, orElse: () => cams.first);
      final c = CameraController(back, ResolutionPreset.high, enableAudio: false);
      await c.initialize();
      if (mounted) setState(() => _cam = c);
    } catch (_) {
      // 桌面或沒有相機：用相簿選照片
    }
  }

  @override
  void dispose() {
    _cam?.dispose();
    widget.client.postEvent('camera.closed').catchError((_) {});
    super.dispose();
  }

  Future<void> _shoot() async {
    final c = _cam;
    if (c == null) return _pick();
    final f = await c.takePicture();
    final bytes = await f.readAsBytes();
    setState(() => _photo = bytes);
    _segment(bytes);
  }

  Future<void> _segment(Uint8List bytes) async {
    _peopleMask = null;
    if (!PeopleMask.supported) return;
    try {
      final m = await PeopleMask.of(bytes);
      if (mounted && identical(bytes, _photo)) setState(() => _peopleMask = m);
    } catch (_) {}
  }

  Future<void> _pick() async {
    final f = await ImagePicker().pickImage(source: ImageSource.gallery);
    if (f == null) return;
    final bytes = await f.readAsBytes();
    setState(() {
      _photo = bytes;
      _good = null;
    });
    _segment(bytes);
  }

  Future<Uint8List> _renderQuick() async {
    final b = _boundary.currentContext!.findRenderObject()! as RenderRepaintBoundary;
    final img = await b.toImage(pixelRatio: 3);
    final data = await img.toByteData(format: ui.ImageByteFormat.png);
    return data!.buffer.asUint8List();
  }

  Future<void> _saveQuick() async {
    setState(() => _busy = true);
    try {
      final png = await _renderQuick();
      final msg = kIsWeb ? '網頁版請長按畫面另存' : '已存：${await saveBytes('合照_${DateTime.now().millisecondsSinceEpoch}.png', png)}';
      _toast(msg);
    } catch (e) {
      _toast('$e');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _requestGood() async {
    if (_photo == null || _pose == null) return;
    setState(() => _busy = true);
    try {
      final out = await widget.client.compositeGood(_photo!, _pose!.png, _place.position);
      setState(() => _good = Uint8List.fromList(out));
      if (!kIsWeb) _toast('已存：${await saveBytes('合照好版_${DateTime.now().millisecondsSinceEpoch}.jpg', out)}');
    } catch (e) {
      _toast('$e');
    } finally {
      setState(() => _busy = false);
    }
  }

  void _toast(String s) {
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(s)));
  }

  Widget _overlay(BoxConstraints box) {
    final pose = _pose;
    if (pose == null) return const SizedBox.shrink();
    final h = box.maxHeight * _place.height;
    final w = h * pose.aspect;
    return Positioned(
      left: box.maxWidth * _place.cx - w / 2,
      top: box.maxHeight * _place.bottom - h,
      width: w,
      height: h,
      child: GestureDetector(
        onScaleStart: (_) => _scaleStart = _place.height,
        onScaleUpdate: (d) => setState(() {
          _place.cx = (_place.cx + d.focalPointDelta.dx / box.maxWidth).clamp(0.0, 1.0);
          _place.bottom = (_place.bottom + d.focalPointDelta.dy / box.maxHeight).clamp(0.2, 1.2);
          _place.height = (_scaleStart * d.scale).clamp(0.15, 1.2);
        }),
        child: Image.network(widget.client.poseUrl(pose), headers: widget.client.headers, fit: BoxFit.contain),
      ),
    );
  }

  Widget _canvas() {
    final base = _photo != null
        ? Image.memory(_photo!, fit: BoxFit.contain)
        : (_cam != null ? CameraPreview(_cam!) : const Center(child: Text('按下面的相簿選一張照片')));
    return RepaintBoundary(
      key: _boundary,
      child: AspectRatio(
        aspectRatio: _cam != null && _photo == null ? 1 / _cam!.value.aspectRatio : 3 / 4,
        child: LayoutBuilder(
          builder: (_, box) => Stack(fit: StackFit.expand, children: [
            ColoredBox(color: Colors.black, child: base),
            _overlay(box),
            if (_behind && _photo != null && _peopleMask != null)
              IgnorePointer(child: PeopleLayer(photo: _photo!, mask: _peopleMask!)),
            const Positioned(
              right: 8,
              bottom: 6,
              child: Text('AI 合成 · 厝內', style: TextStyle(color: Colors.white70, fontSize: 11)),
            ),
          ]),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('佮阿嬤翕相')),
      body: ListView(padding: const EdgeInsets.all(12), children: [
        if (_error != null) Card(child: Padding(padding: const EdgeInsets.all(12), child: Text(_error!))),
        if (_good != null) ...[
          const Text('好版（家用主機重畫光影）', style: TextStyle(fontWeight: FontWeight.bold)),
          Image.memory(_good!),
          const SizedBox(height: 12),
        ],
        Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 520), child: _canvas())),
        const SizedBox(height: 12),
        SegmentedButton<String>(
          segments: const [
            ButtonSegment(value: 'left', label: Text('站倒爿')),
            ButtonSegment(value: 'center', label: Text('坐中央')),
            ButtonSegment(value: 'right', label: Text('站正爿')),
          ],
          selected: {_place.position},
          onSelectionChanged: _pose == null ? null : (s) => setState(() => _place.preset(s.first, _pose!)),
        ),
        if (_peopleMask != null)
          SwitchListTile(
            title: const Text('阿嬤徛佇大家後壁'),
            subtitle: const Text('照片裡的人會擋在阿嬤前面'),
            value: _behind,
            onChanged: (v) => setState(() => _behind = v),
          ),
        if (_poses.length > 1)
          SizedBox(
            height: 88,
            child: ListView(scrollDirection: Axis.horizontal, children: [
              for (final p in _poses)
                GestureDetector(
                  onTap: () => setState(() => _pose = p),
                  child: Container(
                    margin: const EdgeInsets.all(4),
                    decoration: BoxDecoration(
                      border: Border.all(color: p == _pose ? Theme.of(context).colorScheme.primary : Colors.transparent, width: 3),
                    ),
                    child: Image.network(widget.client.poseUrl(p), headers: widget.client.headers, height: 76),
                  ),
                ),
            ]),
          ),
        const SizedBox(height: 12),
        Wrap(spacing: 8, runSpacing: 8, alignment: WrapAlignment.center, children: [
          if (_photo == null)
            FilledButton.icon(onPressed: _shoot, icon: const Icon(Icons.camera), label: Text(_cam != null ? '翕' : '選相片')),
          OutlinedButton.icon(onPressed: _pick, icon: const Icon(Icons.photo_library), label: const Text('相簿')),
          if (_photo != null) ...[
            FilledButton.icon(onPressed: _busy ? null : _saveQuick, icon: const Icon(Icons.save), label: const Text('存快版')),
            FilledButton.tonalIcon(onPressed: _busy ? null : _requestGood, icon: const Icon(Icons.auto_awesome), label: const Text('做好版')),
            TextButton(onPressed: () => setState(() { _photo = null; _good = null; }), child: const Text('重翕')),
          ],
        ]),
        if (_busy) const Padding(padding: EdgeInsets.all(16), child: Center(child: CircularProgressIndicator())),
      ]),
    );
  }
}
