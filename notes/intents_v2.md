# Intents v2: cube-aware planner, then OBS v5.10 (plan, 2026-11-27)

Base: main bdd0e1c (OBS v5.9, `planner.py` 12 rules, `intent.py` 7 kinds). r51 (24 h Piper run) was trained without
intents (`--p-plan 0`, `--intent-scale 0`). This note replaces items 7 and 8 of the session handoff. Design background:
`behaviour_design.md` sections 4.1-4.6; the earlier web research: `pro_strategies.md`.

## 1. What the research says, and what it means here

Sources are community guides (mixed quality, mostly beginner level; no pro-team source). Rows marked *data* come from
this repo's game files or host measurements, not from guides.

| Tactic | Evidence | Where it goes |
|---|---|---|
| Each cube gives **+400 HP and +10 % damage** | *data*: `items.csv` BattleRoyaleBuff Value 10, Value2 400 | strength model (2.1) |
| A knocked-out player drops **min(cubes / 3 + 1, 5)** cubes (solo), not all of them | *data*: `issue21.md` (94 % of 1647 falls exact). Guides disagree (one cube / half / all) | strength model: a cube-rich kill pays less than its risk |
| Don't take even fights; poke, or a short trade | 1v1 guides (one borrowed from LoL dueling) | engage needs a clear edge (2.1) |
| Third-party only when someone is already low; don't get caught in the crossfire | showdown guides (several agree) | `fight` rule exists; target choice uses strength (2.1) |
| Collect cubes safely early, stay on the edges, avoid the early centre scrum | showdown guides | farm weighting (2.2) |
| Keep ammo in reserve; peek only with ammo to defend; reload first | ammo / counter guides | ammo gate on engage (2.1) |
| At low HP reset and heal fully; low-HP peeks get punished by divers | counter guide | re-engage threshold (2.1) |
| Leave the gas early; move inward as the zone shrinks ("rim early, centre late") | showdown guides | `rotate` rule (2.3) |
| An enemy hiding next to the gas: cut off its escape | showdown guide | `pin` rule (2.4) |
| Check bushes (shoot into them) before walking in or while breaking a box next to one | beginner + Knockout guides | new kind `check_bush` (3.2) |
| Charge the super safely, keep it for a finish or a surprise | Knockout guide, beginner guides | new kind `super` (3.2) |
| Team modes: focus one enemy, make 2v1s | `pro_strategies.md` | focus-fire target choice (2.5) |
| Bait (fake a retreat, pull an enemy into a bush or a mate) | no clear source found | left out |

## 2. PR A: planner fixes, no observation change (OBS stays v5.9)

### 2.1 Engage by strength, cube-aware (the owner's ask: a cube-rich enemy is a bad target)
- Strength of a player = effective HP x damage multiplier:
  `S = hp_frac x (base_hp + 400 c) x (1 + 0.1 c)`, c = cubes held. Mine: c from cond (own cubes, index 26 x 10),
  base_hp from cond 8. Enemy: base_hp from its known stats (ID0 + 8), else my own base_hp; c = **my own count as the
  prior** until OBS v5.10 gives the real one (3.1). Same cubes on both sides cancels, so today the only change for
  enemies is that the comparison uses strength instead of HP; once 3.1 lands the enemy's cubes count fully.
- Check first, then fix the formula if needed: whether the ent HP fraction's denominator already includes the cube HP
  (host encoder: hp / max_hp with max_hp = base + 400 c, or the base).
- Ratio `R = S_enemy / S_me`. Engage when `R < 0.7`, or `R < 1.0` with aggressive >= 1.2 and the enemy in my range.
- **Outclassed**: an enemy with `R >= 1.5` (e.g. same 3000-HP brawler, 4 cubes vs my 0, both full HP: 4600 x 1.4 / 3000 = 2.1) is never an engage
  target, and when it is within its reach + 2 tiles it triggers a new rule `outclassed` (after `keep_away`): away from
  it. Reason: "Shelly 5 tiles E, 6 cubes vs my 1 (x2.2 my strength): staying away" (same brawler, 3600 HP: 6000 x 1.6 / (4000 x 1.1)).
- Exception, finishing: an enemy below 25 % HP in my range is engaged whatever its cubes are (its drop is
  `c / 3 + 1`, and it dies before its damage bonus matters).
- Ammo gate: engage (and the third-party engage in `fight`) needs ammo >= 2/3 (self 1), except a finish.
- Heal reset: after `low_hp` fired, engage needs hp >= 0.8 (the planner is pure: read it as hp < 0.8 and no enemy in
  my range -> no new engage; a finish still goes).
