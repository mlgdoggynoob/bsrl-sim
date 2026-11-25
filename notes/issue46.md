# Issue #46: activate the rest of the gadgets

Base: main 48387c6 (`gears.patch` last in the chain). Host change: `engine/patches/gadgets_batch3.patch` (`gadget.c`, two
small additions to `env.c`). Checked with `python -m super_audit --gadget [--gadget-slot 1]` and `python -m gadget_check`.

## Result

83 of the 213 enabled gadget cards (cards.csv MetaType 5, not Disabled) are usable now, 58 before this batch (the
README said 55; 8 more classified but were masked). New this batch, 25 cards, each one seen live in
`super_audit --gadget`:

| kind | how | cards (accessories.csv rows) |
|---|---|---|
| SKILL (11) | the game's own skill path runs the gadget's Skill | Charge skills: RocketGirl_Jump, Speedy_Dash, ShotgunGirl_Dash, Rock_Jump, Mender_DashHeal, FutureGirl_Leap; and BowDude_Totem, Ninja_InvisibleArea, Gladiator_Amp, MagicalGirl_FlyArea, HammerDude_Pull (5 of the 8 old `g_masked` rows) |
| NEXT (8) | the shipped skill code changes the next attack once the accessory is armed | Sniper_Seeker, ElectroSniper_Bounce, Silencer_BigProjectiles, Duelist_Silence, Skater_ProjectileTaunt, Chronomancer_ProjectileStasis, Reviver_OnlyDoubleHeal, Reviver_OnlyDoubleDamage |
| AREA (+6) | the accessory's AreaEffect at the brawler, as the existing AREA kind | HookDude_Push, ShieldTank_Heal, Morningstar_Fire, Morningstar_Ice, Dancer_BlockProjectiles, Daredevil_Hide |

Still masked (classify, no full effect live): HookDude_Homing (shots never hit), AssaultShotgun_Bomb (the skill path flies
the projectiles, no explosion, no damage), Speedy_Rewind (marker projectile and area spawn, the teleport back is server code).

## How (libg v68.279, static reading + live probes)

- Gadget skills. The input kind for a SkillData of type 5 (+0x1ac) is 18; 0xc2cef4 sends it to 0xb465c8(ch, 18, ...),
  whose 0xb591d8 looks for the character's skill instance of type 5, and the fire 0xb487c4 runs it. Two things were
  missing: the instance (the hero setup 0xb59de0 builds it at 0xb5a260..0xb5a294 into slot 3 of the 4-slot skill array
  (+0x458, count +0x464) from the hero entry's +0x88, which the host's roster leaves empty: slots 2 and 3 are NULL), and the
  player's gadget state the fire checks (0xc42d88: flag +0x19c, cooldown +0x198 = 0, uses +0x1a0 > 0, max +0x1a4).
  `skill_inst` builds the instance with libg's constructor 0xb7aa98 into slot 3 and calls 0xb8159c(inst, power level - 1)
  as the hero setup does; `skill_fire` opens the player state (the host keeps uses and cooldown itself) and sends the input
  (`env.c` `env_skill_fire`, the same input `skill_idx_input` sends). The skill activation 0xb7b268 then runs the
  BehaviorType's handler with the earlier rounds' fixes (charge mover, summons, items). Cooldown: the accessory's, else the
  skill's Cooldown, else its RechargeTime (getter 0xb0dc44, ms / 50: the Charge gadgets have Cooldown 0, RechargeTime 2400).
- Next attack. Character::getAccessory 0xb422c8 is `mov x0, xzr; ret` in this build; its 5 callers are in the skill code
  (0xb7b540 skill tick, 0xb7fc10 Attack handler, 0xb81f9c use-skill, 0xb82464, 0xb842ac). With it returning player +0x190,
  the use-skill code marks an armed (+0x3c) type 23 accessory applied (+0x54 = 1) when the weapon skill (instance +0x44 = 1)
  starts, and the Attack handler (0xb7ea6c) fires the accessory's CustomObject projectile instead of the weapon's
  (SubType 2); SubType 21 swaps the attack's area (0xb7fa7c). The arming and the end are server code: the host arms on use
  and disarms once the applied attack's weapon instance is idle again (`next_tick`), or at death. Every other reader of the
  accessory checks +0x3c first, so an unarmed accessory changes nothing.
- AREA also takes `spawn` rows with an AreaEffect and no CustomObject and `heal` rows with an area (SubType 5 / 6).

## Next-attack SubTypes (what the client code reads)

