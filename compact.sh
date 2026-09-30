#!/usr/bin/env bash
# Run inside a checkout of the data branch: every finished day (before today, UTC) becomes a release asset
# data-YYYY-MM-DD.tar and is removed from the working tree.  Prints "compacted" if anything was packed.
set -euo pipefail
today=$(date -u +%F)
days=$( (ls -d */????-??-?? 2>/dev/null | xargs -n1 basename; ls log 2>/dev/null | sed 's/\.log$//') | sort -u | awk -v t="$today" '$0 < t')
for d in $days; do
  tar cf "data-$d.tar" $(ls -d */"$d" log/"$d".log 2>/dev/null)
  gh release view "data-$d" >/dev/null 2>&1 || gh release create "data-$d" --title "data $d" --notes "Recorded prices for $d (UTC)" --target main
  gh release upload "data-$d" "data-$d.tar" --clobber
  rm -rf */"$d" log/"$d".log "data-$d.tar"
  echo compacted
done
