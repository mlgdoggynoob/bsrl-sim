# Mico (sim codename: Leaper): super and bush research for issues #91 / #92

Research date 2026-11-28. Tags: [wiki] numbers from the fandom MediaWiki API (page Mico, Version History/2023-2026, Showdown),
[multi-source] 2+ independent sources, [community] one guide / opinion, [unverified] my inference or no source.
Nothing in the repo was edited. "Leaper" is the task's codename; no source gives an internal game name, and the sim table
name was not available here (roles.py needs it for BRAWLERS).

## 1. Identity
- Mico, Mythic, class Assassin, title "Am I a joke to you?", the 74th brawler, free in the Brawlidays 2023 calendar [wiki].
- Attack "Mic BOOM!": not a projectile. He jumps up to 4 tiles (5.33 with the Presto gadget), is airborne about 0.58 s
  regardless of distance, and hits everything in a 1.5-tile radius on landing. The whole attack takes about 0.75 s [wiki].
- While airborne he is immune to all damage except status effects and damage over time. The damage lands a frame before the
  jump ends, so he is also immune to instant retaliation (Jacky's counter, Nani's Return to Sender, Meg's Heavy Metal
  star power) and knockback, and can hit enemies hiding inside Gale's Twister [wiki].
- Wall passing: the jump crosses obstacles and water; if more blocks or a lake are in the way the distance stretches "up to a
  limit or to the nearest piece of ground" [wiki]. A guide says a jump over walls can flank [community: pinkcrow / exitlag
  search snippets]. The limit is not quantified anywhere I found: [unverified], check in the sim.
- Super "Out of Frame": jumps out of frame, invulnerable, steers his landing, lands with damage and knockback (section 2).
- Movement: 855 ("very fast"), 1025 with the super active [wiki]. Very slow reload (2.4 s), 3 ammo bars.
- Trait: one jump = one ammo bar, so every reposition costs ammo that is slow to come back.

## 2. Numbers
| Item | Value | Tag / source |
|---|---|---|
| HP | 3500 (level 11 infobox). Older guides: 3300 (gamewith, stale), history 3000 -> 3300 in 2024; the 3500 step is not in the version history I read | [wiki] infobox; gamewith differs |
| Attack damage | 1140 on landing (1090 before a 2025 buff) | [wiki] infobox + Version History/2025 |
| Attack range / radius | 4 tiles jump, 1.5-tile landing radius, 5.33 tiles with Presto | [wiki] [multi-source: theclick snippet "4-tile jump range"] |
| Reload | 2.4 s per bar (2.6 s before the 2025 buff); ammo 3 bars | [wiki]; Version History/2025 |
| Attack time | 0.75 s to finish; airborne 0.58 s | [wiki] |
| Super charge per hit | 21.65 % per attack hit (about 5 hits); 10.8 % hypercharged-attack figure also listed | [wiki] infobox |
| Super | 1190 landing damage, knockback, 2.33-tile radius; 1 s delay, then up to 6 s airborne; the landing marker grows as it locks on; super range 0 in the game table (steered, not aimed) | [wiki]; range 0 from the task facts |
| Super while airborne | immune to damage (not status / DoT); can reload and heal while up; cancelled if stunned, pulled or knocked back during the 1 s delay | [wiki] [multi-source: theclick / buffbuff snippets "cancelled during the delay"] |
| Super speed | 1025 vs 855 | [wiki] |
| Super does not break walls or grass | | [community: guide snippet] |
| Gadget Clipping Scream | 3 projectiles, slight spread, 25 % attack damage each (wiki infobox says 456 per projectile, description 570 total; buffbuff says 272 each: they disagree), slow 2 s, needs an enemy within 9 tiles, 15 s cooldown | [wiki]; conflict noted |
| Gadget Presto | next jump +1.33 tiles (34 %), no gadget icon shown, 14 s cooldown; guides call it the kill-confirm / escape-extender | [wiki] |
| Star power Monkey Business | every 5 s the next attack steals 1/3 of the enemy's ammo and gives it to Mico; the bar charges even when not attacking; resets on a miss | [wiki] |
| Star power Record Smash | +100 % damage to non-brawlers (boxes, turrets, safe): 2280 per jump on a box | [wiki] |
| Hypercharge Sound Check | the next super also stuns for 1.5 s; +20 % speed, +5 % damage and shield (2024: speed 20 -> 24 %, shield 25 -> 5 %); the wiki tip says use the hypercharge as a stat buff after a landing, not with an immediate super (the 6 s flight wastes it) | [wiki] Version History/2024; gamewith lists +24 % / +25 % dmg / +5 % [community] |

