import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../engine_client.dart';

String agoTaigi(DateTime d) {
  final days = DateTime.now().difference(d).inDays;
  if (days <= 0) return '今仔日';
  if (days == 1) return '昨昏';
  if (days < 7) return '$days 工前';
  if (days < 14) return '頂禮拜';
  return '${d.month} 月 ${d.day} 日';
}

/// 我最近去哪玩：傳照片給阿嬤看。照片也可以直接丟進共享 Drive 的 trips 資料夾。
class TripsScreen extends StatefulWidget {
  const TripsScreen({super.key, required this.client});
  final EngineClient client;

  @override
  State<TripsScreen> createState() => _TripsScreenState();
}

class _TripsScreenState extends State<TripsScreen> {
  late Future<List<Trip>> _trips = widget.client.trips();
  bool _uploading = false;

  Future<void> _upload() async {
    final files = await ImagePicker().pickMultiImage(requestFullMetadata: true);
    if (files.isEmpty) return;
    setState(() => _uploading = true);
    try {
      final n = await widget.client.uploadTripPhotos([
        for (final f in files) (name: f.name, bytes: await f.readAsBytes()),
      ]);
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('傳了 $n 張，阿嬤會看到')));
      setState(() => _trips = widget.client.trips());
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      setState(() => _uploading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('予阿嬤看我去佗位𨑨迌')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _uploading ? null : _upload,
        icon: _uploading ? const SizedBox.square(dimension: 20, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.add_photo_alternate),
        label: const Text('傳相片'),
      ),
      body: RefreshIndicator(
        onRefresh: () async => setState(() => _trips = widget.client.trips()),
        child: FutureBuilder<List<Trip>>(
          future: _trips,
          builder: (context, snap) {
            if (snap.hasError) return ListView(children: [Padding(padding: const EdgeInsets.all(24), child: Text('${snap.error}'))]);
            if (!snap.hasData) return const Center(child: CircularProgressIndicator());
            final trips = snap.data!;
            if (trips.isEmpty) {
              return ListView(children: const [
                Padding(
                  padding: EdgeInsets.all(24),
                  child: Text('還沒有旅行。按「傳相片」，或把照片丟進共享 Drive 的 trips 資料夾。\n'
                      '照片要開定位拍，阿嬤才知道你去哪。', style: TextStyle(fontSize: 16, height: 1.5)),
                ),
              ]);
            }
            return ListView.builder(
              padding: const EdgeInsets.fromLTRB(12, 12, 12, 96),
              itemCount: trips.length,
              itemBuilder: (_, i) {
                final t = trips[i];
                return Card(
                  clipBehavior: Clip.antiAlias,
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    SizedBox(
                      height: 160,
                      child: ListView(scrollDirection: Axis.horizontal, children: [
                        for (final p in t.photos.take(10))
                          Padding(
                            padding: const EdgeInsets.only(right: 2),
                            child: Image.network(widget.client.mediaUrl(p), headers: widget.client.headers,
                                height: 160, fit: BoxFit.cover,
                                errorBuilder: (_, _, _) => const SizedBox(width: 120, child: Icon(Icons.broken_image))),
                          ),
                      ]),
                    ),
                    ListTile(
                      title: Text(t.title, style: const TextStyle(fontSize: 18)),
                      subtitle: Text('${agoTaigi(t.start)} · ${t.photos.length} 張'),
                    ),
                  ]),
                );
              },
            );
          },
        ),
      ),
    );
  }
}
