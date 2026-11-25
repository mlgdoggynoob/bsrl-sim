# #6 leftovers (R-T's split, Bonnie's hypercharged launch) and what was left of #5

Branch claude/focused-mayer-2c1pv8, base main 6419479 (after #43). Host change: `engine/patches/split_and_paint.patch`.
libg v68.279. 1 tile = 300 u, 20 ticks/s.

## State at the start (measured on 6419479)
- R-T (`Splitter`, Split): `super_audit` "unverified, summons: SplitterLegs". Probe: the legs spawn at his feet, but his
  walk is unchanged (756 u in 20 ticks whole and split), his attack stays SplitterWeapon (2100 on a target next to him), the
  legs never attack, and his second super is spent with no effect (no teleport, no heal, legs stay).
- Bonnie's hypercharged launch: already works since #43 (`hyper_char_changed` keeps the hypercharge across the change into
  CannonGirlSmall). `super_audit --hyper`: works, CannonGirlExplosionOvercharged r800 + BulletExplosionOvercharged + 6 teeth,
  2100 landing damage. A probe: enemies 600 u from the landing are stunned for ~20 ticks (CannonGirlOverchargedStun).
- #5: `super_audit --only` all 23 charge-ulti brawlers + Bonnie's small form: 24 works. `charge_check`: 4 of 5, "Berry
  paint" failed (also on main before this branch).

## libg offsets (R-T)
- BehaviorType Split = 18 (string table at 0xb0b7fc). It has no case in the activation switch 0xb7b268 (jump table at
  0x1fd1a0, index 18 -> default 0xb7c5dc). The use-skill code 0xb819fc calls the split 0xb5c7b0(char) at 0xb82328 for an
  ulti with BehaviorType 18.
- 0xb5c7b0: hero kind (char +1064, else CharacterData +572, test 0xab2fd0: 0 or 26) -> spawn the Pet (0xab3da4) with
  0xb56e00 at his position. The UniqueProperty 13 test at 0xb5c810 is followed by a discarded 0xab2fd0 call: the rejoin
  branch is compiled out.
- Partner getter 0xb392d4(char): UniqueProperty (CharacterData +660, getter 0xab3d04) == 13, then +1064 / +572 into
  0xab2fd0 and `mov x0, xzr` (0xb3930c): always NULL. Callers: damage root 0xb42838 / 0xb44674 / 0xb44b64 (results unused),
  use-skill 0xb82edc (the partner fires its weapon too: Eat Static from the legs), 0xb9c458 (component tick), 0xb9cb2c /
  0xb9cbb4 (after a character change: kills the partner chain).
- 0xb502e8 = "is a minion" (owner >= 0 and not hero kind): only the head passes its attack on, no recursion.
- Brawler_Splitter component: ctor 0xb9c0fc (factory case 0xb9e9a0), vtable 0x120a968, slot +0x40 = 0xb9c42c, the tick.
  Like Draco's MountUp tick, libg never calls it. It does: partner = 0xb392d4; weapon slot 0 -> partner's weapon or
  CharacterData +0x260 via 0xb35c3c (call 0xb9c4bc, return 0xb9c4c0); with a partner, 0xb5901c(char, card(MetaType 3)
  Value2, 2, 0) at 0xb9c4f8 (return 0xb9c4fc); hypercharged and +68 <= 0: SplitterCirclingProjectile (0xb9c2d0); no
  partner: the circling projectiles are removed (0xb75998(p, 5)).
- 0xb5901c(char, speed, ticks, flag) is a bare `ret` with 7 callers; at 0xb7f25c (UniqueProperty 9) the amount is
  Speed x UniquePropertyValue1 / 100 and the ticks a CharacterData getter: an absolute speed boost for N ticks. Only R-T's
  call site is taken; the other 6 stay a no-op.
- Card values: 0xace760(CharacterData, MetaType) -> card, 0xaa9568(card, k) -> Value (k 1 +272, 2 +276, 3 +280).
  Splitter_ulti: Value2 100 (speed), Value3 1000; SplitterLegs_ulti: Value3 1000 (heal icon).
- Retire as 0xb4ffec does: HP +964 = 0, +3273 = 1 (not for UniqueProperty 2).