Reads of a type 23 accessory and the SubType compares found after them: skill code 2 (projectile swap, 0xb7ea8c), 21 (area
swap, 0xb7fa7c), 25 and 32 (both end in the compiled-out stub 0xb27cfc: server code); character code 0xb3b784 (SubTypes 9,
10, 12, 23, 24), 0xb4c090 / 0xb4d990 / 0xb4dcd8 (1), 0xb4d9e4 (7), 0xb4e2bc (3, 7, 11, then the stub), 0xb3e184 (29, stub),
0xb4f3f4 (30, stub). The character-code reads were not decoded or tried in this batch; with the accessory armed
(`next_classify` would take them) they are the next candidates: TntDude_Stun (3), ShieldTank_Pull (7), MinigunDude_AmmoSink
(10), Sandstorm_StunSleep (11), Cooker_Poison (23), Cooker_Healing (24). Their effects (stun, pull, poison) are not visible to
super_audit as it is, so a check would have to come with them.

## Not done, and why

- Summons and placed objects (`spawn` with a character: turrets, pets, decoys, towers; the meteor / air strike areas): the
  summon spawn 0xb5a6b4 takes values the Attack handler computes from power-level modifiers (0xb565b0, 0xb565a8, 0xb5281c);
  calling it from the host would need those worked out first. Not attempted.
- Status buffs, shields, transforms, vision, cocoons, the rest of `ulti_change` (the client reads +0x55 only for type 31 and
  then calls the stub 0xb27cfc), pets / summon control, rewind: the behaviour is server code; the rows hold raw CustomValues
  without units, so an implementation would be guessed numbers.
- swap_weapon_skill (4 rows): the client calls the stub 0xb27cfc and the change-skill stub 0xb35c3c; `superfix_cc.c`'s weapon
  swap could do the swap, but how long it lasts (ActiveTicks 100000 = until used, CustomValue6 1) is not settled. Not done.

## Every enabled gadget card, by accessories.csv Type

"usable (kind)" = the host activates it (dash / heal: gadget_check; the rest: super_audit --gadget, its class from the
runs for this batch); "not usable" carries the reason.

