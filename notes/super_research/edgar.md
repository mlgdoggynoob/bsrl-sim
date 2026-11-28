# Edgar (sim codename Enrager): super and bush research for issues #91 / #92

Research date 2026-11-28. Tags: [wiki] numbers from the fandom MediaWiki API, [multi-source] 2+ independent sources, [community]
one guide / opinion, [unverified] my inference or no source. Nothing in the repo was edited.

## 1. Identity
- Edgar, Epic, class Assassin, title "CEO of Brawl Stars" [wiki]. Sim codename Enrager (repo: `scenarios.py` assassin_rush uses
  "Enrager" as the native assassin; super_audit.py names its hypercharge area `EnragerOverchargeSuper`, "effect compiled out of this libg").
- Attack "Fight Club": two quick piercing scarf punches, range 2 tiles (shortest in the game), total unload about 0.4 s,
  each punch heals him 35 % of the damage it deals. Direct hit only, no lob, no wall pass [wiki].
- Movement: 855 ("very fast"), 1055 right after the super for 2.5 s [wiki]. (One guide says 1025 after the super [community]; wiki wins.)
- Trait: the super charges by itself, 3.3 %/s, so about 30 s from empty; the hypercharge about 77 s [wiki]. Same trait as Darryl.
- Whole kit = melee burst plus self-heal plus a short, reliable gap-closer.

## 2. Numbers
| Item | Value | Tag + source |
|---|---|---|
| HP | 3700 (base, before cubes) | [wiki] Edgar infobox |
| Punch damage | 540 per punch, 2 punches (1080 per full attack) | [wiki]; "2 bullets" in the infobox |
| Heal per punch | 189 (35 % of 540); Fisticuffs +30 % = 45.5 % | [wiki] |
| Range | 2 tiles; hyper Buffie extra punches reach 4 tiles at -50 % damage | [wiki] |
| Reload | 0.7 s (0.467 s hypercharged) | [wiki] |
| Super charge per hit | 8.775 % per punch hit (21.9 % hypercharged) plus 3.3 %/s passively | [wiki] |
| Super "Vault" range | 6.67 tiles; aim point is the landing point; a lake in the way extends the jump to the nearest ground | [wiki] |
| Super duration | jump about 0.86 s; fully immune to damage while airborne (not to damage-over-time / status effects) | [wiki] |
| Super landing | +200 movement points (855 -> 1055) for 2.5 s; no damage by itself | [wiki]; "attack itself does no damage" [community] search snippet |
| Wall passing | yes, any obstacle, walls and water; over lakes extends. Gadget jump only clears 1 tile thick | [wiki] [multi-source: pinkcrow 2026-10 "jumps over walls and obstacles"] |
| Gadget Let's Fly | scarf up to 6.67 tiles; if it hits a brawler or wall he jumps to it, landing on the far side of the target; no speed boost; 18 s cooldown | [wiki] |
| Gadget Hardcore | shield = 50 % max HP (3700 in the wiki text at max 3700 cubes aside), decays 5 % every 0.35 s; 17 s cooldown | [wiki] |
| Star power Hard Landing | landing hits a 3-tile radius for 1341 (wiki infobox; description says 1490), 2682 direct hit within 1.17 tiles (2980 in the description). Gadget jump deals half | [wiki] numbers differ by section |
| Star power Fisticuffs | +30 % heal per punch | [wiki] |
| Hypercharge Outburst | after the super: +150 % super charge rate, +50 % reload speed for the rest of the duration; +5 % damage and shield, +20 % speed. Using Let's Fly does not trigger it | [wiki] |
| Removed "Wasabi Power" | super range 16.67 tiles, historic only. Do not use | [wiki] |

