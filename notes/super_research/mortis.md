# Mortis (sim codename Undertaker): super and bush research for issues #91 / #92

Research date 2026-11-28. Tags: [wiki] numbers from the fandom MediaWiki API (Mortis page), [multi-source] 2+ independent sources,
[community] one guide / stats site, [unverified] my inference or no source, [repo] read from this checkout. Nothing in the repo was edited.
Game-table facts from the brief: class assassin, main attack = DASH (skills.csv weapon BehaviorType Charge, 2.67 tiles, melee), super
BehaviorType Attack (bats, 10 tiles, heals him).

## 1. Identity
- Mortis, Mythic, class Assassin, title "Creature of the Night" [wiki]. Sim codename `Undertaker` (roles.py asserts it as an attack-dasher with
  Geisha, Leaper, Samurai, Stalker; obs_v5 asserts brawler_stats("Undertaker")[7] == 1, i.e. melee) [repo]. The star power card is `Undertaker_unique`
  (star_check: steal_souls, heal 20 % of max hp on a kill) [repo].
- Main attack "Shovel Swing": he dashes 2.67 tiles in the aimed direction and hits every enemy brawler the dash passes through (pierce, damage
  along the path); no hit without moving; the dash is cut short by a wall in the way [wiki]. "Melee" in the sim's sense: he must reach the enemy.
- Long dash: while he does not attack, a yellow bar under the ammo bar fills in 4.5 s (2.5 s with Coiled Snake); full bar = the next dash is 2 tiles
  longer (4.67) after a short wind-up [wiki]. Two guides say it charges only with all ammo in hand [multi-source: clutchpoints 2026-07-31, gamewith 2025-06].
- Movement 855 ("very fast", same as Edgar); the dash itself runs at 2700 [wiki]. Reload 2.4 s per bar, 3 bars, no cooldown between dashes [wiki].
- Super "Life Blood": a swarm of bats in one direction, long range, passes through walls, damages enemy brawlers and heals him; width 2.67 tiles,
  bat speed 3000 [wiki].
- Whole kit = three back-to-back melee passes, a free gap-closer / gap-opener, and a through-the-wall ranged finisher that heals.

## 2. Numbers
| Item | Value | Tag + source |
|---|---|---|
| HP | 4000 (wiki infobox base). Other pages: 3800 (gamewith 2025-06, pinkcrow 2026-09), 8000 "level 11" (clutchpoints) | [wiki] conflict, see section 7 |
| Dash damage | 1000 per dash hit at base (infobox); 3 dashes = 3000 = 75 % of his own HP | [wiki]; pinkcrow says 1600 at its level |
| Attack range | 2.67 tiles; 4.67 with the full bar | [wiki] [multi-source: pinkcrow, gamewith] |
| Ammo / reload | 3 bars (one guide says 5, unsupported), 2.4 s reload, "second slowest in the game" | [wiki] / [community] pinkcrow |
| Super charge per hit | 21.25 % per dash hit; 30.15 % per super hit; no passive charge | [wiki] |
| Super range / width / speed | 10 tiles, 2.67 wide, 3000 (flight ~1 s); passes walls | [wiki] |
| Super damage / heal | 900 base (22.5 % of his own base HP); heals the full damage dealt, stacking per enemy hit, only on enemy brawlers (not boxes), nothing on a miss | [wiki]; gamewith 2025-06 and pinkcrow 2026-09 say 125 % of damage dealt [community] |
| Gadget Combo Spinner | instant spin, 2.67 tile radius, no ammo; 18 s cooldown; damage 1600 (infobox) vs 2000 (text) "same as main attack" | [wiki] conflict; Buffie: +30 % to enemies under 50 % |
| Gadget Creature of the Night | turns into bats: immune, untargetable, passes obstacles AND water, forced straight forward; range 5 tiles; 24 s cooldown (starts on use) | [wiki] [multi-source: exitlag / clutchpoints snippets "escape corners"] |
| Star power Creepy Harvest | +20 % max HP heal when he defeats a brawler | [wiki] [repo star_check] |
| Star power Coiled Snake | long-dash bar 4.5 s -> 2.5 s; Buffie: 35 % damage reduction 0.5 s on the long dash (nerfed 40 -> 35 % on 2026-04-22) | [wiki] / [community] mobilematters search snippet |
| Hypercharge Blood Boomerang | super returns to him: second wave of damage and heal (double), faster bat; +20 % speed, +5 % damage / shield; charge rate nerfed 40 -> 30 % (2025-03) | [wiki] [community] pinkcrow |
| Removed: Wasabi Power, Bat Storm gear | historic, ignore | [wiki] |
| Recent patches | Jan 2026 Buffie update reworked gadgets; Nov 2026 notes: no Mortis balance change (skin only) | [community] search snippet; supercell release-notes-november-2026 fetched |

