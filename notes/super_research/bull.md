# Bull (BullDude): research for #91 (super_role) and #92 (bush ambush)

Researched 2026-11-28. Tags: [wiki] fandom MediaWiki API, [multi-source] 2+ independent sources agree, [community] one guide,
[unverified] no source / my inference. No Reddit, no game tables, no battle host: no number here is confirmed in the sim.

## 1. Identity
- Bull, Tank class, Rare, 15 launch brawlers (oldest tier). Fandom title "Bulldozer!". Codename `BullDude` is the sim's name; no web source gives it [unverified].
- Attack "Double-Barrel": 5 shotgun shells, spread 40.5 degrees, 440 dmg per shell, range 5.33 tiles, projectile speed 2853 [wiki].
  Damage falls off by shells missing, not per-shell falloff: full 2200 only when all 5 hit, i.e. at point blank [wiki + gamewith, multi-source].
  Not a lob (shells do not pass walls) [unverified, standard shotgun]. No pierce (the Hypercharge buffie adds pierce).
- Movement speed 800 ("Fast"); 2000 while charging [wiki]. Fast and tanky is the identity: he dodges, not tanks [community: fandom "Other"].
- Trait (Tank): the Super charges from damage TAKEN (all enemy damage incl. spawnables, after shields). 2.4 x max HP of damage = full Super [wiki].
  Each own hit also gives 11 % [wiki infobox].

## 2. Numbers
| Item | Value | Source |
|---|---|---|
| HP | 5000 | [wiki], gamewith [multi-source] |
| Attack | 5 x 440 (2200 max), reload 1.6 s, range 5.33 tiles | [wiki] |
| Charge per hit dealt | 11 % (20 % with T-Bone Missile hit) | [wiki infobox] |
| Charge from damage taken | 2.4 x max HP of damage to fill; so about 12000 dmg | [wiki Trait] |
| Super (Bulldozer) range | 11 tiles ("Very long") | [wiki infobox]. See section 7: looks long vs. my memory of the game |
| Super damage | 1000 per wiki; 960 per gamewith and the patch history (960 after the 2024 trait rework) | [wiki] vs [community], section 7 |
| Super effect | Charges in the aimed direction, destroys obstacles it hits, knocks back + damages enemies in the path; slows enemies within 3 tiles for 2.5 s at the END of the range | [wiki] |
| Super limits | Takes damage while charging (not airborne). Cannot be aimed to end in water. Knockback does not interrupt it, stuns do. Stops at indestructible walls (hypercharge text) | [wiki] |
| Super gain per cycle | Super charge 30 % per Super-charge hit [wiki infobox "SuperSuperCharge = 30%"] | [wiki] |
| Gadget T-Bone Missile | 1280 dmg + 1280 heal on enemy brawler hit, range 6, 18 s cooldown, 3 charges; not usable during Super (wiki page text says 1600/1600, the infobox 1280: conflict) | [wiki] |
| Gadget Stomper | 2.67 tile radius, slow 50 % for 1 s; on an already slowed enemy it STUNS instead. 20 s cooldown | [wiki] |
| Stomper + Super | Super slows at its end, so Stomper right after = stun. Guides also say Stomper during the charge cancels the Super (slow 1.5 s, 3 tiles) | [wiki, powerleagueprodigy, gamewith, fandom tips: multi-source] |
| Star Power Berserker | Reload doubles (0.8 s) below 60 % HP (older notes: 40 %, 50 %) | [wiki] |
| Star Power Tough Guy | -30 % damage taken below 30 % HP (gamewith says 40 %; metaforge snippet says 30 %) | [wiki] vs [community] |
| Hypercharge Jaws of Steel | During the Super: -80 % damage taken, +20 % speed (mobilematters 25 %), shield/damage boost 5 %. Hypercharge charge: 3.3 % per hit, 9 % per super hit, 30 % multiplier | [wiki], [multi-source on 80 %] |
| Hypercharge buffie | Main attack pierces; damage scales 5 shells at min range to 1 at max; projectile faster, range effectively longer | [wiki] |