## 3. #91 super_role
Roles: **engage_dash** (primary) and **escape_dash** (secondary). A true finisher only with Hard Landing (area damage 1341, 2682 direct).
Why: the jump does no damage by itself, makes him untargetable for about 0.86 s, crosses walls, and leaves him with +23 % speed;
good players use it to close onto a target or to leave a lost fight. The super refills itself in about 30 s, so it is cheap to use,
but "Edgar wants the super ready before engaging" [multi-source].
Params for a rule: super_range 6.67 tiles, wall_pass true, airborne_invuln about 0.86 s, speed_after 1055 for 2.5 s, no damage (damage 1341/2682 only with Hard Landing, which the observation cannot see).

| Situation | What to do with the super | Rule condition (planner terms) | Tag + source |
|---|---|---|---|
| Dive a thrower / sniper / low-HP ranged brawler | jump onto it, then punch combo: 2 punches 1080, heals 378 | enemy within 6.67 tiles (straight line, walls ignored), enemy range >= 4 tiles (keep_away rule 6 already says "away" for me: Edgar inverts it), enemy not "tank" (R < 1.0), my hp >= 0.5, super ready | [multi-source] wiki "specifically weaker ones like throwers and sharpshooters" + pinkcrow 2026-10 "low on ammo or separated" |
| Enemy just emptied its ammo | jump in right after its last shot, punch | enemy known ammo 0 (the obs has no enemy ammo; use "enemy fired 3 shots within the last 2 s" as a proxy [unverified]) | [wiki Tips] "wait for them to use some or all of their ammo, then jump on them" |
| Close a gap on a retreating low-HP enemy (finish) | jump, then punch | enemy hp < 25 % and 3-6.67 tiles away, any wall between (jump passes) | [community] |
| Escape | jump away through/over a wall, run with +23 % speed | hp < 0.35 and enemy within 1.2 x reach (rule 3 low_hp) and super ready: jump 5-6 tiles away over a wall or to a bush, away from the threat | [multi-source] vpesports snippet "keep your gadget or Super for the escape"; wiki "escape more effectively when in danger" |
| Cross a wall to flank | jump over a wall to land beside a camping enemy that shoots at the wall's other side | thrower_wall rule 5: a KNOWN thrower with a wall between and super ready: super instead of "engage around the wall" | [wiki]+[unverified] fit |
| Jump into a bush | aim the landing on a bush tile; after landing he is hidden again and the +speed lasts | bush within 6.67 tiles, enemies near but not looking; use for hide/escape | [unverified] mechanics follow from "lands where aimed"; the bush-escape pattern is [community] (bush play guides) |
| Gas | cross a gas wall quickly or jump out of a gas pocket | rule 1/2 with a wall or gas band between me and safe tile, super ready | [unverified] |
| DON'T | keep the super while low on HP if the enemy has the knockback / stun gadget or can punish a jump | enemy known as Piper (knockback gadget), Rico, Brock: do not jump from < 6 tiles; a lazy jump is punished the instant it lands | [community] zathong list (Piper, Rico, Brock "hard counters ... snipe his jumps") + search snippet "wait for Edgar to jump in before punishing him" |
| DON'T | jump on a full-HP tank (Bull, El Primo, Rosa, R-T, Gus, Shelly) when the super is the only escape | enemy R >= 1.0 and not low | [multi-source] pinkcrow win-rates + wiki "doesn't have health to outmatch tanks" |
| DON'T | Edgar-vs-Edgar: if low HP, never super before the enemy Edgar does | enemy is Enrager and my hp < 0.5 and the enemy super is probably ready | [wiki Tips] |
| Vs another Edgar with no super | jump ahead to flank | enemy Enrager, my super ready | [wiki Tips] |

