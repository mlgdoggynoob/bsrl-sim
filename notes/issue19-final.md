# Issue #19 final: running notes

Branch `claude/focused-mayer-2c1pv8`, base d3080dd (main with `split_and_paint.patch`). Host change:
`engine/patches/status_final.patch`. Checked by `python -m status_check` battles 3 and 4 (scenes 12-20).

## Offsets (libg v68.279, static reading)
- Area type ints (string compares at 0xa96604, stored to AreaEffectData +0x118): 0 Damage .. 57 GiveUlti; the ones here:
  18 ChargeSuper, 19 PetrolDistribution, 32 EnragerOverchargeSuper, 33 SwitchSkill, 40 BulletSpin, 41 BulletSpin2,
  42 MeepleWallSpawn, 43 HpBasedStun, 44 MeepleCheatArea, 45 HotAndOverheals, 51 ShootsProjectileToSource, 55
  GladiatorWallSpawn, 57 GiveUlti. No `cmp` with 18 / 32 / 33 / 40 / 42-45 / 51 / 55 / 57 after a +0x118 load anywhere.
- AreaEffectData loader (0xa95800..0xa96604): +0x13c CustomValue, +0x140 CustomValue2, +0x144 BulletExplosionBulletDistance,
  +0x154 PushbackStrength, +0x17a IsPersonal, +0x17d RequireLineOfSight, +0x1b8 InnerRadius, +0x1bc InnerRadiusDamagePercent,
  +0x1a4..+0x1b0 OverHeal*, +0x1d4 LifeStealPercent, +0x1d0 SuperChargeScalePercent.
- The apply's own target test (0xb29e8c..0xb29fcc): r = 0xb2b298(data, ch); |dx|, |dy| <= r, then dx²+dy² <= r²; with
  InnerRadius > 0 and InnerRadiusDamagePercent == 0, closer than InnerRadius is out; with +0x17d the line test on the sim's
  tile map (0xc2a588 = sim +0x68): 0xa56398(map, ax, ay, cx, cy) if data byte +0x201 is set, else 0xa56dc0 (both call
  0xa563c8, w7 = 0 / 1); 1 = clear. +0x201 read as BooleanAttributes StrictLineOfSight [?] (only
  UndertakerGadgetSkillComboSpinnerBuddyAreaExplosion has it).
- CharacterData +0xb8 = AreaEffect (column global 0x123fe34, read at 0xaafbf4). No client code spawns it for a summon.
- StatusEffectData (loader 0xba3814): +0xc0 UltiChargePercent, +0xc4 UltiChargeBoostPercent, +0xc8
  OverchargeChargeReducePercent, +0xcc AmmoReducePercent, +0x13e..+0x142 AttackPierceCharacters / AttackThroughWalls /
  UltiAttackThroughWalls / MoveThroughWalls / MoveThroughWater (bytes).
- Max's hypercharged super: SpeedyUlti (AreaBuff) is the only skill with OverchargedProjectiles (+0x68, count +0x74) and no
  Projectiles (+0x64 == 0). Live: only SpeedyUltiOverchargedArea spawned, no projectile, before this patch.

## Done (status_check, this branch, all 20 scenes ok)
| Item | Host | Measured |
|---|---|---|
| ChargeSuper 18 (Max) | `superfix.c` max_drinks throws SpeedyOverchargedProjectile to each teammate; area_extra: CustomValue to each teammate brawler inside, once | teammate super charge 0 -> 1000 (of 4000) |
| GiveUlti 57 (Max) | area_extra: Damage (300) to each teammate inside, once (owner left out [?]) | not reached, see below |
| EnragerOverchargeSuper 32 (Edgar) | while the area lives: reload r = CustomValue 50 (my_reload_pct), super charge +CustomValue2 150 % (env.c my_charge) | ammo refill between attacks 213 -> 321; super charge per damage 0.325 -> 0.812 |
| SwitchSkill 33 (Angelo) | owner inside: slot 0 = weapon SecondarySkill (InsectManWeaponPoison), back outside (superfix_cc_switch) | MosquitoProjectile -> MosquitoProjectilePoison |
| BulletSpin 40 (Darryl) | each trail area: CustomValue (2) BulletExplosionBullets, 1300 u, spread turned 45° per tick [?] | BarrelBotOverchargedProjectile seen during the roll |
| HotAndOverheals 45 (Pam) | type set to Hot 4 at the first tick; summon areas (below) heal every 20 ticks [?] | teammate 2220 -> 3060 in 30 ticks (2 x 420) |
| HpBasedStun 43 (Meeple) | stun CustomValue2 + (CustomValue - CustomValue2) x missing HP fraction ticks [?]; RageQuit is an AREA gadget now | at 3600 / 6600 HP (16 ticks): enemy moved 0 u, later 240 u |
| GladiatorWallSpawn 55 (Damian) / MeepleWallSpawn 42 | spawnfix wall shape, tile DynamicCode = CustomValue (26 GladiatorWallDefault) | 5 GladiatorWallDefault tiles |
| Stun LoS (item 3) | superfix_area_reach in superfix_cc_area; Fang's KickerDude_Sweep (spin_shoot, no projectile) is an AREA gadget now | enemy in the open 0 u, behind a wall 240 u (not stunned) |
| Stun shapes (item 4) | the same test honours InnerRadius rings | no data row to measure, see below |