#### next_attack_change (37, 8 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Beamer | 23000545 | Beamer_Slow | not usable: SubType 33: no client code compares it (the reads decoded: SubTypes 1, 2, 3, 7, 9-12, 21, 23-25, 29, 30, 32); the change is server code |
| Beamer | 23000546 | Beamer_Pierce | not usable: SubType 16: no client code compares it (the reads decoded: SubTypes 1, 2, 3, 7, 9-12, 21, 23-25, 29, 30, 32); the change is server code |
| Chronomancer | 23000918 | Chronomancer_ProjectileStasis | usable (next_attack); audit: works |
| ClusterBombDude | 23000253 | ClusterBombDude_ExtraMines | not usable: SubType 8: no client code compares it (the reads decoded: SubTypes 1, 2, 3, 7, 9-12, 21, 23-25, 29, 30, 32); the change is server code |
| Cooker | 23000603 | Cooker_Poison | not usable: SubType 23: character code reads it (see 'Next-attack SubTypes' below), not decoded or tried in this batch: a candidate for the next one |
| Cooker | 23000604 | Cooker_Healing | not usable: SubType 24: character code reads it (see 'Next-attack SubTypes' below), not decoded or tried in this batch: a candidate for the next one |
| CrossBomber | 23000460 | CrossBomber_Burst | not usable: SubType 2 without a CustomObject projectile: the client branch needs the projectile name; the change (range / burst) is server code |
| DoorMan | 23000537 | DoorMan_Puller | not usable: SubType 17: no client code compares it (the reads decoded: SubTypes 1, 2, 3, 7, 9-12, 21, 23-25, 29, 30, 32); the change is server code |
| DoorMan | 23000538 | DoorMan_DamageDrop | not usable: SubType 8: no client code compares it (the reads decoded: SubTypes 1, 2, 3, 7, 9-12, 21, 23-25, 29, 30, 32); the change is server code |
| DragonRider | 23000736 | DragonRider_KnockUp | not usable: SubType 27: no client code compares it (the reads decoded: SubTypes 1, 2, 3, 7, 9-12, 21, 23-25, 29, 30, 32); the change is server code |
| Duelist | 23000588 | Duelist_Silence | usable (next_attack); audit: works |
| ElectroSniper | 23000463 | ElectroSniper_Bounce | usable (next_attack); audit: works |
| FishTank | 23000579 | FishTank_Slow | not usable: SubType 32: the client reads the armed accessory and calls the compiled-out stub 0xb27cfc; the effect is server code |
| Fury | 23001050 | Fury_Teleport | not usable: SubType 30: the client reads the armed accessory and calls the compiled-out stub 0xb27cfc; the effect is server code |
| Ghost | 23000834 | Ghost_IncreasedRange | not usable: SubType 25: the client reads the armed accessory and calls the compiled-out stub 0xb27cfc; the effect is server code |
| InsectMan | 23000678 | InsectMan_Pierce | not usable: SubType 16: no client code compares it (the reads decoded: SubTypes 1, 2, 3, 7, 9-12, 21, 23-25, 29, 30, 32); the change is server code |
| JetpackGirl | 23000473 | JetpackGirl_JumpAttack | not usable: SubType 15: no client code compares it (the reads decoded: SubTypes 1, 2, 3, 7, 9-12, 21, 23-25, 29, 30, 32); the change is server code |
| Leaper | 23000640 | Leaper_LongerJump | not usable: SubType 25: the client reads the armed accessory and calls the compiled-out stub 0xb27cfc; the effect is server code |
| Maisie | 23000572 | Maisie_ReloadAndDamage | not usable: SubType 19: no client code compares it (the reads decoded: SubTypes 1, 2, 3, 7, 9-12, 21, 23-25, 29, 30, 32); the change is server code |
| MinigunDude | 23000404 | MinigunDude_AmmoSink | not usable: SubType 10: character code reads it (see 'Next-attack SubTypes' below), not decoded or tried in this batch: a candidate for the next one |
| Painter | 23000767 | Painter_AreaDuration | not usable: SubType 28: no client code compares it (the reads decoded: SubTypes 1, 2, 3, 7, 9-12, 21, 23-25, 29, 30, 32); the change is server code |
| Puppeteer | 23000563 | Puppeteer_MoreDamage | not usable: SubType 18: no client code compares it (the reads decoded: SubTypes 1, 2, 3, 7, 9-12, 21, 23-25, 29, 30, 32); the change is server code |
| Reviver | 23000595 | Reviver_OnlyDoubleHeal | usable (next_attack); audit: works |
| Reviver | 23000596 | Reviver_OnlyDoubleDamage | usable (next_attack); audit: works |
| Sandstorm | 23000405 | Sandstorm_StunSleep | not usable: SubType 11: character code reads it (see 'Next-attack SubTypes' below), not decoded or tried in this batch: a candidate for the next one |
| ShieldTank | 23000522 | ShieldTank_Pull | not usable: SubType 7: character code reads it (see 'Next-attack SubTypes' below), not decoded or tried in this batch: a candidate for the next one |
| Silencer | 23000498 | Silencer_BigProjectiles | usable (next_attack); audit: works |
| Skater | 23000886 | Skater_ProjectileTaunt | usable (next_attack); audit: works |
| SnakeOil | 23000461 | SnakeOil_Spread | not usable: SubType 14: no client code compares it (the reads decoded: SubTypes 1, 2, 3, 7, 9-12, 21, 23-25, 29, 30, 32); the change is server code |
| Sniper | 23000291 | Sniper_Seeker | usable (next_attack); audit: works |
| SpawnerDude | 23000349 | SpawnerDude_ExtraPorter | not usable: SubType 6: no client code compares it (the reads decoded: SubTypes 1, 2, 3, 7, 9-12, 21, 23-25, 29, 30, 32); the change is server code |
| Stalker | 23000991 | Stalker_Lifesteal | not usable: SubType 29: the client reads the armed accessory and calls the compiled-out stub 0xb27cfc; the effect is server code |
| StickyBomb | 23000378 | StickyBomb_Range | not usable: SubType 2 without a CustomObject projectile: the client branch needs the projectile name; the change (range / burst) is server code |
| StickyBomb | 23000462 | StickyBomb_Vision | not usable: SubType 8: no client code compares it (the reads decoded: SubTypes 1, 2, 3, 7, 9-12, 21, 23-25, 29, 30, 32); the change is server code |
| TntDude | 23000294 | TntDude_Stun | not usable: SubType 3: character code reads it (see 'Next-attack SubTypes' below), not decoded or tried in this batch: a candidate for the next one |
| Whirlwind | 23000262 | Whirlwind_Trail | not usable: SubType 13: no client code compares it (the reads decoded: SubTypes 1, 2, 3, 7, 9-12, 21, 23-25, 29, 30, 32); the change is server code |
| Whirlwind | 23000317 | Whirlwind_Fly | not usable: SubType 5: no client code compares it (the reads decoded: SubTypes 1, 2, 3, 7, 9-12, 21, 23-25, 29, 30, 32); the change is server code |

