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

## Checked against the game tables (2026-11-28, `roles._check`)
- Ranges and super ranges in the table match skills.csv (CastingRange / 3 = tiles): Piper 10 / 8.67, Shelly 7.67 /
  7.67, Bull 5.33 / **11** (the agent's unconfirmed 11-tile charge is right), Edgar 2 / 6.67, Poco 7 / 9.33, Dynamike
  super damage **2200** (the wiki's 6000 is stale).
- Poco's heal and Sandy's cloak are BehaviorType **Attack**: planner rule 4 (attack super at a low enemy) fires them
  today. With `--plan-roles 1` rule 4 needs the finisher role.
- Edgar's punch is a projectile in the tables (obs melee flag 0); Mortis is `Undertaker`.
- Classes come from characters.csv `ClassArchetype`, so every brawler has a class default (roles.py).

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
