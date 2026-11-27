# Loose findings and decisions (2026-11-23 .. 11-26)

Collected from the session handoff folder: things measured or decided along the way that have no issue or note of their
own. Each line is dated by when it was found. Check against the current code before relying on one.

## Measured

- **Scenario pass rates** (`scenarios.py`, 112 episodes, 2026-11-23):
  - The native AI and a fresh policy separate on `third_party`, `low_hp_close`, `cube_rich_low` and `assassin_rush`.
  - `gas_endgame` doesn't test skill: standing still passes it.
  - `bush_memory` passes by chance about 0.19 of the time.
  - `mate_under_fire` is hard even for the native AI.
  - The standard error is about 0.12 at 16 episodes per scenario.
- **`NbeResp` damage:** `damage_dealt` / `damage_taken` are per step, cleared after every response. MAEnv reads them
  correctly (2026-11-23).
- **Possible host bug, not fixed:** about 1 in 365 respawns in native-played battles comes back at the park spot
  (2026-11-23).
- **Piper's damage probe** (2026-11-25, one boot, 10 Piper, AI off): a plain shot at 9 tiles did 0 damage in 40 ticks.
  Unexplained and not checked further. Her super's 2 x 1800 at 1 tile is 4 bombs x 900 (#56).

## Decided by the owner

- **Generated maps** (`--gen`) are only for the vision models' training data, never for RL (2026-11-23).
- **Architecture:** a fast reflex policy (10 Hz) plus a slow planner that picks one intent about once a second with a
  readable reason, where `none` = free play. The planner is rule-based (about 10 rules), with no LLM. The design is in
  `behaviour_design.md`. An external LLM decision API is at most an optional offline auditor of planner picks, never in
  training.
- **Enemy brawler identity in the live bot:** no image-based brawler classifier, because new skins and brawlers are
  added too often. Identity comes only from the names shown during the countdown, read once per new track. Unknown =
  zeros + flag 0 in the observation (`obs_v5` ID_KNOWN).
- **Gadgets:** `--gadgets 0` in training until each kind is implemented and checked against its description
  (2026-11-25, after #54).
- **Game files:** they live in a separate private repository, never in this public one (2026-11-24).

## BrawlAPI (api.brawlapi.com), checked 2026-11-23

- It has no matchups, win rates, per-map stats or tile layouts: the stats arrays are always empty.
- `/game` and `/v2/raw` serve the same game CSVs the sim already reads from the APK, so there is nothing new for the sim.
- Possible use in the live bot: `/v1/brawlers` gives current display names and classes, a closed set for the name
  reading. `/v2/raw/csv_logic/characters` (+ skills, projectiles) gives stats for brawlers newer than the APK; check the
  columns match first. Fetch once per game update and cache it, never during a battle.
