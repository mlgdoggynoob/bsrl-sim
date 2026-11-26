# Issue #63: the four masked REPEAT gadgets

Branch `repeat-masked` from main bff4dde (2026-11-26). Game data and libg v68.279. Patch:
`engine/patches/repeat_masked.patch`, a diff on top of `facing_sync.patch`.

Darryl's BarrelBot_Spin (23000260), Fang's KickerDude_Mines (23000440), Bea's BeeSniper_ExtraBee (23000312) and Amber's
FireDude_FlameShield (23000488) ran the REPEAT code from #61 but stayed in `g_masked`. All four work now and are
unmasked (`gadget.c` g_masked, `super_audit.MASKED`, `desc_audit`'s check). Usable gadgets: 93 of 213 (was 89).

## Darryl: nothing was cut short

- The traced "stops ~1280 u out" was the shot touching the 1500 u target: 1500 - 100 (projectile Radius) - 120 (the
  target's CollisionRadius). 600 is one shot (300 = 240 x CustomValue3 125 %, x2 power level in env's damage root).
- The shot is a plain straight bullet (Speed 3044, no TravelType): libg flies it 2500 u in 16 ticks and ends it on the
  first character it hits. In a one-off run with a local edit that put the target 500 u away (not the audit's setting,
  which puts it at 1500 / 875 u), four of the 15 shots hit it (2400): a close target is hit by more than one shot.
- What was missing is the text's second half: "recharges his Super by <VALUE2>% if it hits enemies". Value code 10
  (0x90dc7c) is CustomValue6 / 40 = 1000 / 40 = 25 %. A kind-4 gadget shot gets no charge from libg, so
  `gadget_root_post` now adds CustomValue6 / 4000 of the full super (player +0x58) per enemy hit, capped at full.
  Live: one hit took player 0 from 1976 to 2976 of 4000. `super_audit` checks it: a spin_shoot row with CustomValue6
  expects `recharge` (the shooter's super charge rises by at least 90 % of one hit's CustomValue6 / 4000 during the
  watch, or up to full).
- CustomValue6 getter: 0xa93420 (column word 0x123f000 + 2096, after CustomValue5's 2092).

## Fang: a wrong constant in superfix_items.c

- "The kernels vanish ~670 u out" is the game's own rule: KickerDudeMinesProjectile has ConstantFlyTime (40 ticks of
  flight) and TriggerWithDelayMs 900, and the update 0xb70408 ends it at its trigger tick (start + 18): 1500 x 18 / 40
  = 675 u. The burst spawns KickerDudeGadgetExplosion (BulletExplosion), which spawnfix.c turns into 3 KickerDudeMine
  items (type 25) 600 u around it: 21 items per use, as traced.
- The items armed (+0x94 800 ms, 50 a tick); an enemy within TriggerRangeSubTiles (200: the audit's target) then
  started the fuse (+0x9c 2000 ms), and at 0 they vanished without a pop. An untriggered mine does not pop.
  `superfix_items.c` spawns the item's TriggerAreaEffect when the fuse runs out, but only for the types in FUSE_TYPES,
  and that constant was 0x4802020200005040: the movz / movk at 0xb6cf0c..0xb6cf20 build 0x4800020202005040 (types 6, 12,
  14, 25, 33, 41, 59, 62). The typo dropped type 25 (KickerDudeMine and Tick's ClusterMine) and added 49 (which libg
  never fuses, so nothing changes there). Fixed.
- Live after the fix: 21 "fuse out" pops (KickerDudeMineExplosion, Radius 468), 544 each (1360 x CustomValue3 40 %,
  the text's VALUE1), 5440 on the target (5 pops x 1088 with the x2 power level). A pop comes ~73 ticks after the fire,
  past the audit's 50-tick WATCH, so `_expected_gadget` now watches a repeat row whose projectile leaves items until they
  pop (`fuse_watch`: shots x CustomValue1 + (TriggerWithDelayMs + Value + Value2) / 50 + 20 = 108 ticks).
- Tick's ClusterMine is the same item type: his main attack's mines now pop too (see the checks below).

## Bea and Amber: TravelType 8 needs the circling fields

- The traced build had no `hyper.c` `circle_travel` (it came with `hyper_unmodelled.patch`), so libg's travel step
  0xb709e4 moved them to +0x94 / +0x98 = (0, 0). On main `circle_travel` writes that position, but:
  - `shoot()` uses the plain spawn 0xb78190, which leaves the circle angle +0x454 at 0: Amber's three flames sat on one
    point. libg's own circling spawn 0xb78c58 writes +0x454 and +0x415 = 1 after its 0xb78190 call (0xb790e0 /
    0xb790e4). `gadget.c` `rep_one` now does the same for a TravelType 8 projectile (data +0x210, getter 0xafab60),
    with the shot's aim angle. 0xb78c58 itself is not called: it re-spaces all of the owner's circling projectiles of
    the kind from its own clock and removes extras, which does not fit bees that leave one by one, and its last
    argument is a struct the NULL path skips differently. +0x415 makes the hit code (0xb740f0) call 0xb5a86c on the
    target, which only stores 6 at the target's +0x4a0 [?] (a hit-reaction state).
  - Bea's projectile has no ring radius (TravelTypeVariable empty, no spawner radius), so `circle_travel` returned early
    and the bees stayed at (0, 0). It now spirals such a projectile out from its owner: radius = Speed (560 u/s) x the
    projectile's own elapsed ticks / 20, angle = +0x454 + one turn over SteerLifeTime (97 ticks) [?]: the server's
    spiral is compiled out, these two rates are guesses (the bees end ~2700 u out, near Bea's 3000 u attack range).
    The radius alone grows at Speed and the turn comes on top, so a bee's path is about 3x its Speed on average.
  - The spiral is only for REPEAT gadget shots (`gadget.c` `gadget_rep_shot`, the per-player ring rep_one fills). R-T's
    hypercharged lasers (SplitterCirclingProjectile, spawned by libg's 0xb78c58) also have TravelType 8 and no radius:
    nothing in libg writes the ring radius +0x498 (it is only read, at 0xb70cf8, 0xb766a0, 0xb7671c and 0xb78d50), so
    they keep main's behaviour (left at the map origin, an older open problem, not touched here). The old hyper.c comment
    that said libg's Brawler_Splitter tick gives a radius of 1000 was wrong and is fixed.
- Lifetime (SteerLifeTime), the damage ramp (DamagePercentStart 35 -> End 100 over 0..850 promille of the life: "more
  damage the further they go") and the owner's death ending the flight stay libg's.
- Amber's card text: code 41 is the projectile's SteerLifeTime (100 ticks = the "5 seconds"), not CustomValue2 (450, the
  damage percent of code 51: 210 x 450 % = 945).
- Live: Bea's bees hit at 456 and 516 (228 / 258 x2: 38 % / 43 % of 600 a few ticks out), Amber's flames at 1890 a hit
  (945 x2), every 10 ticks while a flame overlaps the target (PiercesCharacters, DamagesConstantlyTickDelay 10), so a
  target on the ring took 4 hits (7560) in one run and 8 in another. How often a flame passes a target depends on
  `circle_travel`'s orbit speed (Speed read as units/s along the circle: ~9 s a lap at 800 u), hyper.c's guess for
  Melodie's notes too [?]; the game's flames may turn faster and hit fewer times per pass.
- `super_audit`: a ring row (Amber) puts its target on the ring (range TravelTypeVariable, dist_f 1.0, also on the
  retry: on_ring) and watches its SteerLifeTime; a spiral row (Bea) watches the volley plus SteerLifeTime. Not checked
  live (listed in the rows' notes): Bea's damage ramp with distance, Amber's hits per pass.

## A latent bug in gadget.c targets()

- The full run of `super_audit --gadget` on this branch crashed the host on Mico's gadget (signal 11 in `rep_fire`, solo
  too). `targets()` (Gene's and Mico's target list, from #61) tested `d2 >= d2s[k]` on its first insertion, before
  `d2s[k]` was written: with stack garbage below the distance it skipped the target but still counted it, so Mico's
  `env_obj_by_id` got an unset id and returned NULL. This branch's other changes moved the stack layout and exposed it.
  Fixed: the test only runs once the list is full, and Mico's path refuses when the target is gone. The same bug could
  drop Gene's nearest target (a "missing: damage" try in the first full run).

## Debug

`NB_REP_DBG=1`: for each REPEAT shot fired one at a time (not Mico's volley, which goes through `volley()`): its spawn
(from, angle, range, ticks), its position every tick for 120 ticks, its hits on brawlers (removed HP, enemy or ally) and
Darryl's charge. `NB_SUPERFIX_DBG=1` shows the mines' "fuse out" pops.

## Checks run (final build)

- `super_audit --gadget` (all 53): works 50, partial 3. Darryl works (600 damage, super charge +1636, `recharge` seen),
  Fang 4352, Bea 972, Amber 7560; Mico and Gene work on their retry. The 3 partials are not this branch's: Byron (heal
  missing when pre-damaged) and Mandy (damage) are partial on both attempts on plain origin/main too in the same
  two-brawler run; Shelly lost her damage to a neighbour's summon ("foreign summon near") and works alone.
  origin/main's own full run: works 48, partial 1, unverified 1 (its 49 rows, the four still masked).
- `--gadget-slot 1` (13): works 13 (3 on the retry).
- `--attack --only ClusterBombDude`: works at the default watch now (`fuse_watch`: 94 ticks; 3 ClusterMine pops, 1360).
- `--hyper --only Splitter,AxeJuggler`: R-T and Melodie work (R-T 7800 damage, 16 SplitterCirclingProjectile).
- `gadget_check` with a REPEAT roster and random: ok. `status_check` 25 scenes ok, `charge_check` 7 of 7, `test_fast`
  ok (0 of 400 polls differ), `train_ppo --run g --smoke --gadgets 1` ok, `live_check` ok, `showdown_check` ok.
- Self-checks: `super_audit`, `desc_audit`, `gadget_check`, `hyper_check`, `status_check`, `charge_check`,
  `showdown_check`, `star_audit`, `gear_check`, `env_v5` `--check`, `obs_v5`, `fast_obs`, `intent`, `planner`, `model`,
  `scorecard`, `apply_noise` ok (`export_policy --check` needs `onnx`, not installed in this venv).
