#!/usr/bin/env bash
# Update an existing checkout to the latest main, then bring the build up to date (setup.sh: rebuilds the host when its
# sources changed, installs new Python requirements; the game files and qemu stay as they are).
#
#   ./update.sh [--check] [--apt] [--no-python]
#
#   on main         fast-forwards to origin/main (stops if your main has commits of its own)
#   on a branch     merges origin/main into it (stops, merge undone, on a conflict)
#   --check         afterwards runs the self-checks that need no battle (AGENTS.md "Checks", README "Self-checks") and
#                   engine/patches/check_chain.sh (the patch series replays and gives engine/)
#   --apt           also installs system packages (setup.sh without --no-apt)
#   --no-python     passed to setup.sh: leave the venv alone
#   REMOTE          the remote to update from (default origin)
# Stops before touching anything if tracked files have uncommitted changes (commit or `git stash` them first).
set -euo pipefail
# the body is one function: bash reads all of it before the merge below can rewrite this file
main() {
  ROOT=$(cd "$(dirname "$0")" && pwd); cd "$ROOT"
  REMOTE=${REMOTE:-origin}; CHECK=0; APT=0; SETUP=()
  local a; for a in "$@"; do case $a in --check) CHECK=1;; --apt) APT=1;; --no-python) SETUP+=(--no-python);;
    *) echo "unknown option $a"; exit 2;; esac; done
  [ $APT = 1 ] || SETUP+=(--no-apt)
  say() { printf '\n== %s\n' "$*"; }
  obs() { sed -n 's/^OBS_VERSION = "\(.*\)"/\1/p' obs_v5.py; }

  git diff --quiet && git diff --cached --quiet || { echo "uncommitted changes in tracked files: commit or stash them first"; git status --short -uno; exit 1; }
  BR=$(git rev-parse --abbrev-ref HEAD); OLD=$(git rev-parse HEAD); OBS0=$(obs)

  say "fetching $REMOTE/main"
  git fetch "$REMOTE" main
  if [ "$BR" = main ]; then
    git merge --ff-only FETCH_HEAD || { echo "your main has commits that $REMOTE/main does not: move them to a branch, or merge by hand"; exit 1; }
  else
    echo "on branch $BR: merging $REMOTE/main into it"
    git merge --no-edit FETCH_HEAD || { git merge --abort; echo "conflict merging $REMOTE/main into $BR: merge undone, resolve it by hand"; exit 1; }
  fi

  if [ "$(git rev-parse HEAD)" = "$OLD" ]; then echo "already up to date"
  else
    say "what changed"
    git log --oneline --first-parent "$OLD..HEAD" | head -30
    OBS1=$(obs)
    [ "$OBS0" = "$OBS1" ] || echo "NOTE: observation $OBS0 -> $OBS1: re-export policies (export_policy.py) for the bot; old checkpoints still load"
  fi

  say "build (setup.sh ${SETUP[*]})"
  ./setup.sh ${SETUP[@]+"${SETUP[@]}"}

  if [ $CHECK = 1 ]; then
    say "self-checks (no battle)"
    set +eu +o pipefail; source env.sh; set -eu -o pipefail   # env.sh is written for an interactive shell
    fail=0
    for m in "-m obs_v5" "-m intent" "-m planner" "-m model" "-m fast_obs" "-m env_v5 --check" "scorecard.py --check" \
             "apply_noise.py --test" "-m super_audit --check" "-m star_check --check" "-m gadget_check --check" "-m hyper_check --check" \
             "-m charge_check --check" "-m export_policy --check" "-m train_ppo --check" "-m scenarios --check" "-m showdown_check --check" "-m status_check --check" \
             "-m star_audit --check" "-m gear_check --check" "-m imitation" "-m desc_audit --check" "-m desc_values --check" "-m overlay"; do
      # policy_video --check is left out: it needs ffmpeg, which setup.sh does not install (docs/RECORDING.md)
      if out=$(python $m 2>&1); then echo "ok    python $m"; else echo "FAIL  python $m"; echo "$out" | tail -5; fail=1; fi
    done
    # the patch chain replays on the fold commit and gives engine/ (skips itself without git history)
    if out=$(engine/patches/check_chain.sh 2>&1); then echo "ok    ${out#check_chain: }"; else echo "FAIL  engine/patches/check_chain.sh"; echo "$out" | tail -5; fail=1; fi
    [ $fail = 0 ] || exit 1
  fi
  [ $CHECK = 0 ] || { say "done"; echo "Host checks (boot the game, 60-90 s each): source env.sh && python -m live_check --n 2 --minutes 8"; }
}
main "$@"; exit
