# Piper (Marksman, sim codename Sniper): research for #91 (super rules) and #92 (bush lurk / ambush)

Researched 2026-11-28. Tags: [wiki] = brawlstars.fandom.com MediaWiki API wikitext; [multi-source] = 2+ independent sources;
[community] = one fan guide / stats site; [unverified] = inference or conflicting. Numbers are ratios where the wiki mixes
power levels (see section 7).

## 1. Identity

- Name Piper ("The Sniper", prestige title "Headshots Only"). Class Marksman. Rarity Epic. 16th brawler. [wiki 1]
- Codename: the wiki gives none. The sim's "Sniper" is the title; no source confirms the internal name. [unverified]
- Attack "Gunbrella": ONE narrow bullet (width 0.67 tiles), no spread, no pierce, no lob (blocked by walls, so
  line-of-sight matters; the bullet is fast, projectile speed 4000). Range 10 tiles (11.67 with Homemade Recipe). [wiki 1]
- Damage grows with distance: 20 % of max at point blank, full damage only in the last 15 % of range (about 8.5-10 tiles).
  Between those two points the wiki does not say how it scales (linear is the natural guess). [wiki 1; the linear part unverified]
- Reload very slow (2.3 s per ammo), 0.5 s attack cooldown between shots, 3 ammo. Movement speed 750 ("Normal"). [wiki 1]
- Super "Poppin'": a jump (she is airborne about 2 s, immune to all direct damage) that leaves 4 grenades at her take-off
  point; she lands at the aimed spot up to 8.67 tiles away. Grenades knock back and destroy obstacles. [wiki 1]
- The sim treats her as ranged with a "weak up close" profile; every source agrees (section 4).

## 2. Numbers

| Stat | Value | Source |
|---|---|---|
| HP | 2800 (infobox; power level not stated) | [wiki 1] |
| Attack damage | min-range 360, max-range 1800 (infobox; level not stated). Ratio 20 % : 100 %. brawlhub quotes super bombs at 1800 each, wiki at 900: both are the same stat at different levels, so use ratios | [wiki 1], [community 8] |
| Range | 10 tiles; Homemade Recipe: 11.67 | [wiki 1] |
| Reload | 2.3 s (very slow); cooldown 0.5 s | [wiki 1] |
| Super charge per hit | 8.225 % (min range) to 41.225 % (near max range): 3 max-range hits charge it | [wiki 1] |
| Super charge per grenade hit | 20.25 % (hypercharge: 7.075 %) | [wiki 1] |
| Super range | 8.67 tiles (long) | [wiki 1] |
| Super grenades | 4 (6 hypercharged), 900 damage each (infobox), 2-tile explosion radius, 0.3 s fuse after landing | [wiki 1] |
| Super air time | about 2 s, full immunity to direct damage (damage over time still hurts) | [wiki 1] |
| Super quirk | quick-fired (not aimed) the jump lands on the spot she took off, no distance gained; the grenade knockback still pushes short-range enemies away | [wiki 1] |
| Auto Aimer (gadget) | pistol shot at the nearest enemy within 7 tiles, 25 % of min damage, knockback, 18 s cooldown, can cancel an enemy attack in progress | [wiki 1] |
| Homemade Recipe (gadget) | next shot homes, +1.67 tiles range, min damage raised to 25 % of max, 18 s | [wiki 1] |
| Ambush (star power) | extra damage while hidden in a bush: +35 % at max level (1260 extra on a 3600 shot, total 4860). Other pages say +1190 / +595; same stat at different levels or patches | [wiki 1], [community 8] |
| Snappy Sniping (star power) | each hit (also the Auto Aimer shot, turrets, summons) reloads 0.4 ammo | [wiki 1] |
| Hypercharge "Boppin'" | next super: 6 bombs, 1.2 s airborne (faster), lands with 4-tile knockback and a 3-tile terrain-destroying burst, +20 % speed, +5 % damage and shield | [wiki 1] |
| Win rate (3v3 data, 2026-11-27) | 60.6 % over 1849 recent ranked games; tier B (was A on Oct 16) | [community 6] |

## 3. #91 super_role

Roles: **escape_dash** (primary), **finisher** (secondary, only when it costs nothing), **utility** (wall breaking, team
modes only). Why: every source calls Poppin' her escape; the damage is a bonus that also knocks pursuers back, and she is
airborne and undamageable for about 2 s. It is NOT an engage dash: a dive ends with her in melee range of the target and a
slow reload, and the wiki calls the engage a "riskier play" ([wiki 1] Tips).

