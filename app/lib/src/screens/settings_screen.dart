import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../auth.dart';
import '../engine_client.dart';
import '../presence/presence.dart';
import '../settings.dart';
import '../web_sign_in_button.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key, required this.settings, required this.auth, required this.client, required this.onFrameMode});
  final AppSettings settings;
  final FamilyAuth auth;
  final EngineClient client;
  final VoidCallback onFrameMode;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final _url = TextEditingController(text: widget.settings.engineUrl);
  late final _clientId = TextEditingController(text: widget.settings.googleServerClientId);
  late final _frameKey = TextEditingController(text: widget.settings.frameKey);
  String _status = '';

  Future<void> _test() async {
    widget.settings.engineUrl = _url.text;
    setState(() => _status = '測試中…');
    try {
      final h = await widget.client.health();
      setState(() => _status = '連到了：${h['persona']}，LLM ${h['llm']}，語音 ${h['tts']}，Drive ${h['drive'] ? '開' : '關'}');
    } catch (e) {
      setState(() => _status = '連不到：$e');
    }
  }

  Future<void> _registerHome() async {
    try {
      final me = await widget.client.me();
      final home = me['home'] as Map<String, dynamic>?;
      if (home == null) return setState(() => _status = '人格卡沒有填阿嬤家的座標（home）');
      if ((me['frame_key'] as String?)?.isNotEmpty ?? false) {
        widget.settings.frameKey = _frameKey.text = me['frame_key'] as String;
      }
      final err = await Presence.registerHome((home['lat'] as num).toDouble(), (home['lng'] as num).toDouble(),
          radius: ((home['radius_m'] ?? 100) as num).toDouble());
      setState(() => _status = err ?? '好了：回到${home['label'] ?? '阿嬤家'}時阿嬤會知道');
    } catch (e) {
      setState(() => _status = '$e');
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = widget.auth;
    return Scaffold(
      appBar: AppBar(title: const Text('設定')),
      body: ListenableBuilder(
        listenable: Listenable.merge([widget.settings, auth]),
        builder: (context, _) => ListView(padding: const EdgeInsets.all(16), children: [
          const Text('家用主機', style: TextStyle(fontWeight: FontWeight.bold)),
          TextField(controller: _url, decoration: const InputDecoration(labelText: '引擎位址', hintText: 'http://100.x.x.x:8765')),
          const SizedBox(height: 8),
          Row(children: [FilledButton(onPressed: _test, child: const Text('測試連線'))]),
          const Divider(height: 32),
          const Text('家人身分（Google 帳號）', style: TextStyle(fontWeight: FontWeight.bold)),
          TextField(
            controller: _clientId,
            decoration: const InputDecoration(labelText: 'Google Web client ID（Android 需要）'),
            onChanged: (v) => widget.settings.googleServerClientId = v,
          ),
          const SizedBox(height: 8),
          if (auth.signedIn)
            ListTile(
              leading: const Icon(Icons.verified_user),
              title: Text(auth.account!.displayName ?? auth.account!.email),
              subtitle: Text(auth.account!.email),
              trailing: TextButton(onPressed: auth.signOut, child: const Text('登出')),
            )
          else if (auth.canSignInHere)
            FilledButton.icon(onPressed: auth.signIn, icon: const Icon(Icons.login), label: const Text('用 Google 登入'))
          else if (kIsWeb && auth.configured)
            Align(alignment: Alignment.centerLeft, child: webSignInButton())
          else
            const Text('這個平台還不能直接登入，引擎若關閉身分驗證仍可使用。'),
          if (auth.error != null) Text(auth.error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          const Divider(height: 32),
          const Text('回到阿嬤家', style: TextStyle(fontWeight: FontWeight.bold)),
          Text(Presence.supported ? '用阿嬤家的座標註冊背景定位，回家時阿嬤會打招呼。' : '背景定位只有手機 app 有。'),
          const SizedBox(height: 8),
          Row(children: [OutlinedButton(onPressed: Presence.supported ? _registerHome : null, child: const Text('註冊阿嬤家'))]),
          SwitchListTile(
            title: const Text('阿嬤講話時唸出來'),
            value: widget.settings.voiceReplies,
            onChanged: (v) => widget.settings.voiceReplies = v,
          ),
          const Divider(height: 32),
          const Text('阿嬤看板（放阿嬤家的平板）', style: TextStyle(fontWeight: FontWeight.bold)),
          TextField(
            controller: _frameKey,
            decoration: const InputDecoration(labelText: '看板鑰匙', helperText: '家人登入後按「註冊阿嬤家」會自動帶入，或從引擎的 data/frame_key.txt 抄'),
            onChanged: (v) => widget.settings.frameKey = v,
          ),
          const SizedBox(height: 8),
          Row(children: [
            FilledButton.tonal(
              onPressed: () {
                widget.settings.frameMode = true;
                widget.onFrameMode();
              },
              child: const Text('這台當阿嬤看板'),
            ),
          ]),
          const SizedBox(height: 4),
          const Text('看板開啟後長按右上角時鐘離開。不想裝 app 的平板也可以直接用瀏覽器開 <引擎位址>/frame?key=<看板鑰匙>。'),
          if (_status.isNotEmpty) ...[const Divider(height: 32), Text(_status)],
        ]),
      ),
    );
  }
}