#### spawn (19, 6 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| ArtilleryDude | 23000248 | ArtilleryDude_Cover | not usable: spawns a character / area at a target: needs the summon spawn 0xb5a6b4 (args computed by the Attack handler from power-level modifiers) or the server's meteor / air strike targeting; not attempted |
| BeeSniper | 23000271 | BeeSniper_Slow | not usable: spawns a character / area at a target: needs the summon spawn 0xb5a6b4 (args computed by the Attack handler from power-level modifiers) or the server's meteor / air strike targeting; not attempted |
| BlackHole | 23000356 | BlackHole_Shadows | not usable: spawns a character / area at a target: needs the summon spawn 0xb5a6b4 (args computed by the Attack handler from power-level modifiers) or the server's meteor / air strike targeting; not attempted |
| Blower | 23000277 | Blower_Trampoline | not usable: spawns a character / area at a target: needs the summon spawn 0xb5a6b4 (args computed by the Attack handler from power-level modifiers) or the server's meteor / air strike targeting; not attempted |
| Blower | 23000407 | Blower_Stopper | usable (item); audit: works |
| Cocooner | 23000625 | Cocooner_SpawnPets | not usable: spawns a character / area at a target: needs the summon spawn 0xb5a6b4 (args computed by the Attack handler from power-level modifiers) or the server's meteor / air strike targeting; not attempted |
| CrossBomber | 23000385 | CrossBomber_Vision | not usable: spawns a character / area at a target: needs the summon spawn 0xb5a6b4 (args computed by the Attack handler from power-level modifiers) or the server's meteor / air strike targeting; not attempted |
| Dancer | 23001041 | Dancer_BlockProjectiles | usable (area); audit: works |
| Daredevil | 23001071 | Daredevil_Hide | usable (area); audit: works |
| ElectroSniper | 23000371 | ElectroSniper_Trap | usable (item); audit: works |
| Flea | 23000454 | Flea_Jump | not usable: spawns a character / area at a target: needs the summon spawn 0xb5a6b4 (args computed by the Attack handler from power-level modifiers) or the server's meteor / air strike targeting; not attempted |
| JetpackGirl | 23000472 | JetpackGirl_DamageTower | not usable: spawns a character / area at a target: needs the summon spawn 0xb5a6b4 (args computed by the Attack handler from power-level modifiers) or the server's meteor / air strike targeting; not attempted |
| Luchador | 23000292 | Luchador_Meteor | not usable: spawns a character / area at a target: needs the summon spawn 0xb5a6b4 (args computed by the Attack handler from power-level modifiers) or the server's meteor / air strike targeting; not attempted |
| Morningstar | 23000907 | Morningstar_Fire | usable (area); audit: works |
| Morningstar | 23000908 | Morningstar_Ice | usable (area); audit: works |
| Ninja | 23000276 | Ninja_Fake | not usable: spawns a character / area at a target: needs the summon spawn 0xb5a6b4 (args computed by the Attack handler from power-level modifiers) or the server's meteor / air strike targeting; not attempted |
| Roller | 23000364 | Roller_Speed | not usable: spawns a character / area at a target: needs the summon spawn 0xb5a6b4 (args computed by the Attack handler from power-level modifiers) or the server's meteor / air strike targeting; not attempted |
| Ruffs | 23000347 | Ruffs_Cover | not usable: spawns a character / area at a target: needs the summon spawn 0xb5a6b4 (args computed by the Attack handler from power-level modifiers) or the server's meteor / air strike targeting; not attempted |
| Ruffs | 23000402 | Ruffs_AirStrike | not usable: spawns a character / area at a target: needs the summon spawn 0xb5a6b4 (args computed by the Attack handler from power-level modifiers) or the server's meteor / air strike targeting; not attempted |