## What the host does now (R-T)
- `split_partner` replaces 0xb392d4: the head's living legs or the legs' living head (same player +0x80, UniqueProperty 13,
  the other kind).
- The character tick runs the component tick for a UniqueProperty 13 hero, and retires legs with no living head.
- `my_change_skill` (superfix_cc.c) takes return 0xb9c4c0: a mount unless the data is CharacterData +0x260.
- `my_speed_buff` replaces 0xb5901c and records (amount, until) only for return 0xb9c4fc; `superfix_split_speed` adds it
  to `superfix_status_speed` as an absolute boost, so env.c's mover hook and the move re-send see it.
- `my_split` wraps 0xb5c7b0: with living legs it is the rejoin (stop, move to the legs, retire them, heal by the legs'
  card Value3, else 1000); without, the original split.

Measured (charge_check scene 6 and probes): walk 756 -> 867 u in 20 ticks (720 -> 820 speed); one attack: 2480 on an enemy
next to the head and 2480 next to the legs (SplitterLegsDamageArea 1240 x2); the rejoin: 0 u from the legs, legs gone,
HP 2440 -> 3440; knocked out while split: the legs go. Weapon swap log: mount -> skill 20000192, dismount -> 20000190.
`super_audit --hyper`: SplitterCirclingProjectile x16 (the component's hypercharged effect now runs).

## #5: Berry
- The "Berry paint" failure was the check: Crow's poison (the pre-damage) ticked on Berry in the same window as the paint's
  100 HP heal, so his HP never rose (a host log showed the heal at ticks 473 / 493). The heal itself worked.
- The numbers were low. The client's area create 0xb2aefc applies DamageScaleType (+0x138): 1 % of the owner's weapon damage,
  2 % of max HP, 3 % of the ulti damage, 5 level-scaled, 4 (0xb2b184) Damage % of the extra damage the spawner passes. For
  the trail (0xb47360, from the character tick at 0xb3b9c4) the extra is char +0x558, which only the compiled-out charge
  start sets (env.c writes 0). The wiki's 660 / 330 per second at power 1 is 100 % / 50 % of PainterWeapon's 660, so
  env.c's zone takes Damage % of the main attack Damage for DamageScaleType 4 ([?] the server's +0x558). Now 1320 damage
  and 660 heal per second at power 11 (probe: enemy 4760 -> 3440 -> 2120 one second apart).
- Teammates he dashes through are healed by the skill's Damage x2 (3040; #22: the same flat 1520 at power 1). Probe in a
  duo: teammate 4240 -> 7280.

## Dead ends / not done
- Bonnie's hypercharged teeth (CannonGirlBulletExplosionOvercharged, DamageScaleType 4, Damage 25, CustomValue 6,
  BulletExplosionBulletOffset 500, Distance 20), fixed in `heal_scale.patch` (#22 branch): spawnfix.c starts each
  BulletExplosion bullet BulletExplosionBulletOffset units out on its own line (a ring; the server's spawn is compiled out,
  the column name is the evidence), and env.c charge_land sets the landing area's damage word to Damage % (25) of the
  skill's 1000, which the chain copies. Probe (enemies at the landing spot and 650 u out every 60 degrees, one at 1200 u
  between two teeth): centre 2100 (the landing hit only), each of the six 525 (one tooth: 250 x2 power 11 x1.05
  hypercharge), the one between none. `super_audit --hyper`: Bonnie works (2100, 6 teeth), Surge, Chuck, Gus as before;
  Byron's hypercharged super now 3150 on its target instead of 7800 (its 6 SnakeOilHyperExplodedProjectile, offset 600, no
  longer all hit the centre; "missing: heal" either way, the audit's own-heal check). `NB_SPAWNFIX_OFFSET=0`: the old spawn.
- R-T's marks (SplitterTag: the next hit consumes it for extra damage) are main-attack and gadget logic, not the super; not
  checked.
- The second split of a battle spawned legs at 4454 / 7800 HP (the first at 7800): client code in the summon (0xb57804..);
  not traced.
- Not checked against the game: whether the legs go when R-T is knocked out, whether the split speed is +100 absolute
  (only the stub's other callers suggest it), and the rejoin heal at power 11 (2000 since heal_scale.patch, #22: Value3 1000 x2).
- `super_audit` keeps R-T as unverified: the split is charge_check's.