- `fight` (third party): of the two fighters, take the one with the lowest strength, not the lowest HP fraction.

### 2.2 Farm weighting
- Score per box / cube = distance + 3 x (enemies within 6 tiles of it) - 2 x (the target is nearer the map edge than
  I am, while teams left >= 6: "edges early"); cubes keep their priority over boxes. Skip a target whose nearest enemy
  is closer to it than I am and stronger (R >= 1).
- A box next to a bush (<= 2 tiles) with no enemy seen: farm it anyway, but `check_bush` first once 3.2 exists.

### 2.3 `rotate` (before the ring closes, not only holding)
- Poison in view within 5 tiles (the `gas` rule keeps <= 2): move_to a walkable tile 5-7 tiles from the poison on the
  side away from its centroid, not toward a stronger enemy. Priority right after `gas`. Endgame `hold` stays for 2
  teams left, but its tile must be >= 3 tiles inside the poison edge (today 2.5-3.5).

### 2.4 `pin`
- A weaker enemy (R < 0.8) within 2 tiles of the poison and within 8 tiles of me: hold a tile between it and the
  safe side (its position + 2 tiles toward the side away from the poison centroid), so it must cross me or stay in
  the gas. Below `engage` in priority (engage it directly when in my range).

### 2.5 Team focus
- Team size > 1: the engage target is the enemy nearest to my nearest mate if that one is within 12 tiles of me and
  passes the strength test (2v1), else the solo choice.

### 2.6 Also in PR A (already approved)
- Wall-aware paths for `move_to` / `avoid` / `rotate`, reusing `overlay.path` A*, with a self-check.
- `work/runs/launch_ft_intents.sh`: fine-tune the best r51 checkpoint with `--p-plan 0.5 --p-rand-intent 0.3`
  `--intent-scale 0.25 --vlive 1`, `--eval-plan 1`, scorecard at the end.
- `python -m planner` self-check: one synthetic case per new behaviour (outclassed avoid, cube-rich finish, ammo
  gate, rotate direction, pin tile, focus target).
- One PR per change, as before. Rules stay numpy, deterministic, readable reasons.

## 3. PR B: OBS v5.10 (one bump, one BSRL catch-up)

### 3.1 Enemy cubes in the entity row
- `F_ENT` 36 -> 38: col 36 = cubes held / 10 (clip 2), col 37 = cubes known. Enemy and teammate rows only.
- Sim: `who` gives each row's owner player; `Env` passes `cubes` (B, N_ENT) from `NbePlayer.cubes_total` (0 after a
  team knock-out, as the HUD). fast_obs mirrors it; `test_fast` stays bit-equal.
- Noise (live-shaped): per track a "never read" chance and a per-decision +-1 misread chance, fixed per battle like the
  identity noise.
- Live (bsrl): the cube count drawn next to a player's HP bar, read per track on the HUD OCR worker (<= 1 Hz, like
  `brain/hud.py` and the countdown names). Unverified: the number's position and font size on a frame. Measure it on a
  recorded frame before building the reader.
- `model.load_state_dict` pads v5.9 checkpoints (zero columns after LOS, the `_OLD_ROW` path like v5.6), so r51 and
  the PR A fine-tune keep their outputs.
- Planner: `View.ecubes` from col 36 when col 37 is set, else the prior of 2.1.

### 3.2 Two new intent kinds (INTENTS 8 -> 10, N_INT 11 -> 13; block keeps dx, dy, radius, time left)

| id | kind | target | achieved | max | end bonus |
|---|---|---|---|---|---|
| 8 | super | enemy player (anchored) | my super's damage lands on the target | 3 s | 0.05 |
| 9 | check_bush | bush tile within my range | a main attack fired within 15 deg of the tile (0.03); if a hidden enemy was there, it is hit (0.05) | 2 s | as said |

- Invalid: super not ready (self 2 = 0) / ammo 0, target lost (same rules as engage), bush gone.
- Rules: `super` when ready and (the target is in super range and would drop below 0 after it, or a thrower behind a
  wall for a lob super), priority right after `low_hp`; `check_bush` before `hide` / `farm` next to an unchecked bush
  tile within my range, ammo >= 2/3, no enemy in view.