#### (empty) (54, 45 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Arcade | 23000318 | Arcade_Double | usable (skill_area); audit: partial |
| AssaultShotgun | 23000399 | AssaultShotgun_Bomb | not usable: no Skill, no AreaEffect, no CustomObject: nothing in the tables says what it does (server code) |
| AssaultShotgun | 23000487 | AssaultShotgun_Projectiles | usable (shot); audit: partial |
| Barkeep | 23000250 | Barkeep_Slow | usable (area); audit: works |
| Baseball | 23000458 | Baseball_Sticky | usable (shot); audit: works |
| BowDude | 23000263 | BowDude_Totem | usable (skill); audit: works |
| BullDude | 23000272 | BullDudeGadgetSkillMarkEnemy | usable (shot); audit: works |
| BullDude | 23000310 | BullDude_Stomp | usable (skill_area); audit: works |
| Cactus | 23000247 | Cactus_ShootAround | usable (shot); audit: works |
| Cactus | 23000406 | Cactus_Cover | usable (shot); audit: partial |
| ClusterBombDude | 23000355 | ClusterBombDude_Explosion | usable (area); audit: works |
| Crow | 23000286 | Crow_PoisonDagger | usable (shot); audit: works |
| DeadMariachi | 23000267 | DeadMariachi_Regen | usable (area); audit: works |
| DeadMariachi | 23000350 | DeadMariachi_Cleanse | usable (area); audit: works |
| Domain | 23001000 | Domain_Area | usable (area); audit: works |
| Driller | 23000256 | Driller_SpeedBoost | not usable: no Skill, no AreaEffect, no CustomObject: nothing in the tables says what it does (server code) |
| Enrager | 23000340 | Enrager_Gadget_LetsFly | usable (shot); audit: works |
| FishTank | 23000580 | FishTank_Shield | not usable: no Skill, no AreaEffect, no CustomObject: nothing in the tables says what it does (server code) |
| FutureGirl | 23001320 | FutureGirl_Leap | usable (skill); audit: works |
| FutureGirl | 23001321 | FutureGirl_ProjectileGadget | usable (shot); audit: partial |
| Ghost | 23000835 | Ghost_Spooky | usable (area); audit: works |
| Gladiator | 23001247 | Gladiator_Amp | usable (skill); audit: works |
| Gladiator | 23001248 | Gladiator_Wall | usable (shot); audit: partial |
| Gunslinger | 23000273 | Gunslinger_Reload | usable (shot); audit: works |
| Gunslinger | 23000319 | Gunslinger_BigBullet | usable (shot); audit: works |
| HammerDude | 23000261 | HammerDude_Immunity | usable (shot); audit: works |
| HammerDude | 23000351 | HammerDude_Pull | usable (skill); audit: works |
| IceDude | 23000326 | IceDude_Freeze | not usable: no Skill, no AreaEffect, no CustomObject: nothing in the tables says what it does (server code) |
| KatanaKid | 23001298 | KatanaKid_FishNet | usable (shot); audit: works |
| MagicalGirl | 23001255 | MagicalGirl_FlyArea | usable (skill); audit: works |
| MagicalGirl | 23001256 | MagicalGirl_Healing | usable (shot); audit: works |
| MechaDude | 23000489 | MechaDude_ReloadTower | usable (shot); audit: works |
| Mechanic | 23000251 | Mechanic_Slow | not usable: no Skill, no AreaEffect, no CustomObject: nothing in the tables says what it does (server code) |
| Meeple | 23000878 | Meeple_RageQuit | usable (area); audit: partial |
| Mender | 23001183 | Mender_DashHeal | usable (skill); audit: works |
| MinigunDude | 23000257 | MinigunDude_BurstHeal | not usable: no Skill, no AreaEffect, no CustomObject: nothing in the tables says what it does (server code) |
| Mummy | 23000274 | Mummy_Push | usable (shot); audit: works |
| Mummy | 23000459 | Mummy_Acid | usable (shot); audit: works |
| Ninja | 23000408 | Ninja_InvisibleArea | usable (skill); audit: works |
| Percenter | 23000302 | Percenter_CharmAttack | usable (shot); audit: works |
| Percenter | 23000457 | Percenter_Lifesteal | usable (shot); audit: works |
| Rock | 23001282 | Rock_Jump | usable (skill); audit: works |
| RocketGirl | 23000245 | RocketGirl_Jump | usable (skill); audit: works |
| RocketGirl | 23000316 | RocketGirl_MegaRocket | usable (shot); audit: works |
| Rosa | 23000242 | Rosa_GrowBush | not usable: WallSpawn area: spawnfix.c's wall ring would build walls, not bushes |
| Shadowdemon | 23001191 | Shadowdemon_CloneBullet | usable (shot); audit: works |
| Shaman | 23000249 | Shaman_PetSlam | not usable: no Skill, no AreaEffect, no CustomObject: nothing in the tables says what it does (server code) |
| ShotgunGirl | 23000255 | ShotgunGirl_Dash | usable (skill); audit: works |
| ShotgunGirl | 23000288 | ShotgunGirl_Focus | usable (shot); audit: works |
| Speedy | 23000254 | Speedy_Dash | usable (skill); audit: works |
| Speedy | 23000311 | Speedy_Rewind | not usable: no Skill, no AreaEffect, no CustomObject: nothing in the tables says what it does (server code) |
| TrickshotDude | 23000409 | TrickshotDude_BounceHeal | usable (shot); audit: works |
| Undertaker | 23000265 | Undertaker_Swing | usable (shot); audit: works |
| Undertaker | 23000290 | Undertaker_Reload | usable (shot); audit: works |

#### ulti_change (7, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Ambusher | 23000755 | Ambusher_TeleportGrenade | not usable: changes the next super (the client reads +0x55 for SubType 31 only, then calls the compiled-out stub 0xb27cfc); server code |
| Conductor | 23000612 | Conductor_PassWalls | not usable: changes the next super (the client reads +0x55 for SubType 31 only, then calls the compiled-out stub 0xb27cfc); server code |
| Dancer | 23001042 | Dancer_RechargeUlti | not usable: changes the next super (the client reads +0x55 for SubType 31 only, then calls the compiled-out stub 0xb27cfc); server code |
| Roller | 23000401 | Roller_MegaStunt | not usable: changes the next super (the client reads +0x55 for SubType 31 only, then calls the compiled-out stub 0xb27cfc); server code |
| RopeDude | 23000392 | RopeDude_WeakUlti | not usable: changes the next super (the client reads +0x55 for SubType 31 only, then calls the compiled-out stub 0xb27cfc); server code |
| Silencer | 23000497 | Silencer_Mine | not usable: changes the next super (the client reads +0x55 for SubType 31 only, then calls the compiled-out stub 0xb27cfc); server code |
| WeaponThrower | 23000506 | WeaponThrower_Explode | not usable: changes the next super (the client reads +0x55 for SubType 31 only, then calls the compiled-out stub 0xb27cfc); server code |

