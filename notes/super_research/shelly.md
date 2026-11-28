# Shelly (sim: ShotgunGirl), research for #91 / #92

Tags: [wiki] = brawlstars.fandom.com via MediaWiki API (live 2026-11-28); [multi-source] = 2+ independent sources; [community] = one guide / fan page; [inference] = my own reasoning from numbers; [unverified] = no source.
Case for the #92 self-check: "Shelly vs Piper ambushes".

## 1. Identity
- Shelly, class Damage Dealer, rarity Starting Brawler (unlocked at the start). Title "No time to explain!". [wiki]
- Codename: no source gives it; the sim's "ShotgunGirl" is taken from the brief. [unverified]
- Attack "Buckshot": a cone burst of 5 shells (wiki). Spread 27 degrees, projectile speed 3100, range 7.67 tiles ("Long"). Damage per shell 340. [wiki]
  - Other sources disagree on the shell count (one search snippet says 9, another 5 shells of 4 bullets each). The wiki and gamezebo's "five times her attack" fit 5. [wiki] [conflict, see section 7]
  - No pierce through enemies on the main attack (each shell hits one target). Shells do not pass walls. The shot is a flat line, no lob over walls. [community: gamezebo "hits one target at a time"; wall: wiki on the Super]
- Super "Super Shell": 9 shells, spread 45 degrees, range 7.67 tiles (same as the attack), 360 per shell, pierces enemies, knocks surviving enemies back, destroys walls and bushes. Shells do NOT pass through walls: each shell vanishes after breaking one wall tile. [wiki]
- Speed: 800 ("Fast"). [wiki]
- Her attack gets deadlier the closer the target is: more shells land. Max damage is 5 x shell damage at point blank (1700 at wiki base level). [wiki, gamezebo]

## 2. Numbers
| Item | Value | Source |
|---|---|---|
| HP | 3900 (base, wiki infobox) | [wiki] |
| Main attack | 5 shells x 340 = 1700 max (all hit) | [wiki] |
| Range | 7.67 tiles (10 with Clay Pigeons) | [wiki] |
| Reload | 1.5 s | [wiki] |
| Spread | 27 degrees (13.5 with Clay Pigeons) | [wiki] |
| Full-damage zone | NO source gives a tile number. "Damage drops dramatically beyond 4 tiles" (PinkCrow, 2026-09-26). My geometry: at d tiles the cone is 2 d tan(13.5 deg) = 0.48 d tiles wide, so 5 shells span ~1.4 tiles at 3 tiles and ~1.9 at 4. An enemy ~1 tile wide takes most shells inside ~3 tiles. | [community] + [inference] |
| Super charge per attack hit | wiki infobox "10.05%" (7.5% with Clay Pigeons); per super hit 4.8%. Unit unclear (per shell or per attack). | [wiki], [unverified] unit |
| Super | 9 shells x 360 = 3240 max, range 7.67, 45 degrees, knockback, breaks walls and bushes | [wiki] |
| Super hits 2 enemies | recharges it (chains of 2-3 supers possible) | [community: PinkCrow] |
| Fast Forward (gadget 1) | dash 2.67 tiles (wiki) / "3-tile" (PinkCrow); fully reloads ammo; 16 s cooldown; cancelled by stun / pull / knockback; stopped by walls and water; no damage taken during the dash only with the Buffie. Pick rate 75 %. | [wiki], [community] |
| Clay Pigeons (gadget 2) | next 3 shots: half spread, range 10 tiles, faster shells, same damage, use ammo; 18 s cooldown | [wiki] |
| Shell Shock (star power 1) | Super slows hit enemies 55 % for 2 s (wiki); PinkCrow says 3 s. Pick rate 68 %, "generally outvalues the heal" in 3v3. | [wiki], [community] |
| Band-Aid (star power 2) | when below 40 % HP, instant heal 30 % max HP (2340 at base), bar recharges 15 s. Does not trigger if she is killed from above 40 % in one frame (Bull, Darryl, Nani, Griff, Spike). Most useful in Solo Showdown and Knockout. Scales with power cubes. | [wiki], [community] |
| Hypercharge "Double Barrel" | Super 9 -> 12 shells, spread +33 % (59.85 deg), +20 % speed, +5 % damage and shield; hypercharge multiplier 30 % | [wiki] |
| Piper (the opponent) | HP 2800, range 10, reload 2.3 s, damage 360 at min range up to 1800 at max range; Super "Poppin'": hops away, 2 s fully immune in the air, drops 4 grenades (900 each, 2 tile radius, knockback, breaks walls) | [wiki] |

