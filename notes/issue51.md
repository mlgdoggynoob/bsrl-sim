# Issue #51: gears

Branch `claude/focused-mayer-2c1pv8` on main 8a68bc6, 2026-11-25. Game data: v68.279 `csv_logic`, libg v68.279.

## Where the gears are

Not in `cards.csv` (its "gear" matches are `...ChargeArea` names) and not in `accessories.csv` (gadget visuals).
They are their own table, `gear_boosts.csv`, data type 62 (libg's table list registers `csv_logic/gear_boosts.csv` with
type 0x3e at 0xb05020), so global ids are 62000000 + the named row's index (the unnamed rows below a gear continue its
`ExtraHerosAvailableTo` / `HeroDeprecated` lists). `gear_rarities.csv`: RareGear is `AvailableToAllBrawlers`, Super
Rare and Epic gears only go to the brawlers listed. `gear_levels.csv` (levels 1-3, tokens / scrap) has no battle
numbers: one ModifierValue per gear. Texts from `localization/texts.csv`.

| id | Name | LogicType | Rarity | ModifierValue | Type | For | What it does (TID text) |
|---|---|---|---|---|---|---|---|
| 62000000 | ForestSpeed | 0 | Rare | 15 | percent | all | +15 % speed when moving in bushes |
| 62000001 | HealthRegen | 1 | Rare | 50 | value | all | recover health 50 % more effectively |
| 62000002 | LowHealthDamage | 2 | Rare | 15 | percent | all | +15 % damage while below 50 % health |
| 62000003 | Vision | 3 | Rare | 40 | ticks | all | reveal opponents for 40 ticks (2 s) after damaging them |
| 62000004 | ConsumableShield | 4 | Rare | 900 | value | all | a 900 shield; regenerates in 10 s when at full health |
| 62000005 | ReloadSpeed | 5 | Super Rare | 15 | percent | ElectroSniper, Flea, Duplicator, FireDude | 15 % faster reload |
| 62000006 | SuperChargeRate | 6 | Super Rare | 10 | percent | Knight, IceDude, Silencer, Controller, CannonGirl, Wally, Luchador, Driller | super charges 10 % faster |
| 62000007 | SuperHealth | 7 | Epic | 1000 | value | ClusterBombDude (Tick) | Tick's head +1000 health |
| 62000008 | SuperRange | 8 | Epic | 3 | value | HookDude (Gene) | longer Magic Hand |
| 62000009 | PoisonDamage | 9 | Epic | 30 | percent | Crow (deprecated) | +30 % poison damage |
| 62000010 | SlowIncrease | 10 | Epic | 30 | percent | Cactus (deprecated) | Spike's super slows 30 % more |
| 62000011 | SmokeDuration | 11 | Epic | 2 | value | Ninja (deprecated) | Leon's smoke bomb +2 s |
| 62000012 | SuperShield | 12 | Epic | 20 | percent | Sandstorm (Sandy) | enemies in the sandstorm deal 20 % less damage |
| 62000013 | PetrolSlows | 13 | Epic | 10 | percent | FireDude (Amber) | oil spills slow enemies 10 % |
| 62000014 | PetDamage | 14 | Super Rare | 25 | percent | Mechanic, SpawnerDude, BlackHole, ArtilleryDude (Shaman deprecated) | pet power +25 % |
| 62000015 | ExtraSpawnling | 15 | Epic | 1 | value | Flea (Eve) | Eve's super +1 hatchling |
| 62000016 | SuperTurret | 16 | Epic | 20 | percent | MinigunDude (Pam) | Pam's turret heals 20 % more |
| 62000017 | GadgetCooldown | 17 | Rare | 15 | percent | all | gadget cooldown -15 % |
| 62000018 | SuperBulletSpeed | 18 | Epic | 50 | percent | Undertaker (deprecated) | bat speed +50 % |

