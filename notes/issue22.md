# Issue #22: guessed numbers, checked without game clips

Each number in #22 (and #32 item 7) was checked against the v68.279 game data (`bsrl-game/assets/csv_logic`) and public
sources (the fandom wiki, Supercell's release notes). 1 tile = 300 u, 1 tick = 50 ms.

## Changed

| Number | Was | Now | Source |
|---|---|---|---|
| Gadget uses per battle (`gadget.c` `GAD_USES`) | 3 | no limit, cooldown only (`NB_GAD_USES=3` restores 3) | Release notes, Feb 2025: gadgets "no longer have charges but are now based on cooldowns" and can be used "an unlimited amount of times in a match". The data's `accessories.csv` Cooldown agrees with the later notes (Bibi 400 ticks = 20 s, Feb 2026). |
| Meteor warning (`showdown_mods.c` `MET_WARN`) | 60 ticks | 50 (2.5 s) | `area_effects_logic` ExplosionSpawn TimeMs 2500; its skin row is the meteor area with the falling-meteor animation. The wiki says 3 s, likely rounded. |
| Mushroom growth (`MUSH_GROW`) | 60 ticks | 50 (2.5 s) | HealingSpawn TimeMs 2500, skin `healing_mushroom_area_effect`. Only the names link it to EventHealing. |

## Confirmed as they are

- Mico's landing hit: LeaperUltiAreaExplosion Radius 700, already read from the area. In the air 6 s (ActiveTime 6000, wiki).
- Piper's bombs: SniperBombExplosion Radius 600.
- Duo / Trio respawn: 17 s (`RespawnSeconds`) and 3 s of protection after it (wiki: "immunity shield for 3 seconds").
- Bibi's Vitamin Booster: CustomValue1 10 = 10 % of max hp per second for 4 s; on her power-1 hp that is 500/s, the
  card's and the Feb 2026 notes' 1000/s at power 11. The gap in #22 is the damage model's (below), not the gadget's.
- Meteor 2000 damage / 1200 radius, mushroom 1000 per second / 1000 radius / 5 s (already from the data).

## Still guesses: what would settle each

| Number | Where | Why it stays | Clip that settles it |
|---|---|---|---|
| Carl's spin hit radius, 300 | `superfix_moves.c` `WW_R` | No radius on WhirlwindUlti. The "700" in #32 is its CastingRange (the cast ring), not the hit radius. 300 matches the WhirlwindTrail area. Wiki: "a short radius". | Carl spins next to a dummy (training cave), stepping the dummy out a quarter tile at a time; note the last distance that still takes damage. |
| Bull's wall-break lane, 200 | `env.c` `CHARGE_WALL_R` | Not in the data. Wiki: "destroys any obstacles that he makes contact with". | Bull charges along a wall line, offset by half a tile, then one tile; count the tiles broken on each side. |
| El Primo's landing wall break, 300 | `env.c` `CHARGE_LAND_WALL_R` | LuchadorUlti has no area. Wiki: "in a radius around him". | El Primo lands in the middle of a block of walls; count the broken ring. |
| Mico's jump height and ramp, 700 / 6 ticks | `superfix_moves.c` `FJ_H`, `FJ_RAMP` | Not in the data. Only matters for what can hit him mid-air. | Any Mico super, slowed down: time from the jump to full height. |
| Storm schedule: first step at tick 440, one tile per 5 s | `env.c` `gas_step` | The phone agent's measured clock. Not in the data or on the wiki. | One full Solo Showdown from the start: the time of each ring change. |
| Storm damage: 20 % of max hp per second, +5 %/s after 5 s | `env.c` `gas_tick` | The phone agent's numbers. The wiki still says flat 1000 + 300; April 2026 notes add more damage deeper in the gas, with no amount. | A brawler standing at the gas edge and one 2 tiles in, with the damage numbers visible. |
| Meteor / mushroom first spawn, interval, how fast it shortens | `showdown_mods.c` `MET_FIRST`..`MUSH_GAP_MIN` | No column; wiki only says "more often as the match goes on". | One full match of each modifier: the time of every spawn. |
| Damage model: x2 at power 11 for damage, none for heals | `env.c` `my_root` | No level factor in the data. Heal areas have a `DamageScaleType` column (most heals 2), so heals likely scale in the game too; the wiki's power-level page is stale. | A power-11 brawler's hp at spawn and one hit and one heal (Pam's station) against a dummy. This one moves every battle, so do it first. |
| Byron's Shot in the Arm | `gadget.c` HEAL | CustomValue1 25; the card's numbers are code-filled. Sources disagree (800/s vs 597/s). | Byron uses it at full health minus a known amount; read the heal numbers. |
