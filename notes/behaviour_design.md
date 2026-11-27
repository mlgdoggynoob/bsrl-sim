# Behaviour sliders + intents: design (phase 1, read-only)

Kept from the session handoff folder (2026-11-23 .. 11-24). Sections 1-8 are the design the owner approved; the
"As-built notes" sections were written as each step merged (C, S, D, BI, E, the PR #9 gadget port). "scratchpad" scripts
named below were session-local and are not kept. Current behaviour: the docstrings of `env_v5.py`, `obs_v5.py`,
`intent.py`, `planner.py`, `scenarios.py`, `model.py`.

Branch `claude/focused-mayer-2c1pv8`. Built on the concurrent obs change (OBS_VERSION `v5.3`: F_ENT 20 with area
columns; `NbePlayer.cubes` = picked up this step, `cubes_total` = held now, 0 after a team knock-out; live bushes / cover).
Units throughout: 1 step = 2 ticks = 0.1 s; 1 tile = 300 units; reward 1000 damage = 1; a battle is <= 2000 steps
(max_ticks 4000). Base reward (maenv.REWARD_W): dealt 0.5, hp 1.0 (signed hp change), box 0.05, cubes 0.5, kills 1,
gas -0.02 per gas tick, place 5 x (10 - rank) / 9, win 3. **Placement + win spans 8 per battle; one rank step = 0.56.**

Two layers, two inputs:
- **sliders** = per-battle play style (bush camper / aggressive / cube farmer ...), in `cond`, shaped by slider reward terms.
- **intents** = a per-second goal ("leave the gas eastward"), a separate input block, shaped by a small intent-following
  reward, picked by a planner (rules first, value-based later). `none` = free play.

---------------------------------------------------------------------------------------------------------------------

## 1. What to encode, what is already learned, what cannot be done

| Source behaviour | Verdict | Where it lives |
|---|---|---|
| Heuristic-bot archetypes (tank / assassin / thrower / support / sniper) | learned | cond brawler stats (range, melee, thrown, super type) + `hemb` hero embedding; no slider |
| Heuristic-bot spacing (safe_range / attack_range, tanks close to 0.65 range) | learned + style | dealt / hp reward; `kite` (ranged style), `aggressive` (closing style); scorecard `range` per archetype |
| Predictive aim / intercept, auto-aim when the target can't escape | learned | lead hint columns, pointer aim head, `hits`; scorecard `lead`. No term |
| Strafe flip every 1.2 s | learned | dodging comes from `taken` / hp; a fixed-period or "lateral movement" term is worse than learned dodging and is gameable |
| Teammate leash (to mate if > 4 tiles, away if < 1.5) | **slider + intent** | new `leash` slider; `regroup` intent |
| Gas avoidance | **slider + intent** | base gas term + new `gas_safe` slider; `move_to` intent (planner gas rule) |
| Explore toward map centre when nothing is seen | **intent** | planner `move_to` away from the visible map edge (live has no absolute position); `bush_control` scouting |
| Supers: defensive at close range, charge supers as gap closers, throwers in range | learned | fire head super + distance head, cond super type; brawler-specific rules not encoded |
| Gadget (every 3 s in range), hypercharge with super | **impossible** | host cannot trigger them (fire head none / attack / super); `self[3]` gadget is always 0, hypercharge-ready is visible but unusable |
| Hold-to-charge attacks (`must_hold`) | out of scope | fire head is a tap; no host support verified |
| Pro: lead shots | learned | as above |
| Pro: keep distance, avoid assassins | partly | `kite`; enemy brawler identity is not in the obs (ENT has no hero id), so no "avoid assassins" term |
| Pro: third-party only when someone is low | **slider + intent** | `third_party` (fixed), planner fight rule |
| Pro: cubes win, steal by kills, don't die for one | **slider** | `collect` on Δheld (a knock-out / elimination now costs the held cubes) + `--cube-shaping` |
| Pro: leave gas early | **slider** | `gas_safe` margin term |
| Pro: check bushes (shoot them), watch bushes near a box | **slider** | `bush_control` gets a "hit an enemy hidden in a bush" part |
| Pro: low HP -> bush, stop taking damage, regen | **slider + intent** | `retreat` (fixed), `avoid` / `hide` intents |
| Pro: wait for enemy ammo, don't empty yours | base knob | `--reward-w '{"shots": -0.03}'` (exists, HISTORY 77); not a style |
| Pro: team 2v1, focus one, share cubes, roles | partly | `focus`, `protect`, `leash`; cube sharing impossible (no drop action) |

## 2. Slider set (12) with exact terms

### 2.1 Audit of the current 10 terms (`env_v5.slider_terms`)

| # | Problem | Evidence | Fix |
|---|---|---|---|
| A1 | Respawning players count as alive: `alive = pl.alive and not eliminated`, but a waiting player has `alive=1, hp=0` (env.c `waiting(i)`). Bush camp / proximity accrue while dead; **retreat pays the respawn refill** (hp 0 -> max, `low` is latched) ~ max_hp/1000 per knock-out | training_round.patch fill_players | `alive &= pl.reserved[3] == 0`; on the step a player comes back, set `sl["hp"]` = its hp and clear `low` |
| A2 | `damage_taken` includes gas (`taken + gasd`, env.c:1242). protect's `mate_taken`, third_party's `others`, kite's / third_party's `taken == 0` all read gas as an enemy hit | env.c 1242 | enemy damage `te = taken - gas_damage` everywhere "being hit" is meant |
| A3 | protect: `-mate_taken` only for mates within 1800 -> **staying > 6 tiles from a mate under fire avoids the penalty**, while `+0.01` per step within 6 tiles pulls in: contradictory, and 0.01 / step = up to 20 per battle (> placement) = clumping | slider_terms line 128 | split: `protect` = peel only; proximity moves to `leash` (band + anti-clump) |
| A4 | bush_camp `0.01 * hid`: up to 20 per battle per unit weight; pays a bush in an empty corner as much as an ambush spot. **Camping all game beats placement** | line 126 | per-step part only when the bush is actually hiding me from an enemy whose screen I'm on; scale via NORM |
| A5 | collect `box / 1000 + cubes`: a LootBox has 4300 HP (characters.csv) -> **one box = 4.3, one cube = 1**; farms boxes, ignores cubes, ignores gas | line 127 | box x 0.2, cubes on Δheld, x (1 - in_gas) |
| A6 | push: `closing = clip(d_prev - d, 0, 300)` is one-sided -> **walk in / out dithering earns**, a switch of nearest enemy counts as closing, the enemy walking at me counts, absolute HP favours tanks | line 118, 133 | replace by `aggressive` (engagement time, no distance delta) |
| A7 | retreat: hp term cancels (+1 / -1 per 1000), retreat adds `w * gain` -> a bounded "get low, heal" cycle; also pays mates' heals and cube +HP | line 129 | keep (death risk dominates) but exclude the respawn step (A1) and steps with `pl.cubes > 0` |
| A8 | Evals draw random slider weights (`slider_state` always samples `w`) -> eval rank noise once slider_scale > 0 | slider_state | weights from the battle tag (`--eval-sliders`) |
| A9 | `slider_scale == 0` skips the terms (s_* = 0), so a reference run can't measure them | `_finish_step` | measure with `--slider-scale 1e-6` (no code) |
| A10 | Magnitudes not comparable: dk-gated terms are O(10) per battle, time terms O(20), bush_control O(2) | — | per-term NORM (2.3) |

focus, peek, kite (after A2) are fine as proxies. Cover / bush masks are live after the concurrent change.

### 2.2 Recommended set (order = cond order; slots 0-9 keep their index, 10-11 are appended)

Notation per player p and step: `dk = (dealt + bomb) / 1000`, `te = taken - gas_damage`, `alive` as A1, `mhp = max_hp`,
`inr[p,q]` enemy q alive within own range (`sl["range"]`, = CastingRange x 100 units), `d_mate` nearest living,
non-waiting mate (units; inf in solo), `hid_vs[p]` = p on a bush tile and **at least one enemy has p on its screen but
d > 900** (the bush is what hides p) and no enemy sees p. `margin` = gas margin in tiles (below).
All terms are then multiplied by `NORM[k]` and `alive`.

| slot | slider | term (per step, before NORM) | status | main risk -> mitigation |
|---|---|---|---|---|
| 0 | bush_camp | `0.002 * hid_vs + dk * hid_vs_prev` | fixed (A1, A4) | camps instead of placing -> per-step part only when hiding from someone; NORM budget; presets keep `gas_safe` up |
| 1 | collect (cube farm) | `(1 - in_gas) * (0.2 * box / 1000 + max(Δheld, 0)) + min(Δheld, 0)` | fixed (A5) | farms in gas -> gated; dies holding cubes -> drop costs them (negative Δheld at a knock-out / elimination; held = 0 once eliminated as B3) |
| 2 | protect (peel) | `dk * peel`, peel = a mate within 1800 had `te > 0` in the last 10 steps (`sl["mhit"]` countdown) | fixed (A2, A3) | none new; solo = 0 |
| 3 | retreat | `gain * low * (pl.cubes == 0) * ~back` | fixed (A1, A7) | heal loop bounded by 0.4 mhp per low episode |
| 4 | kite | `dk * (te == 0) * (near >= 0.7 range)` | fixed (A2) | tanks trivially satisfy it -> expected; spacing for tanks comes from `aggressive` |
| 5 | peek | `dk * nearcover` | unchanged (cover live) | — |
| 6 | focus | `dk * inr.any * (te[lowest-hp enemy in range] > 0)` | A2 only | proxy (no per-target damage on this host) |
| 7 | **aggressive** (was push) | `dk + 0.5 * kills + 0.002 * engaged`, engaged = `inr.any & hp >= 0.4 mhp` | replaced (A6) | suicide rushes -> engagement time only above 40 % HP; deaths still cost placement + hp |
| 8 | third_party | `dk * (te == 0) * (inr & others).any`, others[p,q] = `te[q] > dealt[p] + bomb[p]` | fixed (A2) | — |
| 9 | bush_control | `0.005 * new_bush_tiles + dk * bushhit`, bushhit = an enemy on a bush tile, not visible to p, within p's range, `te > 0` | extended | walking into bushes (pros avoid it) -> the hit part rewards checking from range |
| 10 | **leash** (new) | `0.002 * [450 <= d_mate <= 1200] - 0.002 * [d_mate < 300]` (heuristic bot 1.5-4 tiles; clump < 1 tile) | new | clumping into AoE -> clump penalty + lower band edge; abandoning fights -> band only, no damage gating; solo = 0 |
| 11 | **gas_safe** (new) | `-0.01 * in_gas - 0.002 * [margin < 2] * [zone >= 4]` | new | endgame zone is all "near gas" -> only when the safe zone half-size `zone` >= 4 tiles; over-camping the centre -> small, bounded |

Gas margin (no new host data): `edge = min(tx, ty, W-1-tx, H-1-ty)` (own tile), `ring = state2.gas_step(tick)` (rings
of 1 tile every 100 ticks after tick 440, the host's storm model; `r.reserved[0]` is the latched step when the storm
schedule is replayed), `margin = edge - ring` (in gas iff < 0), `zone = min(W, H) / 2 - ring`. `live_check` asserts
`in_gas == (margin < 0)` for every alive player (if it fails, read the agent's obs grid channel 3 instead).

Rename `push` -> `aggressive` in the same slot 7: old checkpoints read slot 7 as "push at advantage", close enough to
"aggressive" that the transfer is harmless; say so in the PR.

### 2.3 Normalisation (comparable sliders)

`NORM[k] = 0.5 / mean_battle(|Σ_steps T_k|)` measured once on a reference policy (BC or the current best) with
uniform weights: `python -m env_v5 --norm RUN` reads `episodes.jsonl` `terms["s_*"]` (raw, un-normalised) and prints the
JSON. Static constants (in `env_v5.SLIDER_NORM`, default all 1.0 = current behaviour) or `--slider-norm FILE`; never a
running normaliser (non-stationary reward, checkpoints not comparable). Then **each slider at weight 1 is worth about
0.5 per battle**, a preset with three sliders at 2 about +3 against the base, and with `--slider-scale 0.5` (start
value) balanced sums to ~3 per battle, under the 8-point placement range. Re-measure after a big policy change. The
scorecard check (3.4) decides the final `--slider-scale`: no preset may lose more than 0.5 mean rank vs balanced.

Logging: `s_*` stay raw term sums (for NORM), new `sn_*` = normalised x weight (what the reward got).

## 3. Modes (presets), sampling, evaluation

### 3.1 Presets (`obs_v5.PRESETS`, slider order as 2.2)

| preset | camp | coll | prot | retr | kite | peek | focus | aggr | 3rd | bctl | leash | gas |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| balanced | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| bush_camper | 2 | 0.5 | 1 | 1.5 | 1 | 1 | 1 | 0 | 1.5 | 0.5 | 1 | 1.5 |
| aggressive | 0 | 0.5 | 1 | 0.5 | 0.3 | 0.5 | 2 | 2 | 0.5 | 0.5 | 1 | 0.5 |
| cube_farmer | 0.5 | 2 | 0.5 | 1.5 | 1 | 0.5 | 1 | 0.3 | 1 | 1 | 0.5 | 1.5 |
| third_partier | 1 | 1 | 0.5 | 1 | 1.5 | 1 | 1.5 | 0.3 | 2 | 1 | 0.5 | 1 |
| marksman | 0.5 | 1 | 0.5 | 1.5 | 2 | 1.5 | 1 | 0 | 1 | 1 | 0.5 | 1 |
| team_player | 0.5 | 0.5 | 2 | 1 | 1 | 1 | 2 | 1 | 0.5 | 0.5 | 2 | 1 |

Inference: `cond`'s slider part is `PRESETS[name]` (or any custom vector 0-2); `obs_v5.cond(..., sliders=preset_vec(name))`.
The live runtime exposes the 12 numbers as sliders and the preset names as buttons; nothing else changes.

### 3.2 Training-time sampling (`--slider-sample mix`, default `uniform` = current)

Per player per battle: 40 % uniform U(0, 2)^12 (coverage), 40 % preset-centred `clip(preset + N(0, 0.3), 0, 2)` with a
uniform preset choice, 10 % an exact preset, 10 % sparse (all 0.5, one or two random sliders at 2). The centred draws
put density where the user will steer; the uniform share keeps arbitrary mixes meaningful. Sampled in `slider_state`
from the battle tag: `tag["sliders"]` = {player: vector} overrides (evals, presets), else the sampler.

### 3.3 Evals

- `--eval-sliders balanced` (default `random` = current, A8): eval / evalb player 0 plays balanced.
- `--eval-presets bush_camper,aggressive,cube_farmer` (default none): per preset the same eval seeds 1..N, kind
  `evalp`, `tag["preset"]` -> paired comparisons (same seeds, same brawler / map).

### 3.4 Does a slider change behaviour? (scorecard)

Behaviour counters independent of the weights, accumulated in `sl["beh"]` per player and written to `row["beh"]`:
steps alive, in bush, `hid_vs`, engaged, in gas, margin < 2, mate in band, clumped (< 1 tile), mate-distance sum,
box damage, max / final cubes held, damage dealt, distance to nearest enemy in view / own range (range ratio).

scorecard adds:
- **per preset** (eval kind `evalp`): place, win, trade, plus the shares above, and the diff vs balanced with a paired
  SE. Pass rule (printed): bush_camper hidden share >= 1.5x balanced; aggressive engaged share >= 1.3x and dealt / min
  up; cube_farmer final cubes >= 1.3x and gas ticks not up; team_player clump share not up; every preset place within
  0.5 of balanced.
- **slider slopes** from training rows (random weights): OLS of each behaviour share on the 12 weights -> slope per
  (slider, metric) with a 95 % CI. A slider whose own metric slope is ~0 is dead (no effect learned); free, no extra
  battles.
- **memory check** (from replays, true positions; no extra battles): event = an enemy that I saw (visible last step)
  steps onto a bush tile and is now hidden from me (fair rule: bush, > 900 units) within 8 tiles. For N = 0.5 / 1 / 2 /
  4 s after the event, while it stays hidden and in place (moved < 1 tile): share of my attacks aimed within 20 deg of
  it, and the cosine of my move direction toward it. **No-memory baseline** = the same metrics toward a control bush
  tile at the same distance (+-1 tile) with no enemy, from the same frames (chance level for that geometry).
  Memory half-life = the first N where the metric drops below halfway between N = 0.5 and the control; reported per
  run (`mem_aim`, `mem_move`, `mem_half_s`). With aux heads (section 5) the `bush_enemy` probability over time since
  the event is a direct readout of the same thing. Controlled version: scenario `bush_memory` (section 6).

## 4. Intents (per-second goals)

### 4.1 Intent set (7 + none)

Target = a point given as an offset from the player (dx, dy in 10-tile units, like `ent` XY), optionally anchored to an
entity (an enemy / mate player, a box, a cube). Each has a radius and a max duration.

| id | intent | target / params | covers | achieved | max |
|---|---|---|---|---|---|
| 0 | none | — | free play | — | — |
| 1 | move_to | point (r = 1 tile) | "gas 1 tile away: moving east out of it", explore, reposition | d <= r | 4 s |
| 2 | avoid | point, radius R (default 8 tiles) | "2 players fighting 7 tiles NW: going the other way", disengage at low HP | d >= R | 4 s |
| 3 | hold | point, r = 1.5 tiles | "endgame, enemy in the safe zone: holding the gas edge", hold a choke | timeout while inside (success) | 5 s |
| 4 | engage | enemy player (anchored) | heuristic bot's engage, third party a low enemy | target eliminated after own damage in the last 2 s | 5 s |
| 5 | farm | box or cube (anchored, static) | box / cube farming | box destroyed with own box damage, or cube picked (`pl.cubes > 0` near it) | 5 s |
| 6 | regroup | mate player (anchored) | heuristic bot's leash | 450 <= d <= 1200 | 3 s |
| 7 | hide | bush tile | bush camping, low-HP regen | on the tile with `hid_vs` or no enemy in view | 5 s |

Invalid (ends, no bonus): target player eliminated / respawning (by someone else for engage), anchored target not seen
by me for 1 s (fair `sees` rule), farm target in gas, me knocked out. After any end the intent is `none` until the next
planner tick; an achieved end triggers a re-plan on the next decision.

### 4.2 Observation (OBS_VERSION bump, separate block)

`o["intent"]` (B, N_INT = 11): one-hot 7 (none = all zeros) | dx, dy (10-tile units, clip +-2.5) | radius / 10 tiles |
time left (1 -> 0). The policy input becomes `s = cat[self (8), cond (N_COND), intent (11)]`. All new columns are at the
**tail** of `s`, so `vec.0.weight` (128, in) pads with zero columns and old checkpoints act the same; free play
(`none` = zeros) is exactly the old input. Sim: the offset = target world point - true own position, with the episode's
detector jitter added (anchored targets follow the true object). Live: anchored targets re-anchor to the nearest
detection of their class within 1.5 tiles of the predicted offset; point targets dead-reckon by own velocity (<= 5 s,
small drift). One shared `intent.encode` for both.

### 4.3 Intent-following reward (scaled to steer, never to beat placement)

Per step, `d` = true distance in tiles to the target, `Δ = d_prev - d` (signed: no dithering profit), c = 0.01 per tile:

| intent | per step | end bonus |
|---|---|---|
| move_to | `c * Δ` | +0.03 achieved |
| avoid | `c * (d - d_prev)` while d < R | +0.03 achieved |
| hold | `c * Δ` while d > r, `+0.002` while d <= r | — |
| engage | `c * Δ` while d > 0.8 range, `+0.5 * dk` while the target is in range | +0.05 achieved |
| farm | `c * Δ`, `+0.2 * box / 1000` (box target) | +0.03 achieved |
| regroup | `c * Δ` while d > 1200 units, `-c * Δ` while d < 450 | +0.02 achieved |
| hide | `c * Δ`, `+0.002 * hid_vs` on the tile | +0.02 achieved |

Signed progress telescopes: an intent's total is <= c x start distance + bonus <= ~0.15. The reward is x
`--intent-scale` (default 0 = off, start 0.25): **<= 0.04 per intent, < 1/10 of one rank step (0.56)** and far under a
death (hp + remaining ranks), so a bad intent (engage at 20 % HP) is learnt to be refused, a cheap one followed.
Per battle (~60 non-none intents) <= ~2.4 at full following, normally ~1. Logged: `i_rew` per transition, per episode
`intents` = {kind: [started, achieved, timeout, invalid]}.

### 4.4 Training: sampling, holding, ending

- BC phase: intents off (native AI ignores them).
- Per agent per battle: 30 % **free** (intent always none: protects free play), 70 % **steered**. In steered battles, at
  each planner tick (every 10 decisions, staggered by agent id, and right after an achieved end) with no active
  intent: 50 % the rule planner's choice (which may be none), 30 % a **random valid intent** (random kind among those
  with a valid target, random valid target), 20 % none for that second. The random share is what makes V(s, k) and
  "follow any goal" meaningful off the planner's distribution. Overall none share ~ 55 %.
- Preemption: at a planner tick the planner may replace an active intent only for the gas rule or a target change > 2
  tiles (hysteresis), never in random-intent episodes.
- Flags (all default off / current): `--intent-scale 0`, `--p-steer 0.7`, `--p-plan 0.5`, `--p-rand-intent 0.3`.

### 4.5 Rule planner (`planner.py`, `python -m planner` self-check)

`RulePlanner().plan(self8, ent, grid, rxry, cond, mem) -> (kind, target_dx_dy, radius, anchor, reason)`; reads only
what the policy sees (+ the camera tile offsets `obs_v5._cam`, which live also has), ~1 Hz, numpy, per agent.
Priority rules (first match), thresholds read from the slider part of cond (style-consistent plans):

1. gas: a poison tile within 2 tiles (or under me) -> move_to the nearest tile >= 3 tiles from poison, opposite the
   poison centroid. "gas 1 tile away: moving east out of it"
2. low HP (< 0.35) with an enemy within 1.2 range -> hide (bush away from it) if one within 4 tiles, else avoid(enemy,
   8). "hp 30 %, enemy 4 tiles N: disengaging S"
3. fight: two enemies within 4 tiles of each other and >= 4 tiles from me -> if third_party >= 1.2 and one < 40 % HP:
   engage it ("two fighting 6 tiles N, one at 30 %: third-partying"); else avoid(their centre, 10) ("2 players
   fighting 7 tiles NW: going the other way")
4. endgame: teams left <= 2 (cond HUD) and poison visible -> hold a point 1 tile inside the nearest gas edge, on the
   side away from the enemy. "endgame, enemy in the safe zone: holding the gas edge"
5. regroup: team size > 1 and the nearest visible mate > 4 tiles. "mate 7 tiles E: regrouping"
6. engage: an enemy in view with HP fraction < mine - 0.2, or within range and aggressive >= 1.2. "enemy 5 tiles E at 40 %: engaging"
7. farm: a cube in view -> farm it; else a box with no enemy within 6 tiles. "cube 3 tiles S: picking up"
8. hide: bush_camp >= 1.2, no enemy in view, bush within 5 tiles. "no enemy seen, bush 3 tiles W: hiding"
9. explore: no enemy, no box in view, map edge (out_of_bounds) visible -> move_to 6 tiles away from it. "map edge 5 tiles W: exploring E"
10. else none: "no plan fits: free play".

Self-check: one synthetic observation per rule asserting kind, direction sign and a reason substring; the fallback;
hysteresis; random-valid sampler only returns valid targets.

Use: `Env.intents(ids, o, cond)` (sim; called by train_ppo and train_fast after `ob.build`, so the reference and fast
paths share it and `test_fast` stays bit-equal) runs the tick logic, stores the world target per agent, returns the
(B, 11) block. The reward / end logic runs in `Env._finish_step` on true positions. Evals: `eval` stays free play;
`--eval-plan 1` adds kind `evalp_plan` (planner, same seeds) -> rank planner vs free, follow rate per kind.

### 4.6 Value-based plan choice (roadmap step 2)

- **Honest live value**: today `v = self.v(x) + self.vp(x, priv)`; `self.v` alone is biased (trained jointly with
  priv), and priv doesn't exist live. Add `vl` = MLP(d + HID -> 256 -> 1) on **detached** `cat[x, h]` (zero-init last
  layer): a probe that never changes the policy, trained by MSE to a TD(λ) return of the **base reward without the
  intent reward** (`rew - i_rew`; buffer gets a `rew_int` column; `vl` values for the λ-return from one no-grad pass
  over the rollout in the update, so the acting paths `fast_act` / `act_stacked` are unchanged). Without excluding
  `i_rew`, easy intents would score higher just for their own bonus. `--vlive 1` (default 0); progress logs
  `expl_var_live`.
- Scoring: `model.score_intents(net, s, ent, grid, h, blocks)` -> (K,) `vl` for K candidate intent blocks (the
  planner's valid candidates, one per kind, + none) from the current h, one batched forward. Pick argmax only if it
  beats the rule choice by > 0.05 (return units), else keep the rule choice; `none` scores too, so "no plan fits" falls
  out naturally. Logged per tick into the replay frame: `{"cands": [["farm", 0.62], ["avoid", 0.41], ["none", 0.38]],
  "pick": "farm", "reason": "..."}`; viz shows it. Eval kind `evalp_value` (`--eval-vplan 1`).
- Calibration check: on evalp_value rows, predicted `vl` of the pick vs realised base return (binned) in scorecard.
- Step 3 (later): a planner net over the same 8 kinds + target choice among the candidate set, trained on the scored
  ticks (distil the value choice) or by PPO at 1 Hz with `vl` advantages.

### 4.7 Sliders and intents together

Both are inputs (sliders in cond, intent in its own tail block), both rewards add: `rew = base + slider_scale * Σ
w_k NORM_k T_k + intent_scale * i_rew`. No override while an intent is active: sliders say *how* (stay hidden while
moving, keep range while engaging), intents say *what*. The planner reads the sliders (thresholds in 4.5), so a
bush_camper picks hide / avoid more, an aggressive one engage. If eval shows conflicts (e.g. bush_camp 2 refusing
move_to out of gas), add `--intent-slider-damp f` (slider reward x (1 - f) while an intent is active; default 0).

## 5. Auxiliary prediction heads (readable intermediate outputs)

Heads on `cat[x, h]` (trunk + GRU), trained alongside the policy, never used for acting. Their gradients flow into
the shared encoders / trunk / GRU (the point is a better representation) but not into the policy or value heads
(separate modules). Labels come from the sim's true state at train time only; live never needs them.

| head | output | label (true state) | horizon | loss | rel. weight |
|---|---|---|---|---|---|
| `fut` | per enemy-block slot (ent 0-8, class enemy): dx, dy of that enemy in 1 s, relative to my position now (10-tile units) | slot matched to the true player nearest its position at row j (gate 1.5 tiles, greedy); label = that player's true position at row j+10 minus mine at j, clip +-2.5 | 1 s (10 steps) | Huber (delta 0.1 = 1 tile), masked to present + matched slots with row j+10 in the same trajectory and the target alive | 1.0 |
| `hit` | P(I take enemy damage in the next 1 s) | any `te > 0` in rows j .. j+9 | 1 s | BCE | 0.5 |
| `gas` | gas margin (tiles / 10, 0 in gas) | `gas_margin` (2.2) at row j | now | Huber | 0.5 |
| `bush` | 8 sectors: P(an enemy hides in a bush there) | an alive enemy on a bush tile within 5 tiles, not visible to me (fair rule), by bearing sector | now | BCE, 8 multi-label | 0.5 |

- Head shapes: `fut` = per-slot MLP on `cat[x, h, ent_row]` (like `cand`: d + HID + F_IN -> 128 -> 2); the others one
  Linear(d + HID -> 128) + ReLU + Linear(128 -> 1 / 1 / 8). Module `self.aux` (ModuleDict).
- Loss: `--aux-w 0` (default = current behaviour: no aux loss, no gradient) x Σ rel. weight x head loss, added to the
  PPO / BC loss. Start `--aux-w 0.1` (PPO value coef is 0.5). Works in BC and PPO phases.
- Labels: `Env.aux_now(ids)` at poll time (like `priv`; train_fast: computed in the worker next to `priv_fast`)
  writes `tpos` (10 x 2 true positions, f32), `talive` (10), `me`, `gm`, `be` (8). `te` (enemy damage taken, /1000)
  goes into the transition terms in `Env._finish_step`. `fut` / `hit` are built at update time from the trajectory
  row lists (rows j+1..j+10), numpy, < 0.1 s per rollout.
- Checkpoints: new keys only (`aux.*`); old checkpoints load with strict=False and get fresh aux heads; frozen /
  league / eval nets never use them. `fast_act._stack` stacks only acting parameters (skip `aux.` and `vl.`: no extra
  weight memory per stacked net). Export for live may drop `aux.*`.
- Cost: buffer + ~45 numbers / row (~6 MB at 40 k rows); update forward + ~2-3 % (9 slots x a 128-wide MLP is small
  next to the grid conv); acting unchanged.
- Debugging readouts:
  - progress.jsonl: `aux_fut_tiles` (median error) next to `aux_fut_cv_tiles` (constant-velocity extrapolation from
    the slot's obs velocity: the head must beat it), `aux_hit_auc`, `aux_gas_mae_tiles`, `aux_bush_auc`; a viz chart
    "Aux readouts".
  - replays: the main process runs the aux heads on the one recorded row per poll (~0.3 ms, only when `--aux-w > 0`)
    and returns them with the actions; frames get `"x"` (predicted: per visible enemy the 1 s position, p_hit, gas
    tiles, 8 bush sectors) and `"xt"` (truth). viz draws predicted positions as hollow rings with an arrow, bush
    sectors as wedges, p_hit / gas as bars next to the truth.
- Placement: in **step C** together with the live value head: both add heads to model.py, update-time losses, buffer
  columns and the "skip non-acting params" rule in fast_act, and both are labels / targets the actor never sees. Two
  commits (C1 value head, C2 aux) in one PR, so a C2 problem can be reverted alone.

## 6. Hard-scenario eval set

Fixed seeded situations every checkpoint is scored on (FSD-style hard cases); failures go to the replay dashboard.
Shipped Showdown maps only (generated maps are not used for RL).

### 6.1 Setting a scenario up on this host (no host change)

1. RESET as usual: `seed`, `div` (location, `chr` per player, `team_groups`) via `make_div`; `act_tick` 200.
2. Scripted pre-roll inside `Env._start_battle` for `cfg["scenario"]`, synchronous on that instance, before
   `super()._start_battle` (so MAEnv's trackers start from the post-roll state):
   - `inst.setup(positions, ai_off, super_fill, unprotect)` (`CMD_SETUP`: teleport + stop + HP = max per player,
     native AI off, super charge fill, spawn protection off).
   - Low HP without a host change: teleport the player onto an edge tile, step M ticks with the storm forced to a ring
     that covers it (STEP `gas = k + 1`, `instance.step(storm=k)`) and `hold_mask` on it; the HP loss is deterministic
     (sim determinism, `t2_determinism.py`). Teleport heals, so teleports of *other* players come after and the damaged
     player is not teleported again.
   - Fewer players left (endgame): teleport the extra players deep into a forced ring and step until eliminated (gas
     ramps from 20 %/s); they count as gas eliminations.
   - Cubes on an enemy: a natural pre-roll (all native AI, ~60 s, fixed seed) and pick the enemy with the most cubes.
3. During the scenario: `Env._send_step` passes the scenario's forced storm ring each step (otherwise the clock model).
4. Positions are given as "nearest floor tile to (fx, fy) of the map" or "a bush tile within r of P" and resolved
   from `s.map_tiles` at setup (deterministic per map).
Fallback if the gas pre-roll proves too noisy: a small host patch `SETUP set_hp[i]` (deps change, recorded in
`host/training_round.patch`).

### 6.2 Scenarios (each: 2 maps x 2 brawler picks x 4 seeds = 16 episodes)

| name | setup | horizon | scored | pass |
|---|---|---|---|---|
| gas_endgame | 3 players left, ring forced to a ~5-tile zone, agent on the gas edge, an enemy inside | 30 s | survival, gas ticks, placement | outlives >= 1 enemy, gas damage < 20 % HP |
| third_party | two native enemies 3 tiles apart (fighting), 8 tiles from the agent, one pre-damaged to 40 % | 15 s | kill on the low one, damage taken | a kill, HP stays > 50 % |
| assassin_rush | agent marksman (Sniper) vs an assassin (Mortis / Edgar) 7 tiles away, AI on; others far, AI off | 15 s | survival, trade, mean distance | alive at the end or a kill |
| low_hp_close | agent at ~30 % HP, full-HP enemy 5 tiles away, a bush 3 tiles away | 15 s | survival, damage taken, time hidden | alive at the end |
| cube_rich_low | natural pre-roll, the cube-richest enemy damaged to ~35 %, agent teleported 6 tiles from it | 15 s | kill, cubes gained, survival | a kill and alive |
| mate_under_fire | trio, a mate 5 tiles away with two enemies 3 tiles from it, agent full HP | 15 s | mate alive, agent damage dealt, agent alive | mate and agent alive |
| bush_memory | an AI-off enemy visible 4 tiles away for 1 s, then teleported into an adjacent bush (hidden) | 5 s | aim / move toward it at 0.5 / 1 / 2 / 4 s vs a control bush (3.4) | attacks within 20 deg >= 2x control at 2 s |

Scores are per-episode numbers (not the reward), so they stay comparable when reward weights change.

### 6.3 Where it lives and what it costs

- `scenarios.py` (new): `SCENARIOS` specs, the position resolver, the pre-roll script, score / pass functions.
  `python -m scenarios --check`: specs valid, resolver on a synthetic map, score / pass on synthetic traces, every
  scenario pass rule reachable. `python -m scenarios --ckpt X --n 2`: standalone run (2 boots in parallel, 60-90 s).
- Trainer hook: `--eval-scenarios 0` (default off). On: each eval (or every `--scenario-every k`-th) queues the 112
  scenario battles on the eval instances as kind `scn:<name>`, played by the frozen eval copy; no extra boots.
- Results: `scenarios.jsonl` per eval {update, per scenario: pass rate, mean scores}; viz chart pass rate per scenario
  over updates. Every scenario episode is recorded (a Recorder on each worker, scenario kinds only) to
  `replays/scn/u<update>_<name>_<k>.json` with its pass / fail; the viz replay list shows failures first.
- Cost: 112 episodes x (~1 s reset + ~5 s pre-roll + 15-30 s horizon) ~ 2.6 k game-seconds per eval. Wall time = that
  / (sim speed-up x eval instances); measure it in the step's smoke run (at a 5x speed-up on 4 eval instances it is
  ~2-3 min). A synchronous pre-roll blocks its worker while it runs; switch to a non-blocking state if it costs > 5 %
  of worker time.
- Step **S**, after C and before D: it is the baseline that D / E (intents, planner) must not regress.

## 7. Phase-2 code changes, smallest useful step first

Each step = one PR, checks listed; OBS_VERSION bumps on top of the concurrent `v5.3`.

**Step A — slider fixes, NORM, presets, evals, scorecard (no obs change).**
- `env_v5.slider_terms`: A1-A8 fixes; `te`; `hid_vs`; `sl["mhit"]` countdown; `sl["beh"]` counters; Δheld from
  `cubes_total` (now held) with `sl["held"]`. `slider_state(..., w=None)`: weights from `tag["sliders"]` or
  `sample_sliders(rng, mode)`. `SLIDER_NORM` (all 1.0) applied in `_finish_step`; `sn_*` terms; `row["beh"]`.
  `env_v5 --norm RUN`. `_check`: each fix as an assert (respawn step pays no retreat, gas damage is not a hit, box term
  0.2, dithering earns nothing, mate-distance can't dodge protect, normalised terms).
- `obs_v5`: `PRESETS`, `preset_vec(name)` (+ asserts: shape, 0-2, names).
- train_ppo / train_fast flags: `--slider-norm FILE`, `--slider-sample uniform|mix`, `--eval-sliders random|balanced`,
  `--eval-presets LIST` (all default = current). Battle tags carry `sliders` / `preset`.
- `scorecard.py`: per-preset groups, paired diffs, pass rule, slider slopes; `--check` gets synthetic rows for both.
- Checks: `env_v5 --check`, `obs_v5`, `scorecard --check`, then one `train_ppo --smoke` host run.
- The term changes alter the reward only when `--slider-scale > 0` (default 0): say so in the PR.

*As built (commit c538c16):* `push` stays in slot 7 with a signed same-target closing fix (B replaces it with
`aggressive`); protect's proximity term is dropped now (comes back as `leash` in B); own range floored at 600 units
(Rock has no CastingRange); NORM measured on the native AI (`env_v5 --native 1`, 821 battles), `--slider-norm
measured`; eval rows of the policy now go to `eval_episodes.jsonl` (they never reached episodes.jsonl, so scorecard's
eval groups were empty).

**Step B — leash, gas_safe, aggressive (OBS v5.4).**
- `obs_v5.SLIDERS` += `leash`, `gas_safe`, `push` -> `aggressive`. `cond`: `stats 13 | sliders[:10] | team 3 | hud 2 |
  sliders[10:]` (tail append, so the generic pad zero-fills the new `vec.0` columns), `COND_SLIDERS` = cond index per
  slider (consumers never hard-code), `N_COND = 30`, `OBS_VERSION = "v5.4"`. obs_v5 asserts the index map.
- `env_v5`: the two new terms, `gas_margin(x, y, tick, W, H)` helper (+ live_check assert vs `in_gas`).
- `model._check_stage2`: an old (N_COND 28) checkpoint acts the same; docstring `s = cat[self 8, cond 30]`.
- Checkpoints save `"obs_version"`; load prints a notice when it differs.
- Checks: `obs_v5`, `model`, `fast_obs`, `env_v5 --check`, `test_fast` (shapes), smoke.

*As built (commit 96d0e44):* gas ring = `NbeResp.reserved[0]` (latched storm step, the host's exact rule; live_check
100 % agreement with in_gas); normalisation = mean per-battle sum of |term| (`sa_*`), team sliders over team battles
only; NORM_MEASURED re-measured for all 12 (778 native battles); scorecard rules with undefined metrics are n/a.

**Step C — live value head + aux heads (no obs change).** C1: `model.Policy.vl` (zero-init), `value_live(x, h)`;
trainer `--vlive`, `rew_int` buffer column (zeros until D), second λ-return, `expl_var_live`. C2: `model.Policy.aux`
(section 5), `aux_losses(...)`, `--aux-w 0`; `Env.aux_now` + `te` term; buffer columns `tpos talive me gm be te`;
worker shm block + `fast_obs.aux_fast`; update-time label builder (`train_ppo.aux_labels`, shared by train_fast);
readout row for the recorder; viz chart + replay overlay. fast_act: stack only acting params; `_check` that
`act_block` outputs are unchanged with `vl` / `aux` present. model `_check`: aux shapes, masked losses, old checkpoint
acts the same. Checks: `model`, `fast_act`, `fast_obs`, `env_v5 --check`, `test_fast`, smoke.

**Step S — hard-scenario eval set.** `scenarios.py` (6.3) + `--check`; `Env._start_battle` pre-roll and
`Env._send_step` storm override for `cfg["scenario"]`; trainer `--eval-scenarios 0`, `--scenario-every`;
`scenarios.jsonl`, scenario recorders, viz list. scorecard memory check (3.4). Checks: `scenarios --check`,
`env_v5 --check`, one host run `python -m scenarios --ckpt <bc.pt> --n 2` (2 boots), smoke.

**Step D — intent input + reward with random valid intents only (OBS v5.5).**
- `obs_v5`: `INTENTS`, `N_INT = 11`, `N_S = N_SELF + N_COND + N_INT`; `intent.py` (new): kind specs (radius, max
  duration, end rules), `encode`, `step_reward`, random-valid sampler; `python -m intent` asserts (telescoping total,
  bonus only once, invalid on target loss, per-intent cap <= 0.15, none = zeros).
- `env_v5.Env.intents(ids, o, cond)` + reward / ends in `_finish_step`; `i_rew`, `rew_int`, episode `intents` counts.
- `model` / `fast_act` / `train_ppo` / `train_fast` / `test_fast`: `NS` -> `O.N_S`; `s` gets the intent block.
  `model._check_stage2`: old checkpoint + zero intent block acts the same.
- Flags: `--intent-scale 0`, `--p-steer`, `--p-rand-intent` (planner share 0 until E). Replay frames carry `"i"`.
- Checks: `intent`, `obs_v5`, `model`, `fast_obs`, `env_v5 --check`, `test_fast`, smoke.

**Step E — rule planner.** `planner.py` (+ self-check), `--p-plan`, `--eval-plan`, planner reason strings into replays
and viz; scorecard follow rate per kind, rank free vs planner. Checks: `planner`, smoke.

**Step F — value-based choice.** `model.score_intents`, `--eval-vplan`, candidate logging, scorecard calibration.

Never run long GPU jobs here; the user decides the training runs (suggested: Step A+B on the current trio run with
`--slider-scale 0.5 --slider-sample mix --slider-norm norm.json --eval-presets ...`).

Approved order: A, B, C, S, D, E (F later). Generated maps (`--gen`) are not used for RL and not touched.

## 8. Main risks

- Time-based terms (bush hiding, leash band, engagement) scale with survival; at the wrong scale they beat placement.
  Guard: NORM budget 0.5 per slider, `--slider-scale` set by the "no preset loses > 0.5 rank" check.
- Leash teaches clumping into AoE -> anti-clump band edge; the area-effect columns (v5.3) let the policy see the AoE.
- Cube farm vs gas -> gas gate, knock-out drops held cubes (host change), gas_safe high in the cube_farmer preset.
- Dead sliders (no behaviour change) -> slider slopes in scorecard; fix by raising that term's NORM.
- Intents overriding survival -> per-intent reward <= 0.04 at scale 0.25 (< 1/10 rank step); random intents teach refusal.
- Value-based choice on a biased value -> honest `vl` (no priv, no intent bonus), margin 0.05, calibration check.
- Aux heads pull the shared trunk away from what the policy needs -> small `--aux-w`, KL anchor, eval rank must not
  drop; `fut` labels hinge on slot -> player matching under noise (gate 1.5 tiles, masked when unmatched).
- Scenario pre-roll HP via gas is indirect (gas blocks regen for a while after) -> fixed per seed thanks to sim
  determinism; host `set_hp` patch as fallback.

---------------------------------------------------------------------------------------------------------------------

## As-built notes for step C (commits C1 = live value head, C2 = aux heads)

**Shared plumbing (C1).**
- `model.NONACT = ("vl.", "aux.")`: parameter prefixes acting never uses. `model.acting_params(net)` is what
  `fast_act.StackedActor._stack` (weights + version key) and `model.act_stacked` stack; both self-checks assert that
  randomising the NONACT weights leaves every acting output bit-equal. `test_fast` passes (real batches).
- The NONACT modules are built inside `torch.random.fork_rng(devices=[])` on their own seed (initial_seed + 1 / + 2),
  so `Policy()` under a given seed draws the same acting weights as before step C and the global CPU RNG stream is
  unchanged (with the flags off a run consumes the same random numbers as before).
- `Policy.seq(..., feats=True)` also returns `xc = cat[x, h]` (N * L, d + HID); `Policy.row_feats(s, ent, grid, h)` =
  cat[x, gru(x, h)] for single rows from their stored GRU input state (the acting math, no grad).
- Optimizers: the main Adam holds exactly the acting parameters, in the original order (old checkpoints' "opt" still
  loads); the NONACT heads have their own Adam (`opt_x`, saved as "opt_x", same lr schedule) and their own grad clip
  (0.5), so the main clip norm is not diluted by probe gradients. With both flags off the update is the same
  computation as before step C.
- `train_ppo` holds the shared helpers (train_fast imports them): `gae` (the old inline loop, same arithmetic),
  `expl_var`, `row_pass` (one no-grad pass over the rollout's rows, batches of 4096), `head_loss` (minibatch loss of the
  NONACT heads, returns stats), `split_params`, `TR_X` (transition terms the buffer keeps; train_fast workers send them).
- `python -m train_ppo --check` (new, no game): gae vs the inline formula, aux_labels on a synthetic trajectory, auc.

**C1: live value.** `Policy.vl` = Linear(768, 256) + ReLU + Linear(256, 1), zero-init last layer, on `xc.detach()`,
no priv (197 121 parameters). Flag `--vlive 0|1` (default 0). Target: its own lambda-return of `rew - rew_int`; buffer
column `rew_int` = transition term `"i_rew"` (no env writes it yet: zeros). **Step D: write the intent reward into the
transition terms as `"i_rew"` (and include it in `rew`); nothing else in the trainers needs to change.** Values for
the lambda-return come from `row_pass` over all buffer rows (pending rows bootstrap). Loss 0.5 x 0.5 MSE (as the
critic). progress.jsonl (only with the flag): `expl_var_live` (next to `expl_var` = the critic with priv),
`vloss_live`, `extra_s` (time of the targets / readout pass). viz: explained-variance chart shows both.
For step F: `net.value_live(net.row_feats(s, ent, grid, h))` scores a candidate input; `score_intents` does not exist yet.

**C2: aux heads.** `Policy.aux` (ModuleDict, 398 092 parameters): `fut` per enemy-block slot (ent 0-8) MLP on
cat[xc, ent row + lead] -> 2, `hit` / `gas` / `bush` MLPs on xc -> 1 / 1 / 8, all 128 wide. Not detached: gradients
reach the encoders / trunk / hemb / GRU; the model self-check asserts no gradient reaches pi / v / vp / cand / free /
free_score / vl. Flag `--aux-w W` (default 0 = no aux loss, no gradient; start 0.1), loss = W x sum(AUX_REL x head)
with AUX_REL fut 1.0, hit 0.5, gas 0.5, bush 0.5 (`model.aux_losses`), in BC and PPO phases, masked to alive rows.
- Labels at poll time: `env_v5.Env.aux_now(ids)` -> (B, 40) rows, layout `env_v5.AUX` (tpos 10 x 2 true positions in
  tiles, talive = alive non-respawning enemy, me, gm = gas margin in tiles from `gas_margin`, be = 8 sectors, sector k
  centred on k x 45 degrees, 0 = right, clockwise on the y-down screen). `te` = (damage_taken - gas_damage) / 1000 is
  in every transition's terms (`Env._finish_step`). Buffer columns tpos talive me gm be te (`Buffer.F.update` after the
  class). train_fast: computed in the worker, second shm block per worker (only with `--aux-w`).
- Update-time labels: `train_ppo.aux_labels` (numpy, ~0.1 s per 2 k rows on CPU incl. nothing heavy). fut: greedy
  slot -> true-enemy matching within 1.5 tiles of the seen position (relative to me at row j), label = that enemy's
  true position 10 rows later in the same trajectory minus mine at j, / 10 tiles, clip +-2.5, masked unless matched
  and the enemy is alive at j+10. hit: any te > 0 in rows j..j+9; known once 10 transitions follow, the trajectory
  ended (done), or a hit already came. gas: max(gm, 0) / 10. bush: be.
- Readouts (progress.jsonl, only with the flag; pre-update predictions from `row_pass` on the rows trained on):
  `aux_fut_tiles` (median error) next to `aux_fut_cv_tiles` (constant velocity from the slot's seen velocity, moved on
  by model.LAT ticks relative to me) and `aux_fut_still_tiles`; `aux_fut_n`, `aux_fut_match` (share of seen enemy slots
  matched to a true enemy = label coverage under noise), `aux_hit_auc`, `aux_hit_rate`, `aux_gas_mae_tiles`,
  `aux_bush_auc`, `aux_bush_rate`, `aux_loss_<head>`. viz: three "Aux" charts (only when the keys exist).
- Replays: with `--aux-w` the main process runs `train_ppo.aux_readout` (the learner's / acting net's aux heads) on the
  row the recorder will record (`Recorder.row`; train_fast: the worker sends its index, the readout goes back with the
  actions as a third reply element). Frames get `"x"` = {f: [[seen dx, dy, predicted dx, dy]...] per seen enemy slot
  (10-tile units), h: p_hit, g: gas tiles, b: 8 probs} and `"xt"` = {g: true gas margin, b: true sectors, h: enemy
  damage this step}. viz draws predicted 1 s positions (rings + arrows), the true positions 10 frames later (crosses),
  bush sector wedges (filled = predicted, outline = true) and p_hit / gas with the truth.

**Deviations from the doc (and why).**
- No `fast_obs.aux_fast`: one implementation (`Env.aux_now`, vectorised per poll like priv_fast) serves both trainers,
  so there is nothing to keep bit-equal.
- `fut` is parametrised as the slot's seen position + a zero-initialised MLP offset (starts at "stays where seen";
  the readout at update 1 equals `aux_fut_still_tiles`), instead of predicting the absolute offset from scratch.
- The NONACT heads get a separate Adam and grad clip (the doc did not say); needed so `--vlive` / aux heads do not
  change the policy's clipping and the old optimizer state keeps loading.
- `extra_s` is reported separately from `update_s` (the no-grad pass + labels run before the update loop).
- Revertability: C2 reverts on its own; C1 builds the plumbing C2 uses (row_pass, head_loss, TR_X, the optimizer
  split), so reverting C1 means reverting C2 first.

**Measured costs (CPU smoke, 2 instances, rollout 2048, 64-chunk minibatches; noisy: instances share the 4 cores).**
- Parameters: acting 2 393 858 (unchanged), + vl 197 121, + aux 398 092 (total 2 989 071). Stacked acting weights
  unchanged (NONACT skipped).
- update_s per update (BC / PPO / PPO): baseline 3.17 / 4.18 / 12.24 (the 12.2 overlapped an eval), --vlive 1:
  3.14 / 3.92 / 3.99 + extra_s 0.34-0.37; --vlive 1 --aux-w 0.1: 3.12 / 4.23 / 4.23 + extra_s 0.76-1.32 (labels +
  the pass). Acting is unchanged; on GPU the pass is a fraction of one epoch's forward.

**What step S / D must know.**
- S: aux readouts are a free memory-check signal: replay frames carry the `bush` sector probabilities per step
  (`"x".b`) and the true sectors (`"xt".b`), so the bush_memory scenario can read P(hidden enemy) over time directly.
- D: intent reward -> terms `"i_rew"` (excluded from the live value's target automatically). If the intent block is
  added to `s`, `row_feats` / `value_live` / aux heads need no change (they read `xc`); zero-pad `vec.0` as usual.
  `--vlive` must be on in the runs whose value is used for step F (V(s, k) needs a trained `vl`).
- A smoke shows early PPO rows with no enemy damage at all (the 1-update BC policy hardly fights): `aux_hit_auc` /
  `aux_bush_auc` are `null` when a rollout has one class only.
- Commits: C1 = 690fdbb, C2 = 0ebe377 (branch claude/focused-mayer-2c1pv8, not pushed). The README rows for C2
  (`--aux-w`, `python -m train_ppo --check`) landed in the unrelated commit 2bfe0fd; reverting C2 must also drop them.
  `git revert 0ebe377` applies cleanly (tested); `git revert 690fdbb` alone conflicts (C2 uses its plumbing).

---------------------------------------------------------------------------------------------------------------------

## As-built notes for step S (hard-scenario eval set)

**Files.** `scenarios.py` (new: specs, layout resolver, pre-roll, trace, scores / pass rules, summary, replay recorder
+ index, `--check`, standalone run), `env_v5.Env` hooks, `train_ppo` / `train_fast` flags + eval hook, `viz.html`
section, README row. No host change, no obs / action change (OBS_VERSION stays `v5.4`), fast paths untouched.

**Flags (both trainers, defaults = current behaviour).** `--eval-scenarios 0` (1 = the set joins the evals),
`--scenario-every 1` (on eval 0, k, 2k, ...), `--scenario-seeds 4` (layouts per scenario / map / pick; `--smoke` sets
1 = 28 episodes; > 4 reuses layouts with new battle seeds). Outputs: `scenarios.jsonl` (one row per scenario eval:
update, minutes, scn_s, episodes, invalid, per scenario {n, pass, mean of every score, pass_pick, pass_map}, `_all`),
`scenario_episodes.jsonl` (per episode: item, pass, scores, pre-roll info, rank), `replays/scn/u<update>_<name>_<map>_p<pick>_s<seed>.json`
+ `replays/scn/index.json` (newest 3 scenario evals kept, ~12 MB each). Scenario rows are not written to
episodes.jsonl / eval_episodes.jsonl (scorecard unchanged).

**How it runs.** Items queue on the eval instances as kind **`evalscn`** (tag `scn` = name, `item` = {name, loc,
pick, seed, update}) instead of the doc's `scn:<name>`: the existing `kind.startswith("eval")` routing then gives
them the frozen eval copy, keeps their rows out of the buffer and counts them in the eval's "busy" check with no
other change. `scenarios.battle_cfg(item)` returns the MAEnv cfg (own map, brawlers, trio groups, balanced sliders,
`ctl [0]`, end "agents", `cfg["scenario"]` = resolved layout). `Env._start_battle` calls `scenarios.preroll` (sync on
that instance) before MAEnv's trackers start; `Env._send_step` -> `scenarios.send_step` (events + forced storm ring
every step: 0, or the endgame zone); `Env._battle_over` ends at the horizon; `Env._finish_step` appends a trace row
and puts `row["scn"] = {name, item, battle, pre, scores, pass}` into the agent's episode row. A battle whose agent is
out after the set-up gives an episode row with `invalid` and no `scn` (0 in the 364 episodes of the final live runs). Replays: a
`scenarios.Recorder` on every worker (frames via the shared `train_ppo.replay_head / replay_frame`, also used by the
main Recorder now), the main process writes the index. viz: "Hard scenarios" section (pass rate per scenario chart,
latest table, replay picker sorted newest eval / failures first; plays in the existing replay view, with the
scenario's scores above the action line).

**Set-up facts measured on this host (probes S_probe*.log).**
- `Instance.setup(ai_off=...)` clears a bot's AI flag for good (env.c re-sets it per tick only for the local player):
  scenarios never use it; AI on / off = `native_mask` (a non-native, non-controlled player stands still).
- Storm pre-damage is exact: 20 % of max HP per hit (first 5 s), 3 hits = 40 % (7800 -> 3120 for Shelly), ~56 ticks;
  the stop is adaptive (step 2 ticks until hp <= target), so no noise -> the host `set_hp` fallback was not needed.
  Granularity is 20 %: the doc's 30 / 35 / 40 % all became 40 % (3 hits).
- Endgame: 7 extras deep in a forced ring are eliminated in ~82 ticks (storm eliminations, ranks 10..4).
- **damage_dealt in setup battles is fine**: the host clears NbePlayer damage_dealt / damage_taken after every response
  (per-step values). super_audit overwrote `dd` with the last step's value (hence 0); a controlled shooter's summed
  damage_dealt equals the target's HP loss (7800 = 7800). Normal battles / slider rewards were never affected (MAEnv
  reads it per step). super_audit fixed in its own commit.
- Sim speed in sim-only steps: 2000-2800 ticks/s per instance; the eval cost is the Python loop, not the sim.

**Scenarios as built** (agent = player 0; enemies AI on unless said; extras >= 16 tiles away, AI off; maps
Survival651 + Survival612 — only 4 of 25 shipped maps have an open 6 x 6 centre with 4 endgame layouts, the stage-1
map Survival604 has 1; picks = agent Piper (Sniper) / Shelly (ShotgunGirl) unless said):
| name | set-up | horizon | pass |
|---|---|---|---|
| gas_endgame | extras killed by a forced ring, zone forced to 6 x 6 (ring 27), agent on the zone's edge tile, Colt 3 + Shelly 4 tiles away inside | 30 s | outlived >= 1 enemy and gas damage < 20 % max HP |
| third_party | Shelly at 40 % 8 tiles away, Colt 3 tiles from her (7-11 from the agent) | 15 s | kills >= 1 and HP min > 50 % |
| assassin_rush | agent Piper, Mortis / Edgar (the 2 picks) 7 tiles away | 15 s | alive at the end or a kill |
| low_hp_close | agent at 40 %, Shelly 5 tiles away, a bush tile 3 tiles from the agent (>= 4 from the enemy) | 15 s | alive at the end (never down) |
| cube_rich_low | 45 s all-native natural pre-roll (agent healed by a teleport in place every 4 ticks), the enemy with the most cubes teleported 6 tiles from the agent and stormed to 40 %, others far, AI off | 15 s | that enemy killed by the agent and alive |
| mate_under_fire | trio, native mate (Shelly) 5 tiles away, Colt + Shelly (one team) 3 tiles from the mate, 5-9 from the agent | 15 s | mate and agent never knocked out |
| bush_memory | Shelly (AI off) 4 tiles away for 1 s, then teleported into an adjacent bush 3.4-5.5 tiles from the agent; control = another bush at the same distance +-1, >= 60 deg apart | 5 s | attacks within 20 deg of the hidden enemy in the 2 s after >= 2 x those toward the control, and >= 1 |
Scores (all from the episode's numbers): survived, t_alive_s, dealt_k, taken_k (enemy), gas_frac, kills, hp_min, plus
outlived / place, kill_low, mean_dist_tiles / trade, bush_s / hidden_s, kill_rich / rich_cubes / cubes_gained,
mate_up, and bush_memory's aim_e / aim_c / move_e / move_c at 0.5 / 1 / 2 / 4 s + revealed_s.

**Live results (112 episodes each, 2 instances; S_scn_*.log), pass rate native AI / fresh policy / BC-smoke:**
gas_endgame 0.12 / 0.38 / 0.44, third_party 0.38 / 0 / 0, assassin_rush 0.81 / 0.38 / 0.44, low_hp_close 0.44 / 0 / 0,
cube_rich_low 0.44 / 0.12 / 0, mate_under_fire 0.06 / 0 / 0, bush_memory 0.19 / 0.19 / 0 (the BC smoke never fires).
Reading: third_party, low_hp_close, cube_rich_low, assassin_rush separate the native AI from an untrained policy.
gas_endgame does not: the native AI walks out of the forced zone (it does not know the forced ring, gas_frac 0.26),
and standing still while the two enemies fight passes. bush_memory at chance is ~0.19 (random aim); the native AI does
not shoot into bushes. mate_under_fire is hard even for the native AI (mate survives 19 %). With n = 16 the SE of a
pass rate is ~0.12; read scores (hp_min, t_alive_s, aim_e_2 ...) next to pass rates, or raise --scenario-seeds.

**Cost (measured).** Standalone, 112 episodes on 2 instances after boot: 51-60 s (1058 game-seconds at ~9x realtime
per instance; pre-roll 0.05 s mean, 5 s total, cube_rich_low's natural pre-roll ~0.3 s). In the train_fast smoke
(2 instances, CPU acting) the eval with 28 scenario episodes took 37.9 s vs 29.9 s without -> ~0.3 s per episode, the
full set ~0.5-1 min on 2 eval instances, about half on 4. The synchronous pre-roll is ~4 % of the eval's instance time
(5 s of 120 instance-seconds) and 0 outside scenario evals, under the doc's 5 % bar: no non-blocking state was built.

**Deviations.** kind `evalscn` (above); maps 651 + 612 (604 lacks endgame layouts); 40 % instead of 30 / 35 %
(storm-hit granularity); gas_endgame anchors only 3 tiles apart (they sit on a 6-tile edge), others 6; the scorecard
replay-based memory check (3.4) is not built (bush_memory is the controlled version; aux "x".b covers the readout);
super_audit's damage fix is a separate commit.

**What step D / E must know.**
- Scenario battles go through `Env` like any battle: an intent block in `s` (D) is built for them by the same code;
  give them the `none` intent (or the planner's, E) through the tag, e.g. `tag["intent"]`, so their numbers compare
  across D / E. They are the "must not regress" baseline: compare scenarios.jsonl pass rates and scores at equal
  --scenario-seeds before / after.
- New scenarios: add a SCENARIOS entry (roles / who / ai / picks / pass in `score()`) and a pass + fail case to
  `_check`; `python -m scenarios --check` asserts 4 layouts on both maps.
- `scenarios.send_step` replaces MAEnv._send_step for scenario battles: any change to the step command there
  (e.g. new flags) must be mirrored.
- E's planner reason strings could go into scenario replays the same way (frames are built by replay_frame).

---------------------------------------------------------------------------------------------------------------------

## As-built notes for step D (intent input + intent-following reward, random valid intents; OBS v5.5)

**Files.** `intent.py` (new: SPEC, `encode`, `phi` / `new` / `step_reward`, `candidates` / `sample`, `python -m intent`),
`obs_v5` (INTENTS, N_INT 11, N_S 49, S_INT 38 = the block's offset in s, I_XY / I_RAD / I_LEFT, OBS_VERSION `v5.5`),
`env_v5.Env` (intents, reward / ends, counts), `model` (vec.0 width N_S), `fast_act` (NS = N_S), `train_ppo` / `train_fast`
(flags, `policy_s`, `intent_frame`, `intent_stats`, `load_opt`), `test_fast`, `scenarios` (tag + standalone run), viz
(intent target / radius in the policy view, kind + time left in the action line), README / AGENTS check lists.

**How intents are switched on.** Only by `--intent-scale S > 0` (both trainers; class attribute `Env.intent_scale`).
At 0 (default) `Env.intents` returns the zero block without touching any RNG or state, `_finish_step` skips the intent
step, transitions get no `i_rew` term, episode rows no `intents` keys: reward and outputs are those of step S. With
`S > 0`: `--p-steer 0.7` (agents per battle that get intents), `--p-rand-intent 0.3` (chance per planner tick of a random
valid intent, else none). There is no separate on-flag.

**Observation.** `s = cat[self 8, cond 30, intent 11]`; block = one-hot of kinds 1..7 | dx, dy (target - own position,
10-tile units, clip +-2.5) | radius / 10 tiles | time left 1 -> 0; `none` = all zeros = the v5.4 input exactly.
- Radius column per kind: move_to 1, avoid 8 (R), hold 1.5, engage 0.8 x own range (`sl["range"]`, floor 600 units),
  farm 1, regroup 4 (the band's outer edge), hide 0.5.
- Offset = the target's true world point (anchored players: where they are now; boxes / cubes: their exact position
  when sampled, static) minus the true own position, plus per-decision N(0, sigma) noise, sigma per agent and battle
  from `obs_v5.NOISE["jitter"]` (0 with `--noise 0`). Drawn from Env's own RNG stream (`Env._irng`, seeded from the Env
  seed), not ObsV5's, so the observation RNG streams (and fast_obs bit-equality) are untouched. The block is not
  latency-delayed (the intent comes from the planner side, not the camera).
- model: a fresh `Policy()` draws exactly the v5.4 weights under a given seed (checked against the v5.4 code: every
  tensor equal) plus 11 zero `vec.0` columns; v5.4 checkpoints load through the generic pad and act bit-identically
  with a zero or any intent block (`_check_v55`; also checked on the real smoke checkpoint `runs/ftS`, max |d| 0.0).

**Reward (intent.py, numbers chosen).** Every per-step progress term is a potential difference `c x (phi_prev - phi)`
(c = 0.01 per tile), so it telescopes exactly and dithering earns 0; the potential is capped per kind (`dcap`).
| kind | phi(d) | extra | bonus | max | worst-case total |
|---|---|---|---|---|---|
| move_to | min(d, 10) | — | 0.03 | 4 s | 0.13 |
| avoid | -min(d, 8) | — | 0.03 | 4 s | 0.11 |
| hold | min(max(d, 1.5), 5) | 0.002 / step inside | — | 5 s | 0.135 |
| engage | min(max(d - 0.8 range, 0), 5) | 0.5 x dk in range, <= 0.05 per intent | 0.05 | 5 s | 0.15 |
| farm | min(d, 8) | 0.2 x box / 1000 (box target), <= 0.03 per intent | 0.03 | 5 s | 0.14 |
| regroup | min(max(d - 4, 0), 10) + max(1.5 - d, 0) | — | 0.02 | 3 s | 0.12 |
| hide | min(d, 6) | 0.002 on the tile while hidden | 0.02 | 5 s | 0.08 |
Plus a hard per-intent cap CAP = 0.15 on the running total (`min(tot + r, CAP) - tot`, telescoping kept). Deviation:
the design's engage `+0.5 x dk` and farm `+0.2 x box` were unbounded (a 4300-HP box alone = 0.86, a 5 s fight several
points), so they got sub-caps; the base reward already pays damage / boxes. The step an intent goes invalid pays 0.
`python -m intent` asserts telescoping on random walks, the bonus once, invalid on target loss / knock-out, every kind's
best case <= CAP, none = zeros, the sampler.

**End rules as built.** achieved / timeout / invalid as section 4.1, with these concrete readings:
- engage: achieved when the target goes down (eliminated or respawning) in a step where I got a kill, or within 2 s
  (20 steps) of a step where I dealt damage, it was in my range and it took enemy damage (per-player damage only on this
  host); down otherwise = invalid.
- farm box: "destroyed" = no box within 1 tile of the point in my raw state2 row of that response (the host lists the
  nearest 6 boxes / 8 items at any distance; a full list ending before the point counts as present), read in
  `_finish_step` before MAEnv may reset the instance; achieved if I did box damage in the last 2 s, else invalid. Cube:
  achieved when I picked one up (`pl.cubes > 0`) within 1.5 tiles of it, gone otherwise = invalid. Target tile in the gas
  = invalid.
- "not seen for 1 s" applies to anchored targets only: enemies by the fair sees rule, mates by the screen rule (never
  bush-hidden), farm objects by the screen rule. Point targets (move_to / avoid / hold / hide) have no seen rule.
- hide: invalid if the tile stops being a bush (live mask); "hidden" = slider_terms' hid_vs or no enemy in my view.
- me knocked out / eliminated = invalid (so a respawning agent never carries an intent; no ticks while respawning).

**Ticks, sampling.** Per agent per battle (`Env._intent_agent`, first `intents()` call): free or steered (p_steer);
battles tagged `"intent": "none"` (eval, evalb, evalp, scenario battles) and native-AI battles (BC) are always free.
Tick = decision n with `(n + player) % 10 == 0`, or the decision right after an achieved end (`replan`). A tick only
acts when no intent is active (no preemption in D). `Env._choose`: one draw u; `u < p_plan` -> planner (None in D);
`u < p_plan + p_rand_intent` -> `intent.sample`; else none. With p_plan = 0 the planner's design share (50 %) falls to
none, so in D an idle steered agent starts an intent with 0.3 per second.
Random-valid sampler (`intent.candidates`, valid targets only; a random kind among the non-empty ones, then a random
target): move_to = walkable tile (floor / bush / slow / fast / ice) 3-8 tiles away, gas margin >= 1; avoid = a seen
enemy within 7 tiles (as a static point), else a tile 2-5 tiles away; hold = walkable 2-4 tiles, margin >= 1; engage =
a seen enemy within 12 tiles; farm = a box / cube in my fair state2 row, not in the gas; regroup = a mate on screen
outside the 1.5-4 tile band; hide = a bush tile on screen 1-6 tiles away, margin >= 1.

**Logging.** Transition term `"i_rew"` = intent_scale x the intent reward (it is inside `rew`; the trainers' `rew_int`
column, so `--vlive` excludes it with no other change). Episode rows: `intents` {kind: [started, achieved, timeout,
invalid]} (kinds with starts only), `intent_mode` free | steered, `terms.i_rew`, `ret` includes it. progress.jsonl (only
with S > 0): `t_i_rew`, `intents` (summed over the recent 400 rows), `intent_follow` (achieved / started), `steered`.
Replay frames: `"i"` = {k: kind, t: [dx, dy] (10-tile units, as the policy saw it), r: radius / 10, l: time left}.

**Also fixed here.** Resuming an older checkpoint: torch loads an Adam state whose moments are narrower than the grown
`vec.0` weight without complaint and the first step crashes; `train_ppo.load_opt` (both trainers) zero-pads such
moments like the weights (test in `train_ppo --check`; host: train_fast `--resume runs/ftS/ckpt_last.pt` (v5.4)
smoke ran 3 PPO updates). Both trainers print a notice when a checkpoint's obs_version differs.

**Checks (this container, CPU).** `intent`, `obs_v5`, `model`, `fast_obs`, `fast_act`, `env_v5 --check` (synthetic
battle: off = zeros / no state, tag none + BC free, staggered ticks p0 at 0 / p3 at 7, encoding, signed progress into
rew and `i_rew`, achieved -> re-plan off-tick, engage invalid / achieved, box broken via the raw row, episode row),
`train_ppo --check`, `scenarios --check`, `scorecard --check`, `apply_noise --test`. Host: `test_fast` with intents on
(p_steer = p_rand = 1: 6861 of 6951 rows carried an intent; acting max |d| 4.5e-5, allclose ratio 0.31; observations 0 of
400 polls differ); `train_ppo --smoke` (default: no intent keys anywhere, ckpt obs v5.5, vec.0 128 x 49);
`train_ppo --smoke --intent-scale 0.25 --vlive 1 --eval-scenarios 1` (28 scenario episodes, 0 replay frames with an
intent; evals free); `train_fast --smoke --intent-scale 0.25 --vlive 1`; the resume smoke above (replay u0003: 100 of
550 frames with "i"). The 1-update BC policy follows almost nothing (intent_follow 0.02-0.04, most ends are timeouts):
expected before training.

**What step E needs.**
- Planner hook: set `Env.planner` (an object with `plan(env, s, p, b, w, o, cond)` -> an `intent.new` candidate
  {kind, q (player, -1), pt (x, y units), obj ('box' / 'cube' / None), reason} or None) and `Env.p_plan`; add `--p-plan`
  and set it in `train_ppo.set_intents`. `w` = `Env._world(s)` (true positions, up, team, fair screen / sees, tiles,
  ring), `b` = the row in this poll (`o` = the observation rows, `cond` = env.cond rows; `self.last_vec[b]` = the fair
  state2 row). The planner must read only what the policy sees (+ `obs_v5._cam`); convert its observation-space
  targets to world points with the true own position, as `_scene` does for boxes / cubes.
- Preemption (gas rule / target moved > 2 tiles) is not built: `intents()` ticks only without an active intent. E adds
  a branch for `st["act"] is not None and tick` that asks the planner only; a random intent has `it["reason"] ==
  "random"` (never preempted, design 4.4).
- Reason strings: `it["reason"]` is kept per intent; add it to the replay frame next to `"i"` (`train_ppo.intent_frame`
  reads the block only; E needs the Env state there, e.g. a per-row reason list returned beside the block).
- `intent.candidates(scene)` is the valid-target set per kind (F's candidate scoring can reuse it).
- Evals with the planner (`--eval-plan`, kind `evalp_plan`) need a tag other than `"intent": "none"` (e.g. `"plan"`) and
  `_intent_agent` steering those battles with p_plan = 1; scenario battles stay `none` for D / E comparability.

## As-built notes for step BI (enemy brawler identity + line of sight; OBS v5.6)

**Files.** `obs_v5` (identity / LOS columns, `id_lut` / `hero_names` / `id_row` / `id_row_of_data`, `id_draws`,
`noisy_id`, `los`, NOISE `id_*`, `from_state2(..., who)`, `ObsV5.build(..., who=)`, `_check_id`, `--live` identity
census), `env_v5` (`Env.who` / `Env.last_who`, F_STATE in `_flags`, `heroes()` = `obs_v5.hero_names()` minus skip.json,
`_check_who`), `fast_obs` (same draws, slot moved to e[10], `who=`), `model` (`ENT_IN`, `_widen`, `pad_param`,
`_check_v56`), `train_ppo` (`load_opt(..., net=)`, `id_name` in replay frames, `who=env.last_who`), `train_fast`,
`scenarios`, `test_fast` (who recorded per poll), `viz.html` (given brawler name next to a known player in the policy
view), README.

**Entity row (F_ENT 20 -> 36).** Old columns unchanged (0 present, 1..10 class one-hot in ENT order, 11-12 dx dy,
13-14 vx vy, 15 hp, 16-19 area RAD / harms / helps / slows). New, at the end of the row:
| col | name | meaning |
|---|---|---|
| 20-32 (`ID0` .. `ID0 + 12`) | identity stats | `obs_v5.brawler_stats` of the row's brawler (player rows) or of the projectile's owner: 20 range (CastingRange / 30 = 10-tile units, the unit of dx / dy), 21 speed, 22 reload, 23 projectile speed, 24 spread, 25 bullets, 26 thrown, 27 melee, 28 hp, 29 super attack, 30 super charge, 31 super other, 32 super range |
| 33 (`ID_KNOWN`) | known | 1 = identity given; unknown = 13 zeros + 0 |
| 34 (`LOS`) | wall_between | enemy / teammate rows only (class cols 1 / 2): a projectile-blocking tile on the line me -> it |
| 35 (`LOS + 1`) | water_between | same rows: a movement-only tile (water, rope_fence) on that line |
Rows with identity: enemy and teammate (non-summon) rows of the enemy block, and projectile rows (both classes; the
own-projectile class `teammate_projectile` = my projectiles, always known). Summons, boxes, cubes, areas: zeros
(summons: live cannot tie a bear / turret to its owner's countdown name; deviation allowed by the brief, documented).
Noticed, not changed: the sim's class `teammate_projectile` is only MY projectiles (state2 projectile feature 5 = own);
a teammate's projectile is class `enemy_projectile` (its identity side is WHO_MATE, so it carries the mate's brawler).

**Where identity comes from (no host change).** The host already writes the snap2 dump the encoder reads into shared
memory every step (env.c: snap2 then write_obs); F_STATE only stops it zeroing `state_ints` (no other effect), so
`Env._flags` sets it and `Env.who` (called in `_gather`) reads the dump: player rows (team, controlled character),
characters (owner = [2], data id = [1]), projectiles (owner = [2]). Rows are matched by position: the encoder writes
dx, dy = float32((x - my x) / 3000), so the same float32 of the dump's positions equals the row exactly (ties of two
objects on one spot: the first in dump order). Brawler = the owner's character data id -> `id_lut` row (the tag's pick
for a player whose character is gone, e.g. a projectile of an eliminated player). `who` = (B, N_ENT, 3) int16
[player, id_lut row, side WHO_FOE 0 / WHO_MATE 1 / WHO_ME 2], -1 = none. `python -m obs_v5 --live` (300 decisions):
120 / 120 brawler rows owned, all on the right side, at the owner's true position, with its brawler, identity columns
= its stats; 788 / 788 projectile rows owned (own <-> feature 5, 44 from mates); summons / boxes / items never owned.

**Noise (per episode = per battle, obs RNG, fast_obs bit-equal).** `id_draws` runs at the end of `_episode`'s draws:
chances `id_known` U(0.2, 1.0) per enemy, `id_known_mate` U(0.8, 1.0), `id_wrong` U(0, 0.05) per known enemy,
`pj_owner_known` U(0.3, 1.0) per projectile row, then per player slot (16) u_known, u_wrong and a wrong-pick offset 1 ..
n-1 (never the true brawler). Player identity (known, given brawler) is a function of the episode draws only: FIXED per
player for the battle (live keeps it per track). Me: always known; mates: never wrong. A projectile row is known iff
its owner is known (and gets the owner's given brawler, wrong included) and this decision's link draw (one
`r.random((B, N_ENT))` after the seg draw) < pj_owner_known; own projectiles always. All ranges are GUESSES until the
live reader (countdown OCR + nickname per track; projectiles linked by origin) is measured (comment in NOISE).
Noise keys missing (custom noise dicts) = perfect identity; `noise=None` (trainer `--noise 0`) = clean = every owned
row known; `who=None` = every identity unknown (zeros). The extra draws shift the obs RNG stream (statistically the
same noise as before; no flag, as an obs version bump).

**Line of sight.** `obs_v5.los(ent, grid)`: LOS_N = 32 samples (t = (k + 0.5) / 32) on the straight line from my tile
centre (cell 12.5, 12.5) to the row's position (dx, dy x 10 tiles), my tile and the row's own tile left out, cells
outside the window ignored, UNKNOWN blocks nothing. `_BLOCK_PJ` = indestructible, destructible_wall, fragile_wall,
bouncer, gravity, destructible (Fragile), power_box (every tiles.csv row with BlocksMovement + BlocksProjectiles; power_box
for live); `_BLOCK_MV` = water, rope_fence. Noisy build: computed on the noisy rows and the noisy grid of the frame
(seg / HUD / bleed noise included), before the latency queue; clean: on the clean grid. Live computes the same from
its 25 x 25 grid and boxes. Real battles (random actions, 5950 rows): wall_between on 83 % of player rows (cluttered
maps), water_between 0.07 %. Cost: FastObsV5 build ~+20 % (64 rows: ~0.25 ms noisy_id, ~0.15 ms los).

**Model / checkpoints.** The new 16 input columns of `ent.0`, `cand.0` and `aux.fut.0` sit between the obs row and the
lead columns; a fresh Policy builds those layers at the v5.5 width (same RNG draws: checked tensor-equal against the
c6086a8 model under two seeds) and `_widen` inserts zero columns. `pad_param(name, v, o)` (load_state_dict and
`train_ppo.load_opt(..., net=)`, both trainers) maps an old input width after the x part: 16 -> v5.2 without lead,
18 -> v5.2 + lead, 22 -> v5.3-v5.5 + lead; other grown tensors pad at the tail as before. Real checkpoints t_D2 (v5.5)
and ftS (v5.4) loaded in the new Policy vs the c6086a8 model: logits, value and aux fut max |d| 0.0 with random
identity / LOS columns. `_check_v56` asserts the same on synthetic weights.

**What step E should read.** Per enemy row k of `o["ent"]` (slots 0-8, class col 1 = enemy): known = col 33; thrown =
col 26, melee = col 27, range = col 20 (10-tile units: compare with hypot(col 11, col 12) directly), super range = col
32, hp = col 28, speed = col 21; wall_between = col 34, water_between = col 35. Rules needing class skip when col 33 = 0
(e.g. "thrower behind a wall": col 33 and col 26 and col 34 -> approach around it or leave hypot(dx, dy) < col 20).
Constants: `obs_v5.ID0` (20), `ID_KNOWN` (33), `LOS` (34); stats order = `brawler_stats` docstring.

**Checks (this container, CPU).** `obs_v5` (`_check_id`: true stats + known 1 when given, zeros + 0 when not / who
None, summons / boxes / areas zero; wall on the line / off the line / water only / own tile / UNKNOWN; noisy: 400
battles x 6 decisions, player identity fixed per battle, known share 0.5 / 0.9 as set, id_wrong 1 never the truth,
mates never wrong, own always known, projectile links per decision ~0.5), `model` (`_check_v56`), `fast_obs` (with who),
`fast_act` (identity columns + weights random), `env_v5 --check` (`_check_who` on a synthetic dump), `intent`,
`train_ppo --check` (load_opt moment layout, `id_name`), `scenarios --check`, `scorecard --check`, `apply_noise --test`.
Host, one at a time: `obs_v5 --live` (census above); `test_fast` (intents on as D left it: 0 of 400 polls differ,
acting max |d| 4.2e-5 / allclose ratio 0.28, 2440 rows with a known brawler); `train_ppo --run t_BI0 --smoke` (ckpt
obs v5.6, ent.0 128 x 38, replay frames carry the given name); `train_fast --run t_BI1 --smoke --intent-scale 0.25`;
resume smokes `train_fast --smoke --resume runs/t_D2/ckpt_last.pt` (v5.5) and `runs/ftS/ckpt_last.pt` (v5.4): 3 PPO
updates each after the zero-pad notice. `live_check` not run (no host change). The first t_BI1 attempt ran out of its
0.2 h smoke budget while a CPU benchmark ran beside it; rerun alone: ok.

## As-built notes for step E (rule planner; no obs change, OBS_VERSION stays v5.6)

**Files.** `planner.py` (new: `RulePlanner.decide` on one agent's observation rows, `RulePlanner.plan` = the Env hook,
`resolve` (world target + anchors), `preempts`, `synth` (synthetic rows), `python -m planner`), `env_v5` (`_choose` /
`_plan` / `_preempt`, `_intent_agent` tag "plan", `last_why`, episode `plan_rules`, `_check_planner`), `train_ppo`
(`--p-plan`, `--eval-plan`, `set_intents`, `eval_intent`, `eval_plan`, `intent_stats` plan_rules, `intent_frame` "y" /
"iy", `policy_s` passes `o["i_why"]`), `train_fast` (same flags / eval kind), `scorecard` (`evalp_plan` group,
`intent_report`: follow rate per kind + rule census), `viz.html` (reason in the action line; `esc`), README row + check
list, AGENTS check list. No host change, obs / fast_obs / fast_act / model untouched (test_fast not needed: the intent
block is computed once per poll by Env.intents and shared by both paths, as in D). Scenarios: unchanged (tag "intent":
"none"; send_step untouched, no step-command change).

**Rules as built** (first match; dx, dy in tiles; reasons as printed by `python -m planner`):
| # | rule | fires when | intent | example reason |
|---|---|---|---|---|
| 1 | gas | solid poison within 2 tiles (or under me) | move_to nearest walkable tile >= 3 tiles from poison, away from the poison centroid | gas 2 tiles away: moving S out of it |
| 2 | low_hp | hp < clip(0.35 + 0.1 (retreat - 1), 0.25, 0.45), enemy within 1.2 x reach (known: max(col 20, col 32) x 10, cap 12; unknown: my range) | hide (bush 1-4 tiles, farther from it) else away | hp 30 %, Gunslinger 9 tiles N (reach 11 tiles): disengaging S |
| 3 | thrower_wall | KNOWN enemy, thrown (col 26), wall_between (col 34), d <= its range + 1, me no thrower | engage if hp >= 0.6 and (aggressive >= 1.2 or it < 50 %), else away | thrower TntDude 6 tiles NE behind a wall: leaving its range SW |
| 4 | keep_away | kite >= 0.5, KNOWN enemy with range <= 5.5 tiles (or melee col 27 and <= 8), d <= its range + 2, my range >= 1.5 x its | away | Undertaker (melee, range 3) 4 tiles E: keeping my distance W |
| 5 | fight | 2 enemies <= 4 tiles apart, both >= 4 from me, centre <= 10 tiles, one < 90 % | third_party >= 1.2 and one < 40 %: engage it; else away from the centre | two fighting 6 tiles N, one at 30 %: third-partying |
| 6 | endgame | teams left = 2, poison in view | hold a walkable tile 2.5-3.5 tiles from poison, <= 6 tiles from me, max (d_enemy - 0.5 d_me) | endgame (2 left), enemy 5 tiles E: holding the gas edge 2 tiles W |
| 7 | regroup | team > 1, nearest mate > clip(4 + 2 (1 - leash), 3, 6) tiles | regroup (anchored) | mate 7 tiles E: regrouping |
| 8 | engage | nearest enemy <= 12 tiles that is weaker (known: hp x col 28 < my hp - 0.2 my max, hit points; unknown: fraction < mine - 0.2) or in my range with aggressive >= 1.2 | engage | Blower 5 tiles NE at 100 % (4000 vs my 5700 hp): engaging |
| 9 | farm | a cube in view; else collect >= 0.5, a box, no enemy within 6 tiles of me; objects within 1.5 tiles of poison skipped | farm | cube 3 tiles S: picking up |
| 10 | hide | bush_camp >= 1.2, no enemy, not in a bush, bush 1-5 tiles | hide | no enemy seen, bush 3 tiles W: hiding |
| 11 | explore | no enemy, no box, >= 3 solid out_of_bounds tiles | move_to a walkable tile ~6 tiles away from their centroid | map edge 5 tiles W: exploring E |
| 12 | none | — | none | no plan fits: free play |

**Choices where the design left a detail open (simplest consistent option).**
- "Away from" a point: avoid(point, R 8) only when it is closer than 7 tiles (avoid is achieved at d >= 8: a farther
  point would pay the 0.03 bonus at once); else move_to a walkable tile ~4 tiles straight away. Applies to rules 2-5.
- Slider thresholds beyond the design's three (third_party / aggressive / bush_camp >= 1.2): low-HP threshold from
  retreat, regroup distance from leash, keep_away needs kite >= 0.5, boxes need collect >= 0.5.
- "Fighting" = two enemies close together AND one of them below 90 % (in teams two close enemies may be mates; damage is
  the cheapest "they are trading" evidence); only fights within 10 tiles (the census showed 12-13 tile "fights").
- Endgame = exactly 2 teams left (at 1 left nobody remains to hold against); hold point 2.5-3.5 tiles from poison (the
  gas rule fires within 2, so the hold point does not trigger it at once) and <= 6 tiles from me.
- Grid noise: a class counts only where a 4-neighbour has the same class (`_solid`: single wrong seg tiles are not gas /
  bush / map edge). Detector noise: with noisy obs (`RulePlanner(noisy=True)`; trainer sets noisy = --noise) a row counts
  only when confirmed: velocity != 0 (tracked >= 2 decisions; a new / false detection has velocity exactly 0 in the
  noisy path) or, players, identity known. Clean obs: every row (static objects have velocity 0 there). Live has both
  signals (track age, countdown names). This raised the census match rate of engage picks from 57 % to 91 %, farm 75 ->
  96 %, regroup 84 -> 99.7 % (false detections of a random class / hp were often picked).
- Own position inside the tile: `sub` from env.last_meta (live: the camera tile offsets of obs_v5._cam).
- World targets / anchors (`resolve`): offset + true own position; engage -> nearest enemy I see (fair rule) within 2
  tiles (jitter + 2 decisions of latency), regroup -> nearest mate on screen within 2, farm -> nearest box / cube of my
  fair state2 row within 1.5, hide -> nearest true bush tile within 1.5, move_to / hold -> snapped to a truly walkable
  tile within 1.5 (else as seen). Not matched -> no intent, reason + " (target not matched)", counted as picked, not started.
- Preemption (`planner.preempts`, at a tick with a held PLANNER intent; random intents never; none never): a
  higher-priority rule replaces it if it is gas or its target is > 2 tiles from the held one; the same rule re-targets
  if its target moved > 2 tiles. The replaced intent gets no end count (started > ends by the preemptions; its reward so
  far stays, telescoping is cut like a timeout). Every tick of a held planner intent calls the planner (no RNG).
- Planner share: `--p-plan P` (default 0.0 = Env.planner None = the D behaviour) uses D's one draw u per tick: u < P
  planner, u < P + p_rand_intent random, else none. Design numbers = `--p-plan 0.5 --p-rand-intent 0.3` (20 % none).
  `--p-plan` / `--eval-plan` without `--intent-scale > 0` exits with a message.
- `--eval-plan 1` (design 4.5, step E line): kind `evalp_plan`, the eval seeds vs 9 native, tag "intent": "plan" ->
  player 0 steered, every tick on the planner (no draw); evals.jsonl gets pl_episodes / pl_rank / pl_ci95 / pl_win /
  pl_top3 (compare with the free "eval" of the same seeds) + pl_follow + pl_rules; rows go to eval_episodes.jsonl;
  scorecard groups them as `evalp_plan`.
- Logs: episode rows `plan_rules` {rule: [picked, started, preempted]} (planner agents only), progress `plan_rules`
  (summed, only when present), replay frames "i".y = the active intent's reason ("random" for sampler intents), "iy" =
  the planner's reason for none (until the next tick). viz prints them in the action line. Scenario frames: none.

**Deviations from the design.** Rules 3 / 4 added (BI combat rules); rule 2 uses the known enemy's reach; rule 8
compares hit points for known enemies; `decide(self8, ent, grid, cond, sub)` instead of `plan(..., rxry, ..., mem)`
(no memory: the confirmation filter replaced what a memory would do); everything listed above.

**Checks (this container, CPU).** `planner` (every rule on its synthetic state with kind / direction sign / reason
substring, priority order on 11 overlapping states, identity rules skip ID_KNOWN 0, slider thresholds, gas / bush
single-tile noise, new detections ignored, clean mode, farm next to poison, fight range, preemption hysteresis),
`env_v5 --check` (`_check_planner`: pick anchored to the true player, last_why, plan_rules, same pick keeps the intent,
gas preempts at the next tick only, random intent never preempted, none / unmatched = no intent with reason, tag "plan",
episode row), `train_ppo --check` (intent_frame y / iy, plan_rules sums, eval_plan, eval_items, eval_intent),
`scorecard --check`, `intent`, `scenarios --check`, `apply_noise --test`, `obs_v5`, `fast_obs`, `fast_act`, `model`: all
ok. Default-flag equivalence (scratchpad E_equiv.py): db6c5ea's env_v5 vs this one, 5 seeds x 600 polls x 5 agents with
random intents on: every block, intent reward and the intents' RNG state identical. Host, one at a time:
`train_ppo --run t_E0 --smoke --intent-scale 0.25 --p-plan 0.5 --eval-plan 1 --eval-scenarios 1` ok (evalp_plan 4
episodes, tag plan, pl_* in evals.jsonl, 28 scenario episodes with 0 of 1884 frames carrying an intent, progress
plan_rules; both replays were BC battles); `train_fast --run t_E1 --smoke --resume runs/t_E0/ckpt_last.pt --intent-scale
0.25 --p-plan 0.5 --eval-plan 1` ok (replay u0003: 150 of 530 frames with an intent, all with "y": random 76, planner
reasons 74); `train_ppo --run t_E2 --smoke` (defaults) ok: no intents / plan_rules / i_rew / pl_ keys in any output, no
"i" / "iy" in replays.

**Live census** (scratchpad E_census.py, E_census*.log: 2 instances, 5 min, random maps / brawlers / teams, 3 agents per
battle on a scripted intent follower, p_plan 1, noisy obs; final version): 31 053 planner calls, 0.65 ms mean, 3.6 ms
p99. Share of calls (matched): gas 9.8 % (100 %), low_hp 3.0 % (99.6 %), thrower_wall 0.1 % (98 %), keep_away 0.6 %
(100 %), fight 0.4 % (100 %), endgame 10.3 % (100 %), regroup 9.6 % (99.7 %), engage 5.4 % (92 %; most misses name a
known brawler at low HP = it went down within the latency), farm 21.4 % (96 %), hide 6.1 % (99.8 %), explore 4.1 %
(100 %), none 28.9 %. Share of a rule's started intents that replaced a held planner intent (preemption): gas 39 %,
endgame 25 %, farm 26 %. Ends [started, achieved,
timeout, invalid] with the scripted follower: move_to 3218/2282/296/106, regroup 2203/1795/273/46, hide 1855/1406/45/85,
farm 2500/223/648/539 (the follower never shoots boxes), engage 657/133/150/206, hold 888/260/11/38, avoid 300/118/12/48.

**What step F / later should know.** `planner.RulePlanner.decide` is pure (rows in, pick out) and `View` exposes the
parsed rows; F can score the rule pick against `intent.candidates`. `endgame: holding the gas edge here` dominates the
endgame picks (the agent is already at a spot 2.5-3.5 tiles from poison; hold then pays 0.002 / step inside).
The farm rule takes the nearest box at any distance in view (seen up to 14 tiles); a distance cap is a later knob.

## As-built notes for the PR #9 port (gadgets, OBS v5.7)

**How.** `git merge origin/claude/project-thread-vpdumh` (0e52ec9, written against v5.2 as "obs v5.3") into the local
branch at main be6c3bb; every conflicted file was resolved from main's side with PR #9's change ported by hand, renamed
to OBS v5.7. Nothing of PR #9 was dropped. Changes on top of PR #9: fire_x is built on a forked RNG stream and
registered last; load_opt keeps an older Adam state (new tail parameters start fresh); scenario battles get no gadget
loadout; test_fast exercises the gadget class on real batches; gadgets.patch regenerated against main's patched deps.

**Observation / action (OBS_VERSION v5.7).** No input shape change: self 3 (always 0 before) = gadget usable now,
`from_state2(..., gadget=)` / `ObsV5.build(..., gadget=)` / `FastObsV5.build(..., gadget=)` (latency-delayed like the rest
of self). `obs_v5.FIRE = (none, attack, super, gadget)` = NbeAction.fire codes 0-3, `FIRE_READY = (None, None, 2, 3)`,
`FIRE_AIM = (F, T, T, T)`. The contract change is the fire head's class list (4 classes), hence the bump.

**Model.** `Policy.fire_x = Linear(768, N_FX = 1)`, zero-init, appended to pi's 3 fire logits (pi keeps its 28 outputs).
Built inside `fork_rng` after the aux heads: a fresh Policy draws exactly the v5.6 weights and the global CPU RNG stream is
unchanged (checked against be6c3bb's model.py under 3 seeds, scratchpad G_equiv.py); its parameters are the last two of
`acting_params` = the tail of the main Adam. vec.0's self-3 column starts at 0 (fresh) and is zeroed on loading a
checkpoint without fire_x (its weights were never trained: input always 0). `mask_fire` (replaces mask_super) masks super
by self 2 and gadget by self 3. Own `model.dist_logp_ent` (models4's masks only a 3-class head): aim counts for FIRE_AIM
classes, distance only for super; same draws and values as models4 on 3 classes (asserted). `masked_kl`: aim weighted by
P(an aiming class). fast_act: fire_x fused in the head matmul after free_score (existing columns keep their offsets),
`sample` uses FIRE_AIM; `_check` makes the gadget class live and asserts it is sampled only on rows with self 3.
`train_ppo.load_opt` -> `_opt_tail`: an optimizer state with fewer parameters per group (and moments that fit) gets
fresh ids for the appended ones (Adam starts them fresh), else fresh Adam as before. `train_ppo --check` covers it.

**Env / trainers.** `env_v5.gadget_cards` (cards.csv MetaType 5 by Target), `with_gadgets(cfg, rng)`,
`make_battle_fn(gadgets=)` (drawn last), `gadget_ready(r, p)`, `Env.gadget(ids)` from NbeResp gad_*. `--gadgets 1` (both
trainers, default 0): loadouts on every battle except scenario battles (cfg "scenario", kept comparable), drawn from
MAEnv's rng (rng_b unchanged); `ob.build(..., gadget=env.gadget(ids))`. `fire_hist` has len(FIRE) bins (one more 0 bin
with the defaults; viz already slices labels). Host: PR #9's gadget.c / NbeResp gad_* / proto.py / env.c unchanged;
host/gadgets.patch regenerated as a diff on top of training_round + fair_view + live_state (applies to be6c3bb's deps,
result identical). Host rebuilt (nbhost_rl, setup.sh's build line); SETUP.md notes that setup.sh rebuilds only when the
binary is missing.

**Gadget kinds on this host: none.** gadget.c g_impl is empty, so every gadget publishes kind NONE / 0 uses and self 3
stays 0; `--gadgets 1` therefore trains exactly like the defaults until a kind is implemented (fire_x gets no gradient).
Live gadget_check (3 min, before the check list was cut): gad_valid set, requested cards reach the host (332 691
agent-steps with a card, 29 140 without: brawlers with no gadget card), 18 085 fire 3 while not ready spent nothing,
Env.gadget agreed with the response.

**Checks.** Self-checks all ok: obs_v5, intent, planner, model, fast_obs, fast_act, env_v5 --check, train_ppo --check,
scenarios --check, scorecard --check, apply_noise --test, super_audit --check, gadget_check --check. Offline checkpoint
check (G_equiv.py): t_E0, t_E1, t_BI0 (v5.6), t_D2 (v5.5), ftS / C1_ft_vl (v5.4), ftA (v5.3) give the same logits / value /
act_stacked as be6c3bb's model (max |d| 0.0) with self 3 = 0; with self 3 = 1 only the gadget logit (0) is new. Host:
test_fast ok (intents on, --gadget-p 0.5: 400 polls, 0 observations differ, acting max |d| 4.7e-5 / allclose ratio 0.32,
1247 gadget actions sent, none while self 3 was off); train_ppo --run t_G0 --smoke --gadgets 1 ok (ckpt v5.7, fire_hist
4 bins). Run before the user cut the list, all ok: live gadget_check, live_check --n 2 --minutes 4, train_ppo --run t_G1
--smoke (defaults), train_ppo --run t_G2 --smoke --resume runs/t_E0 (v5.6: "optimizer state loaded; 2 parameters added
since start fresh"). Skipped (user: minimal checks): the train_fast --gadgets 1 --resume smoke (stopped mid-run).
Not done: AGENTS.md check list does not list `gadget_check --check` (README does).
