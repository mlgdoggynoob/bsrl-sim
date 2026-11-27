# Recording a policy's games with the game's graphics

`policy_video.py` plays battles with a checkpoint in the real game client (libg + the nbgl GL host), records every frame and
writes MP4s. Use it to see how a run plays: what it does in the storm, how it aims, how it fights. It plays new battles: training
battles are not rendered, so there is no footage of them to keep.

## What you need

- A built host (`./setup.sh`). Brawlers turn to their aim and walking direction only with a host that has `facing_sync`
  (`engine/patches/facing_sync.patch`); a host built before it renders every brawler facing the camera.
- `xvfb-run` (package `xvfb`) and `ffmpeg`. On a machine with a display, `xvfb-run -a` can be left out.
- A checkpoint: `$SIM_WORK/runs/RUN/ckpt_last.pt` or any `ckpt_uNNNN.pt`. The run's `config.json` next to it says which
  loadouts it trained with (gadgets, hypercharge, star powers, gears); the recording uses the same ones.

## Steps

```bash
cd bsrl-sim && source env.sh
python -m policy_video --check                       # no host: flags, run config, battle setup, ffmpeg
cp $SIM_WORK/runs/RUN/ckpt_last.pt $SIM_WORK/runs/RUN/ckpt_video.pt   # optional: a copy the trainer will not overwrite
xvfb-run -a python -m policy_video --ckpt $SIM_WORK/runs/RUN/ckpt_video.pt --out $SIM_WORK/video/RUN --tries 5
```

The copy keeps `config.json` next to the checkpoint, so the loadouts are still read from it. Checkpoints copied anywhere
else need the flags (`--gadgets 0 --hyper 1 --star-powers 1 --gears 1`, as the run's `config.json` says).

Output in `--out`:

| File | What it is |
|---|---|
| `try<k>_20fps.mp4` | Battle k, one frame per game tick (20 fps = real time) |
| `policy_<fps>fps.mp4` | The best battle (lowest rank, then the longest), motion-interpolated to `--fps` (default 30) |
| `episodes.json` | Every battle: seed, rank, ticks, kills, file |

A frame sheet to look at a battle quickly without playing it:

```bash
ffmpeg -loglevel error -y -i $SIM_WORK/video/RUN/try0_20fps.mp4 -vf "select='not(mod(n\,100))',scale=640:-1,tile=4x3" -frames:v 1 sheet.jpg
```

## Options

| Flag | Default | Meaning |
|---|---|---|
| `--tries N` | 1 | battles to play; the best one becomes `policy_<fps>fps.mp4` |
| `--seed0 S` | 91000000 | seed of the first battle (then S+1, ...); same seed, same map and spawns |
| `--fps F` | 30 | frame rate of the final video (ffmpeg `minterpolate`) |
| `--size WxH` | 1920x864 | render size |
| `--brawler`, `--loc` | Sniper (Piper), Survival604 | everyone's brawler and the Showdown map, as the trainer's flags |
| `--every K` | 2 | the policy decides every K ticks (2 = as in training) and holds its move in between, with no fire |
| `--max-ticks T` | 4000 | a battle ends after T ticks (200 s) |
| `--overlay 1` | 0 | draw over every frame (`overlay.py`): a box with its showdown-vision det class tag above it for every entity the client renders (player, enemy, enemy_summon, power_box, power_cube, teammate_projectile = the policy's own shots, enemy_projectile), and the rule planner's pick, asked every second on the policy's observation: rule and reason in a text panel, a white A* path over the walkable tiles to its target. The planner is display only: the policy plays on intent none, as in the evals |
| `--gadgets`, `--hyper`, `--star-powers`, `--gears` | -1 | 1 / 0 = on / off; -1 = as the run's `config.json` |

`NBHOST_FACING=0` before the command renders the old front-facing look. `NBHOST_BIN=path` plays with another host binary
(for example one built next to a running training run, below).

## Cost and timing

One battle boots a host (30-40 s), then runs at about 1 s of game per 4-5 s of wall time on a 4-core CPU: a 60 s battle
takes about 5 minutes, five tries 20-30 minutes, and the 30 fps pass a few more minutes. It takes about one core while it runs.

## While a training run is going

- It adds one host to the ones training uses: run it with `nice -n 10` so training keeps priority, and check there is
  RAM for it (about 1.5 GB).
- Do not rebuild `nbhost_rl` under a running run whose watchdog may restart it (`setup.sh` deletes the old binary
  before the new one is built). Build a second binary instead and point the recorder at it:

```bash
cd engine/native/loader && sed 's/nbhost_spawnfix2/nbhost_facing/g' build.sh | sh && cd -
NBHOST_BIN=$PWD/engine/native/loader/nbhost_facing nice -n 10 xvfb-run -a python -m policy_video --ckpt ... --out ...
```

## What the video is and is not

- Player 0 is the policy (the camera follows it); the other 9 are the native AI, all on the same brawler, Solo Showdown.
- The policy sees what it sees in training: the noisy observation with detector latency, not the true state.
- Battles are sampled from the policy's action distribution, so the same seed can go differently. The best of several
  tries shows what the policy can do, not what it does on average: the run's evals (`evals.jsonl`, `scorecard.py`) say that.
