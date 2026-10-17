#!/usr/bin/env bash
# One ~5.4 h chunk of the lipcloud GitHub Actions twin for ONE program set (lipgen | lipalt).  Called by .github/workflows/lipcloud.yml.
# PAPER ONLY: recorder + paper bot, public GET endpoints only; no keys, no orders.  The only credential in scope is the workflow's own
# GITHUB_TOKEN (used by `gh api` to fetch the previous chunk's state artifact).
#   lipcloud_chunk.sh gen|alt SECONDS        env: TAG (default main), GH_TOKEN, GITHUB_REPOSITORY, PYTHON (default python)
# Layout (repo root):  out/   -> uploaded as the data artifact  (books/tape/meta dirs, paper jsonl, logs, draw copy)
#                      state/ -> uploaded as the state artifact (draw file + series-category cache + paper state), restored next chunk
set -u
kind=$1; secs=$2
TAG=${TAG:-main}; PY=${PYTHON:-python}
cd "$(dirname "$0")/.."
mkdir -p out state
sname="lipcloud-state-lip$kind-$TAG"
case $kind in
  gen) rec=lipgen_rec.py; draw_seed=live/lipgen_draw.jsonl; draw=state/lipgen_draw_cloud.jsonl ;;
  alt) rec=lipalt_rec.py; draw_seed=live/lipalt_draw.jsonl; draw=state/lipalt_draw_cloud.jsonl ;;
  *) echo "kind must be gen|alt"; exit 2 ;;
esac
root=out/lip${kind}_cloud; pout=out/lip${kind}_paper_cloud.jsonl; pstate=state/lip${kind}_paper_state.json

# ---- restore state from the newest unexpired state artifact; seed from the branch snapshot only if none exists (list call OK, empty) ----
id=""; ok=0
[ -z "${GITHUB_REPOSITORY:-}" ] && ok=1            # local test run (no repo env): no restore, seed from the snapshot
for i in 1 2 3 4 5 6; do
  [ "$ok" = 1 ] && break
  if res=$(gh api "repos/$GITHUB_REPOSITORY/actions/artifacts?name=$sname&per_page=30" --jq '[.artifacts[]|select(.expired==false)]|sort_by(.created_at)|reverse|.[0].id // empty' 2>>out/supervisor_$kind.log); then
    id=$res; ok=1; break
  fi
  echo "artifact list failed (try $i)"; sleep 20
done
if [ "$ok" != 1 ]; then echo "FATAL: cannot list state artifacts; refusing to reseed silently"; exit 1; fi
if [ -n "$id" ]; then
  gh api "repos/$GITHUB_REPOSITORY/actions/artifacts/$id/zip" > state.zip && unzip -oq state.zip -d state && echo "restored state artifact $id: $(ls state | tr '\n' ' ')" || { echo "FATAL: state download failed"; exit 1; }
  rm -f state.zip
else
  echo "no state artifact named $sname: seeding from branch snapshot"
  cp "$draw_seed" "$draw"
fi
[ -f "$draw" ] || { echo "FATAL: no draw file $draw"; exit 1; }
if [ "$kind" = gen ]; then                        # CatCache writes live/lipgen_series_cat.json: point it into state/ so new categories persist
  [ -f state/lipgen_series_cat.json ] || cp live/lipgen_series_cat.json state/lipgen_series_cat.json
  ln -sf "$PWD/state/lipgen_series_cat.json" live/lipgen_series_cat.json
fi
echo "chunk $kind tag=$TAG secs=$secs start=$(date -u +%FT%TZ) draw_lines=$(wc -l < "$draw")"

# ---- run recorder + paper bot until the deadline; each is restarted (bounded) if it exits early (e.g. first programs pull failed) ----
end=$(( $(date +%s) + secs ))
supervise() {                                       # name, command... ; appends --max-seconds <remaining>
  local name=$1; shift; local n=0 rem
  while [ $n -lt 40 ]; do
    rem=$(( end - $(date +%s) )); [ "$rem" -le 20 ] && break
    "$@" --max-seconds "$rem"; echo "$(date -u +%FT%TZ) $name exited rc=$? rem=$rem try=$n" >> out/supervisor_$kind.log
    n=$((n + 1)); sleep 10
  done
}
supervise rec "$PY" -u live/$rec --root "$root" --draw "$draw" --log out/lip${kind}_rec_cloud.log > /dev/null 2>&1 &
sleep 25
supervise paper "$PY" -u live/lipcloud_paper.py --kind "$kind" --root "$root" --out "$pout" --state "$pstate" >> out/lip${kind}_paper_cloud.log 2>&1 &
wait

# ---- wrap up ----
cp "$draw" out/ 2>/dev/null
echo "chunk $kind done $(date -u +%FT%TZ)"
echo "--- recorder HB (last 2):"; grep " HB " out/lip${kind}_rec_cloud.log | tail -2
echo "--- paper (last 3):"; tail -3 out/lip${kind}_paper_cloud.log
echo "--- files:"; find out -type f | sort | head -40; du -sh out state
