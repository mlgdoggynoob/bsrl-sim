# Making the sim run

Everything the sim needs is in this repository: nirkt's battle host and environment are in `engine/` with this
project's changes already applied (README "Credits"). `setup.sh` builds it.

## Quick start (Linux x86-64 or WSL2 Ubuntu 24.04)

```bash
git clone https://github.com/mlgdoggynoob/bsrl-sim && cd bsrl-sim
./setup.sh                                                         # ~10 min the first time
source env.sh
python -m obs_v5 && python -m model && python -m env_v5 --check   # self-checks: no battle, need the game files
python -m live_check --n 2 --minutes 8                             # boots the host: teams, respawn, maps, HUD mask
python -m train_ppo --run t --smoke                                # 3-update plumbing check of the trainer
```

The game build is not stored in this repository. `setup.sh` downloads it (1.2 GB) once into `work/` from `APK_URL`, by default
nirkt's copy (the link from nirkt's original `setup.sh`; not an official Null's Brawl host, so it may go away). To use
a copy you already have: `APK=/path/to/nb_68.279_release_7c5c5152.apk ./setup.sh`. Either way its
`lib/arm64-v8a/libg.so` must match `engine/native/LIBG_SHA256`, or `setup.sh` stops before anything runs it. `./setup.sh --no-apt` skips system packages, `--no-python` skips
the venv. `TORCH_INDEX_URL` picks the torch build (for example ROCm or CPU wheels).

## Updating

`./update.sh` (from the repo root) brings a checkout to the latest `main` and rebuilds what changed: README "Updating".
`./update.sh --check` also runs the self-checks.

## What is in engine/

One tree of nirkt's code (`engine/NOTICE.md` says which file came from which repo):

