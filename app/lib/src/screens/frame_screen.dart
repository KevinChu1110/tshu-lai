import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../engine_client.dart';
import 'trips_screen.dart' show agoTaigi;

/// 阿嬤看板：放在阿嬤家的平板，全螢幕大字輪播孫子們最近去玩的照片。零操作。
/// 長按右上角 3 秒離開（避免阿嬤不小心按掉）。
class FrameScreen extends StatefulWidget {
  const FrameScreen({super.key, required this.client, required this.onExit});
  final EngineClient client;
  final VoidCallback onExit;

  @override
  State<FrameScreen> createState() => _FrameScreenState();
}

class _FrameScreenState extends State<FrameScreen> {
  final _slides = <({String url, Trip trip})>[];
  int _i = 0;
  Timer? _next, _reload, _clock;
  DateTime _now = DateTime.now();
  String? _error;

  @override
  void initState() {
    super.initState();
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
    _load();
    _reload = Timer.periodic(const Duration(minutes: 10), (_) => _load());
    _next = Timer.periodic(const Duration(seconds: 12), (_) {
      if (_slides.isNotEmpty) setState(() => _i = (_i + 1) % _slides.length);
    });
    _clock = Timer.periodic(const Duration(seconds: 20), (_) => setState(() => _now = DateTime.now()));
  }

  Future<void> _load() async {
    try {
      final trips = await widget.client.trips(frame: true);
      setState(() {
        _error = null;
        _slides
          ..clear()
          ..addAll([
            for (final t in trips)
              for (final p in t.photos.take(8)) (url: widget.client.mediaUrl(p, frame: true), trip: t),
          ]);
        if (_i >= _slides.length) _i = 0;
      });
    } catch (e) {
      setState(() => _error = '$e');
    }
  }

  @override
  void dispose() {
    _next?.cancel();
    _reload?.cancel();
    _clock?.cancel();
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    super.dispose();
  }

  static const _week = ['一', '二', '三', '四', '五', '六', '日'];

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.sizeOf(context);
    final big = (size.width / 12).clamp(36.0, 110.0);
    final s = _slides.isEmpty ? null : _slides[_i];
    final t = s?.trip;
    final where = t == null ? '' : (t.places.take(2).join('、').isEmpty ? '外口' : t.places.take(2).join('、'));
    return Scaffold(
      backgroundColor: const Color(0xFF1B1712),
      body: Stack(fit: StackFit.expand, children: [
        if (s != null)
          AnimatedSwitcher(
            duration: const Duration(milliseconds: 1600),
            child: Image.network(s.url, key: ValueKey(s.url), fit: BoxFit.contain, width: size.width, height: size.height),
          )
        else
          Center(
            child: Text(_error == null ? '孫仔猶未傳相片來\n等一下就有矣' : '看板連袂著\n$_error',
                textAlign: TextAlign.center, style: TextStyle(color: Colors.white, fontSize: big * 0.6, height: 1.5)),
          ),
        if (t != null)
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            child: Container(
              padding: EdgeInsets.fromLTRB(size.width * .05, 48, size.width * .05, 40),
              decoration: const BoxDecoration(
                gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter,
                    colors: [Colors.transparent, Color(0xDD000000)]),
              ),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
                Text.rich(
                  TextSpan(children: [
                    TextSpan(text: '${t.who ?? '孫仔'} 去 '),
                    TextSpan(text: where, style: const TextStyle(color: Color(0xFFF3B562))),
                  ]),
                  style: TextStyle(color: Colors.white, fontSize: big, fontWeight: FontWeight.w800, height: 1.1),
                ),
                const SizedBox(height: 8),
                Text(agoTaigi(t.start), style: TextStyle(color: const Color(0xFFE6D8BF), fontSize: big * .5)),
              ]),
            ),
          ),
        Positioned(
          top: 24,
          right: 32,
          child: GestureDetector(
            onLongPress: widget.onExit,
            child: Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
              Text('${_now.hour}:${_now.minute.toString().padLeft(2, '0')}',
                  style: TextStyle(color: Colors.white, fontSize: big * .8, fontWeight: FontWeight.w700,
                      shadows: const [Shadow(blurRadius: 12)])),
              Text('${_now.month} 月 ${_now.day} 日 禮拜${_week[_now.weekday - 1]}',
                  style: TextStyle(color: const Color(0xFFE6D8BF), fontSize: big * .4, shadows: const [Shadow(blurRadius: 12)])),
            ]),
          ),
        ),
      ]),
    );
  }
}
