# Issue #49: Brawl TV imitation rows, step 4 (trainer side)

Steps 1-3 (recording Brawl TV on the owner's emulator, vision models on spectator frames, action labels) need the
owner's machine and are not built here. This branch builds step 4 so their output can be trained on at once.

## What is built

- `imitation.py`: the shard format (docstring = spec), `write_shard` (step 3 calls it), `load` (a folder of shards or
  one), `Dataset.sample` / `batch` (windows of consecutive rows of one episode), `python -m imitation` self-check.
- `train_ppo.py`, all flags default off (nothing changes, no extra RNG draw, with them off):
  - `--imit-data PATH`: the shards. Needed by the next two.
  - `--imit-updates N`: N BC updates on the rows (each = `--epochs` minibatches of `--imit-chunks` windows), run after
    the native-AI BC phase and before the KL anchor `ref` is frozen, so PPO anchors to the imitation-pretrained policy.
    Resumed runs (no BC phase): once at the start. lr `--bc-lr`.
  - `--imit-w W`: W x the same loss on `--imit-chunks` fresh windows added to every PPO minibatch (native-BC updates
    excluded). Logged as `imit_nll` / `imit_w` in progress.jsonl.
  - `--imit-chunks` (64) and `--imit-burn` (16): window count per minibatch, context rows before the `--seq` target rows.
- The loss is the BC loss: `net.seq` -> `dist_logp_ent` -> mean weighted by `w` (`train_ppo.imit_nll`; the BC update's
  masked mean is now the shared `wmean`, same math). No value term (no returns in the data). Only a log-likelihood is
  built; a KL term would need the pro's distribution, and a hard label's KL is this NLL.

## Dataset format (one .npz per recording, N rows in time order)

| key | shape, dtype | meaning |
|---|---|---|
| `format` | str | `imit1` |
| `obs_version` | str | `obs_v5.OBS_VERSION` (now v5.9); load refuses any other, the shard must be rebuilt |
| `s` | (N, 49) f16 | policy vector input cat[self 8, cond 30, intent 11] |
| `ent` | (N, 39, 36) f16 | entity rows, `ObsV5.build` o["ent"] |
| `grid` | (N, 25, 25) u8 | seg-class grid, o["grid"] |
| `act` | (N, 4) i16 | move 0-16, fire 0-4 (none / attack / super / gadget / hypercharge), aim 0-359, distance 0-7 |
| `w` | (N,) f32 | label quality 0..1 (0 = ignored) |
| `ep` | (N,) i32 | episode id, rows of one episode contiguous; GRU state is zero at an id's first row |
| `source` | str | free text |

Shapes come from `obs_v5` (N_S, N_ENT, F_ENT, G), not hard-coded. Aim is read only when the fire class aims
(`obs_v5.FIRE_AIM`), distance only for a super; other values must still be in range (0). A label whose fire class the
policy masks (super / gadget / hypercharge while its self column is 0) gets `w = 0` from the writer.

## What steps 1-3 must produce

1. Rows built by the same code as live play: `obs_v5.ObsV5.build` on the frame (noise as the live bot sees it: the
   spectator frames go through the same detector / seg models), `s = cat[self, cond, intent]` with `cond` from
   `obs_v5.cond(brawler, sliders, team_size, cubes, players_left)` and an all-zero intent block (free play). The
   self column 2 / 3 / 4 (super / gadget / hypercharge ready) must be set when the pro could use it, or those labels
   are dropped.
2. One shard per (recording, followed player), decisions at the policy's rate (`ticks=2`: every 2 game ticks, 10
   rows/s), consecutive in time, one `ep` per battle life (a respawn or a cut in the footage starts a new `ep`).
3. Labels in the heads' units: move = the 17-way stick bin the policy uses, fire class, aim in degrees (bin 0 =
   +x, as `model` / `obs_v5` define it), distance bin for supers; `w` from how sure the labeller was.
4. `imitation.write_shard(...)` for each; check with `python -m imitation` and `load(dir)`.

Not decided here (research, not plumbing): how much `--imit-w` / `--imit-updates` helps, and whether the cond sliders
of a pro should be a fixed preset. Nothing here was run against real data.
