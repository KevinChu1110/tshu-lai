import 'dart:io';

import 'package:path_provider/path_provider.dart';

Future<List<int>> readFileBytes(String path) => File(path).readAsBytes();

/// 存到 app 文件資料夾，回傳路徑。
Future<String> saveBytes(String name, List<int> bytes) async {
  final dir = await getApplicationDocumentsDirectory();
  final f = File('${dir.path}/$name');
  await f.writeAsBytes(bytes);
  return f.path;
}
