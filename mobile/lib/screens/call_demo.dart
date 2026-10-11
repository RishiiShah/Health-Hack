import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../data/api.dart';
import '../data/fake/fakes.dart';
import 'incoming_call_screen.dart';
import 'shared.dart';

/// Dummy mode: rings the coverage call for the fake backend's sent offer, as
/// the web demo does once the lead has approved. Answer speaks the recording.
void openCallDemo(BuildContext context) {
  final fake = FakeServices(autoAnswer: false);
  fake.services.alerts.enableSound();
  Navigator.of(context).push(
    MaterialPageRoute<void>(
      fullscreenDialog: true,
      builder: (_) => _CallDemo(fake: fake),
    ),
  );
}

class _CallDemo extends StatefulWidget {
  const _CallDemo({required this.fake});
  final FakeServices fake;
  @override
  State<_CallDemo> createState() => _CallDemoState();
}

class _CallDemoState extends State<_CallDemo> {
  Offer? _offer;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final fake = widget.fake;
    // The fake has no text-to-speech; this is the backend's ElevenLabs voice,
    // recorded once for the fake's sent offer, so Answer speaks.
    final audio = await rootBundle.load('assets/offer_call.mp3');
    fake.offers.audio = audio.buffer.asUint8List();
    await fake.signInAs('okafor');
    final offers = await fake.offers.listOffers();
    final sent = offers.offers.where((o) => o.status == OfferStatus.sent);
    if (mounted) setState(() => _offer = sent.firstOrNull);
  }

  @override
  void dispose() {
    widget.fake.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final offer = _offer;
    if (offer == null) return const LoadingScreen();
    return IncomingCallScreen(services: widget.fake.services, offer: offer);
  }
}