#### give_buff_to_self (4, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Crab | 23000774 | Crab_DoubleTokens | not usable: status buff on self: the buff's strength / duration formula is server code (CustomValues have no unit in the tables) |
| Digger | 23000806 | Digger_Treasure | not usable: status buff on self: the buff's strength / duration formula is server code (CustomValues have no unit in the tables) |
| DragonRider | 23000737 | DragonRider_LastStand | not usable: status buff on self: the buff's strength / duration formula is server code (CustomValues have no unit in the tables) |
| Samurai | 23000817 | Samurai_OneAttackOnly | not usable: status buff on self: the buff's strength / duration formula is server code (CustomValues have no unit in the tables) |

#### swap_weapon_skill (4, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Alternator | 23000931 | Alternator_DamageMode | not usable: swaps the weapon skill for CustomObject (the client calls the stub 0xb27cfc then the change-skill stub 0xb35c3c); a swap through superfix_cc.c is possible, not done in this batch |
| Alternator | 23000932 | Alternator_SlowMode | not usable: swaps the weapon skill for CustomObject (the client calls the stub 0xb27cfc then the change-skill stub 0xb35c3c); a swap through superfix_cc.c is possible, not done in this batch |
| Meeple | 23000877 | Meeple_WallAttack | not usable: swaps the weapon skill for CustomObject (the client calls the stub 0xb27cfc then the change-skill stub 0xb35c3c); a swap through superfix_cc.c is possible, not done in this batch |
| Voodoo | 23000850 | Voodoo_AllBuffsAttack | not usable: swaps the weapon skill for CustomObject (the client calls the stub 0xb27cfc then the change-skill stub 0xb35c3c); a swap through superfix_cc.c is possible, not done in this batch |

#### give_status_effect (3, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Domain | 23001001 | Domain_InverseDamage | not usable: status / shield / transform on self: duration and strength come from server code, the tables give raw CustomValues only |
| PowerLeveler | 23000285 | PowerLeveler_ExtraLevels | not usable: status / shield / transform on self: duration and strength come from server code, the tables give raw CustomValues only |
| PowerLeveler | 23000485 | PowerLeveler_Shield | not usable: status / shield / transform on self: duration and strength come from server code, the tables give raw CustomValues only |

#### heal (7, 4 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Baseball | 23000275 | Baseball_Heal | usable (heal) |
| HookDude | 23000252 | HookDude_Push | usable (area); audit: works |
| Knight | 23000416 | Knight_Heal | not usable: heal SubType 3 needs state the host does not have (sleep, Knight's / Mecha's rage / mech, area heal with ally targeting) |
| MechaDude | 23000423 | MechaDude_Heal | not usable: heal SubType 4 needs state the host does not have (sleep, Knight's / Mecha's rage / mech, area heal with ally targeting) |
| Sandstorm | 23000270 | Sandstorm_Sleep | not usable: heal SubType 1 needs state the host does not have (sleep, Knight's / Mecha's rage / mech, area heal with ally targeting) |
| ShieldTank | 23000521 | ShieldTank_Heal | usable (area); audit: works |
| SnakeOil | 23000333 | SnakeOil_Heal | usable (heal) |

#### change_character (2, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Geisha | 23000940 | Geisha_Gadget_1 | not usable: status / shield / transform on self: duration and strength come from server code, the tables give raw CustomValues only |
| Geisha | 23000941 | Geisha_Gadget_2 | not usable: status / shield / transform on self: duration and strength come from server code, the tables give raw CustomValues only |

#### cocoon_self (2, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Cocooner | 23000626 | Cocooner_CocoonSelf | not usable: status / shield / transform on self: duration and strength come from server code, the tables give raw CustomValues only |
| Redirecter | 23001219 | Redirecter_CocoonSelf | not usable: status / shield / transform on self: duration and strength come from server code, the tables give raw CustomValues only |

#### consumable_shield (2, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| AxeJuggler | 23000670 | AxeJuggler_Shield | not usable: status / shield / transform on self: duration and strength come from server code, the tables give raw CustomValues only |
| Enrager | 23000403 | Enrager_Protection | not usable: status / shield / transform on self: duration and strength come from server code, the tables give raw CustomValues only |

#### take_damage (2, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Knight | 23000465 | Knight_Rage | not usable: status / shield / transform on self: duration and strength come from server code, the tables give raw CustomValues only |
| SoulCollector | 23000514 | SoulCollector_SelfDamage | not usable: status / shield / transform on self: duration and strength come from server code, the tables give raw CustomValues only |

#### teleport_to_pet (2, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Arcade | 23000259 | Arcade_Teleport | not usable: needs pets / summons (not spawned by this host) or position history (rewind): server code |
| Duplicator | 23000456 | Duplicator_Swap | not usable: needs pets / summons (not spawned by this host) or position history (rewind): server code |

