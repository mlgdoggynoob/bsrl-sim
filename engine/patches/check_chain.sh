#!/usr/bin/env bash
# Checks that engine/patches/series replays: the engine/ tree of commit 7ac04b9 (the fold of deps/ into engine/) plus the
# patches in `series`, in order, must give exactly the engine/ of the working tree (patches/, *.md and untracked files such
# as the game, build outputs and caches left out). Strict: `patch -F0` (no fuzz), any rejected hunk fails.
#
#   engine/patches/check_chain.sh        exit 0 = the chain reproduces engine/, 1 = it does not, 2 = usage / tool error
#
# Needs git history (the 7ac04b9 commit): without it (shallow clone, tarball) it says so and exits 0.
# Patch levels: -p1 when the first header is `--- a/...`, else -p0 (see series). To add a patch: record it as
# diff(tree after the series so far, tree with your change), add its name at the end of series, run this.
set -u
BASE=7ac04b9
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$HERE/../.." && pwd); cd "$ROOT"
git rev-parse --git-dir >/dev/null 2>&1 && git cat-file -e "$BASE^{commit}" 2>/dev/null \
  || { echo "check_chain: skipped (no git history with $BASE: shallow clone or tarball; git fetch --unshallow)"; exit 0; }
T=$(mktemp -d) || exit 2; trap 'rm -rf "$T"' EXIT
git archive "$BASE" engine | tar -x -C "$T" || exit 2
names=$(sed 's/#.*//; s/[[:space:]]*$//; /^$/d' engine/patches/series)
n=0; offs=0
for p in $names; do
  f=$ROOT/engine/patches/$p.patch
  [ -f "$f" ] || { echo "check_chain: FAIL  series names $p.patch, which does not exist"; exit 1; }
  if grep -m1 '^--- ' "$f" | grep -q '^--- a/'; then L=1; else L=0; fi
  if ! out=$(patch -p$L -F0 --no-backup-if-mismatch --reject-file=/dev/null -d "$T/engine" < "$f" 2>&1); then
    echo "check_chain: FAIL  $p.patch does not apply in order (-p$L, no fuzz) on the tree the patches before it leave:"
    echo "$out" | grep -E 'FAILED|can.t find|Reversed|malformed|fuzz' | head -8; exit 1
  fi
  offs=$((offs + $(echo "$out" | grep -c 'offset')))
  n=$((n + 1))
done
# files patches touch (+++ lines; a vendor/ path is py/ here), compared even when a doc
touched=$(for p in $names; do grep -h '^+++ ' "$ROOT/engine/patches/$p.patch"; done | sed 's/^+++ //; s/[[:space:]].*//; s#^b/##; s#^vendor/#py/#' | sort -u)
# the tree to compare: tracked files of engine/ (no patches/, no docs) plus the touched ones
want=$( { git ls-files engine | sed 's#^engine/##' | grep -v -e '^patches/' -e '\.md$'; echo "$touched"; } | sort -u)
bad=0
for f in $want; do
  [ -f "engine/$f" ] || [ -f "$T/engine/$f" ] || continue
  if [ ! -f "$T/engine/$f" ]; then echo "check_chain: MISMATCH  engine/$f exists, the chain does not make it"; bad=1
  elif [ ! -f "engine/$f" ]; then echo "check_chain: MISMATCH  the chain makes engine/$f, the working tree lacks it"; bad=1
  elif ! cmp -s "$T/engine/$f" "engine/$f"; then echo "check_chain: MISMATCH  engine/$f differs from the chain's result"; bad=1; fi
done
[ $bad = 0 ] || { echo "check_chain: FAIL  the working tree is not the chain's result (patch recorded on the wrong base, or an edit with no patch)"; exit 1; }
echo "check_chain: ok  $n patches replay in order on $BASE and reproduce engine/${offs:+ ($offs hunk offsets)}"
