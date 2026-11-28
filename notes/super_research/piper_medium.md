# Piper (Marksman, sim codename Sniper): research for #91 / #92

Date 2026-11-28. Tags: [wiki] fandom API wikitext, [multi-source] 2+ independent sources, [community] one guide / snippet,
[unverified] inference or leak. Wiki infobox numbers are power-level-1 values; the level-11 figure is about x2 (see section 7).

## 1. Identity
- Piper, Epic, class Marksman. Wiki page title "The Sniper"; sim codename Sniper (repo notes/desc_audit.md rows Sniper_*). [wiki]
- Attack "Gunbrella": ONE narrow, fast bullet (projectile speed 4000, width 0.67 tile), no spread, no pierce, not a lob (walls
  block it). Range 10 tiles (Very Long), 11.67 with Homemade Recipe. Damage grows with distance: 20 % of max at min range,
  full damage in the last 15 % of range. 0.5 s between shots, reload 2.3 s (Very Slow), 3 ammo. [wiki]
- Movement speed 750 (Normal). [wiki]
- Super "Poppin'": hops away (a jump over walls), drops 4 grenades at the take-off spot. Hypercharge "Boppin'" is the variant. [wiki]
- Weak up close, "glass cannon", only strong at range. [wiki][multi-source: samurai-gamers, wiki]

## 2. Numbers
| Item | Value | Source |
|---|---|---|
| HP | 2800 at level 1 (infobox); June 2026 notes: "Health increased from 2500 to 2800" | [wiki]; supercell June 2026 release notes (src 4) |
| Attack damage | 360 at min range, 1800 at max (level 1); June 2026 notes: max 1700 -> 1800 | [wiki], src 4 |
| Range / reload / cooldown | 10 tiles / 2.3 s / 0.5 s between shots | [wiki] |
| Super charge per hit | attack 8.2 - 41.2 % (more at long range); super hit 20.25 % | [wiki] |
| Super range | 8.67 tiles (Long); she lands where aimed, quick-fire lands on the spot | [wiki] |
| Super effect | airborne 2 s, immune to damage while in the air (status / over-time damage still applies); 4 grenades under her, 900 dmg each (level 1), 2-tile blast radius, 0.3 s fuse after landing, knockback, destroys walls | [wiki] |
| Gadget Auto Aimer | shot at nearest enemy within 7 tiles, 25 % of min damage (wiki text 180 dmg), knocks back; cooldown 18 s (Oct 2025 notes: cooldown -50 %, damage +35 %, so the wiki value may be stale) | [wiki]; src 6 |
| Gadget Homemade Recipe | next shot homes, +1.67 tiles range, min damage 25 % of max; cd 18 s | [wiki] |
| Star power Ambush | +35 % damage while hidden in a bush ("+1260 at max range", total 4860 at level 11); ammo bar turns yellow, shot has a rainbow trail | [wiki]; game8 snippet says +800, noff +595 (older) |
| Star power Snappy Sniping | hit reloads 0.4 ammo (Auto Aimer hits count) | [wiki] |
| Hypercharge Boppin' | next super: 6 bombs, airborne 1.2 s (faster), knockback 4 tiles and wall destruction 3-tile radius on landing, +20 % speed, 5 % dmg / shield; charge 7.075 % per super hit, 2.9 - 14.4 % per attack | [wiki] |
| Level 11 (June 2026 leak) | HP 5000 -> 5600, max damage 3400 -> 3600 (consistent with 2 x the level-1 numbers) | [unverified leak: src 5 snippet] |

## 3. #91 super_role
Roles: **escape_dash** (primary), **utility** (wall breaker, secondary), **finisher** (rare, grenades 900 x up to 4 on a low or cornered target).
Why: invulnerable for 2 s in the air plus knockback grenades make it the one answer to an assassin on top of her; the damage is a bonus.
[multi-source: wiki tips, samurai-gamers "cannot be damaged while flying", powerleagueprodigy]

Parameters: range 8.67 tiles (aimed landing), 2 s airborne, jump passes walls and water [wiki: "behind walls, across water regions"],
blast radius 2 tiles, 4 grenades, grenade fuse 0.3 s after landing. Landing point is predictable (2 s in the air) [wiki].