#### vision (2, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| BlackHole | 23000266 | BlackHole_Vision | not usable: status / shield / transform on self: duration and strength come from server code, the tables give raw CustomValues only |
| RopeDude | 23000490 | RopeDude_Vision | not usable: status / shield / transform on self: duration and strength come from server code, the tables give raw CustomValues only |

#### absorb_shells_shield_pushback (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Bulletstorm | 23001063 | Bulletstorm_AbsorbShellsShieldPushback | not usable: server code (no skill, area or item the host could run; absorb_shells_shield_pushback) |

#### activate_skill (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| InsectMan | 23000677 | InsectMan_Fly | not usable: server code (no skill, area or item the host could run; activate_skill) |

#### aim_with_gadget_collision (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| TrickshotDude | 23000246 | TrickshotDude_ShootAround | not usable: server code (no skill, area or item the host could run; aim_with_gadget_collision) |

#### bush_slow (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Rosa | 23000348 | Rosa_BushControl | not usable: server code (no skill, area or item the host could run; bush_slow) |

#### chained_proj_speed (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| AxeJuggler | 23000669 | AxeJuggler_ProjectileSpeed | not usable: status / shield / transform on self: duration and strength come from server code, the tables give raw CustomValues only |

#### consume_bush (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Wally | 23000244 | Wally_Heal | not usable: server code (no skill, area or item the host could run; consume_bush) |

#### consume_fish_heal (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| KatanaKid | 23001297 | KatanaKid_HealFish | not usable: server code (no skill, area or item the host could run; consume_fish_heal) |

#### deal_dot_insta (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Crow | 23000243 | Crow_Shield | not usable: server code (no skill, area or item the host could run; deal_dot_insta) |

#### dive (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Puppeteer | 23000564 | Puppeteer_Dive | not usable: server code (no skill, area or item the host could run; dive) |

#### explode_souls (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| SoulCollector | 23000513 | SoulCollector_ExplodeSouls | not usable: server code (no skill, area or item the host could run; explode_souls) |

#### fake_main_attack (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Fury | 23001049 | Fury_FakeAttack | not usable: status / shield / transform on self: duration and strength come from server code, the tables give raw CustomValues only |

#### following_area (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| BarrelBot | 23000313 | BarrelBot_Slow | not usable: server code (no skill, area or item the host could run; following_area) |

#### invisible (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Attacher | 23000648 | Attacher_Cardboardbox | not usable: status / shield / transform on self: duration and strength come from server code, the tables give raw CustomValues only |

#### item_area_trigger (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| WeaponThrower | 23000505 | WeaponThrower_Pull | not usable: server code (no skill, area or item the host could run; item_area_trigger) |

#### jump (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Duelist | 23000587 | Duelist_Jump | not usable: server code (no skill, area or item the host could run; jump) |

#### kill_projectile (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Controller | 23000278 | Controller_Explode | not usable: server code (no skill, area or item the host could run; kill_projectile) |

#### mine_trigger (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| BowDude | 23000289 | BowDude_MineTrigger | not usable: server code (no skill, area or item the host could run; mine_trigger) |

#### movement_speed (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| CannonGirl | 23000480 | CannonGirl_Speed | not usable: status / shield / transform on self: duration and strength come from server code, the tables give raw CustomValues only |

#### override_bloodhunt_hp_trigger (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Stalker | 23000992 | Stalker_BloodhuntOverride | not usable: status / shield / transform on self: duration and strength come from server code, the tables give raw CustomValues only |

#### pet_attack_speed (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Mechanic | 23000295 | Mechanic_TurretBuff | not usable: status / shield / transform on self: duration and strength come from server code, the tables give raw CustomValues only |

#### pet_control (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Duplicator | 23000433 | Duplicator_StaticDuplicate | not usable: needs pets / summons (not spawned by this host) or position history (rewind): server code |

#### poison_trail (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Redirecter | 23001218 | Redirecter_PoisonTrail | not usable: server code (no skill, area or item the host could run; poison_trail) |

#### promote_minion (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| SpawnerDude | 23000269 | SpawnerDude_Promote | not usable: needs pets / summons (not spawned by this host) or position history (rewind): server code |

#### random_buff (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Jester | 23000530 | Jester_RandomBuff | not usable: status / shield / transform on self: duration and strength come from server code, the tables give raw CustomValues only |

#### random_ulti (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Jester | 23000529 | Jester_ReRollUlti | not usable: server code (no skill, area or item the host could run; random_ulti) |

#### recall_minions (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Shadowdemon | 23001192 | Shadowdemon_Recall | not usable: needs pets / summons (not spawned by this host) or position history (rewind): server code |

#### reload_spawn_shell (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Bulletstorm | 23001062 | Bulletstorm_Reload | not usable: server code (no skill, area or item the host could run; reload_spawn_shell) |

#### remove_item_and_ulti (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Conductor | 23000611 | Conductor_RemoveSign | not usable: server code (no skill, area or item the host could run; remove_item_and_ulti) |

