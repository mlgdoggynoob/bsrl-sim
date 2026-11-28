# Sandy (Controller) - research for #91 / #92

Research date 2026-11-28. Web access was thin: the wiki API gave the numbers; liquipedia, metaforge, exitlag and noff returned
403; two WebSearch calls gave only snippets. Most "when to use" advice below is [wiki tips] plus [unverified] game knowledge.
Where the repo itself holds data (engine/labeller notes, status_check.py) it is cited as [repo].

## 1. Identity

- Name Sandy ("The Sleepy"), class **Controller** (confirmed, wiki infobox), rarity **Legendary**, 29th brawler. [wiki]
- Codename: no web source gives one. The repo names his super zone `Sandy_def_ulti` (area effect SmokeScreen, data id 17000217;
  other skins `Sandy_003_ulti`, `Sandy_006_ulti`), but the brawler's codename is `Sandstorm`: notes/desc_audit.md keys his cards Sandstorm_* (Sandstorm_unique, Sandstorm_Sleep), as it keys Piper's Sniper_* [corrected at merge]. [repo:
  engine/labeller/fixes/z_1027_s042.py, status_check.py]
- Attack "Pebble Blast": 3 clusters of pebbles in a wide cone (36 degrees spread), pierce through enemies, one cluster can hit
  a given enemy (so no shotgun stacking), range 6 tiles, projectile speed 3500. Not a lob: walls block it. [wiki]
- Movement speed 800 (fast); 1200 with Hypercharge + Super (see below). [wiki]
- Super "Sandstorm": a star-shaped object is thrown up to 7.33 tiles; it makes a stealth zone. [wiki]

## 2. Numbers