| Situation | What to do with the super | Rule condition (planner terms) | Tag + source |
|---|---|---|---|
| An assassin / melee brawler closes in (Edgar, Mortis, Leon, Fang, Bull, Darryl, Primo, Shelly, Buzz, Bonnie, Kenji, Rosa, Bibi) | Jump away, aimed (not quick-fired), land 7-8.67 tiles from it | super ready; known enemy melee or range <= 5.5 within 4-5 tiles (inside its dash range); my range >= 1.5 x its; landing tile aimed directly away | [multi-source] 1, 3, 5, 6 |
| Swarmed or pinned by 2+ enemies | Jump out; the grenades also knock the nearest back | super ready; 2+ enemies within 4 tiles; hp any | [community] 1, 4 |
| Aiming the landing | Land behind a wall, across water or a gap, not near another enemy; the 2 s airtime makes the landing spot predictable | landing tile reachable-for-me but with a longer path for the chaser (wall/water between), no enemy within 6 tiles of it | [wiki 1] Tips, [community] |
| Quick-fire when cornered | Quick-fire only against a short-range enemy in a real emergency (knockback is "reliable" at point blank); otherwise always aim | enemy within 2 tiles and no walkable tile 6+ tiles away in 5 steps | [wiki 1] |
| Low hp, enemy within 1.2 x reach | Jump before the hp fraction is lost, do not walk first (rule 3 would walk a slow brawler into a dash) | rule 3 condition + super ready + enemy fast/melee: jump instead of hide | [community] 2, 6 |
| Enemy below 50 % in super range and I am safe | Finisher is possible (4 x 900 within 2 tiles of the landing) but spends the escape | ONLY if no assassin / melee brawler is within 10 tiles and no 2nd enemy in view; else hold | [community] 5 ("using her super for damage spends an escape") |
| Opening the map | Drop grenades at walls an enemy hides behind or to open sight-lines; pros prefer this over escapes | team mode only, no assassin visible, enemy thrower / tank behind a wall within 8.67 | [community] 3, 8 (single-source each) |
| Don't: using it as an opener | Hold the super as zoning / finishing burst, not an opener; hold it until an enemy over-extends into her lane | super ready and no threat: do nothing | [community] 7 |
| Don't: breaking walls near mates | Walls she breaks may be cover for a teammate | team size > 1 and a mate within 6 tiles of the wall | [community] 5 |
| Don't: landing | Never land near other enemies or in gas; do not jump into the poison edge | landing tile >= 3 tiles from poison (same as rule 1) and >= 6 from any other enemy | [wiki 1] |
| Hypercharged jump | 6 bombs + 4-tile knockback on landing: land right behind an enemy, then back off and shoot. Strong finisher against assassins | hypercharge ready (not in cond today; ignore for now) | [wiki 1] |

Charge priority: sources say "charge Piper's super as a priority"; three max-range hits fill it. So she should shoot at max
range, not hold the shot [wiki 1].

## 4. #92 bush play

**can_ambush: no for melee-style ambush; yes only as a ranged ambush (shot from a bush).** Her bush play is a sniper nest,
not a dive. Short-range ambush is the worst thing she can do (360 vs 1800). Trigger distance:
8.5-10 tiles (full-damage band, with Ambush +35 % on top). Charge-super ambush: no, her super is a retreat.

