# Poco (Support) - research for #91 super_role and #92 bush play (2026-11-28)

Tags: [wiki] numbers from brawlstars.fandom.com API; [multi-source] 2+ sources agree; [community] one guide / opinion;
[unverified] inference or an old / conflicting source. All numbers unconfirmed in the sim (no game tables here).

## 1. Identity
- Name Poco, in-game title "El Mariachi"; class Support; rarity Rare; one of the 15 first-beta brawlers. [wiki]
- **Codename: `DeadMariachi`** (sim internal). Not from a web source: the repo itself maps it (engine/py/nbpc/diversity.py:73
  `("DeadMariachi", "Poco", "wide wave (piercing cone)", ...)`, projectile types `DeadMariachiProjectile` 6000335 (attack) and
  `DeadMariachiUltiProjectile` 6000336 (super), `DeadMariachiOverchargedUltiProjectile` 6001521 (hypercharged super);
  super_audit.py:285 already treats the super as heal-only via `HealOwnPercent`). [repo]
- Attack "Power Chord": 4 rows of musical notes in a 65 degree cone, pierces (hits every enemy / ally in the cone), same damage at
  any range, medium-long range 7 tiles; walls stop it (attack is a normal projectile). Heals allies it hits for 5 % of max HP
  (older wiki text; see conflicts). [wiki] [multi-source]
- Super "Encore": a bigger, faster wave, same 65 degree cone, 9.33 tiles; **heals Poco himself and every ally it hits; does not
  touch enemies** (unless Screeching Solo); **passes through brawlers and obstacles (walls)**; shows green for everyone;
  does not heal summons. [wiki] [multi-source: wiki + search summaries; wall-pass change dates to a 2017 update]
- Speed 750 (Normal). [wiki]

## 2. Numbers
| Item | Value | Source |
|---|---|---|
| HP | 4000 [wiki infobox, level-11 style number] | wiki |
| Attack damage | 760 (infobox "Attack"), reload 1.6 s, range 7 tiles | wiki |
| Attack heal to allies | 200 in infobox ("Healing"), "5 % of max HP" in the text | wiki (internal mismatch) |
| Super charge per attack hit | 20.8 % per hit (hypercharge 8.3 %) | wiki |
| Super range / width | 9.33 tiles (Very Long), 65 degree cone, projectile speed 5000 vs 2500 for the attack | wiki |
| Super heal | 2100 to self and each ally hit (gamewith also 2100 "very long range") | wiki + gamewith |
| Super duration | instant (a travelling wave, no zone) | wiki ("Poco's Super is instant") |
| Gadget Tuning Fork | 3.33 tile radius circle around Poco, heals self and allies 1400 now + 2 more waves 2 s apart (3 x 1400 = 4200 wiki; gamewith 370/s over 5 s; Supercell notes 400 x 3 over 6 s: numbers differ by patch); cooldown 20 s; Buffie +25 % reload | wiki, gamewith, supercell |
| Gadget Protective Tunes | lobbed AoE 3.33 tiles, 4 s, cleanses and immunises teammates (stun, slow, poison, knockback); cooldown 24 s | wiki |
| Star Power Da Capo! | attack heal +10 % max HP; attacks auto-target allies | wiki |
| Star Power Screeching Solo | super also damages enemies "equal to his main attack's damage": 1520 (wiki), 760 (gamewith, Supercell Aug 2026 notes, likely level-1 numbers); no super charge from it; auto-aim still aims at allies | wiki, gamewith, supercell |
| Hypercharge Medic's Melody | Encore overheals: full-HP allies get a shield decaying over 5 s; +20 % speed, +5 % damage / shield; Buffie: attack cone 180 degrees | wiki, supercell |
| Hypercharge multiplier / charge | 40 % ; attack hypercharge charge 8.3 % | wiki |