## 3. #91 super_role
Roles: **engage_dash** (primary) and **escape_dash** (secondary; wiki tips say it works "similarly to Janet's super ... escaping
during the countdown as well as recovering in the air"). Not a finisher by the planner's test (1190 is 34 % of his own HP
but a 3500-HP target survives it; against a squishy target below about 1190 it is a finish). The class default in roles.py would
give "utility" because the super BehaviorType is FlyJump, not Charge: Mico needs an explicit BRAWLERS entry.
Why: the super is a 6 s untouchable window with a steerable 1190 knockback landing; the 1 s delay is the only vulnerable part.
The planner assumes a fixed super range; Mico's is 0 in the table. super_audit.py models FlyJump as "the shooter walks towards
the target once CastingTime is over", so the real reach is walking speed x about 5 s. I found no source with a tile number
for how far he can fly: [unverified], measure with super_audit (LONG_WATCH exists for Mico's jump).

| Situation | What to do with the super | Rule condition (planner terms) | Tag + source |
|---|---|---|---|
| Hurt, a diver or R >= 1 enemy near, enemy still > 3-4 tiles away | Super now; fly away (6 s, invulnerable) and reload/heal in the air; land far or on a bush | role escape_dash: super ready, hp < 0.5 (planner ESC_HP 0.6), threat dist >= 3.5 tiles (so the 1 s delay is not spent inside its reach) | [wiki] airborne immunity; delay vulnerability [wiki] |
| Hurt and the enemy is already within 2-3 tiles | Main-attack jump first (0.58 s, 4 tiles, hits it), then super once it is > 3.5 tiles or behind a wall | dash_escape (B1) then super_escape next tick; needs ammo >= 1 | [wiki] tip "keep at least 1 ammo to disengage"; sequence [unverified] |
| Enemy has stun / pull / knockback in range or is a known CC brawler | Do NOT start the super inside its reach: the delay cancels it | veto super_escape / super_engage when a known CC enemy is within its range + 1 | [wiki] cancel rule; "crowd control cancels his mobility" [community snippet] |
| Engage a squishy / isolated target 5-10 tiles away with my hp >= 0.6 | Super, steer onto it, knockback landing, then 1-2 jumps to finish | super_engage: enemy beyond 4 tiles, passes engage test or < 40 %; my ammo >= 2 after landing; enemy not stunning | [multi-source] buffbuff + theclick snippets: aim at "clusters or key targets like Support or Marksman"; wiki: "corner them, the marker slows as it locks on" |
| Enemy at 25-35 % hp, 4-5.5 tiles, ammo >= 1 | Main jump finishes it (1140); keep super | rule 4 finisher-style test with the attack: enemy hp x its max < 1140 | [unverified] arithmetic from [wiki] numbers |
| Enemy low and fleeing out of jump reach | Super as a chase tool: 6 s of flight at 1025 speed, kill by landing | enemy hp < 0.35 (1190 landing), distance 5-12 tiles, super ready | [community] "assassins hunt isolated targets"; reach [unverified] |
| Hypercharge ready | Land with the main jump first, then hypercharge for speed / damage; do not super straight after activating | hypercharge ready and an enemy within 4 tiles | [wiki] tip |
| Enemy fires at a pre-aimed spot (thrower, Amber fire) | Jump / super through it: airborne = untouchable, ground fire misses | wiki Showdown: Amber "must be careful against airborne Mico" | [wiki] Showdown page |
| Constant-damage brawlers (Carl, Gigi) | Do not jump in: he takes the damage the moment he lands | known enemy Carl / Gigi within reach: no ambush, no engage | [wiki] tip |
| Hold the super | Hold it as the escape while a diver (Edgar / Mortis / Fang / Leon / Buzz) is on the map | the planner's "escape_dash keeps its super while a diver is within 10 tiles unless the target < 25 %" | [unverified] fits wiki "Mico lacks recovery, so assassins are deadly" |
| Gas | Land >= 3 tiles from the poison, or use the 6 s flight to cross a gas wall | landing tile filter as R1 | [unverified] |

## 4. #92 bush play
can_ambush: **yes** (assassin, class default already true), with the **main-attack jump**, not the super. The jump is the
signature of the class: airborne 0.58 s, untouchable, lands onto a target that never saw him. The super is a poor ambush:
the 1 s delay is visible and cancellable and the landing marker is a telegraph [unverified whether enemies see it].
| Question | Answer | Tag + source |
|---|---|---|
| Trigger distance (no super) | 3.5 tiles. The jump reaches 4, the landing hits 1.5 tiles around, and a 0.75 s attack gives a walking enemy time to leave: jumping at 3-3.5 gives the least time. Against slow-reacting targets 4 tiles works; Presto 5.33 for a last-moment kill | [unverified] arithmetic from [wiki]; planner default would be 2.5 (half range clipped), too short |
| Ammo gate | >= 2 bars before springing: one to land, one to leave. Never empty all 3 (listed top mistake: "no escape during the 2.4 s reload") | [multi-source] theclick snippet + wiki tip |
| Lurk (hold fire in a bush) | Lurk against ranged brawlers that out-damage him in the open (marksmen, artillery, Colt-like) until they come within 3.5 tiles, then spring. Do not lurk against assassins that out-jump him (Edgar 6.67, Mortis): hide and leave | [community] snippets: "wait for the enemy to use super or step out of position"; "long-range damage punishes him in the open" |
| Who he dives (good vs) | Squishy short/mid range with slow reload or poor mobility: Willow, Brock, Berry (gamewith: jump closes distance, dodges Berry's attack), Finx and Ziggy (theclick counter lists name Mico), Support / marksmen (buffbuff). Boxes with Record Smash | [community] gamewith, theclick snippets, buffbuff |
| Who beats him up close | Assassins: Edgar, Buzz, Lily, Cordelius; high-burst damage dealers (Colt); tanks that soak a 1140 jump and kill him (3500 HP, 3 hits needed); Carl and Gigi (area / constant damage) | [community] gamewith + mobilematters + wiki tip; tanks from search snippet |
| Who beats him from range | Tick, Mandy, long-range damage; maps with long sightlines hurt him | [community] mobilematters + snippet |
| Shelly-type burst on the landing tile | Claimed in one search summary, not found in any page text | [unverified] |
| Bush tricks | Jump out of a bush onto a target (the attack reveals him; he is untouchable until the landing frame). Jump over a wall into a bush to break line of sight (the jump passes obstacles). Super behind cover so the 1 s delay is safe ("use your Super behind cover", wiki tip) | [wiki] tip; jump into a bush [unverified] |
| Reveal on attack | No Mico-specific twist found; the jump itself may show him in the air. Generic rule: an attack from grass reveals the attacker briefly [community: wiki pages for Jessie / Shelly hint at it], duration not found | [unverified] |

## 5. Mode differences
- Showdown (solo / duo): strongest mode for him [multi-source: exitlag snippet "high pick and win rates in Solo and Duo Showdown",
  mobilematters "Solo Showdown or Duels", search summaries "Solo Showdown, Knockout, Bounty"]. Isolated targets, boxes
  (Record Smash), Monkey Business ammo steal on a third-party kill, escape by super when the lobby closes in.
- 3v3: weaker [community: one stats site, 44.2 % win rate, 0.7 % pick rate, undated, low confidence]; he needs a mate to
  absorb fire and should avoid diving into a grouped team ("avoid diving into a grouped team", search snippet). In team modes the
  super is more a reset and a Brawl Ball / Gem Grab escape than a pick tool.
- Map: long open maps hurt him, walls and bushes help (guides advise walls and bushes for flanks and quick escapes).

## 6. Proposed rule sketch
Profile: `Leaper = dict(roles=("engage_dash","escape_dash"), ambush=True, trigger=3.5, lurk=False, rules=("dash_escape",))`.
- **super_escape (R1 variant, Mico)**: super ready, hp < 0.5 or 2+ enemies within 4 tiles, nearest threat 3.5-8 tiles (not inside),
  no known CC brawler within its range + 1 -> super; landing = far side / a bush, >= 3 tiles from poison.
  "hp 40 %, Enrager 5 tiles E: flying away W (super, 6 s untouchable)". Sits at R1; needs a super range parameter (srange = 0 now).
- **dash_escape (B1, Mico)**: hp < 0.35 or R >= 1.5 within reach + 2, ammo >= 1 -> jump 4-8 tiles to the far side, preferring a
  tile behind a wall and the farthest from all enemies; keep 1 ammo. "hp 30 %, Buzz 3 tiles E: leaping W over the wall (attack)".
  After B1, super_escape next tick if the threat is now >= 3.5 tiles. B1 as written has no LOS / wall bonus: add one.
- **ambush (R3)**: in a bush, ammo >= 2 bars, hp >= 0.5, nearest enemy out-dueled (R < 1.2): hide until within 3.5 tiles, then jump
  onto it; skip Carl / Gigi. "Piper 6 tiles E, in a bush: waiting for 3.5". Not the super-spring (R3 uses super range with an
  engage_dash super ready; with srange 0 it would never fire correctly: force trigger 3.5).
- **super_engage (R4, Mico)**: super ready, enemy 5-10 tiles, passes engage test or < 40 %, my hp >= 0.6, ammo >= 2, no CC enemy
  within reach -> super on it. "Brock 8 tiles E at 35 %: flying in (super)". Needs a defined reach (see section 7).
- **finish_jump (new, near rule 4)**: ammo >= 1 and an enemy within 4 tiles with hp x max hp < 1140 -> jump it. "Piper 3 tiles E at 28 %: jump".
- **no_dive_grouped (near fight / engage)**: do not engage into two or more enemies within 4 tiles of each other when the target is
  full HP. [unverified, from a snippet]

## 7. Conflicts and gaps
- Super range: table 0, real behaviour = steered flight. No source gives the maximum landing distance or the steer speed in tiles/s.
  Needs super_audit / a live check. The planner's R1 / R3 / R4 all read srange and would misbehave at 0.
- Does the super cross walls? The wiki says the 2025 fix made targeting smooth "going over obstacles and water", so yes in practice
  [wiki]; the exact allowed landing set (walkable tiles only) is not stated.
- HP: wiki 3500, gamewith 3300 (stale, also lists attack 1090 and a "Spiders" gadget that the wiki lacks). Trust the wiki, confirm in
  the game table.
- Clipping Scream damage: wiki infobox 456 per projectile, description 570 total, buffbuff 272 per projectile. Not used by any rule.
- Whether the landing marker or the airborne Mico is visible to enemies in a bush ambush: not found.
- Jump over walls: the max wall thickness / lake width is not published; verify in the sim.
- Matchup lists are weak (guide-level, no win-rate matrix). I could not open noff.gg, brawlify, theclick and exitlag (403); the
  mobilematters / buffbuff / gamewith pages are SEO guides of mixed quality. No pro-player or tournament source was found.
- The Reddit competitive thread that appeared in search (a "guide to countering all brawlers" thread) was not opened (blocked by the brief).

## 8. Sources
1. https://brawlstars.fandom.com/api.php?action=parse&page=Mico (wikitext, edited 2026-11-03): stats, attack, super, gadgets, star powers, hypercharge, tips.
2. https://brawlstars.fandom.com/wiki/Version_History/2024, /2025, /2023 via the API: HP 3000 -> 3300, damage 1090 -> 1140, reload 2.6 -> 2.4 s, hypercharge numbers, targeting fix.
3. https://brawlstars.fandom.com/wiki/Showdown (API): Amber vs airborne Mico; bushcamping lines for the other brawlers.
4. https://mobilematters.gg/brawl-stars/brawl-stars-mico-guide: jump to dodge / escape, counters Cordelius / Colt / Tick / Mandy, best in solo modes.
5. https://buffbuff.com/blog/brawl-stars-mico-guide-attacks-star-power-gadgets-gears-and-more: super as escape and 6 s untouchable, aim at marksmen / support, Showdown strong (low quality summary).
6. https://gamewith.net/brawl-stars/48070: matchups (good vs Willow / Brock / Berry, bad vs Lily / Buzz / Edgar); stale numbers.
7. https://www.theclick.gg/brawl-stars-mico-guide/ (search snippet only, page 403): ammo mistake, super cancelled by stun; theclick Finx / Ziggy counter pages (snippet).
8. https://www.exitlag.com/blog/mico-brawl-stars-abilities-strategies-build-guide/ (snippet only, 403): solo / duo showdown strength.
9. https://pinkcrow.net/brawl-stars/mico-brawler-from-brawl-stars/ , https://clutchpoints.com/gaming/brawl-stars-mico-guide , https://gamingonphone.com/guides/brawl-stars-mico-guide-tips-and-tricks (search snippets only): walls / bushes for flanks, super does not break walls.
10. Could not open: noff.gg, vpesports (redirect chain), theclick, exitlag, brawlify. Reddit not tried.

## 9. Research log
- Worked: fandom MediaWiki API (page text, version history, Showdown), WebSearch (guide summaries), WebFetch on mobilematters /
  buffbuff / gamewith. Failed: 403 on theclick, exitlag, noff, theclick Dynamike counters; vpesports redirects to unrelated hosts (not followed).
- Calls: 8 WebSearch + 10 WebFetch (18 web calls) plus 9 curl runs of about 20 wiki API requests; over the 25 budget when counted together.
- No bush-reveal duration, no airborne-visibility fact and no matchup matrix found: all [unverified].
- At scale: pull the matchups from a stats API (win rate vs each brawler) and measure the super reach and wall limit in the sim
  once, then write rules from numbers, not from guide prose.
