# engine/: nirkt's battle host and environment

Everything under `engine/` is [nirkt](https://github.com/nirkt)'s code, redistributed in bsrl-sim with nirkt's
permission and under nirkt's terms. It is not covered by bsrl-sim's licence (the top-level `LICENSE` covers the
top-level modules only). bsrl-sim's own changes to it are applied in place and recorded in `patches/`.

It used to be two folders, `deps/bulletlabels` and `deps/nbrl-env`. They are now one tree with one `nbpc`:

| Here | From |
|---|---|
| `native/`, `py/nbpc/`, `py/state2.py`, `py/dumps.py`, `labeller/`, `framegen/`, `debug/`, `data/`, `docs/` (but `docs/nbrl-env.md`), `tests/`, `bl.py`, `setup.sh`, `requirements.txt`, `README.md`, `AGENTS.md`, `CLAUDE.md` | [nirkt/bulletlabels](https://github.com/nirkt/bulletlabels) @ `52184b2`; `py/` was `vendor/` there |
| `py/*.py` (the rest: `models4.py`, ...), `train/`, `docs/nbrl-env.md` (its README) | [nirkt/nbrl-env](https://github.com/nirkt/nbrl-env) @ `7ff57bc`, `py/` and `train/` (models, the qemu binary and duplicate host sources were already left out) |

nbrl-env's own `py/nbpc/` and `py/state2.py` are not kept: `state2.py` was identical to bulletlabels', and
bulletlabels' `nbpc` (with nbrl-env's `maenv.py` and `fair.py` copied in) was the one on `PYTHONPATH` already.

What the sim uses from here: `native/loader` (the host, built as `native/loader/nbhost_rl`), `native/qemu` (the patched
qemu build; QEMU itself is downloaded from download.qemu.org by `native/qemu/build.sh`), `native/payloads`,
`native/LIBG_SHA256`, `py/nbpc`, `py/models4.py` and `requirements.txt`. The labeller, the frame generator and the
other nbrl-env scripts are vision-data and earlier training tools, kept as they were.

## bsrl-sim's changes (`patches/`)

- `training_round.patch`, `fair_view.patch`, `live_state.patch`, `gadgets.patch`: in that order, on top of
  bulletlabels @ `52184b2` (SETUP.md lists what each does). Their paths are bulletlabels' (`vendor/nbpc/...` is
  `py/nbpc/...` here).
- `gadgets_dash_heal.patch`: the part of the gadget work that landed after the fold (`gadget.c`'s dash and heal kinds); the
  tree at the fold held an earlier `gadget.c`, and `gadgets.patch` (the whole work, bulletlabels' paths) records the later one.
- Every other patch (`charge.patch` and on; SETUP.md lists what each does) has paths relative to `engine/`.
- `series` is the order they replay in, on `engine/` as it was at commit 7ac04b9 (the fold); `check_chain.sh` replays it
  with no fuzz and compares the result with the working tree. The four bulletlabels-path patches are not replayed.
- `maenv.py` and `fair.py` copied from nbrl-env's `py/nbpc` into bulletlabels' `vendor/nbpc`.
- The game download link removed from bulletlabels' `setup.sh` (the top-level `setup.sh` downloads it instead).
- The merge into this tree: files moved as listed above, path names updated in comments, `labeller/rc.py` (`py/` on
  `sys.path`), the bulletlabels README's layout table and `requirements.txt` (a comment for nbrl-env's tested
  versions). Nothing the sim runs changed. nbrl-env's old scripts put their own folder first on `sys.path`, so they
  now import the merged `nbpc` instead of nbrl-env's older copy.

New changes: keep them small and add a patch here (paths relative to `engine/`, recorded as the diff from the tree the
series leaves to the tree with your change), add its name at the end of `series`, and run `patches/check_chain.sh`.