## 4. #92 bush play
- can_ambush: **yes, always** (not only with the super). Short-range melee brawler; the wiki says "incredibly great ambusher and camper in Showdown" and "bush-camp and wait for an enemy to head near the bush, then exit and attack" [wiki Tips].
- Trigger distance: with the super ready, trigger at <= 6.67 tiles (jump) even from a bush. Without the super: trigger at <= 2 tiles (punch range 2 tiles plus about 1 tile of dash margin, so 3 tiles) [wiki number, margin is [unverified]].
- Lurk: yes, wait in the bush until the super is ready (30 s alone), regenerate, and wait for enemies to pass or burn their ammo [multi-source: 1v9/noff/search snippets "sit in a bush, let it charge"]. Lurk against: ranged brawlers (Piper-class, throwers, sharpshooters) that have no escape tool; those are the best prey. Do not lurk against: tanks that you cannot kill (R >= 1.0).
- Dives: throwers, sharpshooters, low-HP ranged: Ziggy, Grom, Sirius, Najia, Mr. P (+3.8 to +5.0 % win-rate edge) [community, one source pinkcrow 2026-10]. Also high-damage low-HP brawlers after they empty their ammo: El Primo, Shelly, Fang, Griff, Bull, Darryl, Buzz, Nani, Leon, Rosa, Bibi, Spike [wiki Tips]. Slow-unload tanks he outruns: 8-Bit, Pam, Rosa, Buzz, Ash, Frank [wiki Tips].
- Must avoid up close: R-T, Gus, Bull, El Primo, Shelly (negative win-rate, 2.9-4.4 %) [community, pinkcrow 2026-10]; Piper, Rico, Brock because they kite and punish the landing, and Piper's gadget knockback [community, zathong]. Anything with a knockback / stun used right after he lands.
- Bush tricks: (1) approach through cover, then jump on a target that is low on ammo or separated [multi-source]; (2) kite while punching (run away, punch backwards) to extend his reach vs another Edgar [wiki]; (3) double jump with Let's Fly: one jump to attack, one to escape [wiki]; (4) jump onto a wall to leave an exposed position (Let's Fly, gadget only).
- Reveal on attack: general fact, not Edgar-specific: attacking or taking damage reveals a brawler in a bush; no duration number found. Hypercharge activation does not reveal, damaging star powers and gadgets do [community, wiki snippet: Mega Box / Rosa / Jessie pages]. Edgar's twist: the jump itself has no attack, so landing in a bush should not reveal him [unverified]; his first punch reveals him.

## 5. Mode differences
- Solo Showdown: his best mode (S-tier, about 52 % win rate; Double Trouble 60.9 %) because of bushes, walls and the free super charge [community, pinkcrow 2026-10; wiki agrees: "great ambusher in Showdown"]. Prefer enclosed maps (Cavern Churn, Feast or Famine, Rockwall Brawl).
- Duo Showdown: A-tier (49 %); works with a partner who follows up on his engage [community]; pairs with healers (Poco, Pam, Doug, Berry, Byron) [wiki].
- 3v3 modes: Brawl Ball B (46 %), Gem Grab / Knockout / Heist C (43-44 %): open lanes punish a 2-tile range; use the super to steal a mine or to escape; only strong on heavily walled maps [community]. For the sim: in team modes keep the super for the escape more often and jump only to a teammate-supported kill.

## 6. Proposed rule sketch
Rule numbers are the planner's. The sim only knows ids; the rules key on the brawler (ent col ID0) and super range from cond 12.
- **Edgar super_engage** (sits next to rule 4 super, after low_hp): super ready, dash super (cond 9 = 0 for "attack" damage; needs a new `engage_dash` flag), enemy within 6.67 tiles, enemy range >= 4 tiles or hp < 40 %, R < 0.9, my hp >= 0.5 -> super onto it. Reason: "Piper 5 tiles NE at 80 %, ammo gone: jumping on her".
- **Edgar super_escape** (extends rule 3 low_hp): my hp < 0.35, an enemy within 1.2 x its reach, super ready -> jump to the bush / wall-covered tile 4-6.67 tiles away, farther from the enemy. Reason: "hp 25 %, ShotgunGirl 3 tiles E: jumping W to the bush".
- **Edgar lurk** (extends rule 15 hide): no enemy in view and (super not ready or hp < 0.8) -> hide in a bush 1-5 tiles away and hold there until super ready and hp >= 0.8. Reason: "super 40 %, no enemy: lurking in the bush".
- **Edgar ambush** (near rule 11 engage): from a bush, a known ranged enemy (range > 4) or R < 0.7 enemy comes within 6.67 tiles with the super, or within 3 tiles without -> engage now. Reason: "Piper 5 tiles N, super ready: jumping out of the bush".
- **Edgar avoid_tank** (near rule 7 outclassed): enemy known as Bull / El Primo / Shelly / R-T / Gus and R >= 1.0 -> away from it (also forbids super_engage). Reason: "Bull 3 tiles E, full hp: staying away W".
- **Edgar keep_super** (a guard on rule 4 for this brawler): do not jump when the enemy is Piper / Rico / Brock within 6 tiles (knockback / punish) and my hp < 0.6.

