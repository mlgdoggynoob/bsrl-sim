# #6 R-T's split, the rest of the server half

Branch rt-split-extras, base main 48387c6. Host change: `engine/patches/split_extras.patch` (on top of `gears.patch`).
libg v68.279. Builds on `split_and_paint.patch` (`notes/issue6-leftovers.md`): its partner lookup, rejoin and retire are reused.

## What main had
- `split_partner` (0xb392d4), the component tick 0xb9c42c (weapon swap, +100 speed, hypercharge orbiters), the rejoin in
  `my_split` (0xb5c7b0), legs without a living head retired. Nothing for: the legs' death (the head lived on), the storm on
  the legs (only players' brawlers were hit), water (the head stopped at the shore), a rejoin onto a blocked spot (he was
  put on the legs' spot whatever it was).

## What the host does now
- Linked death, `env.c` `split_link`: called where `mech_pop` is (my_root, gas_hit, zone_tick, charge_contact_tick,
  sf_explode). Legs at 0 HP with a living head that is not parked for a respawn -> my_root hits the head for 4 x his max
  HP [?] from the same attacker, or with the root's owner index when the attacker is gone (a dead Piper's bombs). That hit
  skips the hypercharge, status and gear modifiers (`E.split_hit`), so only the root's full block (spawn protection) stops
  it. The kill credit, the duo / trio knock-out and the elimination run as for any death.
- One kill per R-T: `record_event` counts no kill on the legs and a kill but no hit on the head's linked hit. A spread
  that kills the head first and the legs a pellet later counts 1; a head that survives (full block) counts 0. A bomb's
  linked hit stays `in_own_call` 2 (bomb damage). The attacker player's +0x54 (super) and +0x98 (hypercharge) are put
  back after the head's hit. Nobody's hit (no attacker, no owner index: the storm, a meteor): gasNoKillCredit on the head.
  From the storm, `gas_hit` records the head as a storm death (elim_gas) and adds his lost HP to the owner's gas damage;
  the legs never take one of the 16 `gas_lethal_id` slots.
- A knocked-out head (duo / trio) is parked at full HP, so the partner lookup would still see him alive and his legs would
  stay: my_root's knock-out branch now retires them (`superfix_split_drop`), and `split_link` ignores a parked head.
- Storm on the legs, `split_gas` from `gas_tick`: each storm second, living legs on a storm tile get a GasHit of 20 % of
  their max HP [?] (no ramp). Their damage counts in the owner's gas damage (legs +0x80 = his player).
- Water: canWalkOverWater 0xb51200 is hooked (`my_wow`, the data's column or a head with living legs); isSplit 0xb5a7b0 is
  not, its result is dropped at both calls (0xb51224 in 0xb51200, 0xb55560 in 0xb554e4). The mover passes 0xb51200 to its
  pathfinder 0xb51550 (w5, call 0xb47d08). That alone was not enough: env's move input raycasts the joystick target
  (`joy_target_at`, the client's 0x877448) with flag 1, and the client's flag is 1 & ~0xb31e20, the client object's
  canWalkOverWater (data column, or UniqueProperty 13 hero with byte +785). With flag 1 the target stopped at the shore.
  The split head now gets flag 0. Other heroes with CanWalkOverWater in characters.csv (Flea, InsectMan, Ghost, Voodoo,
  Stalker, FutureGirl, Godzilla) still get flag 1 as before: not touched.
- Land search, `superfix_moves.c` `split_land` on the live tile data (+0, so a broken wall is open): 100 u rings up to
  900 u [?], 16 points each, the first walkable point; past that the centre of the nearest walkable tile of the map. Used by
  the rejoin when the legs' spot is blocked, by `head_land` (a head that had legs at his last tick and has none now,
  standing inside the map on a blocking tile; its id table is reset per battle and drops dead heads), and by
  `respawn_tick` (`superfix_land`): a teammate respawning on a split head's spot on water goes to land.

## Measured (host built from these sources, 2026-11-25)
- `charge_check` 7 of 7 scenes ok. Scene 6: walk 756 whole / 867 split, Eat Static 2480 at the head and at the legs,
  rejoin 0 u from the legs, heal 2000. Water (tile 22, 20 on Survival651): whole R-T ends 150 u short of the shore, the
  split head 717 u past it, no legs after the rejoin. Linked death: three Shelly supers break the legs, no shell on the
  head, R-T out, 1 kill credited in all, 1 "rt legs down" log line, the killer's super charge +0.
- Storm battle (split on the spot 2 tiles from the edge, head deep inside, ring 3 forced): legs 7800 -> 6708 -> 5616 ->
  4524 -> 3432 -> 2340 -> 1248 -> 156 -> gone, head dead, player out, elim_gas 1, kills 0. 1092 a second is 14 % of the
  7800 they show: 20 % of a +0x3c8 of 5460, so the legs' max HP word is lower than the HP they spawn with [?].
- Super charge: with the restore in `split_link` taken out (a test build), the killer's charge also rose 0: the root
  charges nothing for a hit without a projectile, so the restore is a guard and charge_check's assertion cannot tell.
- Whole R-T placed on water stays there, but his split puts the legs on the nearest open spot (libg's summon placement;
  probe on tiles 23-25, 20): legs never stand on water in the harness.

## Not done / not checked
- The blocked rejoin, `head_land` and the respawn on land were not run live: the legs cannot be put on water (see
  above), and a surviving head or a water respawn needs a duo battle or spawn protection timed to the legs' death.
- A split head that dies on water drops his power cubes there (libg's death drop) [?]: not probed, not moved.
- The land search does not look at walls in between or at the storm [?].
