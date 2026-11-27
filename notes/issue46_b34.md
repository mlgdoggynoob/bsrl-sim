# Issue #46 batches 3b and 4: summon gadgets and charge gadgets

Game data and libg v68.279. Patch: `engine/patches/summons_dashes.patch`, a diff on top of `masked_seven.patch`.
Usable gadgets: 117 of 213 (was 100): 10 summon rows (batch 3b) and 7 Charge-skill rows (batch 4). Nothing new is
masked. No `OBS_VERSION` bump: summons use the existing summon rows, the charges publish the existing kind DASH.

## Batch 3b: SUMMON

`gadget.c`'s SUMMON kind takes a spawn row whose CustomObject is a characters.csv row and places it with libg's summon
factory 0xb56e00. SubType 1 / 2 put one at the brawler; SubType 5 puts CustomValue1 of them CustomValue2 out, in a ring
that starts at the aim angle (Ruffs: an arc toward the aim, 35 degrees apart), each pulled back onto walkable ground.

- Tara's shadows are retired after CustomValue3 ticks. Ruffs' sandbags get CustomValue4 % of his max HP.
- Grom's tower: the Vision area (type 27) has no client reader, so `gadget_summon_vision` answers `env.c`'s bush hiding
  (through `gadget_self.c`'s `gadget_vision`) for a living tower of the team within the area Radius.
- Janet's speaker (`superfix.c`): a summon has no weapon, so its Damage / Dot area with DamageScaleType 1 takes the
  summoner's weapon Damage x area Damage / 100, and its Dot area is applied again every 20 ticks (the card says "per
  second") while it and the summon live.
- Rico's Type 76 row (aim_with_gadget_collision only bends the aim line) is a SHOT. libg bursts the container by itself
  when it dies (one TrickshotDudeAccessoryExplosion, `spawnfix.c` fires its 8 bullets), so `gadget.c` does nothing more.

Live, `python -m super_audit --gadget`, slot 0:

| Row | Result |
|---|---|
| Penny ArtilleryDude_Cover | 1 barrel at the shooter; it took the target's shot, HP 1500 -> 0 |
| Bea BeeSniper_Slow | the target walked 373 u/s in the pot's area (table 720) |
| Grom CrossBomber_Vision | a bushed target hidden before, seen 10 ticks after |
| Janet JetpackGirl_DamageTower | 1220 damage over 80 ticks (20 before the Dot fix) |
| Stu Roller_Speed | the shooter walked 931 u/s in the booster's area (table 720) |
| Tara BlackHole_Shadows | 7800 damage; 3 shadows 400 u out, all retired by tick 127 |
| Charlie Cocooner_SpawnPets | 5600 damage; spider HP decays 700 -> 0 |
| Ruffs Ruffs_Cover | 3 sandbags at 2400 HP each (40 % of 6000) |
| Leon Ninja_Fake | the clone (libg's Minion_Mirage AI) dealt 5504 damage |
| Rico TrickshotDude_ShootAround | 8 burst bullets, 400 damage |

Guesses: the placement (at the brawler, the ring's start angle, the 35-degree arc); a new use replaces the last use's
living summons (MaxSpawns through the kill-oldest byte); Janet's damage scale and interval; Penny's CV1 and Leon's
CV1 / CV2 are not read. The summons keep their power-1 table HP (barrel 1500, pot 1000, tower 1500, speaker 1000, spider
700), as the other summons on this host do; only Ruffs' sandbags take theirs from the brawler, so against power-11
brawlers the others last about half as long.

Known gap: Leon's clone is reported as an enemy summon, not as a brawler, so an enemy policy can tell it from Leon at
once and the card's "confuse his enemies" does not happen for an agent. Reporting it as a brawler row would change the
meaning of an observation feature (an `OBS_VERSION` bump), so it is left for a separate change.

## Batch 4: CHARGE, and the dash extras

The CHARGE kind runs a gadget's Charge skill: the row's Skill (Wendy FutureGirl_Leap, Glowy Mender_DashHeal, Bolt
Rock_Jump, Brock RocketGirl_Jump, Max Speedy_Dash, Shelly ShotgunGirl_Dash), or the CustomObject skill of an
activate_skill row (Angelo InsectMan_Fly). It goes through `env.c`'s new `env_charge_start`, the native charge mover
0xb4790c with the skill's ChargeSpeed, ChargeType and ChargePushback:

- no super slot (+0x6d8 = 0), no contact damage, no hypercharge refill or pull at the end;
- jumps (ChargeType 11) and flights (20) go straight over walls (+0x98d / +0x98e), the end pulled back along the line
  onto walkable ground;
- the range is the skill's CastingRange; a jump without AlwaysCastAtMaxRange goes to the aim point (`aimed_range`);
- the skill's AreaEffectObject spawns at take-off, AreaEffectObject2 at the landing when AreaEffect2AtEndOfCharge is set;
- its ActivationSelfStatusEffects go on at the start (Max's shield), and the Reload flag fills the ammo (Shelly);
- at the landing, `charge_end` ends the CancelOnChargeEnd statuses (`superfix_status_charge_end`, the same thing
  libg's own charge end does through `my_charge_end`), so Max's 10-tick shield does not outlast a shorter dash;
- the landing area of Bolt's jump (RockGadgetJumpArea, DestroysEnvironment) breaks walls through libg's area apply: a
  probe run landed him one tile from a destructible wall and the wall tile became open;
- a new battle drops the charge jobs left over from the last one (`env_on_build`), since character ids restart.

DASH rows (gadget.c's own dash) now spawn their AreaEffect at the start (Maisie's stun) and SubType 3 adds CustomValue3
x 10 ammo (Clancy). DASH and CHARGE are not ready while the brawler is charging.

Live, `python -m super_audit --gadget`, slot 0 (moved = how far the shooter got, want = the distance gadget.c gives):

| Row | Result |
|---|---|
| Bolt Rock_Jump | moved 720 (want 720); 1000 damage from RockGadgetJumpArea at the landing |
| Brock RocketGirl_Jump | moved 450 (want 450); 2000 damage, the target pushed 1260 u; both areas |
| Wendy FutureGirl_Leap | moved 1500 (want 1500) |
| Angelo InsectMan_Fly | moved 1800 (want 1800); 660 damage from InsectManGadgetDamageArea |
| Glowy Mender_DashHeal | moved 1300; healed 2500 (MenderGadgetSkillHealArea) |
| Shelly ShotgunGirl_Dash | moved 800; ammo +1000 within 6 ticks of the gadget fire (one main attack 4 ticks before it spent a bar) |
| Max Speedy_Dash | moved 1000; the target's shot took 1400 HP before the dash, 0 during it |
| Clancy (dash, SubType 3) | moved 1000; ammo +1000 within 6 ticks of the gadget fire |
| Maisie (dash) | moved 800; the target walked 0 u/s in MaisieDashArea |
| Ollie (dash) | moved 1100 |

Also checked: `python -m gadget_check --roster` (DASH 7 of 7, moved 599-942), a slot-1 regression (Skater, RocketGirl
MegaRocket, Speedy_Rewind, ShotgunGirl_Focus, FutureGirl's grenade all work), and `python -m charge_check` (7 of 7
scenes ok, so the supers' charges are unchanged).

Partial, as before this change (the dash moves, the rest is not modelled): Bonnie (damage and push), Twins (heal), Moe
(push), Ollie (the landing taunt, SkaterGadgetTaunt). Angelo's flight and its damage work, but the drain does not heal him
back. Buzz Lightyear's row is not tested: the host rejects character 16000088.

`desc_audit` flags 4 new rows whose card says more than the host does; they are in `gadget_check.DESC_OPEN`:
CannonGirl_Dash, Twins_Dash, Digger_Dash and Rock_Jump (the card's "loses all speed"). Skater_Jump and InsectMan_Fly are
listed there too (the taunt, the drain's heal-back), though desc_audit does not flag them.

Guesses and not modelled: Bolt's speed loss; Angelo's drain heal-back and PushbackStrengthSelf; the
full range for Glowy, Max and Angelo (they have no AlwaysCastAtMaxRange, but are not jumps); Shelly's reload at the start rather than at the end. Cooldowns follow the batch 0 rule (BonusSkillCooldown): Max
300, Shelly 320, Glowy 340, Wendy and Angelo 360, Bolt and Brock 400 ticks.
