# Gadgets batch 2 (issue #3, map in #32): resume notes

Branch `claude/project-thread-ic20ua` off main fe49fe2. Only `engine/native/loader/gadget.c`, `gadget_check.py`,
`super_audit.py` (--gadget), a new `engine/patches/gadgets_batch2.patch`, README/SETUP lists. Other sessions own hyper.c,
env_v5 / star-power files, env.c storm + spawnfix.c: don't touch.

## Targets (enabled cards, census from the csv tables)
- 33 skill-projectile: accessory Type empty + Skill whose BehaviorType is Attack -> fire the skill's projectile(s) via 0xb78190.
- 11 extra-shot: repeat_shot (6), spin_shoot (5; 2 have no projectile: Kicker Sweep, Painter Push).
- items: ElectroSniper_Trap (ElectroTrap), Blower_Stopper (WindWall) via item factory 0xb55684. Gale's GaleSpringboard is not in items.csv.
- R-T Splitter_ChargeUlti: player +0x54 = +0x58 * CV1 / 100.
- instant heals: Kit Attacher_Cheeseburger (CV1 30 % max hp), Kenji Samurai_HealDamageTaken (CV1 60, CV2 50: % of damage taken, ticks?), Nori KatanaKid_HealFish (needs fish state).
- heal call: 0xb41554(ch, src player, amount, 1, NULL, 0,0,0,0,0) (superfix_status.c).

## State (2026-11-24)
- gadget.c kinds added: SHOT, SKILL AREA, REPEAT, SPIN, ITEM, SUPER (new NBE_GAD_SUPER 7), HEAL_NOW. Offsets in the file header
  and the #defines (from a static read of libg: AccessoryData +0x80 Skill, CustomObject getter 0xa933a8, getXByName 0xad2f1c /
  0xad3c30, SkillData +0x58 projectiles, +0xa0 area, +0x1a8 BehaviorType Attack 0 / AimableArea 28, Type ints 3/9/13/50/56/58).
- 0xb4b660 (damage percent) reads 0 on this host: taken as 100 %, else gadget shots did 0 damage (first audit run).
- Live audit (super_audit --gadget, both slots): 38 of 53 work; 8 rows masked in g_masked (no effect), 7 partial kept.
- super_audit: --gadget-slot, gadget_kind / all_gadgets / audit_gadgets / expected_skill; gadget_check: PROJECTILE / SUPER
  effects, --roster.
- Issue #54 (`repeat_spin_off.patch`): REPEAT and SPIN are off again (kind NONE, code under `#if 0` in gadget.c): they fired
  N copies of the main attack at full damage and range (Piper 5 x 1800). super_audit.gadget_kind returns None for them.
- Next: final checks run (scratchpad checks.sh: gadget_check x2, super_audit x2, test_fast, train_ppo smoke), patch file
  engine/patches/gadgets_batch2.patch (git diff --relative=engine origin/main -- engine), PR.