- Reward cap and scale as the existing kinds (CAP 0.15 x `--intent-scale`).
- Needs: `obs_v5.INTENTS`, `intent.SPEC` / `step_reward` (super damage and shot direction from the step's events: check
  the host publishes super damage separately from damage_dealt; if not, use the super fraction dropping to 0 + damage
  on the target in that step), `planner`, `overlay` text, `export_policy` spec, BSRL `brain/spec.py` / `adapter.py` /
  `policy.py` (refuses other versions) + the cube OCR.

### 3.3 Order and gates
1. PR A (no bump) -> review -> merge.
2. Intent fine-tune from the best r51 checkpoint with PR A's planner: does `evalp_plan` rank better than free play,
   and the follow rate per kind. If following does not help, fix that before adding kinds.
3. PR B (v5.10), with the BSRL catch-up in the bsrl repo (needs it attached with push access).
4. Step F (value-based intent choice), once an intent-trained policy with `--vlive 1` exists.

## 4. Open questions to check (cheap, no training)
- Ent HP fraction: is the cube HP in the denominator? (2.1)
- Duo / Trio drop caps (2 / 3, from `issue21.md`): the strength model is the same; only the "finish" value changes.
- Is the enemy cube count visible to the live client at every zoom, and for players in a bush you see? (3.1)

