# Issue #47: star powers, the compiled-out kinds

Branch `worktree-agent-a4db3fe68e24831c2`, 2026-11-25. Game data: v68.279 `csv_logic`, libg v68.279. Host change:
`engine/patches/star_powers2.patch` (on top of `gears.patch`). Check: `python -m star_check`.

## Result

Of the 215 star power cards (`cards.csv` MetaType 4, not Disabled), 15 ran in this build before (`star_audit.LIVE`, libg's
own readers). This branch adds **11**, each confirmed by a live A/B (carrier and control of the same brawler, the change
compared with the card's own Value columns), so `--star-powers 1` now hands out **26** cards:

| Card | Brawler | How | Check (2026-11-25, Survival642, one boot) |
|---|---|---|---|
| Driller_unique_2 `reduce_all_damage` 20 | Jacky | host: damage taken -V1 % | 3 of 3 hits 0.80 x the control's (936 -> 749) |
| BullDude_unique_2 `low_health_shield` 30, 30 | Bull | host: below V1 % hp, -V2 % damage taken | 11 hits judged, 3 below 30 % at 0.70 x, the rest equal |
| DoorMan_unique `reduce_damage_full_health` 50 | Gray | host: the hit taken at full hp -V1 % | first hit 0.50 x, the next two equal |
| Crow_unique_2 `prey_on_the_weak` 50, 30 | Crow | host: +V1 % damage dealt to a target at V2 % hp or less | poison ticks 160 -> 240 (1.500 x) on a target at <= 30 %, the first hit at full hp equal |
| BullDude_unique `berserker` 60 | Bull | host: below V1 % hp the reload doubles (+100 in the reload aggregate) | ammo regained 372 / 372 above 60 %, 744 / 372 = 2.000 below |
| AssaultShotgun_unique_2 `heal_continuous` 15, 40 | Griff | host: every V2 ticks V1 % of the missing hp | jumps of 358 = 15 % of 2387 missing, then 15 of 105; 40 ticks apart |
| Undertaker_unique `steal_souls` 20 | Mortis | host: a defeated brawler gives V1 % of max hp back | +2000 on the kill vs the control's +400 (20 % of 8000-8400 = 1600-1680 more) |
| HammerDude_unique `steal_souls2` 15, 12 | Frank | host: a defeated brawler gives +V1 % damage for V2 s (20 ticks / s) | swing 2668 within 12 s of the kill, 2320 after (1.150 x); the control 2320 / 2320 |
| TrickshotDude_unique_2 `trait_star_power` (component Values 40 / 10 / 35 / 60) | Rico | host: +35 % move speed below 40 % hp (a speed line crossing re-sends the move) | walked 741 / 756 above, 1013 / 756 = 1.340 below (want 1.35) |
| Gunslinger_unique `trait_star_power` (trait ColtSpeedSp, status 13 %) | Colt | libg itself (Traits attached at spawn) | walked 855 / 748 = 1.144 (want 1.13) |
| PowerLeveler_unique_2 `trait_star_power` (trait InstantChargeSuperPercentAtStart 100) | Surge | libg itself | super charge 4000 vs 0 at the start |

The last two are the probe's class "generic" (no lookup, the row lists Traits): the A/B shows libg runs them, so they
cost nothing. The other 6 "generic" cards were not measured (the effect is not a stat a short A/B reads: bouncing shots,
a wider spread, a super heal, a super's duration, an area slow) and stay out.

## How it is built (`engine/native/loader/starfx.c`, like `gear.c`)

- Per player, `starfx_reset_player` reads the card in the config (+0x08), its Type enum (card +0x100, libg's 0xaa9500)
  and Value1..3 (card +0x110 + 4 x (k - 1), libg's 0xaa9568), and picks the effect by the Type enum. The enums are what
  `star_audit` prints for the cards (82 reduce_all_damage, 38 low_health_shield, 150 reduce_damage_full_health, 2
  prey_on_the_weak, 7 berserker, 115 heal_continuous, 14 steal_souls, 25 steal_souls2). `trait_star_power` (305) is shared by
  all trait cards, so Rico's card is picked by its data id 23000156 (`star_check --check` asserts id and name agree).
- `env.c` (small hook points, all marked "star power round (issue #47)"): `my_root` calls `starfx_damage` for the damage
  dealt / taken modifiers, before the gear shield, which stays last; `record_event` calls `starfx_kill` when a brawler's hp
  reaches 0 (every damage path, Mortis's dash and Frank's hammer included, ends there; `my_root` alone missed
  the charge paths; `E.hid` gives the victim's player because a dead brawler no longer maps to one); `hyper_tick` calls
  `starfx_tick_player` (the periodic heal, and the speed line: a change re-sends the move, as gear.c does for bushes);
  `rec_move` calls `starfx_speed`; `div_publish` resets and publishes `star_*` (appended to `NbeResp` and `proto.py`).
  `superfix_status.c my_reload_pct` adds `starfx_reload_pct`.
- `NB_STAR_FX=0` turns the host effects off (the cards still reach the config).
- Equip is unchanged (`offline.c my_player_ctor`, div "star"); `env_v5.star_cards` / `with_star_powers` use
  `star_audit.equipped()` = `LIVE | star_check.LIVE`. Trainer `--star-powers` still defaults to 0.

Numbers: every one is a Value column of the card (or, for Rico, the component's Values the card text names), the time
unit is 20 ticks a second (the same as the gear texts). Judgement calls, marked [?]:
- [?] Crow's boost applies to every damage of the attacker but the storm, so poison ticks too (the check saw them at
  1.500 x); the card text says "attack and Super".
- [?] Driller's reduction and the other damage-taken cards skip the storm (as the gear shield).
- [?] Griff's heal timer runs from the start of the battle (first heal at tick V2), and only while hp < max.
- [?] DoorMan's "next damage taken" is the hit that finds hp at max; there is no time limit on it.
- [?] A kill that feeds Undertaker / Frank is any lethal hit of the player's brawler on another player's brawler (not
  the storm). A second kill inside Frank's window restarts it (no stacking).
- A kill also drops a power cube (+400 max hp, +10 % damage once picked up): `star_check` compares each Frank with
  itself before and after the buff ended, and Mortis with the control's gain, so the cube cancels out.

## The vtable hypothesis (notes/issue20.md, "the 22 with a sim site"): no

0xb3020c (medikit) is called only by 0xb2fe44, a lazy init of an object (flag +784) whose only caller is 0xb2def8 in
0xb2de2c; the 22 helpers 0xb3020c-0xb30620 are what that init runs. With `NB_STAR_VT=1` the host counts the calls:
the init runs about 10 000 times, with a player, **in the first battle of the boot (the client-mode battle)** and the
call counter then stops; in the sim-only battles training plays (`g_env_simonly`) it is not reached, and `star_audit`
sees type 59 asked 30 times at 0xb3027c in the client battle and never in the sim-only ones, with the card carried or not. So these readers belong to a client object (the one the notes call "the client's list +0xe0"),
not to the simulation; calling them for every sim character would fill fields of an object the sim does not have.
I also tried forcing the init flag at every call (`+784 = 0`): it only made the client battle query type 59 4000 times, nothing
in the sim-only battles. The 22 "none, sim site" cards are therefore not switched on by a call; each would need its effect
written by hand, like the 145. Probed with the four cards Shelly medikit, Mortis `faster_long_dash`, Mr. P
`explosion_damage_increase`, Byron `attack_pierce` (`star_audit --cards`, 2-3 rounds): class `none` for all four.

## What is not done, and why

Every card not above is listed below with its reason. The reasons, by group (counts are cards of the 215 minus the 26
that run):
- **flat hp / damage numbers (58)**: the card text shows the number unscaled (Barley +10 hp per attack, Poco 13, Penny 70,
  Gene 8 a second, ...) and the columns give no power level scaling; the real effect would be a guess. Plus a trigger
  (on attack, on hit, on a pickup) the host cannot see per brawler.
- **shape of a projectile, skill or area (52)**: range, speed, count, duration, extra effect on a hit; the Values are shape
  parameters for libg's skills, no host hook exists (host hooks are damage, heal, reload, speed, shield).
- **a status or crowd control (48)**: slows, stuns, roots, reveals, immunities, extra poison, invisibility speed; libg's skills
  and areas own the status apply; a card has no data-only hook.
- **a condition the host cannot read (about 20)**: the super's state (active, charged, used), a bar, heat, rage, bush /
  wall / water proximity, a gadget window, a pet or turret. Some have a number the data does not give: Samurai's reduction %
  (Value2 empty), Daredevil's seconds (Value2 empty), Wally's bush shield (Value2 60 unexplained).
- **generic, not measured (8)**: Spike's super heal, Surge's bounce, Griff's spread / salvo, Colette's super reduction,
  Conductor's ammo steal, Wendy's slow area, Max's super duration, Ziggy's next-attack damage (Traits / Components run by
  libg; not a stat a short A/B reads).
- Disabled cards (`Disabled` true: every `_unique_3`, Prototype rows) are not in the pool and not counted.

Per card (215 rows: the 15 libg reads, the 11 done, the rest with its reason):

| Card | Brawler | Type | Result |
|---|---|---|---|
| ShotgunGirl_unique | ShotgunGirl | ulti_give_status_effect_enemy | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Gunslinger_unique | Gunslinger | trait_star_power | DONE: generic (libg's own trait ColtSpeedSp): +13 % speed. Checked: walked distance 855 / 748 = 1.144 (want 1.13) |
| BullDude_unique | BullDude | berserker | DONE: berserker: below V1 % hp the reload doubles. Checked: ammo regained 1.000 x above 60 %, 2.000 x below |
| RocketGirl_unique | RocketGirl | more_bullets_ulti | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| TrickshotDude_unique | TrickshotDude | bounced_bullets_stronger | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Cactus_unique | Cactus | trait_star_power | generic (libg attaches its Traits / Components at spawn); the effect is not a stat a short A/B can measure (shot shape, super heal, super duration, area slow): not measured, not handed out |
| Barkeep_unique | Barkeep | heal_self_main_attack | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Mechanic_unique | Mechanic | repair_turret | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Shaman_unique | Shaman | pet_lifesteal | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| TntDude_unique | TntDude | pushback_self | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Luchador_unique | Luchador | fire_dot_ulti | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Undertaker_unique | Undertaker | steal_souls | DONE: steal_souls: a kill restores V1 % of max hp. Checked: +2000 vs the control's +400 (20 % of 8000 / 8400 = 1600 / 1680 more) |
| Crow_unique | Crow | cripple | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| DeadMariachi_unique | DeadMariachi | heal_main_attack | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| BowDude_unique | BowDude | spot | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Sniper_unique | Sniper | ambush | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| MinigunDude_unique | MinigunDude | heal_others_main_attack | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| BlackHole_unique | BlackHole | black_hole_monster | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| BarrelBot_unique | BarrelBot | barrel_defense | a damage reduction whose condition (super active, bar / shot charged, wall or bush proximity, heat, a gadget's window) the host cannot read, or whose number is missing (Samurai, Wally Value2): not implemented |
| ArtilleryDude_unique | ArtilleryDude | chain_spread | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| HammerDude_unique | HammerDude | steal_souls2 | DONE: steal_souls2: a kill gives +V1 % damage for V2 s. Checked: swing 2668 within 12 s, 2320 after (1.150 x); the control 1.000 x |
| HookDude_unique | HookDude | aoe_regenerate | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| ClusterBombDude_unique | ClusterBombDude | repair_self | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Ninja_unique | Ninja | speed_invisible | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Rosa_unique | Rosa | heal_forest | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Whirlwind_unique | Whirlwind | projectile_speed | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Baseball_unique | Baseball | speed_full_ammo | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| ShotgunGirl_unique_2 | ShotgunGirl | medikit | its condition is a state the host does not expose per brawler (the super's state, charge / rage / heat / tokens, an area or a bush / wall / water proximity, a pet or turret, the attack sequence) |
| Shaman_unique_2 | Shaman | pet_attack_speed | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| BullDude_unique_2 | BullDude | low_health_shield | DONE: low_health_shield: below V1 % hp, -V2 % damage taken. Checked: hits above 30 % equal the control's, below 0.70 x |
| Gunslinger_unique_2 | Gunslinger | attack_range | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| MinigunDude_unique_2 | MinigunDude | aoe_dot | its condition is a state the host does not expose per brawler (the super's state, charge / rage / heat / tokens, an area or a bush / wall / water proximity, a pet or turret, the attack sequence) |
| Luchador_unique_2 | Luchador | speed_after_ulti | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Ninja_unique_2 | Ninja | heal_invisible | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| ArtilleryDude_unique_2 | ArtilleryDude | ulti_spawn_explosion | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Crow_unique_2 | Crow | prey_on_the_weak | DONE: prey_on_the_weak: +V1 % damage dealt to a target at V2 % hp or less. Checked: poison ticks 160 -> 240 (1.500 x) on a target at <= 30 %, equal above |
| DeadMariachi_unique_2 | DeadMariachi | damage_super | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Whirlwind_unique_2 | Whirlwind | ulti_defense | a damage reduction whose condition (super active, bar / shot charged, wall or bush proximity, heat, a gadget's window) the host cannot read, or whose number is missing (Samurai, Wally Value2): not implemented |
| Baseball_unique_2 | Baseball | shield_homerun | a damage reduction whose condition (super active, bar / shot charged, wall or bush proximity, heat, a gadget's window) the host cannot read, or whose number is missing (Samurai, Wally Value2): not implemented |
| Rosa_unique_2 | Rosa | damage_buff_super | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| BowDude_unique_2 | BowDude | stun_trap | libg reads it (star_audit.LIVE, #20) |
| Mechanic_unique_2 | Mechanic | turret_electricity | libg reads it (star_audit.LIVE, #20) |
| RocketGirl_unique_2 | RocketGirl | extra_bullet | Brock's fourth ammo: the ammo capacity is a skill field (Value 1 = one more); no host hook, not measured |
| Cactus_unique_2 | Cactus | curve_ball | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Sniper_unique_2 | Sniper | reload_on_hit | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| HammerDude_unique_2 | HammerDude | gain_health | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Undertaker_unique_2 | Undertaker | faster_long_dash | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| TntDude_unique_2 | TntDude | gain_damage_super | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| TrickshotDude_unique_2 | TrickshotDude | trait_star_power | DONE: component: +35 % speed below 40 % hp (the component's Values 40 / 10 / 35 / 60; the text names Values[2] and Values[0]); libg has no reader |
| BarrelBot_unique_2 | BarrelBot | super_reload | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Barkeep_unique_2 | Barkeep | damage_main_attack | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| HookDude_unique_2 | HookDude | grapple_damage | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| BlackHole_unique_2 | BlackHole | black_hole_healer | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| ClusterBombDude_unique_2 | ClusterBombDude | recharge | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Arcade_unique | Arcade | larger_area_ulti | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Arcade_unique_2 | Arcade | plugged_in | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Sandstorm_unique | Sandstorm | aoe_dot | its condition is a state the host does not expose per brawler (the super's state, charge / rage / heat / tokens, an area or a bush / wall / water proximity, a pet or turret, the attack sequence) |
| Sandstorm_unique_2 | Sandstorm | aoe_dot | its condition is a state the host does not expose per brawler (the super's state, charge / rage / heat / tokens, an area or a bush / wall / water proximity, a pet or turret, the attack sequence) |
| BeeSniper_unique | BeeSniper | instant_charged_shot | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| BeeSniper_unique_2 | BeeSniper | shield_while_charged_shots | a damage reduction whose condition (super active, bar / shot charged, wall or bush proximity, heat, a gadget's window) the host cannot read, or whose number is missing (Samurai, Wally Value2): not implemented |
| Mummy_unique | Mummy | increase_dmg_consecutive_dot | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Mummy_unique_2 | Mummy | ulti_leach_health | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| SpawnerDude_unique | SpawnerDude | explosion_damage_increase | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| SpawnerDude_unique_2 | SpawnerDude | secondary_pet_buff | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Speedy_unique | Speedy | component_sp | generic (libg attaches its Traits / Components at spawn); the effect is not a stat a short A/B can measure (shot shape, super heal, super duration, area slow): not measured, not handed out |
| Speedy_unique_2 | Speedy | running_charges_weapon | libg reads it (star_audit.LIVE, #20) |
| Driller_unique | Driller | reflect_damage_aoe | a damage reduction whose condition (super active, bar / shot charged, wall or bush proximity, heat, a gadget's window) the host cannot read, or whose number is missing (Samurai, Wally Value2): not implemented |
| Driller_unique_2 | Driller | reduce_all_damage | DONE: reduce_all_damage: -V1 % damage taken. Checked: every hit 0.80 x the control's (3 / 3 hits) |
| Blower_unique | Blower | stun_wall_push | libg reads it (star_audit.LIVE, #20) |
| Blower_unique_2 | Blower | attack_gives_status_effect | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Controller_unique | Controller | increase_missile_dmg_over_distance | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Controller_unique_2 | Controller | shield_while_ulti | a damage reduction whose condition (super active, bar / shot charged, wall or bush proximity, heat, a gadget's window) the host cannot read, or whose number is missing (Samurai, Wally Value2): not implemented |
| Wally_unique | Wally | increased_explosion | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Wally_unique_2 | Wally | bush_shield | a damage reduction whose condition (super active, bar / shot charged, wall or bush proximity, heat, a gadget's window) the host cannot read, or whose number is missing (Samurai, Wally Value2): not implemented |
| PowerLeveler_unique | PowerLeveler | trait_star_power | generic (libg attaches its Traits / Components at spawn); the effect is not a stat a short A/B can measure (shot shape, super heal, super duration, area slow): not measured, not handed out |
| PowerLeveler_unique_2 | PowerLeveler | trait_star_power | DONE: generic (libg's own traits): super full at spawn. Checked: super charge 4000 vs 0 |
| Percenter_unique | Percenter | push_charge | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Percenter_unique_2 | Percenter | shield_charge | generic (libg attaches its Traits / Components at spawn); the effect is not a stat a short A/B can measure (shot shape, super heal, super duration, area slow): not measured, not handed out |
| FireDude_unique | FireDude | more_petrol | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| FireDude_unique_2 | FireDude | petrol_reload | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| IceDude_unique | IceDude | slippery_to_frost | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| IceDude_unique_2 | IceDude | freeze_damage | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| SnakeOil_unique | SnakeOil | suppress_heals | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| SnakeOil_unique_2 | SnakeOil | attack_pierce | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Enrager_unique | Enrager | charge_end_damage | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Enrager_unique_2 | Enrager | self_heal_increase | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Ruffs_unique | Ruffs | supply_bomb | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Ruffs_unique_2 | Ruffs | increase_team_health | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Roller_unique | Roller | increase_dodge_length | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Roller_unique_2 | Roller | heal_on_charge | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| ElectroSniper_unique | ElectroSniper | electro_shield | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| ElectroSniper_unique_2 | ElectroSniper | ulti_reload_debuff | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| StickyBomb_unique | StickyBomb | target_count_damage | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| StickyBomb_unique_2 | StickyBomb | ulti_area_status | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| CrossBomber_unique | CrossBomber | speed_ulti | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| CrossBomber_unique_2 | CrossBomber | grow_damage_shrapnel | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| RopeDude_unique | RopeDude | min_stun | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| RopeDude_unique_2 | RopeDude | super_charge_area | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| AssaultShotgun_unique | AssaultShotgun | trait_star_power | generic (libg attaches its Traits / Components at spawn); the effect is not a stat a short A/B can measure (shot shape, super heal, super duration, area slow): not measured, not handed out |
| AssaultShotgun_unique_2 | AssaultShotgun | heal_continuous | DONE: heal_continuous: every V2 ticks V1 % of the missing hp. Checked: jumps of 15 % of the missing hp, 40 ticks apart |
| Knight_unique | Knight | extra_rage | depends on Ash's rage meter, not exposed by the host |
| Knight_unique_2 | Knight | reload_from_rage | depends on Ash's rage meter, not exposed by the host |
| MechaDude_unique | MechaDude | downgrade_shield | a damage reduction whose condition (super active, bar / shot charged, wall or bush proximity, heat, a gadget's window) the host cannot read, or whose number is missing (Samurai, Wally Value2): not implemented |
| MechaDude_unique_2 | MechaDude | heal_ulti | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Duplicator_unique | Duplicator | last_shot_damage | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Duplicator_unique_2 | Duplicator | pet_healing_bullets | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| KickerDude_unique | KickerDude | charge_ulti_on_kill | needs to know the kill came from the super (the kill hook sees the attacker, not the skill) |
| KickerDude_unique_2 | KickerDude | reduce_damage_periodically | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Flea_unique | Flea | projectile_reversion | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Flea_unique_2 | Flea | spawn_pet_on_hit | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| JetpackGirl_unique | JetpackGirl | fly_vision | libg reads it (star_audit.LIVE, #20) |
| JetpackGirl_unique_2 | JetpackGirl | faster_focus | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| CannonGirl_unique | CannonGirl | ulti_range | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| CannonGirl_unique_2 | CannonGirl | attack_chain_count | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Silencer_unique | Silencer | item_lifetime_override | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Silencer_unique_2 | Silencer | more_bullets_attack | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| WeaponThrower_unique | WeaponThrower | weapon_pickup_heal | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| WeaponThrower_unique_2 | WeaponThrower | ulti_item_area | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| SoulCollector_unique | SoulCollector | item_healing_increased | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| SoulCollector_unique_2 | SoulCollector | ulti_damage_buff | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| ShieldTank_unique | ShieldTank | ally_area_increase_damage | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| ShieldTank_unique_2 | ShieldTank | ulti_cc_and_damage_reduction | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Jester_unique | Jester | attack_sequence_extra_damage | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Jester_unique_2 | Jester | show_next_ulti | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| DoorMan_unique | DoorMan | reduce_damage_full_health | DONE: reduce_damage_full_health: the hit taken at full hp -V1 %. Checked: first hit 0.50 x, the next ones equal |
| DoorMan_unique_2 | DoorMan | portal_healing | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Beamer_unique | Beamer | charged_bullet_speed | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Beamer_unique_2 | Beamer | shield_while_charged_up | a damage reduction whose condition (super active, bar / shot charged, wall or bush proximity, heat, a gadget's window) the host cannot read, or whose number is missing (Samurai, Wally Value2): not implemented |
| Splitter_unique | Splitter | tag_lasts_longer | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Splitter_unique_2 | Splitter | reduce_all_damage_splitter | a damage reduction whose condition (super active, bar / shot charged, wall or bush proximity, heat, a gadget's window) the host cannot read, or whose number is missing (Samurai, Wally Value2): not implemented |
| Puppeteer_unique | Puppeteer | reload_debuff | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Puppeteer_unique_2 | Puppeteer | ulti_movement_speed | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Maisie_unique | Maisie | attack_max_distance_damage | libg reads it (star_audit.LIVE, #20) |
| Maisie_unique_2 | Maisie | ulti_area_status | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| FishTank_unique | FishTank | charged_speed | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| FishTank_unique_2 | FishTank | wall_shield | a damage reduction whose condition (super active, bar / shot charged, wall or bush proximity, heat, a gadget's window) the host cannot read, or whose number is missing (Samurai, Wally Value2): not implemented |
| Duelist_unique | Duelist | attack_combo_damage | libg reads it (star_audit.LIVE, #20) |
| Duelist_unique_2 | Duelist | ulti_spawn_healing | libg reads it (star_audit.LIVE, #20) |
| Reviver_unique | Reviver | heal_after_lifesaver | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Reviver_unique_2 | Reviver | heal_self_scaled | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Cooker_unique | Cooker | ulti_consume_heat | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Cooker_unique_2 | Cooker | heat_shield | a damage reduction whose condition (super active, bar / shot charged, wall or bush proximity, heat, a gadget's window) the host cannot read, or whose number is missing (Samurai, Wally Value2): not implemented |
| Conductor_unique | Conductor | extra_sign | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Conductor_unique_2 | Conductor | charge_steal_ammo | generic (libg attaches its Traits / Components at spawn); the effect is not a stat a short A/B can measure (shot shape, super heal, super duration, area slow): not measured, not handed out |
| Cocooner_unique | Cocooner | cocoon_lose_health | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Cocooner_unique_2 | Cocooner | ulti_projectile_trail | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Leaper_unique | Leaper | attack_steal_ammo | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Leaper_unique_2 | Leaper | extra_damage_against_non_heroes | libg reads it (star_audit.LIVE, #20) |
| Attacher_unique | Attacher | double_power_cube | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Attacher_unique_2 | Attacher | longer_attach_friendly | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Twins_unique | Twins | transfer_damage_to_pet | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Twins_unique_2 | Twins | ammo_from_pet_damage | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| AxeJuggler_unique | AxeJuggler | movements_speed_from_projectiles | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| AxeJuggler_unique_2 | AxeJuggler | projectile_steer_lifetime | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| InsectMan_unique | InsectMan | super_area_heal | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| InsectMan_unique_2 | InsectMan | fast_water | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| DragonRider_unique | DragonRider | attack_gives_status_effect | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| DragonRider_unique_2 | DragonRider | ulti_heal_self | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Ambusher_unique | Ambusher | teleport_buff_next_attack | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Ambusher_unique_2 | Ambusher | enemy_area_increase_speed | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Painter_unique | Painter | reload_speed_from_own_area | its condition is a state the host does not expose per brawler (the super's state, charge / rage / heat / tokens, an area or a bush / wall / water proximity, a pet or turret, the attack sequence) |
| Painter_unique_2 | Painter | area_effect_no_overlap_bonus | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Crab_unique | Crab | start_power_tokens | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Crab_unique_2 | Crab | takedown_reload | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Digger_unique | Digger | extra_bounce | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Digger_unique_2 | Digger | transformed_movement_speed | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Samurai_unique | Samurai | ulti_longer_charge | libg reads it (star_audit.LIVE, #20) |
| Samurai_unique_2 | Samurai | samurai_shield | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Ghost_unique | Ghost | melee_dead_center_reward | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Ghost_unique_2 | Ghost | ulti_give_status_effect_self | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Voodoo_unique | Voodoo | pet_spawn_shield | libg reads it (star_audit.LIVE, #20) |
| Voodoo_unique_2 | Voodoo | voodoo_pet_slow_debuff | libg reads it (star_audit.LIVE, #20) |
| Lightyear_unique_1 | Lightyear | alt_character | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Lightyear_unique_2 | Lightyear | alt_character | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Lightyear_unique_3 | Lightyear | alt_character | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Meeple_unique | Meeple | environment_pierce_damage | libg reads it (star_audit.LIVE, #20) |
| Meeple_unique_2 | Meeple | super_area_recharge_buff | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Skater_unique | Skater | wall_speed | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Skater_unique_2 | Skater | consumable_shield_charge | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Morningstar_unique_1 | Morningstar | changing_projectile_additional_area | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Morningstar_unique_2 | Morningstar | return_projectile_status_effect | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Chronomancer_unique_1 | Chronomancer | reload_debuff | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Chronomancer_unique_2 | Chronomancer | increase_area_duration_per_damage_dealt_with_projectile_status | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Alternator_unique_1 | Alternator | gain_speed_from_close_allies | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Alternator_unique_2 | Alternator | add_damage_per_projectile_pierce_hit | libg reads it (star_audit.LIVE, #20) |
| Geisha_unique_1 | Geisha | weak_spot_status_and_tag_explosion | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Geisha_unique_2 | Geisha | storm_steal_ammo_and_longer_transform_status_effect | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Stalker_unique_1 | Stalker | faster_hp_regen_when_blood_hunt_active | depends on Alli's blood hunt (rage) state, not exposed by the host |
| Stalker_unique_2 | Stalker | faster_reload_speed_when_blood_hunt_active | depends on Alli's blood hunt (rage) state, not exposed by the host |
| Domain_unique_1 | Domain | domain_additional_status | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Domain_unique_2 | Domain | domain_additional_status | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Dancer_unique_1 | Dancer | dancer_combo_lifesteal | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Dancer_unique_2 | Dancer | ulti_change_status_effect | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Fury_unique_1 | Fury | ulti_area_status | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Fury_unique_2 | Fury | component_sp | generic (libg attaches its Traits / Components at spawn); the effect is not a stat a short A/B can measure (shot shape, super heal, super duration, area slow): not measured, not handed out |
| Bulletstorm_unique_1 | Bulletstorm | weapon_give_status_to_enemy | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Bulletstorm_unique_2 | Bulletstorm | bulletstorm_speed_on_pickup_shell | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Daredevil_unique_1 | Daredevil | dodge_reward | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Daredevil_unique_2 | Daredevil | heal_on_blink | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Mender_unique | Mender | tether_steal_dmg_enemy_to_ally | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Mender_unique_2 | Mender | tether_heal_from_enemy | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| Shadowdemon_unique | Shadowdemon | minion_trait_or_status | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Shadowdemon_unique_2 | Shadowdemon | soul_bullet | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Redirecter_unique | Redirecter | spawn_pet_on_poisoned_enemy_death | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Redirecter_unique_2 | Redirecter | status_effect_damage_scale_current_hp | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Gladiator_unique | Gladiator | stun_wall_push | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| Gladiator_unique_2 | Gladiator | gladiator_load_fire_punch_on_arena_enter | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| MagicalGirl_unique_1 | MagicalGirl | mount_up_get_status_on_damage | a flat hp / damage number whose scale to power level 11 the columns do not give (the text shows it unscaled), plus a trigger (hit, attack, state) the host cannot see: no number to use without a guess |
| MagicalGirl_unique_2 | MagicalGirl | alternative_main_attack_changing_projectiles | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Rock_unique | Rock | rock_knock_up_max_speed | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| Rock_unique_2 | Rock | rock_ulti_cc_immunity | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| KatanaKid_unique_1 | KatanaKid | katanakid_fish_from_super | changes a projectile, skill or area (range, speed, count, duration, extra effect on a hit): no host hook, the Values are shape parameters |
| KatanaKid_unique_2 | KatanaKid | katanakid_speed_boost_attack_max_charge | applies or cancels a status (slow, stun, root, reveal, immunity, extra poison) that libg's skills and areas own; no data-only hook for a card |
| FutureGirl_unique_1 | FutureGirl | trait_star_power | generic (libg attaches its Traits / Components at spawn); the effect is not a stat a short A/B can measure (shot shape, super heal, super duration, area slow): not measured, not handed out |
| FutureGirl_unique_2 | FutureGirl | pet_extra_health | libg reads it (star_audit.LIVE, #20) |