| Situation | What to do with the super | Rule condition (planner terms) | Tag + source |
|---|---|---|---|
| Assassin / melee in her face (Edgar, Mortis, Leon, Fang, Buzz, Darryl, Bull, Primo, Shelly, Kit, Rosa, Bibi, Surge, Crow) | Aim the jump AWAY from it, past a wall or water if possible, grenades knock it back | super ready, enemy within ~4 tiles (its reach + 2, or R >= 1) and hp < ~0.6 or R >= 1: super aimed 6-8 tiles away from the enemy, landing tile not within 5 tiles of any other enemy | [wiki] + [community] src 1, 2 |
| Cornered in the open, low hp | Same, even quick-fired: the grenade knockback alone separates her from a short-range enemy | rule 3 low_hp with super ready and enemy <= 3 tiles: super instead of the walk-away; quick-fire allowed only if enemy range <= 5.5 tiles | [wiki] |
| Enemy low and next to her / charging | Super as a finisher: 4 x 900 in 2 tiles; she also escapes | enemy < 50 % within 2 tiles (rule 4 with range 2) | [community] |
| Enemies camped behind a wall (cover) | Pop a wall to open a lane for her range, when the open map suits her | super ready, strong enemy (R >= 1) hiding within 2 tiles of a wall that blocks LOS, no mate needs the wall | [wiki] + powerleagueprodigy ("check teammates' positions") |
| Rush: jump in, drop bombs, fly off | Risky offense, only when the enemy is low or clustered | 2+ enemies within 2 tiles of each other, both below 50 %, my hp >= 0.7 | [wiki] "riskier play"; [community] |
| DON'T: super only for damage | Pros keep it as the jump; powerleagueprodigy: "using your Super only for damage can leave you without a jump when an assassin reaches you" | Planner: do not fire rule 4 (super at an enemy < 50 % in range) when an assassin / melee enemy is within 8 tiles and no other jump source | [community] src 5 |
| DON'T: land near other enemies, or land short | Aim the landing; auto-aim / quick-fire lands where she took off | landing tile >= 5 tiles from all enemies, not in gas | [wiki] |
| Gas | Jump out of the gas is possible (passes walls) but the landing tile must be outside it | rule 1/2 with a wall between me and the safe zone and super ready | [unverified] inference |
| Hypercharge ready | Short 1.2 s hop, 4-tile knockback: aim the bombs BEHIND the enemy so the knockback pushes it into them | hypercharge on and enemy within 3 tiles | [wiki] |

## 4. #92 bush play
- can_ambush: **not as a melee-style ambush**. Her ambush is a long-range snipe from a bush (Ambush star power, +35 % at max
  range). Up close she does 360 (level 1, 20 % damage); only with the super ready is she a "can survive a charge" brawler.
  [wiki][multi-source]
- Trigger distance: shoot from a bush at 8.5 - 10 tiles (full damage in the last 15 % of range, i.e. >= 8.5 tiles). Below ~5
  tiles her shot is weak: stop lurking, Auto Aimer / super out.
- Lurk: yes against slow or non-ranged targets and when it hides her HP: hold fire in a bush, shoot only targets at 8.5-10 tiles
  (box breaking at range is slow; enemy near a box: shoot the enemy first) [wiki tips]. Do not bush-camp near assassins: a
  bush does not stop a dash; hit-reveal is temporary. [community]
- Dives (up close): nothing; she wins nobody up close except low hp ones. Mid range she beats Brock, Mandy, Belle, Byron,
  Gene, Bea, Bonnie, Colt. [community] src 5 (one site, lists look algorithmic: treat as weak)
- Must avoid: Eve, Nani, Angelo, Mr. P, Tick, R-T, Max, Mortis (src 5); assassins Mortis, Kenji, Mico, Crow, Edgar, Melodie,
  Buzz, Fang, Shade, Leon (wiki "Assassin Brawlers are a major counter"). [multi-source]
- Bush tricks: (a) Homemade Recipe: homing shot to flush a brawler in a small bush (large bushes too big for the curve) [wiki]; (b)
  super jump over a wall to a bush on the far side; (c) check bushes by shooting them before walking in (shoot first) [multi-source:
  notes/pro_strategies.md]; (d) Ambush hides her ammo bar colour (yellow in a bush).
- Reveal-on-attack: **not confirmed**. No source gave a duration for being revealed after attacking from a bush. One Reddit
  analysis snippet (Kaze / Kit / Leon thread) says being HIT reveals "only temporarily" [community, reddit (search snippet):
  r/BrawlStarsCompetitive "bug or feature buster and kaze"]. No Piper-specific twist: Ambush text says the bonus needs her to be
  "hidden in a bush" at the shot. [unverified for the reveal duration]
- Snappy Sniping is the reload build; Ambush is the lurk build. Auto Aimer + Ambush appears in a 2026 build (src 2 snippet).

## 5. Mode differences
- Solo Showdown: samurai-gamers says "not a good pick ... most maps favor close range", hence bush + long snipe + escape
  super; avoid boxes under enemy fire (boxes get stolen, slow to break). [community] src 3
- Duo: "shines when she can see and tag opponents from afar" (src 3); keep the partner between her and assassins.
- 3v3: Bounty / Gem Grab (shoot carriers) good; Heist (walls) fine; Brawl Ball / Robo Rumble weak [src 3]. Team play: the
  super's wall breaking can open lanes for mates; check where they are [src 5]. Lane: mid.
- 3v3 she wants covered positions behind mates; in Showdown she is alone, so the super is the only escape: hold it.