| Folder | What | From |
|---|---|---|
| `engine/native` | Battle host: `loader` (host binary sources), `qemu` (patched `qemu-aarch64` build), `glhost`, `payloads`, `LIBG_SHA256` | [nirkt/bulletlabels](https://github.com/nirkt/bulletlabels) @ `52184b2` |
| `engine/py` | `nbpc` (instances, observation encoding, `MAEnv`, camera rules), `state2.py`, `dumps.py` (bulletlabels' `vendor/`); `models4.py` (network blocks, masked log-prob / entropy) and nbrl-env's other `py/` scripts | bulletlabels; [nirkt/nbrl-env](https://github.com/nirkt/nbrl-env) @ `7ff57bc` |
| `engine/train` | nbrl-env's example training loop | nbrl-env |
| `engine/labeller`, `framegen`, `debug`, `data`, `docs`, `tests`, `bl.py` | bulletlabels' vision-label tools (not used by the sim) | bulletlabels |
| `engine/patches` | This project's changes, listed below | this project |

Changes made to nirkt's code, all recorded in `engine/patches/`:
- `training_round.patch`: team groups, summons and area effects in the observation, per-instance map folders,
  teammate respawn.
- `fair_view.patch`: camera view window (measured trapezoid, per-episode zoom, teammates never bush-hidden).
- `live_state.patch`: live map tiles in `F_MAP` and the observation grid (a destroyed wall / bush reads as open),
  area effects' data id in item feature 5 (obs_v5 looks up radius and kind), power cubes lost at a team knock-out.
- `gadgets.patch` (issue #3, a diff on top of the three above): per-player gadget state in the response (`NbeResp`
  `gad_*`, mirrored in `nbpc/proto.py`) and the host's own gadget activation in `native/loader/gadget.c`, which
  `env.c` `gadget_input` tries first. It implements dash gadgets (the native charge mover, through `env.c`
  `env_dash_start`) and heal-over-time gadgets (Bibi, Byron; ticked from `env.c` `pre_snapshot`), with 3 uses per
  battle (unlimited since `guessed_numbers.patch`) and the game's own cooldown. Every other gadget still reads as not usable.
- `area_gadgets.patch` (issue #3, a diff on top of the patches above): `gadget.c`'s AREA kind (published as SPAWN), the
  gadgets that only drop their area at the brawler (Barley, Poco x2, Tick, Shade, Trunk), spawned with libg's
  `0xb35c40` after the row's ActivationDelay. `python -m super_audit --gadget` checks their effects.
- `gadgets_batch2.patch` (issue #3, a diff on top of `area_gadgets.patch`): more kinds in `gadget.c`. The gadget's own
  skill fired as its projectile(s) through libg's projectile spawn `0xb78190` (SHOT, published PROJECTILE) or as its area
  (Bull's Stomp, 8-Bit's Extra Credits); repeat_shot / spin_shoot volleys of the row's CustomObject projectile (off since
  `repeat_spin_off.patch`); items
  through the item factory `0xb55684` (Bolt, Gale); R-T's super charge (new `NBE_GAD_SUPER`, mirrored in `nbpc/proto.py`);
  instant heals through libg's heal `0xb41554` (Kit, Kenji). Eight rows that classify but showed no effect live are masked
  (`gadget.c` `g_masked`). `python -m super_audit --gadget [--gadget-slot 1]` and `python -m gadget_check` check them.
- `charge.patch` (issue #5, a diff on top of the four above): the charge supers in `native/loader/env.c`. The skill's
  ChargePushback after each contact hit (the game's knockback 0xb49834), Bull's straight lane that breaks walls and bushes
  up to the first unbreakable tile, El Primo breaking the tiles around his landing, trail areas (Stu, Berry, Trunk)
  through the game's own per-tick spawn, Crow's knives at take-off and landing, the end-of-charge area (Bull, Nori,
  Ollie, Damian), and env zones for the two area types the client never applies: Berry's paint (damage to enemies,
  heal to allies) and Damian's arena edge (knockback toward the side an enemy started on). `--native-charge 2` keeps
  only the movement.
- `hypercharge.patch` (issue #4, a diff on top of `gadgets.patch`): the hypercharge card on request (`NbeDiv.hyper_mask`,
  put in the player config by `offline.c`), activation by `NbeAction.fire` 4 through libg's own activation, and in
  `native/loader/hyper.c` the parts the client build lacks: the drain to 0 over 5 s, the end, and the speed / damage /
  shield buffs from `characters.csv` (`env.c` `rec_move` / `my_root`). State in `NbeResp` `hyp_*`, mirrored in `nbpc/proto.py`.
- `hypercharged_supers.patch` (a diff on top of `hypercharge.patch`): libg's `Character::isOvercharged` (0xb35bf0, a
  `return false` in the client build) answers true while a brawler's hypercharge is on, so the game's own skill code uses
  the `Overcharged*` columns of `skills.csv`; where `characters.csv` has an `OverchargedUltimateSkill` (7 brawlers; the
  game builds it as the brawler's third skill instance) it takes the super's place while hypercharged (`hyper.c`
  `swap_ulti` / `hyper_unswap`). Meg's mech takes Meg's card. `NbeResp` `hyp_supers` / `hyp_super_id` count the supers cast
  while hypercharged (`python -m super_audit --hyper`).
- `hyper_supers_fix.patch` (issue #32 item 3, a diff on top of `hypercharged_supers.patch`): `hyper.c` steers homing
  projectiles (TravelType 4: the client build leaves their target position at 0,0; this changes every homing shot, not only
  hypercharged ones), takes the overcharged list for AttackPattern 11's per-attack projectile (Lumi) and the Attack
  handler's summon (Pam), and heals with a hypercharged brawler's Heal areas (Pam); `superfix_moves.c` gives Blink's
  Damage enter area the scaled damage (Gigi).
- `showdown.patch` (issue #21, a diff on top of the others): Showdown rules the client build lacks. `native/loader/env.c`
  `elimination_tick` ends a battle with teams when one team is left (`NbeResp.winner` = that team's lowest-index player);
  `env.c` mirrors each brawler's power cubes into character `+0x874`, so libg's own death drop (inside the damage root)
  drops min(cubes / 3 + 1, 5) cubes, 2 at most for a trio group, as Trio Showdown does; a respawned teammate comes back
  after 17 s (`RespawnSeconds`) with 3 s of spawn protection. `python -m showdown_check` checks it live.
- `showdown_leftovers.patch` (issue #21, a diff on top of the others): the storm's ramp starts after 1 s in Trio (5 s in
  Solo / Duo) and healing inside the gas is halved (`env.c` `gas_tick`; `NB_GAS_RULES=0` restores the phone agent's storm);
  the Meteors and HealingMushrooms event modifiers as env tick jobs in `native/loader/showdown_mods.c`, off unless
  `NB_SD_MODIFIERS=3,5`; WallSpawn areas place every tile closer than their Radius (Sprout: a plus of 5, Rosa's Grow Light:
  3x3) and bush-grow areas grow bushes (`spawnfix.c` `wall_ring`). `NB_SD_DBG=1` logs storm hits and events.
- `trio_respawn_gas.patch` (issue #22, a diff on top of `showdown_leftovers.patch`): a brawler in a group of 3 that
  respawns on a gas tile gets no spawn protection (`env.c` `respawn_tick`; `NB_GAS_RULES=0` off). `NB_SD_DBG=1` logs
  every respawn's gas / protect decision.
- `supers.patch` (issue #6, a diff on top of `gadgets.patch`): supers whose effect the client libg compiles out, in
  `native/loader/superfix*.c` (status-effect store, areas, summons; `NB_SUPERFIX=0` turns it off).
- `status_movement.patch` (issue #19, a diff on top of `supers.patch`): speed boosts and slows from statuses in the mover
  (`env.c` `rec_move`), damage boost / reduce in `my_root`, stuns (projectile `StunLengthMS`, stun and silence areas,
  Bo's stun trap) through libg's stun counter, silence, `CcImmunity`, and Draco's weapon swap on mount
  (`native/loader/superfix_cc.c`; `NB_SUPERFIX_CC=0` turns the stuns, silence and swap off). `python -m status_check`.
- `obs_invisibility.patch` (issue #19, obs v5.9, a diff on top of `status_movement.patch`): the observation encoder
  (`native/loader/encode.c`) leaves out an invisible enemy brawler farther than its reveal distance (1200; "full"
  invisibility: any distance) from the enemy rows and grid channel 5; `env.c` `invis_reach` reads the status
  aggregate and Leon's super (broken by his attack).
- `star_probe.patch` (issue #20, a diff on top of the others): `native/loader/star.c`, the star power probe. With
  `NB_STAR_PROBE=1` it counts the config lookups 0xc34be0 / 0xc34c6c / 0xc34d10 per card type and logs them per battle
  (`offline.c` calls it at each build and tick); without it nothing is hooked. `python -m star_audit`.
- `star_card_hits.patch` (issue #20, a diff on top of `star_probe.patch`): `star.c` also logs, for every lookup hit, the
  card that answered and the player slot whose config it was (`[star] h` lines), so `star_audit` counts a card as read
  only when it answered itself, not when another card of the same Type did.
- `broken_supers.patch` (issue #32 item 5, #6 / #5, a diff on top of the others): normal supers whose server half is
  compiled out. `env.c`: Moe's dive (charge type 22; the folded change to DiggerDrill at 0xb3eae0 / 0xb3eae4 goes to
  `dig_change`, which sets the drill timer and spawns the surfacing hit) and Bonnie's landing hit (type 16, `charge_land`).
  `superfix.c`: Lou's Slippery area deals its damage once a second. `superfix_moves.c`: Kenji's cross slash (area type
  38) and the area of a ChangeCharacter super (Bonnie's return to Clyde, `bl` at 0xb7d010). `superfix_status.c`:
  `superfix_status_cancel` ends Kenji's hide at the slash.
- `guessed_numbers.patch` (issue #22, #32 item 7, a diff on top of the others): numbers checked against the game data and
  public sources. Gadgets have no per-battle use limit, only their cooldown, as in the live game since February 2025
  (`gadget.c` `GAD_USES`; `NB_GAD_USES=3` restores 3 uses). The meteor's warning and the mushroom's growth take 2.5 s,
  the ExplosionSpawn / HealingSpawn areas' TimeMs (`showdown_mods.c`). The other changes are source comments next to
  the numbers that stay guesses (`notes/issue22.md`).
- `status_leftovers.patch` (issue #19 leftovers, a diff on top of the others): `superfix_status.c` answers libg's
  compiled-out reload query 0xb38e04 (statuses' DecreaseReloadTimePercent: Starr Nova's hypercharged super) and
  lifesteal query 0xba3258 (LifeSteal / SourceLifeSteal: Starr Nova's super), keeps the Taunt / Fear flags of a
  character's statuses (`superfix_status_taunt`), and runs area types the apply drops: SmokeScreen (1, hides the owner's
  team inside, Sandy), DamageBoost (10), Heal without pushback (3), HealRegen (17), Cleanse (23), ExtraSuperCharge (31),
  Enemy / AllyChargeSuper (26 / 29). `env.c`: a taunted character walks at the source and a feared one away from it,
  for the policy's actions (`apply_actions`) and the native AI (`rec_move`), and neither attacks (`my_skill_block`).
  `superfix_cc.c` logs the taunt counters.
- `meg_mech.patch` (issue #32 item 5, a diff on top of the others): Meg spawns in her mech and the eject at
  0 HP is server code. `env.c` `mech_pop`: when the mech reaches 0 HP in any damage path, the client's own eject 0xb95364
  makes her small Meg (no kill, no duo / trio knock-out, super reset, no other hit that tick); knocked out as small Meg
  she respawns in her mech (`respawn_tick`). `hyper.c` `hyper_char_changed`: a running hypercharge follows any character
  change. `python -m charge_check` scene 5.
- `split_and_paint.patch` (issues #6 / #5, a diff on top of `meg_mech.patch`): R-T's split and Berry's paint.
  `superfix_moves.c`: the partner getter 0xb392d4 (compiled out) finds R-T's legs and the legs' head, and the host runs his
  Brawler_Splitter component tick 0xb9c42c, which libg never calls: while split his weapon is the legs' Eat Static (both
  blast when he attacks, client code) and he walks +100 faster (the stub 0xb5901c at that call site only, through
  `superfix_status_speed`); his second super puts him where his legs stand, removes them and heals him by 1000
  (SplitterLegs_ulti Value3); legs whose head is knocked out go too. `superfix_cc.c`: the weapon swap takes R-T's call
  site. `env.c`: Berry's paint (DamageScaleType 4) is a percent of his main attack Damage (660 damage / 330 heal per second
  at power 1, x2 at power 11) and his dash heals the teammates he passes by the skill's Damage. `python -m charge_check`
  scenes 4 and 6.
- `status_final.patch` (issue #19 final, a diff on top of `split_and_paint.patch`): `superfix_cc.c` applies Stun, Silence
  and HpBasedStun areas (Meeple's RageQuit, longer the less HP she has) with libg's own target test (circle, InnerRadius
  ring, RequireLineOfSight through the tile map's line test: Fang's sweep) and swaps Angelo's weapon to its SecondarySkill
  inside his SwitchSkill area. `superfix_status.c` runs more area types the apply drops: ChargeSuper and GiveUlti (Max's
  hypercharge), EnragerOverchargeSuper (Edgar: reload and super charge), BulletSpin (Darryl), HotAndOverheals (Pam's
  turret, as Hot). `superfix.c`: Max's hypercharged drinks to each teammate, and a summon's own AreaEffect (the turrets'
  heal, 8-Bit's booster, ...), which no client code spawns. `spawnfix.c`: Meeple's and Damian's wall areas. `gadget.c`: Fang's
  sweep, Painter's push and Meeple's RageQuit are AREA gadgets. `env.c`: Edgar's super charge percent. `python -m status_check`
  scenes 12-20.
- `heal_scale.patch` (issue #22, a diff on top of `status_final.patch`): heals at power 11, like damage (the owner's clip:
  Pam's turret +1400 a second at 10000 hp). `nbhost.h`: `P11_SCALE` 2. `env.c` hooks the area create 0xb2aefc: a heal
  word from power-1 numbers is x2 (not DamageScaleType 2 of a brawler, already a percent of power-11 hp; `NB_HEAL_SCALE=0`
  off). `superfix.c`: Pam's turrets heal 14 % of Pam's max hp a second (the clip; the data's 10 % of the turret's own hp
  gave 304), Poco's super heal x2. `superfix_status.c`: status Healing x2. `superfix_moves.c`: R-T's rejoin heal x2.
  `python -m status_check` scene 16. Notes: `notes/issue22.md`. Also (#6) Bonnie's hypercharged teeth: `spawnfix.c` starts
  BulletExplosion bullets BulletExplosionBulletOffset units from the centre (a ring; `NB_SPAWNFIX_OFFSET=0` off), and
  `env.c` charge_land gives the DamageScaleType 4 chain its Damage % of the skill's Damage (`notes/issue6-leftovers.md`).
  And (#19) `superfix.c`: a summon area of DamageScaleType 1 / 3 on a summon without that skill is made with type 0 (8-Bit's
  booster crashed the host; `notes/issue19-final.md`).
- `gears.patch` (issue #51, a diff on top of `heal_scale.patch`): two gears per player (`gear_boosts.csv`, ids 62xxxxxx)
  from the RESET's `div.gear` into the player config (+0x18 / +0x20, `offline.c` -> `gear.c` gear_equip: libg's own
  "allowed for this brawler" test, else `div_err`). `battle_fix.c`: the character's gear instances for every gear kind
  (were speed and regen only), so libg's own readers run (health regen, super charge, gadget cooldown, ...). `gear.c`
  re-implements the compiled-out ones: damage below 50 % hp and the 900 shield (`env.c` my_root), speed in bushes
  (`env.c` rec_move), reload (`superfix_status.c`); `NB_GEARS=0` turns those off. `NbeResp` gear_* fields.
  `python -m gear_check`. Notes: `notes/issue51.md`.
- `repeat_spin_off.patch` (issue #54, a diff on top of `gears.patch`): `gadget.c` no longer publishes the REPEAT / SPIN
  kinds (repeat_shot / spin_shoot rows with a projectile: Fang's Mines, Dynamike, Leaper, Gene, Barley's HealPotion,
  Bea, Darryl, Amber): they fired N copies of the main attack at full damage and range, not the game's numbers, so they
  publish kind NONE until redone from the game data (the code is kept under `#if 0`). Piper's Auto Aimer is redone as
  the AUTO AIMER kind (PROJECTILE): one PiperHandgunProjectile at the nearest enemy within the row's Range (7 tiles),
  main attack Damage x CustomValue1 % (90), refused with no enemy in range; the push is the projectile's own.
- `desc_audit.patch` (issue #55, a diff on top of `repeat_spin_off.patch` and `hyper_supers_all.patch`): gadgets made to match the game's own description
  (`python -m desc_audit`). AREA gives the row's ShieldPercent for ShieldTicks (Tick's shield before the burst) through a
  new `superfix_status.c` zone, `superfix_status_shield`; SHOT fires extra waves for the cards in `g_waves` (Colt's
  Gunslinger_Reload: two shots); Barley's healing potion (REPEAT fires it as main-attack damage) joins `g_masked`;
  `superfix_cc.c` gives Meeple's RageQuit its knockback (PushbackStrength, scaled like the stun) and lets it run under the stun.
- `gadget_damage.patch` (issue #55 follow-up, a diff on top of `desc_audit.patch`): gadgets that ran without the damage
  their data or text names. Fire 3's `super_dist` sets where a thrown gadget lands (`gadget.c` aimed_range, at least 300 u;
  Griff's coin shower); a SKILL AREA with AreaEffectFollowType 1 stays at the brawler (8-Bit's Extra Credits); ITEM gives
  the item the main attack's Damage x CustomValue1 % (Belle's trap); Gale's tornado joins `g_masked` (this libg has no
  WindWall push). `python -m super_audit --gadget`.
- `maenv.py` and `fair.py` copied from nbrl-env's `py/nbpc` into bulletlabels' `vendor/nbpc` (now `engine/py/nbpc`),
  so one `nbpc` package holds the host side and the environment side.
- The game download link removed from bulletlabels' `setup.sh` (`engine/setup.sh`) (this repo's `setup.sh` downloads it instead).

What `setup.sh` does: system packages (APT list at its top), builds the host as `native/loader/nbhost_rl` (static
ARM64 binary, runs under qemu; rebuilt when the sources in `native/loader` changed since the last build, whose hash is kept in
`nbhost_rl.src`), builds nirkt's patched qemu (~5 min; if that fails, `env.sh` uses the system
`qemu-aarch64`, about 2x slower, same results), creates `.venv`, downloads (unless `APK=` is given), unpacks and checks the game files.

`env.sh` finds all of it under `engine/`. Each path can be overridden: `SIM_ENGINE` (the engine folder), `SIM_WORK` (runs and the
downloaded game build, default `work/`), `SIM_VENV`.

## Troubleshooting
- **Nothing printed after start.** `MAEnv` retries a failed boot forever without a message. Boot one `nbpc.instance`
  with `log_dir=.` and read its `game_*.log`.
- **Every boot dies at once.** `NB_PIX_CAP` (set in `env.sh`, `2400*1080*4`) must equal the frame slot the host was
  built with (`NBE_PIX_CAP` in `native/loader/nbenv_proto.h`).
- **Variables come out empty.** `env.sh` must have LF line endings (CRLF breaks every variable). From Windows, pass
  scripts to `wsl.exe ... bash -s` on stdin.
- **Slow start.** One boot takes 60-90 s. Batch your checks into one run.
- **The fire head never uses most gadgets.** The game build compiles gadget activation out, and the
  host activates only the kinds `native/loader/gadget.c` implements (dash, heal over time, area at the brawler), so for every other
  gadget the class stays masked. `python -m gadget_check` shows which kinds the built host publishes.
- **The fire head never uses hypercharge.** It needs `--hyper 1` (players get their card) and a host built with
  `native/loader/hyper.c`. `python -m hyper_check` checks the built host.
- **Every boot crashes at "loading 45%".** A game file is a Git LFS pointer, not the file (seen with `assets/sc/ui.sc`
  from a git clone of the game files): run `git lfs pull` in that clone.
- **`gadget_check` / `hyper_check` say the host publishes no gadget / hypercharge state.** The host is older than its
  sources. `./setup.sh --no-apt --no-python` rebuilds it when `engine/native/loader` changed (a host built before
  `nbhost_rl.src` existed is rebuilt once).
