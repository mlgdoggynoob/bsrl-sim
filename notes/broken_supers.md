# Broken normal supers (#32 item 5, #6 / #5): running notes

Branch broken-supers, base main 7c84d84. Host change: `engine/patches/broken_supers.patch`.

## Done
- Moe (`Digger`, charge 22): the env.c early return for type 22 blamed start state. The crash was at the end of the
  charge: the character tick 0xb3ae74 (type 22 at 0xb3e38c) calls `bl 0xb4ffec` at 0xb3eae0 to change him into
  DiggerDrill, and the client build folded the stub's NULL into what follows (0xb3eae4 `mov x0, xzr`, then getData(NULL)
  and stores to +0xe14 / +0xe18 of the new character). The bl goes to `dig_change` and 0xb3eae4 becomes `b 0xb3eb08`.
  dig_change: change (my_die -> superfix_change_character), drill timer = UniquePropertyValue1 scaled (100), surfacing
  hit = the start's stack [8] AreaEffectObject2 (DiggerDrillSurface, r800, push 100) with the skill's Damage as extra.
  Untouchable underground through libg's own 0xb5033c (+0x490 and type 22). No contact hits on the path. Only with
  superfix (`dig_ok`): without it the change would only retire him.
- Bonnie (`CannonGirl`, charge 16): the launch changes her into CannonGirlSmall first (0xb7bb58), so the charger has no
  Charge skill and the job's `ulti` flag was 0. No contact hits in the air; `charge_land` spawns CannonGirlExplosion
  (Effect, type 6: the apply ignores it) where she lands and hits enemies within its radius for the skill's Damage.
- Bonnie (`CannonGirlSmall`, ChangeCharacter): the case at 0xb7cfe4 only changes the character. `change_site` (the bl at
  0xb7d010) spawns the skill's AreaEffectObject at the old position and hits enemies in it for the skill's Damage.
- Kenji (`Samurai`): the projectile spawns SamuraiCrossSlashArea (type 38, no Radius / Damage); 38 is outside the
  apply's mask and the slash is server code. `superfix_moves_area` hits enemies near an X of two lines at +-45 degrees
  to the throw direction, once per area, and ends his SamuraiHide (CancelOnCharge) through `superfix_status_cancel`.
- Lou (`IceDude`): IceDudeUltiArea is Slippery (type 20), outside the apply's mask. `slippery_tick` re-runs the apply as
  a Damage area once a second while it lives (area +0xe8 = the projectile's scaled Damage, written at 0xb771ec).
  Lumi's ice gadget area has no damage and is left alone.
- Damian (`Gladiator`): audit miss. The EdgeCrossing ring pushes only at its edge (charge_check's "Damian arena edge");
  super_audit no longer expects a push from it.
- Buster (`ShieldTank`): audit miss. The shield is shipped client code (+3372 flag, the projectile update 0xb70d94); the
  audit's target stood inside the shield line and never shot after the fire. A ProjectileShield shooter now gets its
  target 1500 u away and a shot into the shield 8 ticks after the fire.
- Character changes (Moe, Bonnie): the new object has a new id, so env.c's `env_char_changed` moves the power cubes
  (keyed by id) and their +400 max HP each to it. Bonnie's landing hit goes through the hooked damage root (my_root).
- Meg (`MechaDude`, branch meg-mech, `meg_mech.patch`): the client's spawner puts her in her mech (MechaDudeBig) at the
  start, so her first super is the mech's melee swing; super_audit audits that (START_FORM). At 0 HP the damage root skips
  the mech's death block (0xb44990, only with stack arg s7, which no host call passes) and the eject is server code, so the
  mech stayed at 0 HP and the player was out. `mech_pop` (every damage path) calls the client's eject 0xb95364 (the Send It
  gadget's path): small Meg at full HP, a hop to a free spot, her star powers. No kill, no duo / trio knock-out, her super
  starts empty, no other hit that tick. Knocked out as small Meg she respawns in her mech. A running hypercharge follows
  every character change (`hyper_char_changed`). charge_check scene 5: eject, then her own super builds the mech again.
  Measured: mech 7400 -> 0, Meg 4800/4800, not out, super 0; her super -> mech 7400/7400; Duo knock-out -> respawn in the
  mech; hypercharge 99 -> 95 ticks left across the eject.
  Since the hypercharge follows the change, Bonnie's hypercharged launch also passes `--hyper` (CannonGirlExplosionOvercharged
  where she lands; on broken-supers alone it was the normal explosion).
- Nani (`Controller`): works on main 7c84d84 (3600 damage, push 900 u); the earlier miss was before hyper.c's on_travel.

## Guesses ([?] in the code)
- Kenji's slash: X shape, 600 u each way, 250 u wide. The server's geometry is compiled out.
- Lou: one hit per second; the slide (CustomValue 90) and freeze build-up (CustomValue2) are not done.
- Bonnie: landing radius = CannonGirlExplosion's 200 (else 200); straight flight over walls is not done (pathfinder).
- Meg: her super charge resets at the eject; the ejected Meg takes no other hit in that tick; the mech's destroyer gets
  no kill credit. The server's rules for these are unknown.
- Moe: the surfacing damage is the skill's 600 (the area's own 100 is inside it); the dive follows the pathfinder.

## Left for later
- R-T (`Splitter`): the split needs the partner getter 0xb392d4 (hard NULL), the link, control handover and rejoin. L.
