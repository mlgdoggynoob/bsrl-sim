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
  battle and the game's own cooldown. Every other gadget still reads as not usable.
- `area_gadgets.patch` (issue #3, a diff on top of the patches above): `gadget.c`'s AREA kind (published as SPAWN), the
  gadgets that only drop their area at the brawler (Barley, Poco x2, Tick, Shade, Trunk), spawned with libg's
  `0xb35c40` after the row's ActivationDelay. `python -m super_audit --gadget` checks their effects.
- `gadgets_batch2.patch` (issue #3, a diff on top of `area_gadgets.patch`): more kinds in `gadget.c`. The gadget's own
  skill fired as its projectile(s) through libg's projectile spawn `0xb78190` (SHOT, published PROJECTILE) or as its area
  (Bull's Stomp, 8-Bit's Extra Credits); repeat_shot / spin_shoot volleys of the row's CustomObject projectile; items
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