## 3. #91 super_role
Roles: **engage_dash** (primary), **escape_dash** (secondary, good in team modes, risky in Showdown), **utility** (wall breaking, cuts through a ring of boxes / bushes).
Not a finisher by damage (about 1000 of 5000-hp targets) but it does close the gap for the shotgun finish that follows: the dash itself is the setup, the 2200 shotgun is the kill.
Why: the Super is a very long, fast charge that destroys walls; he deals nothing at range, so the dash converts "out of range" into "point blank".

| Situation | What to do with the super | Rule condition (planner terms) | Tag + source |
|---|---|---|---|
| Enemy hiding behind walls or in a bush, short-range or squishy | Charge through the wall / bush, then shotgun | super ready, enemy 5.3 to ~10 tiles, wall or bush between (LOS blocked), R < 0.7 or enemy < 50 % | [community] samurai-gamers "blitz opponents hiding behind walls or brush" |
| Open lane vs a ranged enemy that kites | Do NOT dash from far into open ground: he just loses HP while closing | skip when enemy range > 1.5 x mine and no cover on the path | [community] fandom, powerleagueprodigy, gamewith |
| Enemy low (< 40 %) and out of shotgun range | Dash then shoot | enemy < 40 %, dist 6-10 tiles; dash end within 5.3 tiles of its predicted position | [unverified] extends planner rule 4 |
| Aim | Stop beside the target, not past it; predict its movement | land point = enemy position + its velocity x ~0.5 s, end adjacent | [community] powerleagueprodigy "stops beside an enemy" |
| Check landing | Before charging, check what can hit him at the end (teammates absent, other enemies within reach) | no other enemy within its reach of the landing tile unless R < 0.5 | [community] powerleagueprodigy |
| Escape: low HP, enemy chasing | Aim away from the fight through terrain; walls broken on the way give a path | hp < 0.35, enemy within its reach, super ready, ideally a bush or cover within the dash length; open lane = he is still shot while fleeing | [community] fandom "Strategies", samurai-gamers |
| Escape in Showdown | The long charge can run into poison: aim so the end tile is not within 2 tiles of gas, or cancel with Stomper | landing tile >= 3 tiles from poison; if gadget ready and gas ahead, cancel | [wiki] fandom tips (poison warning) |
| Stomper follow-up | After the Super lands, Stomper at once turns the slow into a stun for the shotgun | enemy within 2.67 tiles right after the dash, gadget ready | [multi-source] wiki, powerleagueprodigy |
| Hold the Super | Bounty / 3v3: do not rush in with it unless desperate, it feeds stars and charges their super | team mode, enemy team full hp and 2+ enemies near the landing | [community] search snippet (bounty guide) |
| Hold: Brawl Ball | Do not knock enemies back near your own goal posts (can break your walls) | n/a Showdown | [wiki] |
| Hold: wall planning | Breaking a wall opens a path now, but makes the next approach harder and exposes him | do not break a wall that is the only cover between me and a stronger enemy | [community] powerleagueprodigy "walls mistake" |
| Heist / safe | Use super to reach and break the safe | n/a Showdown | [wiki] |
| Water | Cannot end in water, but can cross it (rush over water) | landing tile must not be water | [wiki] |
| Stun / knockback | A stun cancels the charge; knockback does not | enemy with a known stun (Stomper-like, Colette-like) near the landing: low confidence | [wiki] |
| Hypercharge | With -80 % during the charge, even a charge through several enemies is safe | hypercharge active -> relax the "landing check" above | [wiki] |

Super charge control: he charges the Super by TAKING damage, so "tanking early to fill the Super" is part of the kit; but guides say to dodge, not tank, because the enemy charges its own Super [community, fandom].

## 4. #92 bush play
- **can_ambush**: yes, even without the super. His shells do full damage only up close, he is fast, and 5000 HP survives the first exchange.
  "easy to surprise attack from the bush" [community gamewith]; "ambush from bushes, obstacles, chokepoints" [community fandom]; "great for surprising the enemy in Showdown when you start from a bush" [community, snippet].
