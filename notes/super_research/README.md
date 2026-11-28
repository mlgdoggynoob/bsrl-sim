# Super roles and bush play: research pilot (#91, #92)

Pilot of the #91 / #92 research pass, 2026-11-28: one brawler per class, one Sonnet 5.5 subagent each (medium effort;
Piper also at high effort to compare). Web only: this container has no game files, so no number here is confirmed in
`skills.csv` or the sim yet. Tags in the files: [wiki] fandom MediaWiki API, [multi-source] 2+ independent sources,
[community] one guide / stats site, [unverified] inference, [repo] this repo's data.

| Class | Brawler (codename) | super_role | can_ambush | trigger | lurk / notes | file |
|---|---|---|---|---|---|---|
| Marksman | Piper (Sniper) | escape_dash, finisher (rare), utility (walls) | no (ranged snipe from a bush only) | shoot at 8.5-10 tiles | lurk vs assassins / melee; jump 8.67 tiles, ~2 s airborne immune [wiki] | piper.md (high), piper_medium.md |
| Damage Dealer | Shelly (ShotgunGirl) | finisher, utility (breaks walls / bushes) | yes | ~3 tiles (cap 4) | super 7.67 tiles; don't super a Piper mid-jump (immune) | shelly.md |
| Tank | Bull (BullDude) | engage_dash, escape_dash (team modes), utility | yes, also without super | shells ~3 tiles; charge 5-9 tiles | charge ~11 tiles [unverified], breaks walls, no stop on hit | bull.md |
| Assassin | Edgar (Enrager) | engage_dash, escape_dash | yes, always | <= 2-3 tiles; super 6.67 tiles | lurk until super ready (charges itself ~30 s) | edgar.md |
| Support | Poco (DeadMariachi) | heal_team, heal_self; finisher only with Screeching Solo | no | none | cone 9.33 tiles, 65 deg, through walls, ~2100 heal | poco.md |
| Controller | Sandy (Sandstorm) | stealth, zone (star power), utility | weak | 4-6 tiles | cloak r 6.67 tiles, 9 s, enemies see you within 4 tiles [wiki + repo] | sandy.md |
| Artillery | Dynamike (TntDude) | zone, finisher | no (Satchel Charge counter only) | none | lurk behind a wall vs assassins; barrel lobs, 1.3 s fuse | dynamike.md |

