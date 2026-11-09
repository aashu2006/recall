#!/usr/bin/env bash
# Render the demo video slides to 1920x1080 PNGs with headless Chrome.
#   docs/slides/render.sh
# Needs Google Chrome and internet for the IBM Plex fonts (Google Fonts).
set -euo pipefail

cd "$(dirname "$0")"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"

for name in title eval; do
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
    --window-size=1920,1080 --virtual-time-budget=10000 \
    --screenshot="$PWD/$name.png" "file://$PWD/$name.html" 2>/dev/null
  echo "wrote docs/slides/$name.png"
done