## 3. #91 super_role
**Roles: `heal_team` primary, `heal_self` secondary (always applies on cast), `finisher` only with Screeching Solo (and then
only a weak one: 760-1520 dmg, 0.5 s silence with Buffie).** Why: Encore is an instant, wall-piercing, long cone that heals
Poco plus allies and hits no enemy by default. [wiki] [multi-source]

| Situation | What to do with the super | Rule condition (planner terms) | Tag + source |
|---|---|---|---|
| 3v3 / duo, mate hurt and within the cone | cast aimed over the mate (heals both) | team size > 1, mate within 9.3 tiles, mate hp < 0.6 (or 2+ mates < 0.8), my super ready; aim = mate offset | [multi-source] samurai 2019 "when several mates are mid to low", wiki "best when one or two mates took a big hit" |
| Mate hurt behind a wall | cast anyway, wave passes obstacles; no line-of-sight check needed | same, ignore `LOS`; range 9.3 tiles straight | [wiki] pass-through; [multi-source] search summaries |
| Me low, a mate near | aim over the mate so both heal; self-heal is automatic | my hp < 0.4 and mate within range -> super at mate | [community] samurai "always heals himself, aim over allies" |
| Me low, no mate (Solo Showdown) | cast only as a self heal if hp < ~0.35 and an enemy is near and no bush to hide in; otherwise hide | hp < 0.35, enemy within 1.2 x reach, super ready, no bush within 4 tiles | [unverified] inferred: 2100 of 4000 HP is a 52 % heal, a decent panic button |
| Bait low-HP luring | pop it at low HP to make the enemy commit, then it heals | not recommended as a rule (too tactical) | [community] samurai 2019 (old) |
| Screeching Solo, enemy low | finish an enemy at < 25 % hp in the cone (760-1520) | rule 4 `super` as-is: enemy in super range, hp < 0.25; only if the build has the star power (cond lacks it: unknown) | [community] wiki "best to finish low-health enemies" |
| Screeching Solo, enemy behind wall, low hp | super goes through the wall, a safe finisher | same, ignore `LOS` | [wiki] 2017 patch note; [unverified] current |
| Don't: full-HP team, nobody hurt | hold the super: aiming wastes the charge; "do not just tap the button" | all mates hp > 0.8 and my hp > 0.7 -> no super | [community] samurai, search summaries |
| Don't: super aimed with no ally in the cone and no Screeching Solo | pure self heal (waste) unless hp < 0.35 | same panic condition as above | [community] |
| Don't: Gem Grab zero-gem mate | skip healing a mate with no gems when I carry several | mode-specific (not Showdown); skip | [community] samurai 2019 |
| Hypercharged | cast when mates are at FULL hp right before a push: gives a decaying shield (nothing if hp low) | hypercharge active, mates hp >= 0.95, engage coming | [wiki] "make sure allies are at maximum health" |
| Gadget synergy | Tuning Fork first when mates stand within 3.33 tiles (heals 3x), super for far or low mates | mate within 3.3 tiles -> gadget, else super | [wiki] |
| Gas | none of the roles: the super does not move you or stop gas damage; it heals, so a cast inside gas to outheal only buys seconds | do not cast for gas | [unverified] |

Heal priorities (who first): sources give no explicit order; the consistent reading is lowest hp fraction first, then
mates carrying objectives (ball / gems), then the tank / front-liner. [community] [unverified as a strict order]
Save vs spend: spend when 1-2 mates took a big hit; do not spend on a full-hp team; do not spend only to heal myself unless
Screeching Solo or hp critical. [community]

## 4. #92 bush play
- **can_ambush: no.** Reasons: damage is low (760 per volley of notes), the attack has the SAME damage at any range, so there is no
  close-range burst reward for jumping out; HP 4000 is only moderate and he has no dash / stealth; the super is a heal, not a
  charge. Wiki: "he is typically defeated in solo interactions" and "be careful not to be ambushed". [wiki] [community]