ReloadSpeed lists ElectroSniper, Flea, Duplicator, FireDude; BowDude, RocketGirl, Gunslinger, Arcade, AssaultShotgun and
TrickshotDude are `HeroDeprecated`. SuperChargeRate's BullDude and Enrager are deprecated. A deprecated hero cannot carry
the gear (libg's check 0xae2aa4, below), so PoisonDamage, SlowIncrease, SmokeDuration and SuperBulletSpeed reach nobody
in this build.

## What libg still does

GearBoostData (vtable 0x12067c8, table 62): +0x58 its GearRarityData (+0x58 byte = AvailableToAllBrawlers), +0x60 /
+0x6c the hero list, +0x70 / +0x7c the deprecated-hero list, +0x80 / +0x81 ModifierType is "percent" / "ticks".
Getters: LogicType 0xae2b14, ModifierValue 0xae2b24 (both read the csv row on each call), "allowed for this
CharacterData" 0xae2aa4 (not a Type 26 character; all brawlers or listed, and not deprecated).

Loadout: the player config (the one the star power and gadget cards are in, 0xc33e84 layout) holds the two gears at
**+0x18 and +0x20**. Config lookups: 0xc34ebc(cfg, logicType) -> the gear, 0xc34fc8(cfg, logicType, default) -> its
ModifierValue. A character keeps gear instances (24 bytes, ctor 0xb6a8ec: +0 data, +8 LogicType, +12 the value for
type 4) in **char+0xd68 (count +0xd74)**; 0xb565b8(char, logicType) -> the instance if its gear is allowed for the
character's data. Who fills char+0xd68 in the real game is server code (compiled out); nirkt's `battle_fix.c ensure()`
fills it from cfg+0x18 / +0x20 at character init (0xb34e3c) and the snapshot (0xb360ac), but only for LogicType 0 / 1
(what the phone agent met). The client object's own list (+0xe0, filled by 0xb306cc from the same config) is the
client's and never read by the sim.

Readers in the battle logic (static scan of the calls with a constant type, and the inline loops over +0xd68):

| LogicType | Reader | Notes |
|---|---|---|
| 1 HealthRegen | 0xb46900 (regen amount x (100 + v) / 100), 0xb3ad7c (a timer on the instance) | live once the instance exists |
| 6 SuperChargeRate | 0xb4f928 (super charge x (100 + v) / 100) | live |
| 7 SuperHealth | 0xb7ee68 | live |
| 8 SuperRange | 0xc6e68c (and the client-side 0xc6e5e0) | live |
| 9, 10, 11, 18 | 0xb78548, 0xb4f4d8, 0xb82094, 0xb4c0d4 | readers exist; every hero deprecated |
| 12 SuperShield | 0xb4f520 | live |
| 14 PetDamage | 0xb57240 | live |
| 15 ExtraSpawnling | 0xc34ebc at 0xb3ea40 (config) | live |
| 17 GadgetCooldown | 0xc34fc8 at 0xc401e0 / 0xc42be8 (config) | live |
| 0 ForestSpeed, 2 LowHealthDamage, 3 Vision, 4 ConsumableShield, 13 PetrolSlows, 16 SuperTurret | none | compiled out |
| 5 ReloadSpeed | 0xb31d44 at 0x526ae4 only (client code, below 0xa00000) | compiled out in the sim |

Type 0 and 4 instances are still serialised in the snapshot (0xb6a998, a stub nirkt's `element_writer` replaces: a flag
and, for type 4, the value), but nothing in the sim reads them.

## What this branch does (gears.patch)

- Equip: RESET `div.gear` (two ids per player) -> `offline.c my_player_ctor` -> `gear.c gear_equip`: config +0x18 /
  +0x20 when the id is in table 62 and 0xae2aa4 allows it for the character (and the second is not the same gear),
  else `div_err` bit. `battle_fix.c ensure()` now builds the char+0xd68 instances for LogicType 0-18.
- Re-implemented in `gear.c` (the four compiled-out ones with a plain stat effect): ForestSpeed (move speed x 1.15 while
  the brawler's tile is a bush, at each move send; a bush change re-sends the move), LowHealthDamage (damage x 1.15 while
  the attacker is below 50 % hp, in `env.c my_root`), ConsumableShield (900 in front of the hp, after every other damage
  modifier, not for the storm; full at the start and again after 200 ticks at full hp with no hit; [?] whether a hit on
  the shield alone restarts the 10 s in the real game), ReloadSpeed (+15 to libg's reload aggregate, T x 100 / 115).
  `NB_GEARS=0` turns these four off.
- State: `NbeResp gear_valid / gear_id / gear_shield / gear_stat` (low-hp hits boosted, shield hp absorbed, bush moves,
  reload answers). Python: `env_v5.gear_rows / gear_ok / gear_cards / with_gears`, `make_battle_fn(gears=True)`, trainer
  `--gears 1` (`train_ppo`, `train_fast`; off by default; not in the observation, no `OBS_VERSION` change).

## Live check (`python -m gear_check`, 2026-11-25, Survival642, one battle, native AI off)

| Gear | Where | Result |
|---|---|---|
| (equip) | host | 7 requested gears in the configs, SuperHealth on Maisie rejected (div_err 0x40), shield 900 at the start |
| LowHealthDamage | host | full hp 3000 / 3000; below 50 % 3450 / 3000 = 1.150 |
| ConsumableShield | host | first volley: hp lost 2100 vs control 3000, shield 900 -> 0; full hp at tick 300, shield back at 500 |
| HealthRegen | libg | hp regained 1521 / 1014 = 1.500 |
| ForestSpeed | host | bush path 723 / 626 = 1.154; open ground 643 / 643 = 1.000 |
| ReloadSpeed | host | Surge's ammo regained 492 / 420 = 1.171 (want 1.15; T truncates to whole ms) |
| SuperChargeRate | libg | El Primo's punches: super charge 1884 / 1712 = 1.100 |
| GadgetCooldown | libg | Maisie's dash: cooldown 270 / 318 = 0.849 |

These seven are `gear_check.LIVE`, what `--gears 1` hands out. Every brawler gets two of them (the five Rare ones are for
everyone; ReloadSpeed and SuperChargeRate only for their listed heroes).

## Not done

- Vision (3): its effect is on what the damaged enemy's observers see (shown in bushes for 2 s). The bush rule lives in
  three places (`env.c` emulate_client_flags, `nbpc.fair`, `fast_obs`), per observer; doing it means a per-observer
  reveal state from the host into the observation path, which issue #51 keeps out of scope. Not handed out.
- PetrolSlows (13, Amber) and SuperTurret (16, Pam): no reader in libg; Amber's oil has no slow to scale and Pam's
  turret heal is `superfix.c` TURRET_HEAL_PCT (+20 % would be one line there, but there is no measurement to check it
  against). Not handed out.
- SuperHealth (7), SuperRange (8), SuperShield (12), PetDamage (14), ExtraSpawnling (15): libg's readers exist and run
  once the instance is there (above), but no live A/B was done, so they stay out of `LIVE`.
- PoisonDamage, SlowIncrease, SmokeDuration, SuperBulletSpeed: every listed hero is HeroDeprecated; no brawler can carry them.
