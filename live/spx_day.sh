#!/bin/zsh
# wait for US market hours, then log KXINX-vs-SPX-options snapshots every 5 min until 20:15 UTC (read-only)
cd "$(dirname "$0")"
until [[ "$(date -u +%H%M)" > "1344" && "$(date -u +%H%M)" < "2015" ]]; do sleep 60; done
REQUESTS_CA_BUNDLE=$SSL_CERT_FILE /private/tmp/claude-501/-Users-pupton/52c5af81-35ec-4050-ab80-5f7e86eb3176/scratchpad/pypi03/bin/python spxscan.py --every 300 --until 20:15
