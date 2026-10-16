import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:just_audio/just_audio.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

import '../engine_client.dart';
import '../io_helper.dart';
import '../settings.dart';
import '../sit_detector.dart';

class _Msg {
  _Msg(this.fromMe, this.text, {this.audioOne, this.future = false});
  final bool fromMe;
  String text;
  final bool future;
  final String? audioOne;
}

/// 像 LINE 一樣跟阿嬤講話。她講的每一句如果有語音就依序播。
class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key, required this.client, required this.settings});
  final EngineClient client;
  final AppSettings settings;

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _msgs = <_Msg>[];
  final _input = TextEditingController();
  final _scroll = ScrollController();
  final _player = AudioPlayer();
  final _queue = <String>[];
  final _recorder = AudioRecorder();
  ChatConnection? _conn;
  StreamSubscription? _sub;
  String _status = '連線中…';
  String? _sceneName;
  bool _recording = false;
  bool _playing = false;
  late final _sit = SitDetector(onSit: () => _conn?.event('motion.sit_down'));

  @override
  void initState() {
    super.initState();
    _connect();
    _player.playerStateStream.listen((s) {
      if (s.processingState == ProcessingState.completed) {
        _playing = false;
        _playNext();
      }
    });
  }

  void _connect() {
    _sub?.cancel();
    _conn?.close();
    _conn = null;
    if (widget.client.auth.configured && !widget.client.auth.signedIn) {
      setState(() => _status = '請先到「設定」用 Google 帳號登入');
      return;
    }
    try {
      final c = widget.client.connect();
      _conn = c;
      _sub = c.messages.listen(_onMessage, onError: (e) {
        setState(() => _status = '連不到引擎：$e');
      }, onDone: () {
        if (mounted) setState(() => _status = '斷線了，下拉重連');
      });
    } catch (e) {
      setState(() => _status = '連不到引擎：$e');
    }
  }

  void _onMessage(Map<String, dynamic> m) {
    switch (m['type']) {
      case 'hello':
        setState(() {
          _status = '';
          _sceneName = (m['scene'] as Map)['name'] as String;
        });
        _conn!.voice(widget.settings.voiceReplies);
        for (final e in widget.settings.takePendingEvents()) {
          _conn!.event(e);
        }
      case 'error':
        setState(() => _status = m['code'] == 401 ? '引擎不認得這個帳號：${m['message']}' : '${m['message']}');
      case 'scene':
        setState(() => _sceneName = m['name'] as String);
        // 進門之後才開始看你有沒有坐下來；換到別的情境就停
        if (m['id'] == 'homecoming' && !kIsWeb) {
          _sit.start();
        } else {
          _sit.stop();
        }
      case 'text':
        setState(() {
          if (_msgs.isEmpty || _msgs.last.fromMe || _msgs.last.future) {
            _msgs.add(_Msg(false, ''));
          }
          _msgs.last.text += m['delta'] as String;
        });
        _toBottom();
      case 'sentence':
        final a = m['audio'] as String?;
        if (a != null) {
          _queue.add(widget.client.absolute(a));
          _playNext();
        }
      case 'future':
        setState(() => _msgs.add(_Msg(false, '阿嬤有留一段話予你', audioOne: m['audio'] as String, future: true)));
        widget.client.markFuturePlayed(m['id'] as int);
    }
  }

  Future<void> _playNext() async {
    if (_playing || _queue.isEmpty) return;
    _playing = true;
    try {
      await _player.setUrl(_queue.removeAt(0), headers: kIsWeb ? null : widget.client.headers);
      await _player.play();
    } catch (_) {
      _playing = false;
      _playNext();
    }
  }

  void _send([String? text]) {
    final t = (text ?? _input.text).trim();
    if (t.isEmpty || _conn == null) return;
    setState(() => _msgs.add(_Msg(true, t)));
    _conn!.say(t);
    _input.clear();
    _toBottom();
  }

  void _toBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(_scroll.position.maxScrollExtent,
            duration: const Duration(milliseconds: 200), curve: Curves.easeOut);
      }
    });
  }

  Future<void> _holdStart() async {
    if (kIsWeb || !await _recorder.hasPermission()) return;
    final dir = await getTemporaryDirectory();
    await _recorder.start(const RecordConfig(encoder: AudioEncoder.wav, sampleRate: 16000, numChannels: 1),
        path: '${dir.path}/say.wav');
    setState(() => _recording = true);
  }

  Future<void> _holdEnd() async {
    if (!_recording) return;
    final path = await _recorder.stop();
    setState(() => _recording = false);
    if (path == null) return;
    try {
      final text = await widget.client.stt(await readFileBytes(path));
      _send(text);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    }
  }

  @override
  void dispose() {
    _sit.stop();
    _sub?.cancel();
    _conn?.close();
    _player.dispose();
    _recorder.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(
        title: const Text('阿嬤'),
        bottom: _sceneName == null
            ? null
            : PreferredSize(
                preferredSize: const Size.fromHeight(20),
                child: Text(_sceneName!, style: TextStyle(color: cs.onSurfaceVariant)),
              ),
        actions: [IconButton(onPressed: _connect, icon: const Icon(Icons.refresh), tooltip: '重新連線')],
      ),
      body: Column(children: [
        if (_status.isNotEmpty)
          MaterialBanner(content: Text(_status), actions: [TextButton(onPressed: _connect, child: const Text('重連'))]),
        Expanded(
          child: ListView.builder(
            controller: _scroll,
            padding: const EdgeInsets.all(12),
            itemCount: _msgs.length,
            itemBuilder: (_, i) => _bubble(_msgs[i], cs),
          ),
        ),
        SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(8, 4, 8, 8),
            child: Row(children: [
              if (!kIsWeb)
                GestureDetector(
                  onLongPressStart: (_) => _holdStart(),
                  onLongPressEnd: (_) => _holdEnd(),
                  child: CircleAvatar(
                    radius: 24,
                    backgroundColor: _recording ? cs.error : cs.primaryContainer,
                    child: Icon(_recording ? Icons.mic : Icons.mic_none, semanticLabel: '按住講話'),
                  ),
                ),
              const SizedBox(width: 8),
              Expanded(
                child: TextField(
                  controller: _input,
                  onSubmitted: (_) => _send(),
                  decoration: const InputDecoration(hintText: '共阿嬤講…', border: OutlineInputBorder()),
                ),
              ),
              IconButton.filled(onPressed: _send, icon: const Icon(Icons.send)),
            ]),
          ),
        ),
      ]),
    );
  }

  Widget _bubble(_Msg m, ColorScheme cs) {
    final align = m.fromMe ? Alignment.centerRight : Alignment.centerLeft;
    final color = m.future ? cs.tertiaryContainer : (m.fromMe ? cs.primaryContainer : cs.surfaceContainerHighest);
    return Align(
      alignment: align,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        constraints: const BoxConstraints(maxWidth: 480),
        decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(16)),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Flexible(child: Text(m.text, style: const TextStyle(fontSize: 18, height: 1.4))),
          if (m.audioOne != null)
            IconButton(
              icon: const Icon(Icons.play_circle),
              tooltip: '播放',
              onPressed: () {
                _queue.add(widget.client.absolute(m.audioOne!));
                _playNext();
              },
            ),
        ]),
      ),
    );
  }
}
