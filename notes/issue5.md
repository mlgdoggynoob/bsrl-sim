# Issue #5 (charge supers): running notes

State: merged in #14 (branch claude/project-thread-nfu3i0).

## Done
- Host (engine/native/loader/env.c, recorded in engine/patches/charge.patch): ChargePushback via knockback 0xb49834,
  Bull's straight lane + wall break (0xa53b60, r 200), El Primo landing break (r 300), trail areas via +0x550,
  Crow knives at take-off / landing, end-of-charge area (sp[9]), env zones for HotAndDot 35 (Berry) and
  EdgeCrossing 56 (Damian).
- charge_check.py: live check of walls, Damian's edge, Berry's paint; passes, fails with --native-charge 2.
- super_audit: 81 works (main 70). Nani (Controller) partial is a missed steered shot, also on main.

## Decisions
- No generic admission of area types 35/36/56 in the 0xb29494 mask: tried, Stu's RollerFire area vanished. Zones are
  env-side and only for the charge's own areas.
- Numbers that are guesses: wall radii, Berry heal = CustomValue % of damage, paint damage = Damage x2.

## Open
- Bonnie (type 16) and Moe (type 22): done in broken_supers.patch (#32 item 5, notes/broken_supers.md). Moe was not blocked
  on start state: the type-22 end at 0xb3eae0 folds the stub's NULL into the code that follows (0xb3eae4 `mov x0, xzr`).
- StatusEffect areas (36) spawn but act on nobody (slows, Stu's fire).
- super_audit: a normal attack in its harness does not land (pre-damage often misses); charge_check uses Crow's super.

## Facts worth keeping
- Charge start 0xb475cc args: x3 = x4 Damage, x5 ChargePushback, x6 ChargeSpeed; stack [0] type, [1] AreaEffectObject,
  [2] SpawnedItem, [8] AreaEffectObject2, [9] end-of-charge area.
- Area data: +0x118 Type, +0x124 TimeMs, +0x12c Radius, +0x134 Damage, +0x13c CustomValue, +0x140 CustomValue2,
  +0x154 PushbackStrength, +0x1b8 InnerRadius.
- Area apply mask built at 0xb29600..0xb2961c; types >= 53 cut by the cmp at 0xb29604.

## Next step
- Address review on PR #14. Bonnie / Moe only together with #6's character change.