- **Trigger distance**: shotgun full-damage reach is about 3 tiles (5.33 tiles max range, 5 shells at point blank; spread 40.5 degrees means a miss at long range) [wiki + unverified for the full-damage figure; check the sim's shell spread]. Charge super: from a bush, trigger when the enemy is 5 to ~9 tiles away (just outside its reach for short-range enemies), since the dash then covers the gap in about a half second (speed 2000 vs 800) [wiki speed, unverified timing].
- **Lurk (hold fire, stay hidden)**: yes vs shotgun / melee / medium-range brawlers that walk past; no vs long-range or throwers (they shoot the bush: 5000 HP is a big target; hiding gets him hit and gives them super charge).
- **Dive (R < 0.7, enemy < 60 % or squishy)**: Griff, Edgar, Mr. P [community gamewith]; Edgar, Fang, Darryl, Buzz, Alli, Wendy, Damian, Gigi [community powerleagueprodigy]; Nori [community search snippet]. Squishy / mid brawlers in general [samurai-gamers].
- **Avoid up close**: Shelly (knockback at close range) [multi-source gamewith + ppp + zathong snippet]; Gale (blows him away) [gamewith]; Chester (burst) [gamewith]; Maisie, Stu, Charlie, Colette, Lou, Otis, Surge [ppp]; long range (Piper-like) in the open [samurai-gamers].
  Lists conflict: ppp lists Edgar / Fang as Bull wins, other guide (zathong snippet) lists Buzz, Mortis as Bull counters ("Bull counters all of these"). Treat as noisy.
- **Bush tricks**: (a) charge out of a bush: the dash starts hidden, the enemy sees him only when he fires or when he is in vision; the super is visible once used ("Bull will be visible when he uses his Super") [community search snippet, no URL for the line]. (b) The dash destroys the bush it crosses: so a charge THROUGH a bush removes it as cover afterwards [wiki: destroys obstacles; whether bushes count is unverified]. (c) Speed gear gives 20 % faster movement while hiding in a bush [community snippet]. (d) Approach "through bushes or behind walls so Bull arrives at full health" [community snippet, ppp].
- **Reveal-on-attack**: no source found for the duration; the wiki has no Bush page via the API. Standard game rule: a brawler is revealed when it attacks from a bush [unverified]. No Bull-specific twist found. Bull's Hypercharge buffie gives a longer effective range but does not change visibility [wiki].

## 5. Mode differences
- **Showdown solo**: stalk from a bush, strike when enemies get close; hunt boxes and cubes, avoid poison when escaping with the super [community samurai-gamers, fandom].
  Close-quarter map = strong; gamewith rates Showdown as a strong mode for him.
- **Duo Showdown**: either waits in bush or tanks for the partner; pairs well with throwers (Barley, Tick, Grom, Dynamike) and minion summoners (Juju, Larry) [community fandom tips].
- **3v3**: super is the engage tool: Brawl Ball clears walls, Heist reaches the safe, Bounty focuses the top-star enemy and holds the super unless desperate [community samurai-gamers + snippet]. Gem Grab depends on terrain.
- Planner note: "team focus" rule 11 fits Bull best in team mode; in solo the super should stay at rule 4 plus a new ambush rule.

## 6. Proposed rule sketch
- **bull_ambush** (near rule 15 hide / after 13 check_bush): in a bush, enemy walks within 5.3 + 3 tiles, R < 0.7 or enemy hp < 60 %, ammo >= 2/3, super ready, enemy short or mid range -> super it from the bush and fire at the end. Reason: "enemy 7 tiles E at 55 %, super ready: charging out of the bush".
- **bull_dash_engage** (extends rule 4 super): super ready, enemy 5.3 to 9 tiles, wall or bush in the way or enemy range <= 5.5, no third enemy within its reach of the landing tile -> aim at the enemy's predicted tile, stop adjacent. Reason: "ShotgunGirl 7 tiles N behind a wall: bulldozing through".
- **bull_dash_escape** (next to rule 3 low_hp): hp < 0.35, enemy within 1.2 x its reach, super ready, a bush or cover within 8 tiles away from the enemy, no poison within 2 tiles of the landing -> super away from it. Reason: "hp 25 %, Surge 3 tiles E: dashing W".
- **bull_no_open_dash** (guard on rule 4 / 7): enemy range >= 1.5 x mine, no cover between us, hp < 0.8 -> do NOT dash; keep to bush / use walls. Reason: "Piper 8 tiles N in the open: holding the super, using cover".
- **bull_stomper_follow** (gadget logic, new): within 1 s after the dash lands, enemy within 2.67 tiles -> Stomper (slow -> stun), then shotgun. Reason: "enemy slowed by the super: stomping for the stun".
- **bull_gas_cancel** (near rule 1 gas): super in progress and landing tile within 2 tiles of poison -> Stomper cancel or do not start. Reason: "dash ends in gas: not charging".

## 7. Conflicts and gaps
- Super range: wiki says 11 tiles; I could not cross-check. Wiki ranges look inflated for charge supers; check `skills.csv` / the sim before trusting 11.
- Super damage: wiki 1000 vs gamewith / patch history 960 (history confirms 960 after a rework; the infobox may be newer). Wiki text says 1600 vs 1280 for T-Bone: mixed.
- Stomper during Super: sources disagree between "cancels the Super" (several) and "triggers the stun after landing" (wiki). Probably both, the first from older text.
- Tough Guy threshold: 30 % (wiki) vs 40 % (gamewith). Berserker 60 % (wiki; patch history 60 % since Dec 2020).
- Whether the dash breaks BUSHES: not stated; walls and obstacles yes. Needs a sim check (`engine` tile classes).
- Bush reveal duration on attack: no source. Nothing Bull-specific found.
- No pro commentary or YouTube found for Bull, mostly fan guides. Counter lists differ per site (ppp, gamewith, zathong, noff); treat them as soft.
- Could not open: noff.gg (403), destructoid (403), lootbar (404), brawlify not tried. Reddit not tried.

## 8. Sources
1. https://brawlstars.fandom.com/api.php?action=parse&page=Bull (MediaWiki API): infobox numbers, trait, super, gadgets, star powers, hypercharge, history, tips. [2026-11]
2. https://samurai-gamers.com/brawl-stars/bull-strategies-guide/: engage through walls / brush, escape, ambush with shotgun, matchups, Showdown vs 3v3. [undated]
3. https://powerleagueprodigy.com/bull: super landing, walls mistake, Stomper follow-up, matchup list. [undated]
4. https://gamewith.net/brawl-stars/48133: stats, matchups (Griff, Edgar, Mr. P good; Shelly, Chester, Gale bad), "easy to surprise attack from the bush". [undated]
5. WebSearch snippets: lootbar, destructoid, clasher.us, zathong, noff.gg builds (bush ambush, visible when super used, bounty advice, Stomper cancel, hypercharge 80 %). Could not open the pages. [Sept 2026 for one build page]
6. WebSearch for bush reveal: only Supercell release notes pages (2026) came up, no bush rule.

## 9. Research log
- Used about 18 calls: 6 fandom API (Bull page, tips, history; Bush page does not exist in API form), 4 WebSearch, 6 WebFetch, 2 failed WebFetch, 403s on noff / destructoid, 404 on lootbar.
- Wiki and 3 guides were good; no pro or video source. Search results mostly stale lists.
- At scale: query each brawler's fandom page first (cheap, structured), then 2 guide pages; skip noff / destructoid / brawlify unless fetched through a different path; add a search for "Bush" mechanic once, shared across brawlers, not per brawler.
- Sim check list: super range tiles, whether the dash clears bushes, damage 960 vs 1000, shell spread / full-damage distance.