| Topic | Finding | Tag + source |
|---|---|---|
| Lurk (hold fire, stay hidden) | Yes, in the bush against assassins and melee brawlers: they cannot hit what they cannot see, and a first shot at point blank does 20 % damage. Let them pass, or only shoot when they are 8+ tiles away | [community] 1, 2, 4 |
| Bush camp as sniper | Wiki Showdown tips: "Piper can bush-camp and snipe brawlers, especially with Ambush ... keep other brawlers at a comfortable distance and charge her super" | [wiki 2] |
| Ambush star power | Needs her fully hidden in a bush; the ammo bar turns yellow, the bullet trail turns rainbow. Best with 8.5+ tile shots | [wiki 1], [community 8] |
| Whom to dive | Nobody up close. Good matchups at range: Brock, Mandy, Belle, Byron, Gene, Bea, Bonnie, Colt (guide 5); stats 6 list Tick 69.6 %, Poco 61.3 % (but stats 7 has Poco beating her 55.3 %: see section 7) | [community] 5, 6, 7 |
| Whom to avoid up close | Assassins and tanks that cross open ground: Mortis, Edgar, Leon, Fang, Kenji, Mico, Crow, Buzz, Melodie, Shade, Darryl, Bull, Primo, Shelly | [multi-source] 1, 3, 4 |
| Counters in 2026 stats | Ash 73.9 %, Vince 69.7 %, 8-Bit 69.2 %, Chester 68.4 %, Gale 67.4 % (high-trophy ranked, 3v3 modes, count 317 for Ash); Eve, Nani, Angelo, Mr. P, Tick, R-T, Max, Mortis (guide) | [community] 6, 9 |
| She beats (stats) | Tick 69.6 %, Poco 61.3 %, Crow 60.5 %, Edgar 60.1 %, Dynamike 57.6 %; Mortis 50.7 % (even) | [community] 6 |
| Bush trick: jump into a bush | The jump can land in a bush 7-8 tiles away: she disappears from view when she lands. Not documented as a named trick; follows from the mechanics | [unverified] |
| Bush trick: Homemade Recipe | Use it when you know someone hides in a bush: the shot curves to the nearest enemy; works best against small bushes | [wiki 1] |
| Bush trick: Auto Aimer | Fire it at a pursuer who walks up to the bush: knockback + cancels its attack, then jump or shoot | [wiki 1], [community] 6 |
| Reveal on attack | Attacking from a bush reveals the attacker; no source gives a duration. Bo's "Buffie" gadget is described as removing the reveal, which implies the default is a reveal. Enemies also see you when they come close (no distance given). Vision gear: a damaged bush-hider is visible for 2 s | [community] 10 (search snippet), 11; duration [unverified] |
| Bush as heal spot | Hiding stops enemy tracking, but her HP regen starts only after a few seconds without damage or attacking (wiki Showdown tip) | [wiki 2] |

## 5. Mode differences

- Solo Showdown: weakest. Close-range brawlers dominate the maps, boxes are slow to break at her low close damage, and
  box theft is common [wiki 1]. brawlhub rates it 1/5 (June 2025) vs duo 4/5; samurai-gamers (2019) says she is "not a good
  pick" solo [community 8, 4]. A 2026 stats site rates Showdown S [community 7]: the sources disagree (section 7).
- Duo Showdown: a mate who covers the close range lets her snipe; "shines when she sees opponents" [community 4].
- 3v3 (Bounty, Knockout, Heist): stronger. Open lanes and mates screen the assassins. Win rate 51-53 % in modes listed [community 6].
- Showdown specifics: poison and cube drops; an escape jump over gas is worth a rule; cubes raise enemy HP so a finish
  needs more shots (strength R in the planner already covers it).

## 6. Proposed rule sketch (for the planner docstring style)

- **escape_jump** (sits between rule 2 rotate and rule 3 low_hp; before rule 7 outclassed): my super ready, a KNOWN melee enemy
  or one with range <= 5.5 tiles within 4.5 tiles, and (my hp < 0.7 or R >= 0.8) -> super aimed at the reachable-for-air tile 7-8
  tiles directly away that is >= 3 tiles from poison and >= 6 tiles from any other enemy, preferring a tile with a wall /
  water between. "hp 45 %, Edgar 3 tiles E: jumping W".
- **hold_super** (a gate on rule 4 super): for Piper, rule 4 (attack super at an enemy below 50 %) is blocked while any
  melee / fast enemy is within 10 tiles, or a second enemy is in view; only a FINISH (enemy < 25 % within 8.67) passes.
  Reason: the super is her escape. "enemy 6 tiles S at 30 %, Mortis 8 tiles W: holding the jump".
- **snipe_from_bush** (new, next to rule 13 check_bush / rule 15 hide): hidden in a bush, an enemy at 8.5-10 tiles, ammo >= 2/3 ->
  shoot (Ambush bonus); an enemy within 6 tiles that is melee / fast -> hold fire and stay hidden (lurk), if it comes within 3
  tiles with super ready -> escape_jump. "Colt 9 tiles N, in a bush: sniping".
- **max_range_kite** (extends rule 6 keep_away: her range 10 >= 1.5 x any range <= 6.5): keep 8.5+ tiles from any enemy,
  step back when it closes to < 6. "Bull 5 tiles E: keeping 8 tiles".
- **auto_aimer_peel** (gadget rule, if the sim models gadgets): enemy within 7 tiles and closing, super NOT ready -> Auto Aimer,
  then keep moving away. "Fang 4 tiles N, super used: peeling with Auto Aimer".
- **wall_open** (team modes only, low priority, near rule 5 thrower_wall): super ready, no assassin visible, an enemy thrower /
  tank behind a wall within 8 tiles, mate not within 6 tiles of the wall -> grenades at the wall. "TntDude 6 tiles NE behind
  a wall: breaking it".