- Trigger distance: none. If forced, his best spot is the edge of max range (7 tiles), not melee. samurai 2019: attack shorter-range
  brawlers "from the edge of your range". [community, old]
- **Lurk: partial yes, as a defensive hide.** Hide in a bush at low HP to stop taking damage and to heal when no mate is
  present; Showdown has no natural regeneration trick specific to Poco. His wide 65 degree cone is good for checking bushes
  (rule 13 `check_bush` fits: shoot into a bush from range). [wiki "decent on maps with bushes for checking hidden enemies"]
- Dives / good matchups: shotgun-style short-range brawlers if he keeps his distance (damage same at all ranges, so he kites).
  Gamewith: good vs Dynamike, Max, Tara. [community, old / single]
- Avoid up close: assassins and tanks (Mortis, Frank, Crow noted as counters; also Leon / Edgar / Fang class); high-damage
  long-range brawlers (Griff, Colt, Clancy overpower his healing); poison / anti-heal (Crow, Byron). [multi-source: wiki + gamewith]
- Bush tricks: none brawler-specific. Rule 3 `low_hp` (hide in a bush) fits him; rule 6 `keep_away` fits when the enemy
  is shorter-range (range <= 5.5) since his range is 7. [unverified]
- Reveal-on-attack: no Poco-specific twist found. Generic game rule applies: attacking from a bush reveals you briefly; not
  verified by a Poco source. [unverified]

| Claim | Tag | Source |
|---|---|---|
| Cannot ambush: low damage, no mobility | [wiki] | wiki tips |
| Wide cone checks bushes | [wiki] | wiki tips "Other" |
| Same damage at all ranges, kite from max range | [community, 2019] | samurai-gamers |
| Counters Frank, Mortis, Crow | [community] | gamewith 48129 |
| Assassins that dive past the front line burst him | [community] | search snippet (clutchpoints) |

## 5. Mode differences
- **Solo Showdown:** no teammates, so heal_team never fires; Da Capo! is dead weight (wiki recommends Screeching Solo for Showdown /
  Lone Star / Takedown). The super is then a self heal plus a weak finisher. Wiki and samurai: Poco is "never too viable" solo, poor on
  big open maps, easy prey for tanks and assassins. Charging the super still helps ("attack more readily"). The sim mostly
  needs: play safe, keep range 5-7 tiles, farm boxes with the wide cone (one volley hits several boxes), hide when low, use the
  super as a heal at low HP or to finish a 25 % enemy through a wall. [community] [unverified]
- **Duo Showdown:** the real use case: stay close to the partner, heal them. With a short-range partner add damage and heal; with
  a long-range partner be the front line and heal yourself. [community, samurai 2019]
- **3v3 (Brawl Ball, Gem Grab, Hot Zone, Bounty):** heal the ball carrier / gem carrier; pair with tanks; Tuning Fork and Da Capo! to heal
  without super; one source recommends Poco for Hot Zone. [wiki] [community]
- One ExitLag guide claims a 2026 rework where Power Chord always heals allies; the Supercell Aug 2026 notes show "Power Chord
  always heals allies for 300", consistent with it (see conflicts).

## 6. Proposed rule sketch
- `heal_mate` (near rule 4 `super`, before it): team size > 1, super ready, a mate within 9 tiles with hp < 0.6 (or two mates <
  0.8) -> super aimed over the mate (wall irrelevant). Reason: "mate 6 tiles E at 35 %: Encore through the wall to heal".
- `heal_self_panic` (after rule 3 `low_hp`, which tries to hide first): super ready, hp < 0.35, enemy within 1.2 x its reach, no
  bush to hide in within 4 tiles, solo or no mate in range -> super (self heal 2100). Reason: "hp 30 %, Mortis 3 tiles N, no
  bush: Encore to heal".
