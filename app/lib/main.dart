import 'package:flutter/material.dart';

import 'src/auth.dart';
import 'src/engine_client.dart';
import 'src/screens/chat_screen.dart';
import 'src/screens/frame_screen.dart';
import 'src/screens/photo_screen.dart';
import 'src/screens/settings_screen.dart';
import 'src/screens/trips_screen.dart';
import 'src/settings.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final settings = await AppSettings.load();
  final auth = FamilyAuth();
  await auth.init(serverClientId: settings.googleServerClientId);
  runApp(TshulaiApp(settings: settings, auth: auth));
}

class TshulaiApp extends StatelessWidget {
  const TshulaiApp({super.key, required this.settings, required this.auth});
  final AppSettings settings;
  final FamilyAuth auth;

  @override
  Widget build(BuildContext context) {
    ThemeData theme(Brightness b) => ThemeData(
          colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFFB5652B), brightness: b),
          useMaterial3: true,
          textTheme: Typography.material2021().black.apply(fontSizeFactor: 1.1),
        );
    return MaterialApp(
      title: '厝內',
      debugShowCheckedModeBanner: false,
      theme: theme(Brightness.light),
      darkTheme: theme(Brightness.dark).copyWith(textTheme: Typography.material2021().white.apply(fontSizeFactor: 1.1)),
      home: Home(settings: settings, auth: auth),
    );
  }
}

class Home extends StatefulWidget {
  const Home({super.key, required this.settings, required this.auth});
  final AppSettings settings;
  final FamilyAuth auth;

  @override
  State<Home> createState() => _HomeState();
}

class _HomeState extends State<Home> {
  late final client = EngineClient(widget.settings, widget.auth);
  int _tab = 0;

  @override
  Widget build(BuildContext context) {
    if (widget.settings.frameMode) {
      return FrameScreen(
        client: client,
        onExit: () => setState(() => widget.settings.frameMode = false),
      );
    }
    final pages = [
      ChatScreen(key: ValueKey(widget.auth.idToken), client: client, settings: widget.settings),
      // 合照只在切到這頁時才建立：避免一開 app 就要相機權限、阿嬤誤以為你在拍照
      _tab == 1 ? PhotoScreen(client: client) : const SizedBox.shrink(),
      TripsScreen(client: client),
      SettingsScreen(settings: widget.settings, auth: widget.auth, client: client, onFrameMode: () => setState(() {})),
    ];
    return ListenableBuilder(
      listenable: widget.auth,
      builder: (context, _) => Scaffold(
        body: IndexedStack(index: _tab, children: pages),
        bottomNavigationBar: NavigationBar(
          selectedIndex: _tab,
          onDestinationSelected: (i) => setState(() => _tab = i),
          destinations: const [
            NavigationDestination(icon: Icon(Icons.chat_bubble_outline), label: '阿嬤'),
            NavigationDestination(icon: Icon(Icons.photo_camera_outlined), label: '合照'),
            NavigationDestination(icon: Icon(Icons.map_outlined), label: '去佗位'),
            NavigationDestination(icon: Icon(Icons.settings_outlined), label: '設定'),
          ],
        ),
      ),
    );
  }
}
