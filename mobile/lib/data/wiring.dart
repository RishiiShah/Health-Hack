// Builds AppServices from AppConfig (config.dart), including the mixed mode
// where some repositories are live and the rest are fake (LIVE_REPOS).
import 'api.dart';
import 'config.dart';
import 'fake/fakes.dart';
import 'feeds.dart';
import 'live/live.dart';
import 'platform/browser.dart';

const _repos = ['auth', 'offers', 'shifts', 'lead'];

AppServices buildServicesFromConfig() {
  switch (AppConfig.apiMode) {
    case 'fake':
      return FakeServices().services;
    case 'live':
      break;
    default:
      throw StateError('Unknown API_MODE "${AppConfig.apiMode}" (use fake or live)');
  }

  final base = Uri.parse(AppConfig.apiBaseUrl);
  final unknown = AppConfig.liveRepos == 'all'
      ? const <String>[]
      : AppConfig.liveRepos.split(',').where((r) => !_repos.contains(r.trim())).toList();
  if (unknown.isNotEmpty) {
    throw StateError('Unknown LIVE_REPOS entries $unknown (use ${_repos.join(',')} or all)');
  }
  if (_repos.every(AppConfig.isLive)) return LiveServices.create(base);
  if (!AppConfig.isLive('auth')) {
    // A fake session token means nothing to the backend.
    throw StateError('LIVE_REPOS must include auth whenever another repository is live');
  }
  return _mixed(base);
}

AppServices _mixed(Uri base) {
  final browser = sharedBrowser;
  final live = LiveServices.create(base, browser: browser);
  final fake = FakeServices(browser: browser, alerts: live.alerts);

  // Fake repositories act as whoever signed in on the real backend (the four
  // demo accounts share emails), so fake offers show for okafor@demo.sevaro etc.
  void follow() => fake.backend.user = live.auth.me.value?.userId;
  live.auth.me.addListener(follow);
  follow();

  final offers = AppConfig.isLive('offers') ? live.offers : fake.services.offers;
  final shifts = AppConfig.isLive('shifts') ? live.shifts : fake.services.shifts;
  final lead = AppConfig.isLive('lead') ? live.lead : fake.services.lead;

  final physicianFeed = PollingPhysicianFeed(offers, browser: browser);
  final leadFeed = PollingLeadFeed(lead, browser: browser);
  live.auth.signedOut.listen((_) {
    physicianFeed.stop();
    leadFeed.stop();
  });

  // Countdowns must use the same clock as the offers they count down: the
  // backend's server_now when offers or lead are live, else the fake demo clock.
  final clock = AppConfig.isLive('offers') || AppConfig.isLive('lead') ? live.clock : fake.clock;

  return AppServices(
    auth: live.auth,
    offers: offers,
    shifts: shifts,
    lead: lead,
    physicianFeed: physicianFeed,
    leadFeed: leadFeed,
    clock: clock,
    alerts: live.alerts,
    isFake: true,
  );
}