## What the pilot showed
- **Bush reveal duration: no source has it** (8 of 8 agents). Measure it in the sim (`w["sees"]`, `hid_vs` after a
  shot, #92) instead of searching for it per brawler.
- The issue examples hold: Piper / Dynamike lurk vs Edgar, Shelly / Bull / Edgar ambush, Poco is no healer bucket from
  BehaviorType. Piper's jump is her escape (keep it for assassins, the `hold_super` gate in piper.md).
- Matchup lists are weak: one stats site per brawler, often contradicting guides (Piper beats Edgar 60 % in 2026 3v3
  stats vs "assassins are a major counter" on the wiki). Use them as priors, not rules.
- Numbers: wiki infoboxes mix power levels and lag balance patches (Dynamike super 2200 vs 6000 in the same page, Poco
  rework Aug 2026). The game tables have to win every conflict.

## Round 2: attack dashers (Sonnet 5.5, high effort)
| Brawler (codename) | profile | checked in the tables | open |
|---|---|---|---|
| Mortis (Undertaker) | finisher + heal_self super; dash_escape (main attack), lane (a wall cuts the dash), ambush 3 tiles | attack dash 2.67 tiles (CastingRange 8, AlwaysCastAtMaxRange), super Attack 10 tiles, 900 damage, 4000 HP | the "4.67-tile long dash bar" the wiki describes is not in skills.csv; whether a dash into a bush stays hidden. Built since: super_finish (900 vs enemy HP), avoid_brawl |
| Mico (Leaper) | engage_dash + escape_dash super (sreach 10), dash_escape, ambush 3.5 tiles | attack jump 4 tiles (Charge), super FlyJump: CastingTime 1000 ms, ActiveTime 6000 ms, MovementSpeed 1025, CastingRange 0 | the super's real landing reach (sreach 10 is a stand-in). Built since: finish_jump (1140 damage from skills.csv), no_dive_grouped |

## Checked against the game tables (2026-11-28, `roles._check`)
- Ranges and super ranges in the table match skills.csv (CastingRange / 3 = tiles): Piper 10 / 8.67, Shelly 7.67 /
  7.67, Bull 5.33 / **11** (the agent's unconfirmed 11-tile charge is right), Edgar 2 / 6.67, Poco 7 / 9.33, Dynamike
  super damage **2200** (the wiki's 6000 is stale).
- Poco's heal and Sandy's cloak are BehaviorType **Attack**: planner rule 4 (attack super at a low enemy) fires them
  today. With `--plan-roles 1` rule 4 needs the finisher role.
- Edgar's punch is a projectile in the tables (obs melee flag 0); Mortis is `Undertaker`.
- Classes come from characters.csv `ClassArchetype`, so every brawler has a class default (roles.py).

## Round 3: own planner rules for every researched brawler
From each note's section 6 (rule sketch), the plays the shared role rules did not cover; names and conditions in the
planner module doc "Brawler rules" (B1-B14), self-check scenes in `planner._check`:

| Brawler | rules | from | left out (needs what) |
|---|---|---|---|
| Piper | snipe_band (+ kite an even enemy within 6 tiles) | piper.md: max_range_kite | auto_aimer_peel (gadget state in the planner), wall_open (team modes) |
| Shelly | point_blank (super within 3 tiles; knockback at low hp; rule 4 beyond 3 tiles only on a finish) | shelly.md: super_point_blank, low_hp_knockback | dive_sniper (a flanking path), wall break with the super |
| Bull | charge_cover (hold the charge in a bush / behind a wall vs a longer-range enemy at hp < 80 %) | bull.md: bull_no_open_dash | Stomper follow-up and gas cancel (gadget state) |
| Edgar | avoid_brawl, dive_ranged | edgar.md: avoid_tank, super_engage variant | lurk until the super is ready (overlaps hide / farm) |
| Poco | heal_mate, heal_panic (super mode heal: achieved when the healed hp rises) | poco.md: heal_mate, heal_self_panic | the Screeching Solo finish (star power not in cond) |
| Sandy | cloak_escape, cloak_engage, cloak_endgame (mode escape / place) | sandy.md: cloak_* | zone_bush_check (Rude Sands only), lurk_in_zone; does the cloak hide him after he fires (sim check) |
| Dynamike | barrel_zone (2 enemies together, next to the gas, walled pocket) | dynamike.md: barrel_zone | hold_barrel (rule 4 already needs < 50 %), wall_buffer, super_deny_wall |
| Mortis | super_finish (absolute hp, or a heal below 50 %), avoid_brawl | mortis.md: super finish / heal, avoid_heavy | the long-dash bar (not in the tables), dive_squishy (= engage today) |
| Mico | finish_jump, guard no_dive_grouped | mico.md section 6 | his super's real reach |

The profiles, rules and checklist built on this: `roles.py`, planner role rules, [WORKFLOW.md](WORKFLOW.md),
[CHECKLIST.md](CHECKLIST.md).

## Corrections made at merge
- sandy.md: codename is `Sandstorm` (desc_audit keys `Sandstorm_*`), not `Sandy` as the agent guessed.
- piper.md: cond 9 is BehaviorType == Attack; #91 lists Piper's jump as Charge, so rule 4 does not fire her jump today.
- piper_medium.md, dynamike.md: dropped Reddit mirror links that came back in search results (Reddit blocks this IP;
  the brief ruled out mirrors).

## Access (from a cloud container)
- Reddit: Reddit's own "Blocked" 403 on www / old / api / oauth / .json / .rss. Only search snippets are usable.
- fandom HTML: Cloudflare challenge; `api.php?action=parse&page=<Page>&prop=wikitext&format=json` works.
- noff.gg, exitlag, sportskeeda, destructoid: 403. brawl-up, brawlio, brawlhub, powerleagueprodigy, samurai-gamers: ok.

## Medium vs high (Piper)
| | medium | high |
|---|---|---|
| time | 100 s | 200 s |
| subagent tokens | 103 k | 119 k |
| web calls | 11 | ~24 (wiki Showdown page, 3 stats sites) |
| extra in high | | win-rate matchups, source conflicts, landing rules (wall / water, 6 tiles from others), quick-fire caveat |
| extra in medium | patch history (June 2026 HP 2500 -> 2800, Oct 2025 Auto Aimer) | |
| mistakes | cited a Reddit mirror | wrong cond 9 assumption |

Both are usable. High costs about 15 % more tokens for roughly twice the sources and a better conflicts section.

## For the full roster
- One wiki API call per brawler first (infobox, super, tips), then one stats page for matchups. One bush-mechanics query
  for all brawlers, not per brawler.
- Give agents the codename list (from `obs_v5` / desc_audit) so they don't guess.
- Then confirm every number used by a rule against `skills.csv` / `super_audit` on a host.
