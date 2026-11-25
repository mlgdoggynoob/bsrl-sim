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
- Bibi's Vitamin Booster: CustomValue1 10 = 10 % of max hp per second for 4 s. The sim's brawlers have their power-11 hp
  (Bibi 10000, below), so that is the card's and the Feb 2026 notes' 1000/s.
- Meteor 2000 damage / 1200 radius, mushroom 1000 per second / 1000 radius / 5 s (already from the data).

## Settled by the owner's clip: the damage and heal model (power 11)

The owner's screen recording (training cave, Pam at power 11): 10000 max hp (data Hitpoints 5000); her turret
(HealingStationHeal: Damage -10, DamageScaleType 2, Type Hot) healed +1400 a tick, ticks 1.0 s apart (8000 -> 9400 at
t = 8.6 s, -> 10000, capped, at 9.6 s). So heals are power-11 numbers like damage. `engine/patches/heal_scale.patch`.

How the sim models it (measured before the patch, a probe in a duo battle): brawlers spawn with their power-11 hp from
libg's own level table (Pam 10000, Shelly 7800 = 2 x 3900); damage is x2 in `env.c` `my_root` (one Shelly shot 3000);
summons keep their data hp (Pam's turret 3040), and libg's level scale 0xb565a8 is the identity (server code). The turret
healed 304 a second (10 % of its own 3040). Heals per path, after the patch:

| Heal | Where | Power 11 |
|---|---|---|
| Pam's turrets (normal and hypercharged) | `superfix.c` summon Hot | 14 % of Pam's max hp (`TURRET_HEAL_PCT`, the clip; the data says 10, the wiki 12 % "of Pam's maximum health"), every 20 ticks. `status_check` scene 16: +1400, +1400, 20 ticks apart. |
| Heal areas (Heal, Hot, HealRegen; hyper.c's heal on deploy) | area create 0xb2aefc hooked in `env.c` | the heal word x2, except DamageScaleType 2 of a brawler owner (already a percent of power-11 hp) |
| Status Healing (Byron's SnakeOilHot 380, Gus, Bull's gadget, ...) | `superfix_status.c` trigger | x2 (power-1 data) |
| Poco's super ally / own heal | `superfix.c` heal own | projectile Damage x HealOwnPercent x2 |
| R-T's rejoin | `superfix_moves.c` | card Value3 1000 x2 |
| Regeneration, lifesteal, gadget HEAL / HEAL_NOW (% of max hp or of damage taken), hyper.c's DamageScaleType 2 fallback | libg 0xb3adc4 / 0xb439c4, `gadget.c` | unchanged: a percent of power-11 hp or of power-11 damage |
| Berry's paint (660/s at P11) and dash heal (skill Damage x2) | `env.c` zones / charge | unchanged: already power-11 numbers (#5) |
| Showdown healing mushrooms (1000/s) | `showdown_mods.c` | unchanged: a mode number, not a brawler's |

`NB_HEAL_SCALE=0` turns the heal-area scaling off. A probe of healers under the native AI (two duo battles) saw libg heal
only through regeneration (0xb3adc4) and lifesteal (0xb439c4); the other 17 libg callers of 0xb41554 were not reached and
are left as they are. Not modelled: summons' power-11 hp (the turret still has 3040, half the game's), the hypercharged
turret's overheal shield.

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
| Byron's Shot in the Arm | `gadget.c` HEAL | CustomValue1 25; the card's numbers are code-filled. Sources disagree (800/s vs 597/s). | Byron uses it at full health minus a known amount; read the heal numbers. |