| Stat | Value | Source |
|---|---|---|
| HP | 4100 (base, level 1 of the infobox; scales with power) | [wiki] |
| Attack damage | 900 per cluster hit (one cluster per enemy) | [wiki] |
| Attack range | 6 tiles | [wiki] |
| Reload | 1.8 s | [wiki] |
| Super charge per hit | 16.875 % (6 hits) ; hypercharge adds 6.75 % per hit | [wiki] |
| Super range (throw) | 7.33 tiles ("long"); throw speed 2000 | [wiki] |
| Zone radius | 6.67 tiles; repo logic Radius 2000 units, TILE = 300 units => 6.67 tiles. Two sources agree | [wiki] + [repo] (multi-source) |
| Zone duration | 9 s; repo logic TimeMs 9000 | [wiki] + [repo] |
| Zone effect | Sandy and allies inside are invisible; enemies see them within 4 tiles (repo: reveal distance 1200 units = 4 tiles) | [wiki] + [repo status_check] |
| Zone exceptions | Spawnables (Nita bear) are not hidden; carriers of items (cubes, gems, ball) are visible; robots / Siege turret / Angry Robo see through | [wiki] |
| Gadget Sleep Stimulator | asleep 1.5 s (immobile, still takes damage, broken by knockback / pull / stun), then full HP; cooldown 11 s; not usable at full HP; healing debuffs apply | [wiki] |
| Gadget Sweet Dreams | next attack stuns 1 s, the stun ends when the target takes any damage; cooldown 18 s | [wiki] |
| Star Power Rude Sands | zone deals 216 / s (12 % of main attack per second, wiki body text; Sandy's infobox says 195 / s) to enemies inside; stacks with several zones; stops enemy self-heal; it also reveals nothing by itself but damaged enemies show | [wiki], figures conflict |
| Star Power Healing Winds | zone heals Sandy and allies 410 / s (5 % of max HP per second; infobox says 369) | [wiki], figures conflict |
| Gear Exhausting Storm (Mythic) | enemies inside the zone deal 20 % less damage; shots from outside still deal full damage | [wiki] + [search snippet liquipedia] |
| Hypercharge Swift Winds | next super silences enemies in the zone 0.5 s on landing (no attack, super, gadget); allies in the zone +200 speed points; Sandy +20 % speed, +5 % damage and shield; hypercharge multiplier 40 % | [wiki] |

## 3. #91 super_role

Roles: **stealth** (primary), **zone** (secondary: area denial only with Rude Sands, a heal zone only with Healing Winds),
**utility**. Why: the super does no damage by itself, it throws a 6.67-tile radius, 9 s cloak that hides him and his team.
It is not a finisher, not a dash, not a summon. [wiki]

Parameters for the rules: throw range 7.33 tiles (does the throw pass walls? [unverified]; the star-shaped object is a
lobbed throw in the game, but no source says so); radius 6.67 tiles; duration 9 s; zone fixed once thrown (it does not follow
him); invisible = not seen by enemies farther than 4 tiles. Own cloak does not break on attacking per the wiki (no mention,
unlike Leon, whose page states attacking reveals him) [wiki by omission, unverified].

| Situation | What to do with the super | Rule condition (planner terms) | Tag + source |
|---|---|---|---|
| Disengage, hp low, enemy chasing at range | Throw it at my own feet / 1-2 tiles behind me and walk to the far edge so the enemy loses sight; enemy sees me only within 4 tiles, so break to > 4 tiles | hp < 0.35, enemy within 1.2 x reach but > 4 tiles, super ready -> super at my tile, then hide (rule 3 low_hp); when the enemy is within 4 tiles the zone does not hide me: use the gadget or run | [wiki] 4-tile reveal; use is [unverified] |
| Team engage (3v3) | Throw it 4-6 tiles ahead on the approach so the team walks in unseen, then fight from inside | team size > 1, enemy 6-10 tiles away, mate within 4 tiles, super ready -> super at ~6 tiles toward the enemy (near rule 11 engage) | [wiki tips: "reach the objective hidden"], [unverified] timing |
| Cross open ground / get into bushes | Place the zone so its edge touches bushes; walk through the zone into the bush; enemies think you are still in the zone | zone edge within 2 tiles of a bush, walk into it | [wiki tips] (community, one source) |
| Hold a choke / objective | Put it on the objective or ball and ambush whoever steps in with a short-range mate | 3v3 only; team has a melee / short-range mate | [wiki tips Brawl Ball / Siege] |
| Gas endgame (2 teams) | Zone on the safe-side gas edge, hold inside it: enemies must come within 4 tiles to see me, so I get the first shot | teams left = 2, poison in view, super ready -> super 2-3 tiles toward the safe side of rule 9 endgame tile | [unverified] |
| Rude Sands | Drop it on a bush cluster or a camped box: damage ticks reveal bush campers and block their healing | star power Rude Sands known, no enemy in view, bushes within 7 tiles -> super at the bush cluster (near rule 13 check_bush) | [wiki tips] |
| Healing Winds | Stand and fight inside the zone with mates | hp < 0.6 or mate hurt, star power known | [wiki] |
| DON'T: enemy already within 4 tiles | The cloak does not hide me from them, a throw wastes the 9 s | enemy within 4 tiles and I have > 0.5 hp -> keep the super, fight or gadget | [wiki] 4-tile reveal |
| DON'T: enemy has an area super / splash (Dynamike, Tick, Barley) or is robot-like | Invisible does not stop splash that is aimed at the zone | known thrower / area attacker within its range + 1 of the zone | [search snippet: guide warns of splash and area supers], [unverified] |
| DON'T: carrying a cube | Item carriers stay visible; the zone gives nothing while cubes are held? The wiki says "carrying an item" (cubes, gems, ball) | cubes held > 0 -> the zone does not hide me: keep the super for fighting around the zone or a mate | [wiki] (Leon page: cube pickup flashes visibility; Sandy page: carriers visible) |
| Wall trick | Hide behind a wall, throw the star over it into the open so the zone covers the approach | [unverified] (no source on over-wall throw) | [unverified] |

## 4. #92 bush play

- **can_ambush: yes, but weakly.** Sandy is a mid-range cone thrower (6 tiles, 900 per hit, 1.8 s reload), not a burst brawler.
  From a bush he can open from his full 6 tiles, so he does not need an ambush trigger like a shotgun. [wiki numbers]
- Trigger distance: 4-6 tiles. Inside 4 tiles the sandstorm no longer hides me (4-tile reveal), so ambush from a bush at 4-6
  tiles; closer than 3 tiles he is a poor melee-range fighter. [wiki] + [unverified]
- **Lurk: yes, with the zone.** Zone on a bush or on a chokepoint, hold fire until the enemy comes within about 4-5 tiles, then
  open. Lurk against slow or short-range targets who do not know his position; against Rude Sands this also turns into area
  denial. [wiki tips; community/unverified]
- Dive / beat up close: the Sweet Dreams gadget lets him survive rush brawlers (Mico, El Primo, Kit, Crow, Surge, Buzz, Chuck,
  Mortis, Edgar); the wiki names these as targets of the stun-in-self-defence. [wiki]
- Must avoid up close: assassins who dash into the cone before it fires and long-range brawlers (Amber, Nita named as counters in a
  search snippet). Sleep Stimulator is a bad idea in the open (1.5 s immobile and takes damage). [wiki; search snippet sportskeeda]
- Bush tricks: (a) super edge touching bushes, walk into the bush while enemies watch the zone; (b) use Sleep Stimulator in a
  bush or behind a wall; (c) with Rude Sands drop the zone on bush clusters to flush campers. [wiki]
- Reveal on attack: the wiki for Sandy does not say an attack reveals the cloak (it does for Leon). Standard game rule: attacking
  from a bush reveals you for about a second (the "bush reveal"); the brawler-specific twist for Sandy is the 4-tile reveal radius
  inside the zone. Duration of the bush reveal: [unverified] here (no source found this session).

| Question | Answer | Tag + source |
|---|---|---|
| Can he ambush from a bush? | Yes, from 4-6 tiles (cone, pierce) | [wiki] numbers, [unverified] trigger |
| Hold fire in a bush / zone? | Yes, vs enemies who do not see him; zone on a bush for a team ambush | [wiki tips] |
| Reveal when he attacks from the zone | Not stated on the Sandy page; seen within 4 tiles regardless | [wiki], [repo reveal 1200 u] |
| Easy targets | Rushers, thanks to Sweet Dreams; groups (pierce charges super) | [wiki] |
| Avoid | Long-range / area brawlers; assassins when the gadget is down | [search snippet], [unverified] |

## 5. Mode differences

- **3v3**: the super is a team tool (positioned allies stay unseen; hides objective approach in Gem Grab, Hot Zone, Siege, Brawl
  Ball). Best with a short-range mate who ambushes from inside. Sandy is also an ideal ball carrier (speed). [wiki tips]
- **Showdown (solo)**: the cloak mostly hides only him, so it is an escape / camp tool, not a team enabler. Carrying power cubes
  keeps him visible, which cuts the value of the cloak late in a match. Duo Showdown: Sweet Dreams + Dynamike combo is named.
  [wiki tips; the cube point is [wiki] item-carrier rule applied to cubes, [unverified] for Showdown]

## 6. Proposed rule sketch

- **cloak_escape** (sits right after rule 3 low_hp): hp < 0.35, an enemy 4.5-8 tiles away that is not within 4 tiles, super ready
  (cond 9) -> super at my tile, then hide in a bush 1-4 tiles away; reason "hp 30 %, enemy 6 tiles N: dropping the sandstorm,
  slipping S". Not when an enemy is within 4 tiles, cubes held, or a known thrower in range.
- **cloak_engage** (near rule 11 engage, team size > 1): mate within 4 tiles, enemy 6-10 tiles, super ready, engage test passes ->
  super 5-6 tiles toward the enemy, then engage inside; reason "enemy 8 tiles E, mate 2 tiles W: sandstorm ahead, advancing".
- **cloak_endgame** (rule 9 endgame, super ready): teams left = 2, gas in view -> super on the endgame hold tile, hold inside it;
  reason "endgame (2 left): sandstorm on the gas edge, holding 3 tiles W". [unverified]
- **zone_bush_check** (rule 13 check_bush, Rude Sands only): no enemy in view, 3+ bushes within 7 tiles of the throw point ->
  super on the bush cluster; reason "no enemy seen, 4 bushes 6 tiles N: sandstorm to flush them".
- **lurk_in_zone** (rule 15 hide, super used, zone active): hold fire inside the zone until an enemy is within 5 tiles or below
  50 % hp; reason "sandstorm up, enemy 7 tiles away: holding fire".
- **keep_super** (guard on the above): any enemy within 4 tiles, cubes held in Showdown, or a known area attacker near ->
  do not cast.

## 7. Conflicts and gaps

- Rude Sands damage: wiki infobox 195 / s vs body 216 / s; Healing Winds 369 / s vs 410 / s. Different power levels probably.
- HP 4100 is the base wiki figure; the sim's HP at its level should be taken from the game tables.
- No source on whether the star can be thrown over walls, or on how the cloak behaves when he attacks inside it.
- The exact length of the standard bush-reveal after attacking is not in these sources.
- Sandy's current (2026) strength: a search snippet shows a tier C, 50.4 % win-rate page and another calling him among the best;
  undated, unreliable.
- Needs a sim check: whether the zone's invisibility holds against the observation of enemies at 1200+ units after he fires
  (status_check item 11 only tests the no-attack case).

## 8. Sources

1. https://brawlstars.fandom.com/api.php?action=parse&page=Sandy&prop=wikitext&format=json - all stats, super text, gadgets,
   star powers, gear, hypercharge, tips (date not shown, current).
2. https://brawlstars.fandom.com/api.php?action=parse&page=Leon&prop=wikitext&format=json - Leon's attack reveal, for contrast.
3. WebSearch snippets: liquipedia.net/brawlstars/Sandy (Exhausting Storm), theclick.gg Sandy counters (take space after the
   super is spent), sportskeeda "best brawlers to counter Sandy" (Amber, Nita), a guide warning about splash and area supers.
4. Repo: /home/user/bsrl-sim/status_check.py, engine/labeller/fixes/z_1027_s042.py (Radius 2000, TimeMs 9000, reveal 1200 u).
- Could not open: liquipedia.net/brawlstars/Sandy, metaforge.app/brawlstars/brawlers/sandy, exitlag.com Sandy blog (all 403).

## 9. Research log

- Calls: 2 WebSearch, 3 WebFetch (all 403), 2 wiki API curls. 7 web calls total of the ~25 budget; I stopped because the
  remaining listed sites blocked WebFetch and the wiki had the numbers.
- Worked: the Fandom API (full wikitext); the repo's own engine notes for radius / time / reveal range.
- Failed: liquipedia, metaforge, exitlag via WebFetch. WebSearch returned many low-quality spam results.
- At scale: ask WebSearch for specific guide domains (game8, samurai-gamers) and read them through curl with the proxy README
  instructions; ask for YouTube titles on "Sandy Showdown" to get pro habits.