#### repeat_shot (6, 5 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Barkeep | 23000293 | Barkeep_HealPotion | usable (repeat); audit: partial |
| BeeSniper | 23000312 | BeeSniper_ExtraBee | usable (repeat); audit: partial |
| FireDude | 23000488 | FireDude_FlameShield | usable (repeat); audit: partial |
| HookDude | 23000352 | HookDude_Homing | not usable: repeat_shot of Gene's homing projectile: the 5 shots fly but none hits (libg's homing runs only for hypercharged shots, hyper.c); masked |
| Leaper | 23000639 | Leaper_Shotgun | usable (repeat); audit: works |
| Sniper | 23000268 | Sniper_HandGun | usable (repeat); audit: works |

#### replace_innate_area (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Daredevil | 23001070 | Daredevil_Area | not usable: server code (no skill, area or item the host could run; replace_innate_area) |

#### reposition_wall (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Wally | 23000315 | Wally_Reposition | not usable: server code (no skill, area or item the host could run; reposition_wall) |

#### respawn_environment (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Driller | 23000486 | Driller_Rebuild | not usable: server code (no skill, area or item the host could run; respawn_environment) |

#### return_damage (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Controller | 23000353 | Controller_BounceBack | not usable: server code (no skill, area or item the host could run; return_damage) |

#### rewind (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Chronomancer | 23000917 | Chronomancer_Time | not usable: needs pets / summons (not spawned by this host) or position history (rewind): server code |

#### shadowrealm_transfer_self (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Ambusher | 23000754 | Ambusher_ShadowRealm | not usable: status / shield / transform on self: duration and strength come from server code, the tables give raw CustomValues only |

#### shield_based_on_move_speed (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Rock | 23001281 | Rock_Shield | not usable: status / shield / transform on self: duration and strength come from server code, the tables give raw CustomValues only |

#### shield_pet (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Shaman | 23000314 | Shaman_Shield | not usable: status / shield / transform on self: duration and strength come from server code, the tables give raw CustomValues only |

#### supercharge_tethers (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Mender | 23001184 | Mender_SuperchargeTethers | not usable: server code (no skill, area or item the host could run; supercharge_tethers) |

#### swap_secondary_pet (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Flea | 23000455 | Flea_Symbiosis | not usable: needs pets / summons (not spawned by this host) or position history (rewind): server code |

#### swap_skill_with_pet (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Twins | 23000661 | Twins_SwapSkill | not usable: needs pets / summons (not spawned by this host) or position history (rewind): server code |

#### throw_opponent (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Luchador | 23000264 | Luchador_Grab | not usable: server code (no skill, area or item the host could run; throw_opponent) |

#### trail (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| FireDude | 23000309 | FireDude_Spill | not usable: server code (no skill, area or item the host could run; trail) |

#### trigger_tags (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Splitter | 23000556 | Splitter_TriggerTags | not usable: server code (no skill, area or item the host could run; trigger_tags) |

#### trigger_ulti_area (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| IceDude | 23000400 | IceDude_AreaFreeze | not usable: server code (no skill, area or item the host could run; trigger_ulti_area) |

#### turret_barrage (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| ArtilleryDude | 23000287 | ArtilleryDude_Barrage | not usable: needs pets / summons (not spawned by this host) or position history (rewind): server code |

#### voodoo_self_buff (1, 0 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Voodoo | 23000851 | Voodoo_SelfBuff | not usable: status / shield / transform on self: duration and strength come from server code, the tables give raw CustomValues only |

#### charge_ulti (1, 1 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Splitter | 23000555 | Splitter_ChargeUlti | usable (super) |

#### dash (7, 7 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| CannonGirl | 23000481 | CannonGirl_Dash | usable (dash) |
| Crab | 23000775 | Crab_Dash | usable (dash) |
| Digger | 23000807 | Digger_Dash | usable (dash) |
| Lightyear | 23000869 | Lightyear_Accessory | usable (dash) |
| Maisie | 23000571 | Maisie_Dash | usable (dash) |
| Skater | 23000885 | Skater_Jump | usable (dash) |
| Twins | 23000662 | Twins_Dash | usable (dash) |

#### heal_attached_and_self (1, 1 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Attacher | 23000649 | Attacher_Cheeseburger | usable (heal_now); audit: works |

#### heal_damage_taken (1, 1 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| Samurai | 23000818 | Samurai_HealDamageTaken | usable (heal_now); audit: works |

#### spin_shoot (5, 5 usable)

| brawler | card | accessory row | now |
|---|---|---|---|
| BarrelBot | 23000260 | BarrelBot_Spin | usable (spin); audit: works |
| KickerDude | 23000440 | KickerDude_Mines | usable (spin); audit: partial |
| KickerDude | 23000464 | KickerDude_Sweep | usable (area); audit: works |
| Painter | 23000766 | Painter_Push | usable (area); audit: works |
| TntDude | 23000258 | TntDude_Spin | usable (spin); audit: works |
