#!/usr/bin/env bash
# Build both web bundles from mobile/ (contract: live + fake backup).
#   1. Put the Render URL in config/live.json (API_BASE_URL).
#   2. tool/build_web.sh
#   3. Deploy each folder as its own Vercel project:
#        (cd build/web-live && vercel deploy --prod)
#        (cd build/web-fake && vercel deploy --prod)
# web/vercel.json is copied into each bundle (SPA rewrite to index.html).
set -euo pipefail
cd "$(dirname "$0")/.."

if grep -q REPLACE-WITH-RENDER-URL config/live.json; then
  echo "Set API_BASE_URL in config/live.json first." >&2
  exit 1
fi

flutter build web --release --dart-define-from-file=config/live.json
rm -rf build/web-live && cp -R build/web build/web-live

flutter build web --release --dart-define-from-file=config/fake.json
rm -rf build/web-fake && cp -R build/web build/web-fake

echo "Built build/web-live and build/web-fake."
echo "Send the live Vercel origin to the backend owner for CORS."
