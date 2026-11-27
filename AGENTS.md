# bsrl-sim: guide for coding agents

RL environment + trainer for a top-down battle royale. Python, numpy, PyTorch. Flat modules at the repo root, run as
`python -m <module>` from the root after `source env.sh`.

## Before you change anything
- Read README.md (file map, setup) and the docstring of the file you touch: the docstrings are the spec.
- `engine/` is nirkt's code (`engine/NOTICE.md`), not under this repo's licence. Keep changes there small and record
  each one in `engine/patches/*.patch` (a diff on top of the earlier patches, paths relative to `engine/`).
- `./setup.sh` builds everything (SETUP.md); `./update.sh` pulls `main` and rebuilds what changed.
- No game files, binaries, checkpoints, datasets or run outputs in git (`.gitignore`).

## Checks
- Self-checks (no battle): the list is in README "Self-checks"; `./update.sh --check` runs them all. Run the ones for
  the modules you touched. Every new module gets an assert self-check (`python -m <module>` or `--check`).
- Host checks (60-90 s boot each, so batch them): `live_check`, `showdown_check`, `status_check`, `star_audit`,
  `star_check`, `gear_check`, `test_fast`, `train_ppo --run t --smoke`.

## Rules
- The observation is a contract with whatever runs exported policies (the BSRL bot's `brain/spec.py`, `adapter.py`,
  `policy.py`; `export_policy.py` writes what it loads). A change to a shape, a class list, the slot layout or `cond`
  bumps `obs_v5.OBS_VERSION`, said in the PR. Old checkpoints must still load (zero-init new inputs, pad on load).
- `fast_obs` / `fast_act` must match `obs_v5` / `model.act_stacked`: change both together, then run `test_fast`.
- New trainer flags default to the current behaviour (off).
- Docstrings describe the current state. The reason for a number goes in a short comment next to it.
- No long GPU jobs or many host instances unless the person you work for asked.

## Branches
- One branch per pull request, cut from the latest `main`; never push to `main`. Once its PR merges, restart the
  branch from `main` before adding anything (no new commits on a merged branch).
- To carry an old branch's work over, merge that branch; re-applying or cherry-picking makes duplicate commits.
- Subagent worktrees end committed and merged, or removed. None is left with uncommitted edits.
