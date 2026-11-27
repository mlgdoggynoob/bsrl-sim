# Description values (issue #55 step 2): how the client fills <VALUEn>

Static reading of the shipped `libg.so` (v68.279, `engine/native/LIBG_SHA256`), first 2026-11-25, completed 2026-11-27 on
branch `claude/bsrl-sim-pr-csv-check-7l9ubh` (main 4656c06). Not run in the host. The Python port is `desc_values.py`
(`CODES`); `desc_audit` uses it.

## Where

- cards.csv `Value` / `Value2` / `Value3` are codes, not numbers: for a card whose Type is accessory the client reads
  each in turn and switches on it to compute the number that fills `<VALUE1>` .. `<VALUE3>`.
- Description builder: around 0x90bde8 .. 0x90e4f4 (the `<VALUE1>` / `<VALUE2>` string loads at 0x90c074 / 0x90c098). The
  card Type dispatch (table 0x1fc058) sends accessory cards to 0x90ccd0. The code switch is at 0x90d5ac: `code - 1`
  indexes the halfword jump table at 0x1fc2e0 (85 entries, above that the default 0x90e4f4), target = 0x90d548 + 4 x entry.
  The file has no section headers: virtual address = file offset in the first segment. Disassembled with
  `llvm-objcopy -I binary -O elf64-littleaarch64 libg.so raw.o; llvm-objdump -D --triple=aarch64 raw.o`.
- Registers in the switch: x23 = the AccessoryData, x22 = the brawler's CharacterData (x22 +0x260 = its weapon SkillData),
  x20 = the card's owner (for the level).

## Reading the getters

- Column getters are 16-byte stubs `adrp x8, page; ldr x0, [x0, #8]; ldr w1, [x8, #slot]; b getInt` (0xcf6a18 int,
  0xcf6a28 bool, 0xcf6a08 string). The slot word is filled at load time by name: `adrp x1, name; add x1, ...; bl 0xcf7228;
  str w0, [x8, #slot]`. Scanning every such store gives slot -> column name for 2176 slots, and so the column of every
  stub (664). Examples: 0xa933d0 CustomValue1, 0xa932c8 ActiveTicks, 0xb0dc14 skill Damage, 0xb0dc5c MsBetweenAttacks,
  0xb0d948 CastingRange, 0xab31e8 character Hitpoints (slot 0x123fdbc).
- Linked rows are pointers in the data object. The newer tables load each column by name into a struct field:
  `adrp x1, name; bl 0xe96e10; ldr x0, [x19, #table]; bl 0xac3c6c; str w0, [x19, #off]`. That gives the field maps of the
  status effects (loader 0xba34bc: +0x98 DurationTicks, +0xa0 TriggerRate, +0xab TriggerOnFirstTick, +0xb8 Damage, +0xf0
  Healing, +0xf8 SpeedBoostPercent, ...) and the area effects (0xa9553c: +0x98 StatusEffectEnemy, +0xe0 ChainAreaEffect,
  +0x124 TimeMs, +0x134 Damage, +0x13c CustomValue, +0x140 CustomValue2, ...).
- AccessoryData links, from what each case reads through them: +0x58 StatusEffectAlly, +0x60 StatusEffectEnemy, +0x70
  AreaEffect (the area fields above), +0x78 PetAreaEffect, +0x80 Skill, +0x90 the CustomObject list; libg looks it up in
  the table the case needs (0xad2af0 areas, 0xad2b60 characters, 0xad2f1c projectiles, 0xad2b7c skills).
