# Dynamike (TntDude): research for #91 (super_role) and #92 (bush lurk / ambush)

Date: 2026-11-28. Tags: [wiki] = brawlstars.fandom.com MediaWiki API (read 2026-11-28, so current); [community] = one guide or
snippet; [multi-source] = 2+ agree; [unverified] = inference or not found. Reddit was not opened (blocked).

## 1. Identity
- Dynamike, Super Rare, class Artillery, sim codename TntDude (the sim's `thrower` flag in planner rule 5 names this brawler). [wiki]
- Attack "Short Fuse": 2 sticks of dynamite lobbed OVER obstacles, long range, 1.0 s fuse counted from the throw (not from landing).
  Blast radius 1.5 tiles per stick. The 2 sticks fan out perpendicular to the throw; the spread shrinks the closer he throws, so
  point-blank throws land both sticks on one target (more damage) but are also hard to land on a moving target. [wiki]
- No pierce, no projectile block: the sticks arc, so walls, bushes and brawlers do not stop them. A closer throw lands sooner. [wiki]
- Speed 800 (fast, "above average"). Moderately low HP, and the wiki calls the assassins "huge counters". [wiki]
- Super "Big Barrel o' Boom": one barrel, same range as the attack, lobbed over walls, fuse 1.3 s from the throw, blast 2.67 tiles,
  knocks survivors back 3 tiles, DESTROYS cover (walls, bushes, boxes) in the blast. [wiki]

## 2. Numbers
| Item | Value | Source |
|---|---|---|
| HP | 3000 (infobox, level not stated; planner uses base hp x POWER anyway) | [wiki] Dynamike |
| Attack damage | 800 per stick (1600 if both hit) | [wiki] |
| Attack range | 7.33 tiles ("Long") | [wiki] |
| Reload | 1.4 s ("Fast"), 2 sticks per shot, 3 ammo-style shots? ammo count not in infobox | [wiki] / [unverified] ammo |
| Super charge per attack hit | 25 % (infobox "AttackSuperCharge") | [wiki] |
| Super charge per super hit | 50.05 % (super hit recharges half a super; two enemies hit = full chain) | [wiki] |
| Super range | 7.33 tiles, lob, passes walls | [wiki] |
| Super damage | 2200; Demolition adds +1600 (= 3800); the wiki Tips text still says 6000 / 6660 (old numbers) | [wiki] infobox; tips text stale |
| Super blast / knockback / fuse | radius 2.67 tiles; knockback 3 tiles; fuse 1.3 s; destroys cover | [wiki] |
| Super projectile speed | 1600 (1900 split bombs with Hypercharge) | [wiki] |
| Gadget Fidget Spinner | 12 s cd, 20 sticks in a spiral around him (2.33 to 8.67 tiles out), 2800 per stick, +20 % speed for 2 s (960), cannot attack while on | [wiki] |
| Gadget Satchel Charge | 23 s cd, next attack stuns 1.5 s; cooldown starts when that attack is thrown | [wiki] |
| Star power Dyna-Jump | attack throws him 3 tiles away from the blast, super 5 tiles (more over wide obstacles / lakes), immune while airborne except DoT | [wiki] |
| Star power Demolition | +1600 super damage | [wiki] |
| Hypercharge Boomer | super splits into 8 small bombs on detonation, each 30 % of super damage; +20 % speed, +5 % damage and shield | [wiki] |
| Hypercharge charge | 7.5 % per attack, 15 % per super | [wiki] |
| Edgar for matchup (reference) | HP 3700, range 2, reload 0.7 s, super = jump 6.67 tiles, speed 855 (1055 after super) | [wiki] Edgar |

## 3. #91 super_role
Roles: **zone** (primary: area denial with a 1.3 s telegraph, wall-breaking, knockback) and **finisher** (secondary: 2200 plus
the chain recharge kills <50 % targets). `utility` for wall-breaking. With Dyna-Jump only: `escape_dash` (5 tile self-jump).
Why: the barrel is slow (1.3 s fuse) so it rarely lands on a free-moving target; it hits cornered, stunned, healing or
gas-pinned targets, and its radius (2.67) is far wider than the 1.5 attack.

| Situation | What to do | Rule condition (planner terms) | Tag + source |
|---|---|---|---|
| Enemy below ~50 % in 7.33 tiles | Barrel on it, lead its movement; add a stick pair a beat later so the knockback pushes it into the sticks | rule 4 as now: super ready, enemy hp < 50 %, dist <= 7.3. Prefer when enemy is not already sprinting at me | [wiki] Strategies; rule 4 matches |
| Two or more enemies within 2.67 tiles of one point | Barrel at the centre: hits both, recharges a super, chain | count of enemies within 2.67 of a point >= 2 and dist <= 7.3 | [wiki] tip "damage at least two enemies"; [community] |
| Enemy in an enclosed spot (dead end, walled pocket, box ring) | Barrel at the pocket: no exit, assassins have no wall-breaking | grid: enemy tile has >= 6 of 8 neighbours wall/water, dist <= 7.3 | [wiki] Demolition tip (Edgar, Mico, Leon, Crow, Mortis, Surge named) |
| Enemy within 3 tiles of the gas edge | Barrel placed so the 3 tile knockback pushes it into the gas | enemy within 3 tiles of poison on the poison side of it, dist <= 7.3; Showdown | [wiki] Showdown tip; [community] |
| Enemy stunned by Satchel Charge | Barrel at once: it cannot dodge or shoot back; free super back | Satchel used < 1.5 s ago and the enemy still in view (gadget state not in the obs: [unverified] needs a cond flag) | [wiki] gadget tips |
| Enemy hides behind a wall or box | Barrel over / through the wall: the blast removes the cover, the next sticks land | known wall between us (LOS col), enemy dist <= 7.3, enemy hp < 60 % | [wiki] "break cover"; [multi-source] lob play |
| Assassin sprinting at me, hp low | Throw the SUPER at my feet only with Dyna-Jump (5 tile jump away over walls); otherwise throw sticks AHEAD of the charge | needs star-power flag [unverified]; else rule 3 | [wiki] Dyna-Jump tips |
| Walls around me that I need | DON'T barrel the wall I stand behind: it removes my cover | my tile within 2.67 of the target point and a wall tile between me and the enemy: hold | [wiki] "be careful ... removes protective barriers" |
| Single healthy target at 7 tiles, moving | DON'T throw it (1.3 s fuse + travel, dodgeable); hold for a pin or a second target | enemy hp >= 60 %, moving (velocity != 0), no gas/wall pin: hold the super | [wiki] "players often dodge"; [community] |
| Team 3v3, ally fights an enemy near a wall | Barrel breaks the wall for the team (Heist safe, Brawl Ball goal) | team size > 1; mode-specific: [unverified] if the sim has Heist / Ball | [community] samurai-gamers 2019 |
| Enemy in a bush | Barrel clears the bush (cover destroyed) and chases it out; cheaper: Fidget Spinner or a stick pair into the bush | enemy bush tile in range, not known to be a brawler: use sticks first, super only if hp < 50 % | [wiki] (Fidget Spinner checks bushes); [community] |

## 4. #92 bush play
**can_ambush: no (only a counter-ambush with Satchel Charge).** He has no dash and no short burst; both throws have a delay
(1.0 s). A bush-ambush by TntDude is therefore weak. The issue case "Dynamike vs Edgar never ambushes": agreed, he should
lurk, not jump out.

| Question | Answer | Tag + source |
|---|---|---|
| Trigger distance | none for an ambush. Lurk throw distance: 4-7.3 tiles (both sticks land inside 1.5 tiles at this range only if aimed with a lead). At <= 3 tiles the spread is tight: useful only with Satchel Charge (stun) | [wiki] spread; [community] |
| Lurk (hold fire, stay hidden) vs whom | assassins (Edgar, Mortis, Fang, Leon, Mico, Crow) and anything faster that reaches him in < 1.3 s: staying hidden stops the charge; a thrown stick reveals him and the fuse gives them time to arrive | [wiki] "assassins are huge counters"; [community] |
| Lurk vs ranged / slow targets | don't lurk: free sticks from behind a wall (they cannot answer unless thrower or a wall-breaker, planner rule 5) | [wiki] |
| Dives / beats up close | slow tanks and walls of HP in the open when kited (Bull, Darryl, El Primo, Frank): they cannot reach a Dynamike who throws ahead of them; the wiki still lists heavyweights as not one-shot by super + sticks | [wiki] Strategies |
| Must avoid up close | Edgar (HP 3700, 2 tile punch, 6.67 tile jump, heals by hitting); Mortis (strong answer per a 2026 counter snippet); Leon, Fang, Mico; pierce-through-wall brawlers (Brock, Hank, Squeak, Jacky) when standing against a wall | [wiki] Edgar; [community] theclick snippet; [wiki] wall tip |
| Bush tricks | stand in a bush BEHIND a wall: a lobber is unreachable and hits by surprise; Satchel Charge then lands. Keep a 1+ tile buffer to the wall when facing Brock, Hank, Squeak or Jacky | [wiki] Strategies |
| Bush trick 2 | Dyna-Jump: throw a stick at the feet to hop 3 tiles (over a wall / into a bush); a super hop is 5 tiles; he is immune in the air, so a jump can dodge an assassin's first hit | [wiki] Dyna-Jump |
| Caught by an assassin | Satchel Charge, aimed at the enemy's feet (stun 1.5 s), then back off; against Mortis make him spend ammo first. Fidget Spinner speed boost only if the assassin is not yet in reach | [wiki] Strategies (this exact advice) |
| Does attacking from a bush reveal him? | yes in the real game attacks reveal a bushed brawler; the duration is not given on any page I could open [unverified]. Brawler-specific twist for him: the thrown sticks arc visibly and the blast marks the origin direction, so the bush is likely guessed after the first throw [community inference, unverified] | gap |

## 5. Mode differences
- Solo Showdown: low HP + 1.0 s fuse makes him easy prey; guides say "move cautiously", use obstacles and hold off short-range
  brawlers; the barrel works as gas-pinning and as a kill on <50 % cube carriers. [community] samurai-gamers (2019, old).
- Duo / team: stronger (one source calls him most popular in Duo, another says avoid him in Solo). The super opens paths for
  the partner, flushes bushes and chains from two-target hits. Team size > 1: prefer the finisher / zone use, support rule 11. [community]
- 3v3 team modes: a teammate in front makes him safe and his barrel breaks walls (Heist safe, Brawl Ball goal); a Satchel
  stun + barrel combo is the usual burst. [wiki][community]
- A Sept 2026 stat snippet puts him at D tier, about 44 % win rate overall. [community] (low confidence)

## 6. Proposed rule sketch
- **barrel_zone** (new, right after rule 4 super): super ready, an enemy within 7.3 tiles with a second enemy within 2.67 tiles of
  it, or the enemy within 3 tiles of the gas edge, or in a walled pocket -> super at the pocket centre
  "SomeBrawler 5 tiles N next to the gas at 70 %: barrel to push it in".
- **hold_barrel** (a guard on rule 4): super ready, enemy hp >= 60 %, moving, none of the pins above -> keep the super
  "Edgar 6 tiles E at 90 %, moving: holding the barrel".
- **lurk_assassin** (near rule 3 low_hp / rule 6 keep_away): a KNOWN assassin (Edgar, Mortis, Fang, Leon) within 9 tiles, hp any,
  I am in a bush -> hold fire, stay hidden; if it is within 3 tiles use Satchel Charge, then away from it
  "Edgar 7 tiles W, TntDude in the bush: lurking, not throwing".
- **wall_buffer** (near rule 5 thrower_wall): standing against a wall with a known Brock / Hank / Squeak / Jacky within its range
  -> move 1-2 tiles off the wall
  "Brock 6 tiles E: stepping off the wall S".
- **bush_behind_wall** (near rule 15 hide): TntDude, no enemy in view, a bush within 5 tiles that has a wall between it and the
  open side -> hide there (lob over the wall)
  "no enemy seen, bush 3 tiles W behind a wall: hiding to lob".
- **super_deny_wall** (guard on the barrel): do not throw the barrel when a wall between me and the enemy is within 2.67 tiles of
  the target point and I have no other cover
  "enemy 4 tiles N: keeping my wall, no barrel".

## 7. Conflicts and gaps
- Super damage: infobox 2200 (+1600 Demolition) vs prose 6000 / 6660 in the same wiki page; the prose is old. Use the infobox.
  The search snippets also showed +1000 vs 2200: unresolved, needs the game tables.
- HP 3000 is a base value without the power-level multiplier; the sim's skills table should replace it.
- Hypercharge and Dyna-Jump flags and Satchel state are not in the observation: the rules above that need them are [unverified]
  as implemented. Needs a cond / ent flag or a safe default (assume no Dyna-Jump).
- Bush reveal duration and who sees it: not found (no Bush wiki page by that name; two searches returned nothing). Needs a
  game or host check (`status_check`).
- Edgar matchup: no source gives a Dynamike-vs-Edgar text; I derived it from wiki numbers plus "assassins counter him". The
  only matchup snippets are generic (theclick.gg listed Mortis as a strong answer).
- Most Showdown tips are from 2019 (samurai-gamers); recent 2025-26 guides were blocked (theclick.gg, noff, brawlify 403/none).
- Super charge per hit (25 % attack, 50.05 % super) is the wiki infobox; a chain only works with two targets.
- Spread / 0.33 tile figures from the Fidget Spinner are not needed for the planner.

## 8. Sources
1. https://brawlstars.fandom.com/wiki/Dynamike (MediaWiki API, wikitext read 2026-11-28): all numbers, gadgets, star powers, tips, strategies, assassin and wall remarks.
2. https://brawlstars.fandom.com/wiki/Edgar (API): Edgar HP, range, speed, super jump range.
3. https://samurai-gamers.com/brawl-stars/dynamike-strategies-guide/ (2019-01-23): Showdown solo / duo tips, wall use, super uses in Heist / Brawl Ball. Old.
4. https://www.theclick.gg/?p=76733 and ?p=76731: seen only as search snippets (Mortis a strong answer; spread out; make him use the barrel defensively). Pages returned 403.
5. https://gamewith.net/brawl-stars/48126 and https://www.gamezebo.com/walkthroughs/brawl-stars-character-guide-how-to-play-dynamike/: search snippets only (use walls and obstacles in Showdown; hide in bushes after power-ups). Not opened.
6. https://www.noff.gg/brawl-stars/build/14916/dynamike-tier-max-guide, https://seemeta.com/en/brawl-stars/brawlers/dynamike: seen in results, not opened. Tier / win-rate figures (D, ~44 %, Sept 2026) come from a search snippet, not from the page.
7. reddit (search snippet): r/BrawlStarsCompetitive Mar 15 2019 "learn how to main the highest skill cap brawler": only the title was seen; tips are dated.

## 9. Research log
- Worked: fandom MediaWiki API (Dynamike page was complete and recent, 2026-11); WebSearch standard (4 calls, snippets only); WebFetch of
  samurai-gamers (worked, old page).
- Failed: theclick.gg x2 (403), fandom pages "Bush" and "Tall_Grass" (missing), search for bush reveal duration (nothing).
- Calls: 4 WebSearch + 3 WebFetch (1 ok) + 5 fandom API / curl = 12 web calls.
- At scale: pull each brawler's wiki Tips / Strategies sections through the API first (most useful, current, free), then one
  search per brawler for "counter / matchup"; queue guides through a fetch tool that is not blocked; add a game-side check for
  bush reveal time once, as it is not brawler-specific.