## 3. #91 super_role
**Roles: finisher (primary), escape_dash is NOT it (knockback "escape", a soft one), utility (wall / bush breaking, super cancel).** Tags below. Suggested: `super_role = finisher` with secondary `utility` (breaks walls and bushes) and a soft escape (knockback buys time). Why: it is a short-range burst (7.67 tiles, but damage collapses with range), it pierces, knocks back, and has no dash or heal.

Parameters for the rules: range 7.67 tiles, wall-passing NO (pellets die on the first wall tile, so shots through a wall do less damage the more walls are in the way), breaks walls / bushes YES, knockback YES, slow 55 % for 2 s with Shell Shock, damage up to 3240 at point blank (base level), no heal.

| Situation | What to do with the super | Rule condition (planner terms) | Tag + source |
|---|---|---|---|
| Enemy at point blank, hp low | Shoot: the full 9 shells land, kills most things below ~3000 hp | my super ready, enemy <= 3 tiles, enemy hp (abs) < ~3000 or hp fraction < 50 % | [inference] from wiki numbers; fits rule 4 |
| Ambush from a bush | Wait with the super ready, fire when the enemy is close | my super ready, I am in a bush, enemy 2-4 tiles | [wiki tips: "bush camp ... ambush them with her Super"]; [community: noff via search snippet "high trophy players always bush camp"] |
| Chased at low hp (Showdown / Knockout) | Super the chaser to knock it back, then run (Shell Shock also slows) | hp < ~35 %, enemy <= 3 tiles, no escape tile closer than it | [wiki tips] (rule 3 low_hp could use super as a first step) |
| Enemy charging (dash brawlers Bull, Darryl, El Primo) | Hold until it commits, fire as it arrives: knocks it out of its attack | enemy known dash brawler, within ~4 tiles and moving at me | [community: PinkCrow] |
| Enemy casting a super (Frank, Meg wind-up) | Interrupt: knockback cancels the cast | enemy super animation / channel (not in the sim obs; use "enemy within 4 tiles and is Frank/Meg") | [wiki tips], [multi-source: wiki + gamezebo "cancels Super if mid-use"] |
| Enemy hides behind a wall | Break the wall first, then finish | wall between us, enemy within 7 tiles; damage falls per wall tile hit | [wiki], [community: PinkCrow "break walls that protect enemy snipers"] |
| Unknown bush cluster ahead | Fire the super into it before entering to expose hiders | bush within 1.5 .. 7 tiles, super ready, no enemy in view | [community: PinkCrow] (costs the super; rule 13 check_bush should use the NORMAL attack first) |
| Two enemies in line / close together | Super hits both and recharges itself | 2 enemies within 4 tiles of each other and of me | [community: PinkCrow] |
| Enemy slowed after Shell Shock | Follow with attack or Clay Pigeons to finish | enemy hit by my super in the last 2 s | [wiki tips] |
| DON'T: enemy at 5+ tiles with no wall | Don't fire the super at long range: the spread is wide and most shells miss | enemy > 5 tiles and not fleeing, no wall | [multi-source: PinkCrow "drops beyond 4 tiles", gamezebo, wiki] |
| DON'T: low-value targets / early | Save it for key fights, defensive moments; some guides say wait for the enemy to use theirs first | enemy hp > 70 % and no other threat, or enemy super still ready | [community: exitlag via snippet; noff snippet] (guides conflict, section 7) |
| DON'T: break cover your team needs | In team modes keep the wall | team size > 1, mate behind that wall | [community: powerleagueprodigy] |
| DON'T: wall-bush trick vs Piper | Piper's Super gives 2 s immunity; do not fire the super at her while she is mid-hop | enemy Piper "in the air" (state not in obs) | [wiki Piper] |

