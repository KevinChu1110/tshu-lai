import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';

import 'auth.dart';
import 'settings.dart';

class Trip {
  Trip.fromJson(Map<String, dynamic> j)
      : who = j['who'] as String?,
        start = DateTime.parse(j['start'] as String),
        end = DateTime.parse(j['end'] as String),
        title = j['title'] as String,
        places = (j['places'] as List).cast<String>(),
        photos = (j['photos'] as List).cast<String>();

  final String? who;
  final DateTime start;
  final DateTime end;
  final String title;
  final List<String> places;
  final List<String> photos;
}

class Pose {
  Pose.fromJson(Map<String, dynamic> j)
      : source = j['source'] as String,
        png = j['png'] as String,
        tags = (j['tags'] as List).cast<String>(),
        aspect = (j['w'] as num) / (j['h'] as num);

  final String source;
  final String png;
  final List<String> tags;
  final double aspect;
}

class EngineException implements Exception {
  EngineException(this.status, this.message);
  final int status;
  final String message;
  @override
  String toString() => status == 401 ? '請先用 Google 帳號登入（$message）' : '引擎回應 $status：$message';
}

/// 跟家用主機的引擎講話。HTTP 帶 Google ID token；看板模式改帶 frame key。
class EngineClient {
  EngineClient(this.settings, this.auth);

  final AppSettings settings;
  final FamilyAuth auth;

  Uri uri(String path, [Map<String, String>? q]) {
    final base = Uri.parse(settings.engineUrl);
    return base.replace(path: path, queryParameters: q);
  }

  Map<String, String> get headers =>
      {if (auth.idToken != null) 'Authorization': 'Bearer ${auth.idToken}'};

  /// 圖片與音檔網址。看板模式用 key，其他用 header（Image.network 帶 headers）。
  String mediaUrl(String rel, {bool frame = false}) {
    final path = '/media/${rel.split('/').map(Uri.encodeComponent).join('/')}';
    return uri(path, frame ? {'key': settings.frameKey} : null).toString();
  }

  String absolute(String path) => uri(path).toString();

  Future<dynamic> _get(String path, [Map<String, String>? q]) async {
    final r = await http.get(uri(path, q), headers: headers).timeout(const Duration(seconds: 15));
    if (r.statusCode != 200) throw EngineException(r.statusCode, _detail(r.body));
    return jsonDecode(utf8.decode(r.bodyBytes));
  }

  String _detail(String body) {
    try {
      return (jsonDecode(body) as Map)['detail'].toString();
    } catch (_) {
      return body;
    }
  }

  Future<Map<String, dynamic>> health() async => (await _get('/health')) as Map<String, dynamic>;
  Future<Map<String, dynamic>> me() async => (await _get('/me')) as Map<String, dynamic>;

  Future<List<Trip>> trips({bool frame = false}) async {
    final list = await _get('/trips', {'n': '20', if (frame) 'key': settings.frameKey}) as List;
    return list.map((e) => Trip.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<List<Pose>> poses() async {
    final list = await _get('/poses') as List;
    return list.map((e) => Pose.fromJson(e as Map<String, dynamic>)).toList();
  }

  String poseUrl(Pose p) => uri('/poses/${Uri.encodeComponent(p.png)}').toString();

  Future<int> uploadTripPhotos(List<({String name, List<int> bytes})> files) async {
    final req = http.MultipartRequest('POST', uri('/trips/upload'))..headers.addAll(headers);
    for (final f in files) {
      req.files.add(http.MultipartFile.fromBytes('files', f.bytes, filename: f.name));
    }
    final r = await http.Response.fromStream(await req.send());
    if (r.statusCode != 200) throw EngineException(r.statusCode, _detail(r.body));
    return ((jsonDecode(utf8.decode(r.bodyBytes)) as Map)['saved'] as List).length;
  }

  Future<List<int>> compositeGood(List<int> photo, String pose, String position) async {
    final req = http.MultipartRequest('POST', uri('/photo/composite'))
      ..headers.addAll(headers)
      ..fields['pose'] = pose
      ..fields['position'] = position
      ..files.add(http.MultipartFile.fromBytes('photo', photo, filename: 'photo.jpg'));
    final r = await http.Response.fromStream(await req.send());
    if (r.statusCode != 200) throw EngineException(r.statusCode, _detail(r.body));
    return r.bodyBytes;
  }

  Future<String> stt(List<int> wav) async {
    final req = http.MultipartRequest('POST', uri('/stt'))
      ..headers.addAll(headers)
      ..files.add(http.MultipartFile.fromBytes('audio', wav, filename: 'say.wav'));
    final r = await http.Response.fromStream(await req.send());
    if (r.statusCode != 200) throw EngineException(r.statusCode, _detail(r.body));
    return (jsonDecode(utf8.decode(r.bodyBytes)) as Map)['text'] as String;
  }

  Future<void> postEvent(String name) async {
    await http.post(uri('/events'), headers: {...headers, 'Content-Type': 'application/json'},
        body: jsonEncode({'name': name}));
  }

  Future<void> markFuturePlayed(int id) async {
    await http.post(uri('/future/$id/played'), headers: headers);
  }

  ChatConnection connect() {
    final base = Uri.parse(settings.engineUrl);
    final ws = base.replace(scheme: base.scheme == 'https' ? 'wss' : 'ws', path: '/ws');
    final conn = ChatConnection(WebSocketChannel.connect(ws));
    // 登入憑證放第一則訊息，不放網址（網址會留在伺服器紀錄）
    conn._send({'type': 'auth', 'token': auth.idToken});
    return conn;
  }
}

class ChatConnection {
  ChatConnection(this.channel)
      : messages = channel.stream
            .map((e) => jsonDecode(e as String) as Map<String, dynamic>)
            .asBroadcastStream() {
    // 連不上（引擎沒開、還沒登入）時錯誤會走 stream 的 onError；這裡吃掉 ready 的錯，避免變成未處理例外
    channel.ready.catchError((Object _) {});
  }

  final WebSocketChannel channel;
  final Stream<Map<String, dynamic>> messages;

  void say(String text) => _send({'type': 'say', 'text': text});
  void event(String name) => _send({'type': 'event', 'name': name});
  void voice(bool on) => _send({'type': 'voice', 'tts': on});
  void _send(Map<String, dynamic> m) => channel.sink.add(jsonEncode(m));
  Future<void> close() => channel.sink.close();
}
