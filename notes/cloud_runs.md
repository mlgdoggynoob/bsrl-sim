# Training runs in a 4-core CPU cloud container (r48-r51)

Runs from 2026-11-25 .. 11-27, on mains 48387c6 .. bff4dde, in a cloud container with 4 cores, 15 GB RAM and no GPU.
This file covers the settings that fit that box, what broke, and how to keep a long run alive there. Results go in #48.
The trainer's flags are in `python -m train_fast --help` / `train_ppo --help`.

## Settings that fit 4 cores

The GPU defaults (`--n 12 --rollout 32768`, evals of 200 episodes every 30 min) don't fit. What ran:

```bash
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2   # 4 host instances share the 4 cores with torch
python -m train_fast --run r51 --hours 23.25 --n 4 --rollout 8192 --chunks 128 --bc-updates 20 \
  --eval-min 120 --eval-episodes 8 --evalb-episodes 8 --league-every 10 --overlap-update 0 \
  --gadgets 0 --hyper 1 --star-powers 1 --gears 1
```

- **Torch threads:** the first r48 leg ran with torch on all cores. The main forward was the bottleneck: act_ms 272,
  `w_wait_main` 152 of 161 s, wall_dps 25. With 2 threads, r48 ran at about 250 decisions/s.
- **Throughput:** r51 runs at wall_dps about 230 (150-250), about 26 s per update, and 80-95 updates an hour.
- **RAM:** each host is about 1.2 GB. Evals boot their own instances. With 20 + 20 eval episodes, 9 hosts were up, about
  2 GB stayed free, and the first eval finished 5 episodes in 40 min. Evals of 8 + 8 every 120 min fit.
- **Eval clock:** `train_fast` starts an eval at once after every `--resume` (`ev["t_last"] = 0`), so a restarted run
  repeats an eval at the same update (r51 has two at u35).

## What broke

- **r48** (all four feature flags on, from BC): stopped at u153. The policy had learned a host bug: the REPEAT
  gadget path fired Piper's Auto Aimer as 5 full-damage copies of the main attack (5 x 1800, no falloff, 30-tile reach),
  a one-shot at any range. In nearly every replay after u120, fire class 3 sat at the cooldown cap (about 0.5 %), with
  one-step 5600 HP drops. Found with `work/bug/dmg_probe.py` (not kept), filed as #54, fixed in #57-#61. Lesson: a
  policy finds a broken action fast. Check the fire-class shares and big one-step damage in the replays early.
- **r48 hypercharge:** Piper's hypercharged super was a dud: the leap happened, but `OverchargedBoxOfBombs` never
  exploded, so it did 0 damage against 3600 unhypercharged. That was #56, fixed in #59 / #62.
- **r49** (fresh, gadgets and hyper off): stopped by the owner at u14.
- **r50** (BC u20, then PPO with `--overlap-update 1`): PPO broke within 4 updates (kl_bc 3.1, clipfrac 0.93 by u24).
  Overlap mode looks buggy; not investigated. r51 is the same run with `--overlap-update 0`, resumed from r50's BC u20
  (`--resume` and `--base` both point at that checkpoint, so the evalb opponent stays the BC policy).

## Keeping a long run alive

- The container is reclaimed a few minutes after the session goes idle; this happened twice on 2026-11-26. A running
  host process doesn't count as activity. An open background job in the session does.
- Start the run detached (`setsid nohup ./launch.sh ... >> run.log 2>&1 < /dev/null &`). Then run a watchdog as a
  background session task. Each minute it checks `pgrep -f "train_fast --run <run>"`. When the run is gone, it copies
  `<run>/ckpt_last.pt` (saved every 5 updates) and relaunches with `--resume <copy> --hours <left>`. It exits after
  about 55 min with a status line, so the session wakes, reports and starts it again.
- Keep a fallback timer in the session (75 min) that restarts the watchdog when a reclaim killed it.
- After a reclaim the uptime is 0. The run resumes from the last 5-update checkpoint, so it loses up to 5 updates.

## r51 so far (Piper, rollouts vs native + league)

| | u21 (end of BC) | u101 | u259 |
|---|---|---|---|
| Storm deaths | 0.71 | 0.28 | 0.10 |
| Hit rate | 0.06 | 0.16 | 0.19 |
| Damage dealt per game | 1.35 | 6.0 | 7.4 |
| Average rank of 10 | 5.65 | 5.3 | 5.2 |
| Win rate | 11.8 % | 11 % | 11.7 % |

Evals (8 episodes each, so noisy):

| | Rank vs 9 native | Win | Top 3 | Rank vs 9 BC copies | Win vs BC |
|---|---|---|---|---|---|
| u35 | 6.1 | 0 % | 25 % | 3.25 | 25 % |
| u195 | 4.9 ± 1.9 | 12.5 % | 37.5 % | 1.5 | 87.5 % |

The mechanics improve steadily. Rank and win in the rollouts have been flat since about u120. Training stays stable
(kl_bc 0.2-0.3, entropy 2.3-2.6, clipfrac about 0.08, explained variance about 0.8) with 0 host restarts.