## 6. Proposed rule sketch (planner vocabulary)
- **escape_jump** (sits right after rule 3 low_hp, before 4 super): super ready, brawler is Sniper, enemy with R >= 1 or an
  assassin within 4 tiles (or any enemy within 2.5 tiles), hp < 0.6 -> super aimed 7 tiles away from the enemy, landing a
  reachable-over-walls tile >= 5 tiles from other enemies and outside gas. Reason "hp 25 %, Edgar 3 tiles E: jumping W
  over the wall (super)".
- **hold_super** (a guard on rule 4): for Sniper, do not super an enemy < 50 % at range unless it is a certain finish (<= 2 tiles) or no assassin / melee enemy is within 8 tiles. Reason "Mortis 6 tiles N: keeping the super for the jump".
- **snipe_from_bush** (sits near 13 check_bush / 15 hide): no enemy within 5 tiles, I am in a bush, an enemy 8.5-10 tiles away -> hold position and fire (do not step out). Reason "ShotgunGirl 9 tiles E, I am in a bush: sniping from here".
- **wall_open** (utility, near 5 thrower_wall): super ready, strong enemy behind a wall within 2 tiles of me, no mate needs it, hp >= 0.7 -> aimed pop of that wall. Optional, low priority. Reason "enemy behind wall 5 tiles N: opening the lane".
- **keep_away extension** (rule 6): for a Sniper, make Mortis / Edgar / Leon / Fang / Kenji / Mico / Crow / Buzz count as short-range
  threats even though their range is not <= 5.5, threat radius = their speed-plus-dash reach + 2.
- **pop_when_swarmed** (near 7 outclassed): 2+ enemies within 4 tiles and super ready -> jump out (grenade knockback).

## 7. Conflicts and gaps
- HP / damage at power 11: wiki (level 1) 2800 / 1800; snippet 5000 / 3400; June 2026 leak 5600 / 3600. Matches a x2 level factor;
  the sim's values (repo notes/cloud_runs.md mentions 1800 x 5 as a gadget copy) may follow the pre-/post-patch table. [needs a skills.csv check]
- Ambush bonus: wiki +35 % (1260 at max level), game8 +800, noff +595: older versions. Use the wiki / game table.
- Auto Aimer damage: wiki 180 (25 % of min) vs Oct 2025 notes +35 % damage / -50 % cooldown: wiki may be stale.
- Super grenades count: wiki 4; samurai-gamers says 3 (old); pick 4 (hyper 6). The sim's Poppin' needs a check (notes/cloud_runs.md
  r48 says the hypercharged super was a dud: bomb object never spawned).
- Not found: reveal duration after a bush attack; Piper-specific pro (esports) commentary; Fang / Leon / Edgar matchup details
  beyond the generic "assassins counter her"; Showdown-specific tier data. Reddit blocked (not tried). brawlify / noff: noff 403.
- Needs a sim check: does the sim's super pass walls; landing aim vs quick-fire; whether the invulnerable air time (2 s) is modelled;
  bush hidden flag at the shot for Ambush (notes/issue47.md says the trigger is not readable by the host).

## 8. Sources
1. https://brawlstars.fandom.com/api.php?action=parse&page=Piper (MediaWiki API, current): all numbers, tips, assassin list.
2. https://www.noff.gg/brawl-stars/build/22565/piper-1k-trophy-push-guide-and-build (403 on fetch; search snippet only: 2026 Ambush + Auto Aimer build).
3. https://samurai-gamers.com/brawl-stars/piper-strategies-guide/ (fetched, undated, older): flying immunity, solo vs duo, modes.
4. https://supercell.com/en/games/brawlstars/blog/release-notes/release-notes-june-2026/ : HP 2500 -> 2800, max damage 1700 -> 1800 (official).
5. https://powerleagueprodigy.com/piper (fetched, 2026) and https://powerleagueprodigy.com/blog/may-30-balance-changes-winners-losers-question-marks (snippet: May 2026 health buff; June leak 5600 / 3600): counters list, "don't super only for damage".
6. https://supercell.com/en/games/brawlstars/blog/game-updates/release-notes-october-2025 (snippet only): Auto Aimer -50 % cd, +35 % dmg; hyper duration.
7. reddit (search snippet): r/BrawlStarsCompetitive "bug or feature buster and kaze": hit-reveal is temporary. Not opened (the result was a mirror link: dropped at merge).
8. https://game8.co/games/Brawl-Stars/archives/317109 (snippet only): Ambush +800 (old). Not opened.
Not opened: gamewith, metaforge, seemeta, sportskeeda Piper, brawlify, gamepressure.

## 9. Research log
- 11 web calls: 2 curl to the fandom API (same page, worked), 5 WebSearch (guides, reveal, release notes, counters, bush mechanics), 4 WebFetch (3 worked, noff 403).
- Reddit not tried. No esports source found via search; "pro" claims here are guide-level.
- Search tends to return a generic summary: fetch the specific pages (sportskeeda, metaforge, gamewith) next time; use the wiki
  API for every brawler first (best numbers per call), then one search per open question.
- At scale: one wiki API call per brawler, one counter-list page (a single matchup table beats per-brawler searches), and
  one dedicated bush-reveal mechanics search shared by all brawlers (not per brawler).
