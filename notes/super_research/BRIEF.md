# Research brief: pilot for issues #91 (brawler-specific super rules) and #92 (bush lurk / ambush)

You research ONE Brawl Stars brawler for an RL bot's rule planner. Repo (read-only for you): the bsrl-sim checkout.
The prompt gives you the brawler's codename and its game-table facts (`roles.facts`: class, super BehaviorType, range and
super range in tiles): use them, do not guess a codename. <OUTFILE> = notes/super_research/<name>.md.
Read first, briefly: GitHub issues #91 and #92 are summarised below; `planner.py` docstring (lines 1-90) for the rule
vocabulary (tiles, hp fraction, strength R, reach, rules 1-15); `notes/pro_strategies.md` (earlier research, its style).
Do NOT edit anything in the repo. Write only your output file.

## What the planner needs from you
#91: a `super_role` for the brawler, one or more of: finisher, engage_dash, escape_dash, heal_team, heal_self, shield,
zone, summon, stealth, utility; plus the parameters the rules need (super range / dash length in tiles, wall-passing?,
heal amount and radius, duration, damage) and WHEN good players use the super (engage, escape, finish, heal, zone,
deny), with conditions a rule can test (enemy hp %, distance, my hp %, ammo, walls, bushes, gas, team mode).
#92: can it ambush from a bush (short range / melee / dash super ready)? Trigger distance (shotgun: full-damage range;
melee: reach; charge super: super range). Should it lurk (hold fire, stay hidden) and against whom? Who does it beat up
close / lose to up close (matchups: who to dive, who to avoid)? Bush tricks (jump into a bush, charge out of one).
Also: does attacking from a bush reveal you in the real game, and for how long (any brawler-specific twist)?
Also: Showdown (solo / duo) vs team modes (3v3): what changes for this brawler.

## Sources and access (tested from this container, 2026-11-28)
- Reddit (www / old / api / oauth / .json / .rss) returns Reddit's own "Blocked" 403 to this cloud IP. Do NOT try to get
  around it (no archive.org / mirrors / proxies of Reddit). Search-result snippets that WebSearch returns from Reddit
  threads are fine: cite them as "reddit (search snippet): <thread title/url>".
- brawlstars.fandom.com HTML pages hit a Cloudflare challenge. Its public MediaWiki API works:
  curl -s "https://brawlstars.fandom.com/api.php?action=parse&page=<Page>&prop=wikitext&format=json"
  Use that for wiki numbers (HP, damage, range, reload, super stats, gadgets, star powers, hypercharge).
- brawlify.com and noff.gg return 403 to curl; try them through WebFetch if you have it, else skip.
- Guides (game8, samurai-gamers, pocketgamer, dexerto, bo3, gamerant, ...), YouTube titles/descriptions via search,
  esports / pro commentary. Prefer recent (2025-2026) sources; the game changes with balance patches.
- No game tables (skills.csv etc.) or battle host exist in this container: you cannot confirm numbers in the sim.
  Mark numbers [wiki] and claims [community], [multi-source] (2+ independent sources agree) or [unverified].
- Budget: about 25 web calls. Stop when the sections are filled; do not pad.

## Output: write <OUTFILE> (markdown, 120-220 lines), these sections, in order:
1. **Identity**: name, class, rarity, codename if a source gives it (the sim uses internal names like Sniper, ShotgunGirl,
   BullDude, TntDude, Enrager), attack shape (projectile count, spread, range in tiles, pierce, lob over walls?), speed.
2. **Numbers** (table, each with its source): HP, attack damage, range, reload, super charge per hit if known, super
   range / length, super damage / heal / radius / duration, the gadgets and star powers that change super use or
   ambush, hypercharge effect.
3. **#91 super_role**: role(s), with a one-line why. Then a table: situation | what to do with the super | rule
   condition (in planner terms: tiles, hp %, R, ammo, walls/bush/gas, mode) | tag + source.
   Include the "don't" cases (when pros hold the super) and wall / bush tricks.
4. **#92 bush play**: can_ambush (yes/no/only with super), trigger distance in tiles, lurk vs whom, who it dives, who it
   must avoid up close, bush tricks, reveal-on-attack facts. Table with tags + sources.
5. **Mode differences**: Showdown vs 3v3, short.
6. **Proposed rule sketch**: 3-6 bullet rules in the style of the planner docstring (conditions -> action, a reason
   string like "hp 25 %, ShotgunGirl 3 tiles E: jumping W to the bush"). Say which existing rule each would sit near.
7. **Conflicts and gaps**: where sources disagree, what you could not find, what needs a sim / game-table check.
8. **Sources**: numbered list, URL + one line on what it gave + its date if known. Mark sources you could not open.
9. **Research log** (5-10 lines): which sites worked / failed, how many calls, what you would do differently at scale.