## 4. #92 bush play
- **can_ambush: YES** (best at it of the starters: wiki tips say bush camp with Super, then ambush; gamezebo: "waiting in a bush until an enemy approaches gets her into her ideal close range").
- **Trigger distance** (full-damage shotgun range): about 3 tiles for near-full damage, <= 4 tiles still strong, damage falls fast past 4 (PinkCrow). Walk-in range of an enemy toward a bush ~2.5-4 tiles. Use 3.0 as the trigger and 4.0 as the cap. [community] + [inference]. NEEDS a sim check (damage table by distance).
- **Super vs attack in the ambush:** with super ready, fire the super at 2-4 tiles (9 shells, knockback prevents the counter hit, may kill); with no super, shoot at <= 3 tiles with full ammo (3 shots of 1700 = 5100 at point blank, kills Piper's 2800 in 2 full hits). [inference from wiki numbers]
- **Lurk (hold fire, stay hidden)** vs: long-range snipers that walk blindly (Piper, Brock, Bea, Colt), throwers; against anything with 3-4+ tile reach that would hit her first (Piper out-ranges her 10 vs 7.67). Do NOT fire the attack from a bush at an enemy 6+ tiles away: it reveals her and wastes shells. [inference + community]
- **Dive up close (she wins)**: Mortis, Crow (wide spread + knockback) [community: gamezebo]; Jacky, Rosa, Frank, El Primo, Edgar, Bibi, Sam, Mortis [community: powerleagueprodigy]; squishy short-reach brawlers such as Piper and Tick if they get too close [community: guides via search]. El Primo needs the super first (it can kill her before the super goes off if she has none, per the wiki tips on Bull / El Primo).
- **Avoid up close / lose to**: Bull, Leon, Rosa, Griff (high burst; they can kill her out of the bush she sweeps) [wiki tips]; ranged poke: Colt (-4.2), Brock (-3.8), Bea (-3.5), Piper (-3.2), Spike (-2.7) [community: PinkCrow, 2026-09-26]; Stu, Crow, Surge, Spike, Lola, Gale, Tara, Nita (powerleagueprodigy, 3v3 team context) [community]. Note the two lists conflict on Rosa and Crow.
- **Shelly vs Piper (issue case)**: Piper wins at range; Shelly wins if she reaches ~3 tiles. Sources: "great ... Piper or Tick if they get too close" (guide snippet), VPEsports / theclick treat Piper as a hard counter [community, snippet], PinkCrow "Piper -3.2 ... destroys her before she gets close". Right play: approach through bushes / walls, never in a straight line; or lurk in a bush on Piper's path with the super ready. Piper's Super is her way out: she hops 2 s (immune) and her grenades land where she was, with knockback and 2-tile radius, so do not stand in melee with Piper when she is at full super charge. [wiki Piper]
- **Bush tricks**: (1) Fast Forward (2.67-3 tiles, reloads ammo, stopped by walls) out of a bush to land point blank and have full 3 shots [wiki]; (2) sweep bushes from outside with the wide spread instead of walking in, to expose hiders (wiki tips, multi-source with PinkCrow); (3) Clay Pigeons (10 range, half spread) to finish a target that escapes the ambush, especially after a super knockback [wiki]; (4) super into a bush cluster before entering [community]; (5) the super also destroys bushes, so using it on a bush removes your own cover (wiki tips: "destroying too many walls and bushes can put her at disadvantage").
- **Reveal on attack**: attacking or taking damage reveals a hidden brawler to enemies (wiki, for Jessie's turret: "visible while attacking or taking damage"; Rosa: "damage briefly reveals"; Mega Box page: only star powers that deal damage, raise max HP or heal reveal). Duration in seconds: NOT FOUND in any source. No Shelly-specific twist, except that her spread sweeps bushes. [wiki] / [unverified] duration.

| Claim | Value | Tag + source |
|---|---|---|
| can_ambush | yes, with or without super | [wiki tips] [community gamezebo] |
| trigger distance | 3 tiles (cap 4) | [community + inference] |
| lurk vs | Piper / sniper / thrower walking in blind | [inference] |
| dive | Mortis, Crow, Jacky, Frank, El Primo (with super), Edgar, Bibi | [community] |
| avoid | Bull, Leon, Griff, Rosa; Colt, Brock, Bea, Spike at range | [wiki tips] [community] |
| reveal on attack | yes, duration unknown | [wiki] / [unverified] |

## 5. Mode differences
- Solo Showdown: bush camp with the super ready, wait for them; Band-Aid is best here; Shell Shock slow helps finish; use the super to knock a chaser away at low hp; do not spend the super early (wait for the enemy's) [wiki tips, community].
- Duo Showdown: her best mode (PinkCrow: S tier, ~63 % win). Pairs with a puller or stunner (Tara, Jacky, Gene, Frank, Bull, Kit, Bo): the super finishes the held target [wiki tips].
- 3v3: "not a top-meta pick in organized competitive" (PinkCrow); Shell Shock outvalues the heal; the super also breaks walls for Brawl Ball goals and knocks enemies off objectives; keep the wall your mate needs [community]. Brawl Ball / Hot Zone B-A tier, Knockout / Bounty C tier.
- Note: a SeeMeta page (via search snippet) lists a September 2026 win rate of 43.7 % and ranked tier F: conflicts with PinkCrow's mode tiers. [community, conflict]

## 6. Proposed rule sketch (planner style)
- **Rule 4b "super_point_blank"** (next to rule 4 super): my super ready, ShotgunGirl-class (range-limited burst) super, an enemy within 3 tiles (not 7.67) with hp < 60 % or R < 1.2 -> super. "Enemy 2 tiles S at 45 %: point-blank super". (Rule 4 as written uses the whole super range; for her the range part should be the full-damage range.)
- **Rule 3b "low_hp_knockback"** (just after rule 3 low_hp): hp < 35 %, super ready, enemy within 3 tiles chasing (dist < 3) -> super, then rule 3 runs. "hp 25 %, Piper 2 tiles E: super knockback, then jumping W to the bush".
- **Rule 15b "ambush"** (extends rule 15 hide): I am a short-range brawler (range-in-tiles at full damage <= 4), I am in a bush, ammo >= 2/3 and an enemy with range > 5 tiles walks within 4 tiles: hold fire (no shot above 4 tiles), fire when it is at <= 3. "In the bush, Piper 5 tiles NE closing: holding fire".
- **Rule 6 variant "dive_sniper"** (next to rule 6 keep_away): for a KNOWN enemy with range > 8 (Piper) and a short-range me: do not keep distance; approach from the side with a bush or wall (path), engage inside 3 tiles. Rule 6 itself assumes I out-range; here the reverse is true: add "outrange_needs_cover".
- **Rule 5 variant (wall break)**: super ready, a KNOWN thrower or sniper behind a wall within 6 tiles, hp >= 0.6 -> super the wall (breaks it, 360 x shells less the wall losses), then engage. "Piper 5 tiles N behind a wall: breaking it with the super".
- **Rule 13 check_bush**: for her, use the normal attack (not the super) at a bush within 4 tiles; check from outside the bush. "No enemy seen, bush 3 tiles W: sweeping it".

## 7. Conflicts and gaps
- Shell count of the attack: wiki 5, one snippet 9 (that is the super count) -> use the wiki: 5.
- Max damage: wiki says 5 x 340 = 1700 at level 11; snippets quote 1640 and 3000 for other levels / the super. The sim's skills table decides.
- Full-damage distance: no source gives it (not found in 20+ guides). Needs a sim / game-table check (damage vs distance) before setting the 3 / 4 tile numbers.
- Shell Shock slow: wiki 55 % for 2 s, PinkCrow 3 s. Fast Forward: wiki 2.67 tiles, PinkCrow 3.
- Matchups: PinkCrow (numbers) and powerleagueprodigy disagree on Crow, Rosa, Spike; the wiki tips say she counters Mortis and Crow. Treat Rosa and Crow as unsure.
- Super timing: some guides say "use the super as soon as ready", others "hold it". The wiki prefers holding it for the ambush; pros hold it in Showdown, spend it in team modes [community].
- Bush reveal time after attacking: NOT FOUND. Reddit blocked (not tried).
- noff.gg was 403 for WebFetch: only search-snippet text from it is used.
- Needs a game check: whether Shelly's Super stays in the obs as "super ready" with a range of 7.67 (cond 12), and whether the sim's wall damage loss for pellets is modelled.

## 8. Sources
1. https://brawlstars.fandom.com/wiki/Shelly (MediaWiki API, wikitext, live 2026-11-28): all numbers, gadgets, star powers, hypercharge, tips on bush camp, knockback, wall rules.
2. https://brawlstars.fandom.com/wiki/Piper (API): Piper HP 2800, range 10, Super 2 s immunity, grenades 900 / 2 tiles; Piper tips list Shelly as a pop-in threat.
3. https://pinkcrow.net/brawl-stars/shelly-brawler-brawl-stars/ (2026-09-26): "drops beyond 4 tiles", Super tips, counters with numbers (Piper -3.2), mode tiers.
4. https://www.gamezebo.com/walkthroughs/brawl-stars-character-guide-how-to-play-shelly/ (date unknown): bush ambush, counters, Super cancels supers, "Piper and Dynamike are threats".
5. https://powerleagueprodigy.com/shelly (date unknown): counters list, wall caution; no Showdown or bush info.
6. WebSearch snippets (title + URL only used as hints): exitlag.com/blog/brawl-stars-shelly-mastering (save the super for key fights); noff.gg/brawl-stars/build/13639 and /10304 (bush camp, patience; 403 on fetch); seemeta.com Shelly (win rate / tier); vpesports.com/guides/shelly-guide-to-victory (404 on fetch, snippet only); theclick.gg/?p=76526 (Piper counters Shelly, snippet only).
7. Could not open: noff.gg (403), vpesports.com (404), exitlag.com (403), Reddit (blocked by brief, not tried), brawlify (not tried).

## 9. Research log
- Worked: fandom MediaWiki API (4 calls: Shelly twice, Piper twice, plus 2 failed page lookups "Bush"/"Bushes"/"Terrain" not existing), WebFetch of pinkcrow, gamezebo, powerleagueprodigy; WebSearch.
- Failed: noff.gg 403 x3, exitlag 403, vpesports 404.
- Web calls (WebSearch + WebFetch): 17. Plus about 6 curl calls to the wiki API.
- At scale: fetch the wiki pages for all brawlers in one pass, and look for a game-data source (brawlify, which I did not try) for per-distance damage; the reveal duration is the one question no site answered, so settle it in the sim or by testing in the game.