- Read by guess [?] (not from a loader): CharacterData +0xb8 = AreaEffect (codes 39, 40, 45, 63: Janet's speaker area),
  SkillData +0xa0 = AreaEffectObject (code 71), ProjectileData +0x128 = SpawnAreaEffectObject (from #64), +0x22c =
  SteerLifeTime (from #63, Amber).
- Helpers: 0xba5510 / 0xba5574 = a status's total damage / healing: max(0, DurationTicks / TriggerRate +
  TriggerOnFirstTick) x Damage (Healing), or TriggerOnFirstTick x it when TriggerRate < 1. 0x90eb00 and the inline
  `madd` = the level scale x + (level - 1) x (x / 10). 0xa18e8c (reached through 0x90df58) prints ticks as seconds.

## The codes

| Codes | Number | Unit |
|---|---|---|
| 1-6 | \|CustomValue1..6\| | |
| 10 | CustomValue6 / 40 | |
| 11, 46 / 72 | CustomValue1 / 100, CustomValue3 / 100 | |
| 12, 16 | \|PetAreaEffect / AreaEffect Damage\| | |
| 13, 15, 20, 22 | ActivationDelay, ShieldTicks, ActiveTicks, SpeedBoostTicks | s |
| 14 | ShieldPercent | |
| 17 | AreaEffect CustomValue (ticks) | s |
| 18, 19 | ActiveTicks / CustomValue1 (shown only with CustomValue1 >= 1) | |
| 23, 86 | \|CustomObject area Damage\| (its ChainAreaEffect's when 0) | |
| 24, 25, 30, 44 | CustomValue2, 1, 3, 4 (ticks) | s |
| 26, 79, 80, 82, 84 | DurationTicks of: the CustomObject area's StatusEffectEnemy, the AreaEffect's StatusEffectEnemy, StatusEffectEnemy, StatusEffectAlly (82 and 84) | s |
| 27 | CustomValue2 / weapon MsBetweenAttacks | |
| 28 | ActiveTicks / 20 | |
| 29 | CustomObject character Hitpoints (not level-scaled) | |
| 31 | CustomValue1 / 100 + 1 | |
| 32 | CustomValue3 x 100 / weapon CastingRange | |
| 37, 42 | AreaEffect TimeMs, the CustomObject projectile's SpawnAreaEffectObject TimeMs (x 0.02 ticks) | s |
| 38 | 100 - \|100 + CustomValue3\| x \|100 + CustomValue4\| / 100 (two cuts combined) | |
| 39, 40, 45 | \|CustomObject character's AreaEffect Damage / CustomValue2 / CustomValue\| | |
| 41 | CustomObject projectile SteerLifeTime | s |
| 48 | CustomValue1 + 100 | |
| 50, 51 / 68, 54, 66 | weapon Damage at level x CustomValue1, 2, 3, 4 % | |
| 52, 53, 58 | -(MinigunDudeTowerBurstHeal / PocoRegenArea / CactusCoverHeal Damage) % of Hitpoints at level (areas named in the code) | |
| 55, 62, 63 | \|AreaEffect / CustomObject area / CustomObject character's AreaEffect Damage\| % of weapon Damage at level | |
| 56, 57, 59 / 64 | Hitpoints at level x CustomValue1, 4, \|2\| % | |
| 61, 73 | \|AreaEffect Damage\| % of Hitpoints at level | |
| 70 | CustomValue1 (with a %) | |
| 71 | CustomObject skill Damage, or its AreaEffectObject's Damage x CustomValue % when that is set, at level | |
| 74 | the weapon projectile's area status total damage at level x CustomValue1 % | |
| 77, 78 | StatusEffectEnemy total damage, StatusEffectAlly total healing, at level | |
| 81, 85 | CustomObject skill / Skill Damage at level | |
| 83 | StatusEffectAlly SpeedBoostPercent | |
| 33, 69 | no number | |

Not decoded (desc_values gives None): 21 (SpeedBoost x 100 / a CharacterData field), 34, 35, 43, 47, 49 (CustomValue1 /
a weapon helper 0xb0e1f0: Charlie's spider count), 60 and 65 (the pet character at CharacterData +0x250), 67, 75, 76,
87-90. In use by gadget texts: 47, 49, 60, 65, 67, 75, 76 (7 placeholders).

Checks against numbers settled elsewhere: Piper's Auto Aimer 180 (50: 1800 x 5 % at power 11, gadget.c), Bea 4 bees (19:
16 / 4), Darryl 25 % (10: 1000 / 40, #63), Amber 3 flames / 5 s / 1890 (3, 41, 51; #63), Barley's potion 810/s (59),
Bibi 1000/s for 4 s (her card's own Value, #22), Angelo's drain 660 (71: 2200 x 15 % at power 11; #78 measured 660).
Janet's speaker (63): 10 % of 2000 = 200 damage per second at power 11.

## Paths

Descriptions that do not use codes embed paths such as `<!card.accessory.skill.damage.scaleToLevel>`, which name the data
directly. `desc_values.resolve_path` walks them (links and modifiers in its docstring). Left unresolved: component / trait
paths (brawler-specific components), `maxAmmo`, `cactusMinionHealing`, `bulletExplosionTriggerCount`, and
`actionsOnCancelOnDamage`. With the codes, 181 of the 195 placeholders in gadget texts resolve.

Star power cards fill their `<VALUEn>` from their own card type's code (the values are numbers like 15000 or 2050, not
codes). That code is not read here.
