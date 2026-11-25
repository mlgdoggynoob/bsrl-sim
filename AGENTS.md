# bsrl-sim: guide for coding agents

RL environment + trainer for a top-down battle royale (see README.md). Python, numpy, PyTorch. Every module is flat at
the repo root and is run as `python -m <module>` from the root after `source env.sh`.

## Before you change anything
- Read README.md (file map, setup) and the docstring at the top of the file you touch. The docstrings are the spec.
- `engine/` is nirkt's code (README "Credits", `engine/NOTICE.md`), not under this repo's licence. Keep changes there
  small, and record every one in `engine/patches/*.patch` (a diff on top of the earlier patches, paths relative to
  `engine/`) so the two stay separable. This repo's own code is the flat modules at the root.
- `./setup.sh` builds everything (SETUP.md), `./update.sh` pulls the latest `main` and rebuilds what changed; `source env.sh` before any module. Without the host built, only the
  self-checks that skip the game data run (`scorecard.py --check`, `apply_noise.py --test`).
- No game files, binaries, checkpoints, datasets or run outputs go into git (`.gitignore`).

## Checks
- Self-checks, no battle (`obs_v5` / `env_v5` need the game files from `setup.sh`): `python -m obs_v5`, `python -m intent`, `python -m planner`, `python -m model`, `python -m fast_obs`, `python -m env_v5 --check`,
  `python scorecard.py --check`, `python apply_noise.py --test`, `python -m super_audit --check`, `python -m star_audit --check`, `python -m star_check --check`, `python -m gadget_check --check`, `python -m hyper_check --check`, `python -m charge_check --check`, `python -m export_policy --check`, `python -m showdown_check --check`, `python -m status_check --check`, `python -m gear_check --check`. Run the ones for the modules you touched.
- Host checks (boot takes 60-90 s each, so batch your questions into one run): `python -m live_check`, `python -m showdown_check`, `python -m status_check`, `python -m star_audit`, `python -m star_check`, `python -m gear_check`,
  `python -m test_fast` (fast paths must stay bit-equal to the reference paths), `python -m train_ppo --run t --smoke`.
- Every new module gets an assert self-check (`python -m <module>` or `--check`), like the existing ones.

## Rules
- The observation is a contract with whatever runs exported policies. Changing a shape, a class list, the slot layout or `cond` means bumping
  `obs_v5.OBS_VERSION` and saying so in the PR. Old checkpoints must still load (zero-init new inputs, pad in
  `load_state_dict`).
- The BSRL bot (`brain/spec.py`, `adapter.py`, `policy.py`) mirrors the observation; `export_policy.py` writes what it loads.
- `fast_obs` / `fast_act` must match `obs_v5` / `model.act_stacked`: change both sides together, then run `test_fast`.
- New trainer flags default to the current behaviour (off).
- Keep docstrings current-state. Put the reason for a number in a short comment next to it.
- Never run long GPU jobs or many host instances unless the person you work for asked for it.
- Work on your own branch and open a pull request. Don't push to `main`.