## 7. Conflicts and gaps

- Assassin matchups conflict: the wiki and fan guides call all assassins a "major counter" [wiki 1], and one 2026 guide lists Mortis
  as a counter [community 9], yet 2026 stats show Piper beating Edgar 60.1 % and even vs Mortis 50.7 % [community 6]. Likely the
  jump is used well in ranked 3v3, or the sample is small. Leon and Fang: no data found. Treat assassins as a threat, not a
  proven loss.
- Showdown tier: brawlhub 1/5 solo [community 8], brawlio S [community 7] (that page contradicts itself: S modes vs "best modes").
- Ambush bonus: +35 % wiki, +1190 / +595 / +35 across sites (levels / patches). No 2026 patch source found.
- No source gives a duration for the bush reveal after attacking; wiki has no bush page (API: no page "Bush"). Needs game test or
  the sim's own visibility table.
- Whether the aimed jump passes over walls and water: the wiki says "jump over walls" only through a build page [community]; the
  Poppin' text says "land away". Treat landing as unrestricted by walls but needing a walkable landing tile [unverified].
- Unknown: exact damage curve between min and max range; super charge needed per fight in the sim's tables; the sim's codename
  (could be Sniper from "The Sniper"). Check skills.csv / the host: super range 8.67 tiles, 4 grenades, radius 2.
- [corrected at merge] cond 9 = super BehaviorType == "Attack" (obs_v5.brawler_stats); #91 lists Piper's jump under the
  Charge kind, so cond 9 is false for her and rule 4 does not fire today. The risk applies to any new super_finish rule
  that keys on role rather than BehaviorType. (Original text: cond 9 probably is TRUE for Piper; if so the existing rule 4 would fire her escape on a
  50 % enemy. This is the main #91 risk.

## 8. Sources

1. https://brawlstars.fandom.com/api.php?action=parse&page=Piper (wikitext; infobox numbers, super/gadget/star power text, tips, balance history; undated, current to Hypercharge era 2025-26).
2. https://brawlstars.fandom.com/api.php?action=parse&page=Showdown (wikitext; "Piper can bush-camp and snipe", healing and bush tips, box-hiding tips).
3. WebSearch snippets of Piper wiki "Strategies / Other" (assassin list, quick-fire warning, pros break walls): same wiki, 2026 text.
4. https://samurai-gamers.com/brawl-stars/piper-strategies-guide/ (22 Jan 2019; old: escape, "not a good pick in solo", duo cover fire).
5. https://powerleagueprodigy.com/piper (undated, recent; "super for damage spends an escape", hold the jump vs assassins, matchup list, wall-break warning).
6. https://brawl-up.com/brawlers/piper (2026-11-27; win rates, counters / victims, "save super for escapes when an assassin reaches her").
7. https://brawlio.app/brawlers/piper (2026-09-13; tier S, "zoning or finishing burst, not an opener", mode ratings).
8. https://brawlhub.co/brawlers/piper-brawl-stars/ (2025-06-20; 1800-damage bombs, Ambush +1190, solo 1/5, duo 4/5, hypercharge).
9. WebSearch snippets: noff.gg build pages (Nov 2026; Auto Aimer + Ambush or Snappy Sniping, Shield / Damage gears; pros break walls).
10. https://www.gamepressure.com/brawl-stars/how-can-i-hide/zfc615 (hiding in grass, seen when close or shot at; no timing).
11. WebSearch snippets of wiki Gears / Bo pages (Vision gear 2 s reveal; Bo no longer revealed when attacking from bushes) and the Jessie page (turret visible while attacking).
- Could not open: https://www.noff.gg/brawl-stars/build/10630/the-only-in-depth-piper-guide (403 from WebFetch); brawlstars.fandom.com HTML (not tried); Reddit (blocked, not tried). Search returned no Reddit snippets.

## 9. Research log

- Worked: wiki MediaWiki API (Piper, Showdown, search); WebFetch on samurai-gamers, gamepressure, brawl-up, brawlhub, brawlio, powerleagueprodigy.
- Failed: noff.gg 403; wiki has no "Bush" / "Obstacles" page; no search surfaced a source with the bush-reveal duration.
- About 24 web calls (6 searches, 7 fetches, 11 curl requests).
- At scale: fetch the wiki wikitext for every brawler first (infobox + super + tips), then one stats-site page per brawler for
  matchups; add a dedicated bush-mechanics query once for all brawlers (reveal duration), and test it in the sim instead.