Sources (2026-11-27 searches; community guides): [pocketgamer showdown](https://www.pocketgamer.com/brawl-stars/brawl-stars-cheats-and-tips-everything-you-need-to-know-about-showdown-mode),
[samurai-gamers showdown](https://samurai-gamers.com/brawl-stars/showdown-guide),
[commonsensegamer solo showdown](https://commonsensegamer.com/brawl-stars-tips-and-tricks-for-solo-showdown/),
[boostroom solo showdown](https://boostroom.com/blog/solo-showdown-survival-guide-positioning-timing-and-matchups),
[boostroom counters](https://boostroom.com/blog/how-to-counter-popular-brawlers-matchup-tricks-that-win-games),
[boostroom knockout](https://boostroom.com/blog/knockout-guide-round-by-round-strategy-and-clutch-tips),
[pocketgamer beginner](https://www.pocketgamer.com/brawl-stars/brawl-stars-tips-and-tricks-a-guide-for-the-beginner-brawler/),
[esportstales Crow](https://www.esportstales.com/brawl-stars/crow-guide-abilities-strategies-tips),
[mobalytics dueling](https://mobalytics.gg/blog/lol-5-dueling-tips/), [game8](https://game8.co/games/Brawl-Stars/archives/316954),
[timesaver](https://timesaver.gg/blog/brawl-stars-best-brawlers-showdown-september-2026).

## As-built notes for PR A (planner only; OBS stays v5.9)

**Files.** `planner.py` (rules, strength model, wall-aware targets, `steps` / `path`, self-check, fine-tune command in
the docstring), `README.md` (rule table, file row). No change to the observation, `intent.py`, `env_v5`, the trainers,
`scorecard`, `viz.html` or `scenarios`: they take the rule names from `planner.RULES` (`train_ppo.intent_stats`, episode
`plan_rules`, scorecard's census, replay reasons), so the three new names flow through. `env_v5 --check`'s planner case
still passes unchanged (`synth` gained `ammo=1.0` and `mycubes=0`, defaults that keep its picks).

**HP fraction (2.1 check).** The entity HP column (and self 0) is `hp / maxHp` of the character (`encode.c`: `r[6] /
r[7]`; state2 chars cols 6 / 7 = libg +0x3c4 / +0x3c8, env.c's snap2 dump). The host raises +0x3c8 by 400 per cube held
(env.c: pickup, character change, knock-out loss; `live_check` item 10 checks max HP = 2 x Hitpoints + 400 x
cubes_total), so the denominator already holds the cube HP. Live, the HP bar is drawn against the same max. So
`hp_frac x (base + 400 c)` is the hit points now, and the formula needs no change, with one correction: base is the
power-11 max, 2 x characters.csv Hitpoints (`planner.POWER = 2`, the sim's level; live opponents below power 11 read
as slightly stronger than they are). cond 8 and ent ID0 + 8 carry the table value (/ 10000).

**Built (thresholds as in section 2 unless noted).**
- Strength `S = hp x (2 base + 400 c) x (1 + 0.1 c)`, `R = S_enemy / S_me`; enemy cubes `View.ecubes` = my count (one
  line in `View.__init__`; `decide(..., ecubes=)` overrides it: the self-check uses that, OBS v5.10 will fill it).
- Engage test (rule engage, team focus, fight's third party): <= 12 tiles; a finish (< 25 % and in my range) passes
  alone; else ammo >= 2/3, not healing (hp < 0.8 with no enemy in my range), and R < 0.7, or R < 1.0 in my range with
  aggressive >= 1.2. Solo order: finishes first, then the nearest. Team focus: my nearest mate within 12 tiles -> the
  enemy nearest to it when that one passes. An even fight (R = 1.0) is no longer an aggressive engage.
- `outclassed` (after `keep_away`): R >= 1.5 within its reach + 2 (reach: known max(range, super range) cap 12, unknown
  my range), not a finish -> away. With the prior it fires on HP alone (me at 60 % vs a full same brawler: x1.7) and on
  known tanks (Bull vs Piper, both full: 10000 / 5600 = x1.8, reach 11 + 2).
- `fight`: the weaker of the two by strength; third party needs the ammo gate (or a finish) and R < 1.5.
- `rotate` (after `gas`): poison within 5 tiles and not 2 teams left (else it would undo endgame's hold) -> a reachable
  walkable tile 5-7 tiles from the poison, away from its centroid, outside reach + 1 of every enemy with R >= 1 (dropped
  if that leaves nothing). Endgame hold band is now 3-4 tiles from the poison (was 2.5-3.5), within 6 steps.
- `pin` (after `engage`): R < 0.8, <= 8 tiles from me, <= 2 from the poison -> hold the reachable tile nearest to
  its position + 2 tiles away from the poison centroid. It fires when engage does not: 0.7 <= R < 0.8, or the ammo /
  heal gates block engage.
- Farm: score = distance + 3 x enemies within 6 tiles of the target - 2 if the target is nearer a seen map edge
  (solid out_of_bounds) than I am and >= 6 teams left; ties to the nearer one. Cubes before boxes. Skipped: within 1.5
  tiles of poison, or its nearest enemy is nearer to it than I am with R >= 1. Reason gets "(safer than the nearest)"
  when the score passed over a nearer target.
- Wall-aware targets: `View.steps` (numpy BFS, 8 neighbours, no corner cutting, over walkable + poison + UNKNOWN; a
  blocking tile counts only next to another, seg noise) is computed on first use. move_to / hold / hide tiles are
  picked among reachable tiles (gas / rotate by steps + 0.01 x distance), else the old straight pick. avoid: unchanged
  target; its reason names the escape direction around walls. `planner.path` = overlay.path's A*, so the drawn path and
  the planner agree (checked on 200 random grids against the overlay branch's copy: equal paths).
- Cost: 0.24 ms per call without a move target, ~1.1 ms with gas in view (BFS 0.4 ms; `dist_to` now uses the mask's
  rim only, same values, was 2.5 ms with a 9-column gas band).
- Fine-tune launch: `work/runs/` is gitignored, so the command (4-core r51 settings + `--intent-scale 0.25 --p-plan 0.5
  --p-rand-intent 0.3 --vlive 1 --eval-plan 1`, `--resume` the chosen checkpoint, scorecard after) sits at the end of
  the planner docstring; its flags parse with `train_fast.parse`.

**Self-check (`python -m planner`).** Every existing case, plus: strength numbers, `path` / `steps` (around a wall, no
corner cutting, unreachable, the two agree), gas exit around a wall, rotate direction / band / not at 2 left / away from
a stronger enemy, outclassed (Shelly 6 cubes vs my 1 = x2.5 with an `ecubes` override; the prior cancels; HP-only),
fight by strength and its ammo gate, cube-rich finish (Shelly 10 cubes at 20 %, me at 1 of 3 ammo), ammo gate, heal
reset, team focus, pin tile, farm weighting (enemy near / stronger enemy nearer / edge early), a walled-off bush, the
low-HP escape bending around a wall, and the priority order over 14 overlapping states. Also ok: `intent`, `obs_v5`,
`env_v5 --check`, `train_ppo --check`, `scenarios --check`, `scorecard.py --check`, `policy_video --check`.

**Changed picks to watch in the first census / fine-tune.** `outclassed` and the heal reset make the planner more
passive at mid HP; `rotate` sits above `low_hp` (as planned), so near the gas it moves inward before disengaging; the
thrower_wall engage has no ammo gate (not in the plan). Live census not run (no host boots in this PR).

**Deferred.** check_bush before farming a box next to a bush (3.2); the enemy cubes column (3.1: replace the one
`ecubes` line); duo / trio drop caps in the finish value; `resolve` still snaps world targets without a true-map path
check (overlay draws its own path on the true walk grid).
