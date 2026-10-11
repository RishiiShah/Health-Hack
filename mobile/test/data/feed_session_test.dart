import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:sevaro_mobile/data/api.dart';
import 'package:sevaro_mobile/data/fake/fake_samples.g.dart';
import 'package:sevaro_mobile/data/feeds.dart';
import 'package:sevaro_mobile/data/platform/browser.dart';

class DeferredOffers implements OfferRepository {
  final requests = <Completer<OfferList>>[];
  @override
  Future<OfferList> listOffers() {
    final request = Completer<OfferList>();
    requests.add(request);
    return request.future;
  }

  @override
  Future<NotificationList> notifications() async =>
      NotificationList(items: const [], serverNow: DateTime.utc(2026));
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class DeferredLead implements LeadRepository {
  final requests = <Completer<LeadQueue>>[];
  @override
  Future<LeadQueue> queue() {
    final request = Completer<LeadQueue>();
    requests.add(request);
    return request.future;
  }

  @override
  Future<BroadcastList> activeOffers() async =>
      BroadcastList.parse(jsonDecode(kSamples['mobile_lead_offers.json']!));
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  test('physician restart discards previous session response', () async {
    final repo = DeferredOffers();
    final feed = PollingPhysicianFeed(repo, browser: MemoryBrowser());
    addTearDown(feed.stop);
    final old = OfferList.parse(jsonDecode(kSamples['mobile_offers.json']!));
    final current = OfferList(offers: const [], serverNow: old.serverNow);
    feed.start();
    feed.stop();
    feed.start();
    final refresh = feed.refreshNow();
    expect(repo.requests, hasLength(2));
    repo.requests[1].complete(current);
    await refresh;
    repo.requests[0].complete(old);
    await Future<void>.delayed(Duration.zero);
    expect(feed.offers.value.data, same(current));
  });

  test('lead restart discards previous session response', () async {
    final repo = DeferredLead();
    final feed = PollingLeadFeed(repo, browser: MemoryBrowser());
    addTearDown(feed.stop);
    final old = LeadQueue.parse(
      jsonDecode(kSamples['mobile_lead_queue.json']!),
    );
    final current = LeadQueue(
      pendingCount: 0,
      proposals: const [],
      escalations: const [],
      automatedActions: const [],
      serverNow: old.serverNow,
    );
    feed.start();
    feed.stop();
    feed.start();
    final refresh = feed.refreshNow();
    expect(repo.requests, hasLength(2));
    repo.requests[1].complete(current);
    await refresh;
    repo.requests[0].complete(old);
    await Future<void>.delayed(Duration.zero);
    expect(feed.queue.value.data, same(current));
  });

  test('a feed started in a hidden tab waits until visible', () async {
    final browser = MemoryBrowser()..hidden = true;
    final repo = DeferredOffers();
    final feed = PollingPhysicianFeed(repo, browser: browser);
    addTearDown(feed.stop);
    feed.start();
    await feed.refreshNow();
    expect(repo.requests, isEmpty);
    browser.hidden = false;
    await Future<void>.delayed(Duration.zero);
    expect(repo.requests, hasLength(1));
    repo.requests.single.complete(
      OfferList(offers: const [], serverNow: DateTime.utc(2026)),
    );
    await feed.refreshNow();
  });
}