Summon areas (found on the way, needed for Pam): a summon's CharacterData AreaEffect never spawned (Pam's turret stood
with no area). `superfix_summon_area` spawns it once per summon (if no area of that data follows it), it ends with the
summon; Hot ones heal hurt allies inside every HOT_EVERY = 20 ticks (Pam's turrets: 14 % of Pam's max HP since
`heal_scale.patch`, `notes/issue22.md`) because libg's Hot apply healed nobody (teammate stayed 6600 / 7800 beside the
converted area). This also gives 8-Bit's DamageBooster, Bo's totem, Pam's normal turret and the other 25 AreaEffect summons
their area.

Checked afterwards (#22 branch, `heal_scale.patch`): one `super_audit --only` over the 21 brawlers whose super summons
(Jessie, Nita, Pam, Penny, Tick, 8-Bit, Mr. P, Ash, Meg, Lola, Eve, Bonnie and her small form, Larry & Lawrie, Moe and his
drill, Juju, Najia, Wendy, the two Super Nova forms) against `work/super_audit.json` of 2026-11-24: 8-Bit crashed the host
(SIGSEGV at 0xb0dc18: the area create reads the owner's weapon for DamageScaleType 1, and the booster has none); the other
20 unchanged or better (Meg, Najia partial -> works, the drill no_effect -> works). Fixed: a summon area of DamageScaleType
1 / 3 whose summon lacks that skill is made with DamageScaleType 0 (DamageBoost reads its percent from the data). Then 8-Bit
works, normal (DamageBoost r1000) and hypercharged (DamageBoosterOvercharge, 2484 damage); `--hyper` Pam works;
`--gadget` Rico and Starr Nova work, Bea partial (her slot-0 gadget is not a summon; no earlier gadget audit to compare).
Summons spawned only by gadgets the host does not implement (Bo's totem, Leon's area, Grom's tower, ...) were not reached.

## Not done, with evidence
- GiveUlti 57: comes from SpeedyWeaponOverchargedBuddy (SpeedyWeapon's OverchargedVersion; texts TID_SPEEDY_BUDDY_OVERCHARGE_DESC,
  the "buddy" variant). Live, Max's hypercharged main attack fires SpeedyProjectile (hyp_left 22 at the time), so the
  buddy weapon and its OnEnemyHit area never appear; scene 13 judges only if the buddy projectile shows up.
- ShootsProjectileToSource 51 (Mortis, MortisOverchargedBulletSpawner on UndertakerOverchargedWeapon, DontTriggerAreaAtEndOfCharge):
  live, his hypercharged dash is a type-4 charge with areas (nil) (nil) and no spawnAreaEffect call: the area is never
  created, so nothing to apply. Needs the server's spawn rule first.
- PetrolDistribution 19 (Amber): the areas last 500 ms; the lasting puddle and its ignition are server state. libg reads
  type 19 only in the client view (0x9b9e18) and in a helper that names "PetrolFire" (0xaa9870).
- MeepleCheatArea 44 (Meeple's super): its effect is the MeepleSuperArea status (AttackThroughWalls, pierce, hypercharged
  MoveThroughWalls / Water); no reader of those bytes here, so it needs projectile / mover collision changes.
- MeepleWallSpawn 42: implemented with 55, but unreached: Meeple_WallAttack is `swap_weapon_skill` (not in gadget.c) and
  EndOfLineProjectile has no playable user.
- BulletSpin2 41 (WrathOfAnAngelAreaEffect): no row references it.
- Stun shapes (item 4): every Stun / Silence / HpBasedStun row (ShamanBearSlam, BossTownCrushAoEArea, PullRopeStun,
  KickerDudeSweepStun, MaisieDashArea, MegaBossFrankStunArea, SandStormOverchargedUltiSilenceArea, MeepleRageQuitArea) has
  an integer Radius, no InnerRadius and no RectangularAreaEffectCollision; libg's own test is a circle (+ ring). So there is
  no non-circle stun area in v68.279; the host now runs libg's test, which would honour a ring.
- Buzz's PullRopeStun (on RopeDudeUltiProjectile): live, the super projectile flies but the area never spawns (the grapple
  is server code). Not a status bug.
- Status columns used by one brawler, stored with no effect: OverchargeChargeReducePercent (Starr Nova's hypercharge),
  AmmoReducePercent (Ollie's self status, SignalStrike), DamageBoostTargetCurrentHealthPercent (Alli),
  UltiChargeBoostPercent (Daredevil, RockWeaponDamageBoost, PowerLeveler), DamagePercentRedirectToSource (FutureGirl's
  turret), the through-walls bytes above.

## Guesses [?]
Edgar's values (which is reload, which super charge, both percents); GiveUlti leaves the owner out; BulletSpin's pattern
(SPIN_STEP 45); HpBasedStun's formula and its knockback left out; the summon Hot rate (20 ticks) and scale; Meeple's
CustomValue2 code unused; the turret's overheal shield not modelled.

## Checks (this branch)
status_check (20 scenes ok), hyper_check ok, charge_check 6/6, gadget_check ok (also `--roster KickerDude,Meeple`: SPAWN
6 of 6), test_fast ok, `train_ppo --run t --smoke` ok; `--check` of status_check, gadget_check, hyper_check, charge_check,
super_audit ok.