- `super_finish_through_wall` (extension of rule 4): Screeching Solo equipped (unknown in cond: guard behind a flag),
  enemy < 25 % in 9.3 tiles even behind a wall -> super. Reason: "enemy 8 tiles NE behind a wall at 20 %: Encore finish".
- `hold_super` (a gate on rule 4 for Poco): no ally in the cone, no Screeching Solo, hp >= 0.35 -> never cast (it would waste it).
- `keep_away` (rule 6) tuned: for Poco apply to any enemy with range <= 5.5 and any assassin class; keep 5-7 tiles.
- No lurk / ambush rule: `can_ambush = no`; keep rule 15 `hide` for low HP only (not bush_camp for ambush).

## 7. Conflicts and gaps
- Screeching Solo damage: wiki 1520 vs gamewith / Supercell 760 (level 1 vs level 11 scaling; same for heal numbers).
  Attack damage 760 in the infobox suggests the wiki mixes levels. Check the game table.
- Da Capo! heal: 320 -> 400 (Supercell Sept note), 481 (gamewith), 720 (wiki infobox), 700 / 958 (search summary): patch drift.
- Rework: Supercell Aug 2026 notes list Power Chord always healing allies (300) and a new Tuning Fork (400 x 3 over 6 s);
  older wiki says the attack heals only 5 % max HP and Tuning Fork 1400 x 3. The sim's game build version decides which one.
  The wiki wikitext may predate the rework.
- Wall pass for the super: confirmed by the wiki only (patch note of 2017) and search summaries; the 2019 samurai guide
  warns the wave "can be blocked", an old contradiction. Check the sim's projectile flags for 6000336 (a sim table check).
- No source on a Poco-specific bush reveal time, no pro / esports source, no Reddit (blocked). Showdown ranking:
  Poco is not in the October 2026 top list snippets (Shade, Gus lead); one site rates him S+ overall, seemeta ~C ranked.
- Heal priority order and "save vs spend" are inferred; no source states them explicitly.

## 8. Sources
1. https://brawlstars.fandom.com/api.php?action=parse&page=Poco (wikitext) - all [wiki] numbers, super passes walls, tips. Fetched
   2026-11-28 (curl).
2. https://samurai-gamers.com/brawl-stars/poco-strategies-guide/ - Jan 2019: heal timing, solo / duo advice, same damage at any range.
3. https://gamewith.net/brawl-stars/48129 - super 2100, SP numbers, matchups (counters Frank, Mortis, Crow). Date unknown.
4. https://supercell.com/en/games/brawlstars/blog/release-notes/release-notes-august-2026 - 2026 rework: Da Capo! 300 + 220,
   Tuning Fork, Screeching Solo 760, hypercharge. Aug-Sep 2026.
5. WebSearch snippets (several): exitlag Poco guide (rework claim, page 403 on open), clutchpoints (assassin warning, S+ tier),
   timesaver.gg Showdown tier lists (June / Oct 2026), seemeta (C tier ranked), allclash, samurai ?p=126664.
6. Repo: engine/py/nbpc/diversity.py, super_audit.py, engine/data/glow/clip_kinds.csv - codename DeadMariachi.
- Could not open: exitlag.com (403), noff.gg (403), sportskeeda.com (403). Not tried: Reddit (rule).

## 9. Research log
- 14 web calls total (2 curl to the fandom API, 6 WebSearch, 6 WebFetch of which 3 failed with 403).
- Worked: fandom MediaWiki API (best source), supercell.com release notes, gamewith, samurai-gamers (2019, old).
- Failed: exitlag, noff.gg, sportskeeda (403). WebFetch gave summaries by a small model: numbers may be paraphrased, recheck.
- No pro / video source for solo play; the Poco-in-Showdown advice is thin everywhere and mostly from 2019-era guides.
- At scale: pull the same `Brawler Infobox` fields for every brawler via the fandom API in one script; then spend web calls
  only on Showdown-specific notes and the latest Supercell balance notes; verify numbers against the sim's game tables.
