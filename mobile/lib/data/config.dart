class AppConfig {
  static const apiMode = String.fromEnvironment('API_MODE', defaultValue: 'fake');   // fake | live
  static const apiBaseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://localhost:8000');
  static const liveRepos = String.fromEnvironment('LIVE_REPOS', defaultValue: 'all'); // e.g. "auth,offers"

  static bool isLive(String repo) =>
      apiMode == 'live' && (liveRepos == 'all' || liveRepos.split(',').contains(repo));
}