## 3. #91 super_role
Roles: **finisher** (primary), **heal_self** (secondary, the heal is only on a hit). Also **utility** for through-wall pokes. He is NOT an engage_dash /
escape_dash by super: the dash is the MAIN ATTACK. Keep the planner's `dash_escape` rule (B1) for the escape and the dash for engage.
Why: the bats are his only ranged damage (10 tiles, over walls, ~1 s flight), heal the full damage dealt and are the 4th attack after three dashes are
spent; the wiki says to use them "when low on health and needs to heal quickly, or when the enemy is low and you can't reload an attack in time" and
to "try not to use his Super as a first attack unless very low on health" [wiki Strategies].
Repo note: roles.default(Undertaker) gives roles = (finisher,), ambush True, trigger 2.5, lurk False, rules (dash_escape,) [repo, read from roles.py, not run].
That is close to right; the proposal below adds heal_self and moves the trigger to 3.0.
Params: super_range 10, width 2.67, wall_pass true, damage 900 (base) = 0.225 x his own base HP, heal = damage (or 1.25 x), no stun, no slow.

| Situation | What to do with the super | Rule condition (planner terms) | Tag + source |
|---|---|---|---|
| Finish a low-HP enemy that is out of dash range or fleeing | bats at it, through walls | enemy within 10 tiles and its absolute HP <= 0.2 x my max HP (900 vs 4000 base; use the enemy's stats, not "< 50 %"), super ready, ammo may be 0 | [wiki] "snipe low-health Brawlers even through walls"; [community] pinkcrow "finisher on low-HP enemies" |
| Heal after a lost exchange | bats at any enemy brawler in the line | my hp < 0.5, an enemy brawler within 10 tiles in a straight line (a box heals nothing), no enemy within 3 tiles that out-duels me | [wiki] "when low on health and needs to heal quickly" |
| Multi-hit | wait for 2+ enemies in the line or in a close group, then super: heal stacks, super recharges faster (30 % per hit) | 2+ enemies within the 2.67-wide lane and 10 tiles | [wiki] "hit as many enemies as possible" |
| Team wipe chain | gadget (spinner) -> super -> dash: 3-4 attacks in about 1 s, heals him back up | enemies grouped, my hp >= 0.5, super ready, ammo 3 | [wiki Strategies]; [community] pinkcrow "Gadget, Super, Dash wipe" |
| Chase a fleeing enemy that is out of dash reach | super first (long range, ~1 s flight), dash to close | enemy 5-10 tiles, moving away, below ~40 % | [unverified] fits the numbers |
| Through-wall poke | safe poke at a camper behind a wall | enemy behind a wall within 10 tiles, his hp known and I am safe (no thrower in view) | [community] pinkcrow "safe pokes" |
| Escape heal | after a dash escape ends out of sight: do NOT super unless an enemy is in the lane; healing needs a hit | n/a | [wiki] "if the bats miss, Mortis doesn't heal" |
| DON'T | super as the opening attack at full HP and ammo | hp >= 0.8 and ammo >= 2 and no finish: hold it | [wiki] |
| DON'T | super at boxes (no heal, damage wasted) | target is not an enemy brawler | [wiki] |
| DON'T | super at a Piper mid-jump, a shielded or invulnerable target | enemy super / gadget active (Piper, Edgar jump, Sandy cloak): wait | [unverified] (Piper jump immunity in piper.md) |
| DON'T | keep the super when about to die: use it at hp < 0.3 only if the bats connect and no dash escape is available | prefer the dash first | [unverified] |
| Old advice | "do not hold it back, he can get stuck and need health" | 2019 guide, superseded | [community] samurai-gamers 2019-01-22 |

## 4. #92 bush play
**can_ambush: yes, with the dash (also without the super).** Short range, melee, assassin; the wiki: "Mortis can do well by simply bush-camping and staying
out of fights, dashing away when necessary", third-party fights after they end, "bush-camping and surprising enemies also works well" [wiki Tips].

(c) Trigger distance from a bush, given the 2.67-tile dash:
- Short dash: the dash carries him 2.67 tiles and hits anything in the lane; effective reach = 2.67 + the enemy's body radius (about 0.5 tile, [unverified]).
  Spring when the target is **<= 3.0 tiles** (the repo class default 2.5 is a little low: a target walking toward the bush is hit at 2.5, a stationary one at 3).
- Long dash (ammo full for >= 4.5 s, 2.5 s with Coiled Snake): reach 4.67 + body, spring at **<= 4.0-4.5 tiles** [wiki]. Wind-up is short; a bar charged while
  he waits in the bush is exactly the ambush bonus the wiki describes ("bush-camping and attacking when someone comes near") [wiki Other].
- He ends the dash 2.67 tiles from where he started: if the enemy was 1 tile away he finishes 1.67 tiles BEHIND it, out of the bush and unhidden.
  Plan the pass-through: dash 2 (back through it) and dash 3 as needed; each dash hit gives 21.25 % super, three hits = 64 %.
- Ammo gate for the spring: 3 bars to kill a full-HP squishy enemy (3000 base vs e.g. 3000-3800 HP), 2+ for a target at <= 60 %. The planner's "ammo >= 2/3" matches.

Lurk: yes, against enemies that out-range or out-trade him up close (see below) or while the long-dash bar fills; do not lurk vs a Piper-class sniper
that has seen the bush (a dash from 8 tiles is impossible, a super poke at 10 tiles is possible but exposes him).

(d) Who he dives / who beats him:
| Matchup | Evidence | Tag + source |
|---|---|---|
| DIVE: low-HP ranged and throwers: Brock, Dynamike, Tick, Colt, Nani, Bea, Barley, Crow, Piper, Meg, Rico (juke shots, dash in) | wiki lists them as targets; Bounty / Knockout counter-pick for the same set | [wiki Tips] (older list) |
| DIVE: Leon, Crow, squishy brawlers, grouped teams, low-HP long-range | noff "easy matchups" | [community] pinkcrow-style noff guide 2026-09 |
| DIVE: Bibi (dash through the wind-up), Frank / Ash harder but same trick | wiki: dash behind, gadget, dash in front, repeat; fails vs Hyper Buffie | [wiki Tips] |
| DIVE: Grom, Piper, Mr. P (gamewith "his matchups", easy to close in on and dodge) | | [community] gamewith 2025-06 |
| AVOID: tanks / heavies with more HP and a faster reload: Frank, Ash, Bull, El Primo (low DPS, 3 dashes do not kill them) | wiki: "avoid heavyweights or other assassins"; noff hard counters Frank, Ash | [multi-source] wiki + noff 2026-09 + clutchpoints 2026-07 (Bull, Frank) |
| AVOID: other assassins up close (Edgar, Fang, Leon, Lily) | wiki same sentence | [wiki] |
| AVOID: Shelly, Gale, Janet (knockback, escape, close firepower) | gamewith counter picks | [community] gamewith 2025-06 |
| AVOID: Tara (burst + super trap), Crow (poison cancels heal + mobility), Spike, Gene (pull) | noff 2024 snippet | [community] search snippet |
| AVOID: stun / slow / knockback gadgets: Dynamike's Satchel Charge; dangerous supers: Rico, Colt, Piper, Tick | wiki | [wiki Tips] |
| CONFLICT: Piper and Rico are listed as prey by the wiki and gamewith, as hard counters by noff 2026-09 ("bounce and snipe dashes") | single sources, see section 7 | [community] |

Bush tricks:
1. Entering an unknown bush: he cannot "shoot to check"; pre-aim the attack AWAY from the bush (or aim behind him) and walk in; if someone is there,
   release the dash and it takes him back out [wiki Tips] [community: a 2021 Reddit compendium seen only as a search snippet, outdated].
2. Dash INTO a bush as an escape: land the dash on a bush tile 2.67 (or 4.67) tiles away, break line of sight first; the planner's B1 already adds a bush bonus
   [repo] [unverified in game, follows from the dash ending where aimed].
3. Long dash out of a bush: stand 4.5 s (2.5 with Coiled Snake) with full ammo, spring from 4+ tiles [wiki].
4. Third party: wait out of sight until two enemies finish, dash on the survivor, take the cubes, leave [wiki Tips].
5. Do not open boxes with the dashes first: he runs out of ammo and loses the cube; if he must, dash along a wall (shorter dash = faster unload) and keep a reload [wiki Tips].
Reveal on attack: general rule only, attacking or taking damage reveals a brawler in a bush [community: Rosa / Jessie / Mega Box page snippets via edgar.md]; no
duration found for any brawler. His dash attack moves him out of the bush so the bush hides nothing after the spring. The Nov 2026 patch changes nothing here [supercell].

## 5. Mode differences
- Solo Showdown: conflicting. noff / pinkcrow (page dated 2026-09-26 but data "November 2025"): 53 % win rate, "top solo", Dark Passage and bush maps; GameWith (2025-06)
  "not effective in Showdown"; seemeta (2026-11-27) lists only S+ brawlers for solo / duo and he is not among them. Prior: playable A / B tier, strongest on bush-dense
  and wall-dense maps; play for kills of squishy targets and third parties, not boxes [community].
- Duo Showdown: let the partner check the grass, jump after the partner engages [community, samurai-gamers 2019].
- 3v3: seemeta 2026-11-27 ranked 50.5 %, tier A, pick rate 12 %; good in Gem Grab / Brawl Ball / Hot Zone (reaches the mine, carries, dashes away), poor in Heist,
  Knockout (long-range maps) [multi-source: seemeta, noff, clutchpoints, gamewith]. For the sim: in team modes dash to carry out a 2v1 with a partner and keep 1 bar for the escape.
- Super: in 3v3 it chains with a team wipe; in Showdown it is the heal and the finisher; keep it for a finish when the enemy has 2+ cubes.

## 6. Proposed rule sketch
Existing numbers: B1 dash_escape runs at hp < 0.35 + 0.1 (retreat - 1) with an enemy within 1.2 x its reach, or R >= 1.5 within reach + 2, ammo >= 1 bar, tile 4-6.7 away [repo planner].
- **dash_escape refinements (B1, after super_escape)**: keep >= 1 bar for the escape, 2 bars when an enemy within 6 tiles has a 6+ tile range. Choose the lane
  CLEAR of walls for the first 2.67 tiles (a wall cuts the dash; line check, not BFS steps), prefer sideways over directly away (dodges projectiles). With a full long-dash bar the first
  hop is 4.67 tiles: pick a tile 4.67 away. Reason: "hp 30 %, ShotgunGirl 3 tiles E: dashing W (attack), lane clear".
- **ambush trigger (R3)**: profile trigger 3.0 with ammo >= 2/3 (set `trigger=3.0` in BRAWLERS for Undertaker, not the class default 2.5); with the long-dash bar (no attack for
  4.5 s, ammo full) trigger 4.5. Reason: "Sniper 3 tiles E, in a bush: springing the dash".
- **super finish (rule 4, super)**: enemy within 10 tiles, absolute HP <= 0.2 x my max HP (use the known stats), ammo 0 or enemy outside dash reach -> super it, lowest HP first. Replaces the generic "< 50 %".
  Reason: "Sniper 8 tiles E at 15 %: bats (finish)".
- **super heal (near low_hp rule 3, before dash_escape)**: hp < 0.5, an enemy brawler within 10 tiles in a straight line, nothing within 3 tiles that out-duels me -> super it (the heal needs a hit).
  Reason: "hp 40 %, Sniper 8 tiles E: bats (heal)". When an enemy IS within 3 tiles at hp < 0.35: dash_escape wins, super only if the dash has no lane.
- **dive_squishy (new, next to rule 11 engage)**: known enemy range >= 5 tiles (or low-HP), R < 0.7, within 3 tiles (4.5 with the long bar), ammo >= 2/3 -> dash through it, second dash back. Reason: "Sniper 3 tiles E at 50 %: diving".
- **avoid_heavy (next to rule 7 outclassed)**: known Frank / Ash / Bull / Shelly / Edgar-class enemy with R >= 1.0 within its reach + 2 -> away (also blocks dive_squishy), the dash kept for the escape. Reason: "Bull 4 tiles E, full hp: staying away W".

## 7. Conflicts and gaps
- HP / damage numbers: wiki 4000 / 1000 / 900; gamewith 3800 / 1000 / 900; pinkcrow "level 11" 3800 / 1600 / 1800; clutchpoints 8000 / 2000 / 1800. The sim's skills.csv / characters.csv win; check
  the dash damage per hit and the super damage in the tables, then recompute the 0.2 x HP finish rule (it only needs the ratio super damage / max HP, which is 0.225 on the wiki numbers).
- Super heal: wiki "full damage" vs gamewith / pinkcrow "125 %". Check the table (needs a sim check).
- Ammo: wiki 3 bars; pinkcrow says 5 (looks wrong). Does the long-dash bar fill only at full ammo (clutchpoints, gamewith) or whenever he does not attack (wiki)? Matters for the "stay in the bush 4.5 s" rule.
- Wall behaviour: wiki, clutchpoints and samurai-gamers say a dash is cut short by a wall; pinkcrow says the long dash "can cross walls". Treated as: no wall pass; only Creature of the Night (5 tiles) and the bats pass.
- Counters: Piper / Rico = prey (wiki, gamewith) or counters (noff 2026-09). The wiki list is old (older ages of the game); the matchup lists are single guides. No win-rate matrix found: the seemeta matchup section was truncated by WebFetch (one Bo-vs-Mortis line only: ~50 %).
- Tier: pinkcrow / noff S-tier (53 %), seemeta A (50.5 % ranked), gamewith weak in Showdown. Dates on the noff page conflict (2025 label vs 2026-09-26 publish).
- Not found: reveal-on-attack duration (any brawler), whether a dash ending in a bush stays hidden, dash duration in seconds, the enemy hit box width for the 3.0-tile trigger, exact long-dash wind-up time.
- Needs the sim / host: dash hit width, whether the sim's Undertaker has the 4.5 s bar and the 4.67 tile long dash, super damage / heal, does a dash end inside a bush hidden (`w["sees"]`, `hid_vs`).
- The planner's B1 picks tiles by BFS steps, not by a straight lane; a wall on the lane cuts the dash [unverified in the sim].

## 8. Sources
1. https://brawlstars.fandom.com/api.php?action=parse&page=Mortis&prop=wikitext&format=json: all [wiki] numbers, Strategies / Tips / Other sections (edited 2026).
2. https://pinkcrow.net/brawl-stars/mortis-brawler-brawl-stars/ : stats, mode win rates (Showdown 53 %), hard counters, "can escape 1v3", "long dash crosses walls" (conflict); labelled 2025, page text 2026-09-26.
3. https://clutchpoints.com/gaming/brawl-stars-mortis-guide : 2026-07-31; ammo bar needs full ammo for the long dash; wall cuts the dash; Gem Grab / Hot Zone good, Knockout / Bounty not.
4. https://seemeta.com/en/brawl-stars/brawlers/mortis : 2026-11-27 ranked 50.5 % tier A; no Showdown rows; matchups truncated.
5. https://gamewith.net/brawl-stars/48092 : updated 2025-06-08; HP 3800, counter picks Gale / Janet / Shelly, matchups Grom / Piper / Mr. P, super heals 125 %.
6. https://samurai-gamers.com/brawl-stars/mortis-strategies-guide/ : 2019-01-22 (old); solo risky, duo let ally check grass, super "do not hold back".
7. WebSearch snippets: noff.gg guides (counters Crow, Tara, Gene, Spike; 2024-11), exitlag guide (sideways dash, pre-aim away from bush), mobilematters April 2026 patch (Coiled Snake 40 -> 35 %), vcgamers (low HP bonus gear, old).
8. https://supercell.com/en/games/brawlstars/blog/game-updates/release-notes-november-2026/ : no Mortis balance change, no general bush / reveal change; the 10 s invisibility power-up ends early if you attack.
9. [repo] this checkout: roles.py, planner.py (B1 dash_escape, R3 ambush), star_check.py (Undertaker_unique) [repo].
10. Could not open: noff.gg 16330 and 21588 (403), exitlag (403), brawlify (403). Reddit not tried.

## 9. Research log
- Worked: fandom MediaWiki API (3 curl, the best source), WebFetch on pinkcrow, clutchpoints, gamewith, samurai-gamers, seemeta, supercell notes; WebSearch (6).
- Failed: noff.gg (403 x2), exitlag (403), brawlify (403); seemeta is 279k characters and the matchup block was not in the first 3 slices.
- About 21 web calls (3 wiki curls, 6 searches, 12 fetches incl. 4 failures). No Reddit attempts.
- No source gives the escape ammo reserve or bush reveal time as a number; the "keep 1-2 bars" and 3.0 / 4.5 triggers are my derivations from the wiki's distances [unverified].
- At scale: one shared pass for the bush reveal mechanic; a sim matrix (Undertaker vs each brawler, dive from a bush at 3 tiles, 3 bars) would replace the guide matchup lists, which contradict each other.