## 7. Conflicts and gaps
- Hard Landing damage: infobox 1341 / 2682, description 1490 / 2980; description may include the wiki's own rounding. Not decisive for the rules (the sim obs cannot see it).
- Speed after super: wiki 1055, pinkcrow 1025 (a patch probably); only matters as "about +20 %".
- Counter lists come from single guides with win-rate deltas (pinkcrow, 2026-10) and the zathong list is undated; no Dynamike / thrower-vs-Edgar source found. Wiki says throwers are good targets; no source says Dynamike's Dyna-Jump beats Edgar's jump. Marked [unverified].
- No reveal duration for attacking from a bush found; also not whether Edgar's jump landing in a bush stays hidden. Needs a game-table / sim check.
- The wiki's "ammo gone" advice needs enemy ammo, which the observation lacks; a proxy is needed.
- Does the sim's Enrager really have the free 3.3 %/s super charge and no damage landing? Check in skills.csv / the host.
- Passive charge vs a hypercharge: `EnragerOverchargeSuper` is compiled out per super_audit.py.

## 8. Sources
1. https://brawlstars.fandom.com/api.php?action=parse&page=Edgar (MediaWiki API; Edgar page, edited 2026; all [wiki] numbers, Tips section).
2. https://pinkcrow.net/brawl-stars/edgar-brawler/ (guide dated 2026-10-06: super 6.67 tiles over walls, matchup win-rate deltas, mode tiers).
3. https://zathong.com/brawl-stars-counter/ (search snippet only: Piper, Rico, Brock as hard counters; undated).
4. https://www.theclick.gg/?p=76733 (Dynamike counter guide, search snippet: matchup depends on map; thin).
5. https://1v9.gg/blog/edgar-brawl-stars-guide (search snippet only: wait for the super in a bush; page itself 503, not opened).
6. https://vpesports.com/brawlstars/brawlers/edgar/ (search snippet only: keep gadget or super for the escape; page redirected, not opened).
7. https://brawlstars.fandom.com/wiki/Rosa, /wiki/Jessie, /wiki/Mega_Box (search snippets: attacking or taking damage reveals a bush occupant; hypercharge does not).
8. Could not open: noff.gg Edgar guide (403), theclick.gg Edgar guide (403), fandom Bush / Grass pages (no such wiki page via API), Reddit (not tried).

## 9. Research log
- Worked: fandom MediaWiki API (Edgar page, rich), WebSearch snippets, pinkcrow.net via WebFetch (best single guide).
- Failed: 1v9.gg 503, noff.gg 403, theclick.gg 403, vpesports redirect to another host (not followed), fandom pages for "Bush" / "Grass" missing.
- About 19 web calls (5 searches, 5 fetches, about 9 curl on the wiki). No Reddit attempts.
- At scale: use the wiki API for all brawler numbers, one WebFetch per brawler on pinkcrow-like win-rate sites for matchup deltas, and one shared page for the bush-reveal mechanic instead of repeating the search per brawler.
- Matchup claims are the weakest part: they rest on one 2026-10 win-rate page and an undated list. A pro-commentary source or sim self-play matrix would be better.
