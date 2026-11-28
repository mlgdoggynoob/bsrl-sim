# Brawler research -> planner profile -> training (#91 / #92)

How a brawler goes from "class default" to its own planner profile. The status of every playable brawler is in
[CHECKLIST.md](CHECKLIST.md) (generated: `python -m roles --checklist`). The pilot (one brawler per class) is in
[README.md](README.md).

## What a profile is
`roles.profile(codename)`: roles (finisher / engage_dash / escape_dash / heal / ...), ambush + trigger distance, lurk.
Unresearched brawlers get their class default (roles.py module doc: from the game's ClassArchetype and the super's
BehaviorType). The planner's role rules (`--plan-roles 1`) read it: super_escape, lurk, ambush, super_engage, and the
finisher gate on rule 4.

## Steps per brawler (tick the CHECKLIST columns as you go)
1. **Pick.** Brawlers that are in, or about to join, the training pool first; then one per class, then the rest of each
   class. Batch 6-8 per round.
2. **Research** (`researched`). One subagent per brawler: Sonnet 5.5, **high** effort (pilot: about 15 % more tokens than
   medium for twice the sources and a real conflicts section). Prompt = [BRIEF.md](BRIEF.md) + the codename + its facts:
   `python -c "import roles; print(roles.facts('Sniper'))"`. Output `notes/super_research/<name>.md`.
   - Reddit blocks cloud IPs (its own 403): search snippets only, no mirrors. Fandom: the `api.php` wikitext route.
   - Do not research the bush-reveal duration per brawler: no source has it; it is a sim measurement (#92).
3. **Review the file.** Codename right; every number tagged; mirror / unopened sources marked; claims the brief asked
   for are there (super role table, ambush / lurk table, rule sketch).
4. **Check the numbers** (`checked`). Compare range, super range, super damage / heal with the game tables
   (`roles.facts`, skills.csv); the tables win every conflict. Add an assert for the numbers a rule uses to
   `roles._check`.
5. **Profile.** Add the brawler to `roles.BRAWLERS` (only the fields that differ from its class default, with `file` and
   a one-line `why`) and to `roles.STATUS`. If the research shows a play none of the role rules covers (a heal, a
   shield, a zone), note it under "Rules still to write" below instead of bending a rule.
6. **Scene** (`scene`). A synthetic planner self-check scene for the brawler's key play in `planner._check` (e.g.
   "Piper vs Edgar lurks"). `python -m planner && python -m roles && python -m roles --checklist`.
7. **Train** (`trained`). A run with the brawler in the pool and `--plan-roles 1`; record the run in `roles.STATUS`.

## Measuring a run
- `python scorecard.py <run>`: the rule census and follow rate per rule (super_escape, lurk, ambush, super_engage show
  up by name), `evalp_plan` vs `eval` on the same seeds.
- Intent ends per kind: a super escape that lands is `super` achieved; a lurk / ambush wait broken by a shot is `hide`
  invalid.
- `policy_video --overlay 1` (or `--play-plan`) to watch the picks with their reasons.

## r53 (Piper fine-tune with the role rules)
r52's command plus `--plan-roles 1` (needs `--intent-scale > 0` and `--p-plan > 0` or `--eval-plan 1`, as r52 has).
For Piper the role rules that fire are super_escape (her jump away from divers), lurk (hold fire in a bush vs divers),
the finisher gate (she has no attack super: no change) and keep_away measuring a dash's reach. Ambush and super_engage
need close-range brawlers in the pool.

## Rules still to write
- heal_team / heal_self (Poco): a teammate below X % in the heal cone; needs a "mate HP rose" achieved test.
- stealth (Sandy): cloak to cross open ground or hold a choke; the cloak shows within 4 tiles.
- zone (Dynamike): barrel at a choke / a cornered or gas-pinned enemy (today: rule 4 as a finisher).
- The #92 duel check from skills.csv DPS (today the ambush gate is the strength ratio R with a first-strike margin).
- The bush-reveal duration after a shot, measured in the sim (`w["sees"]`, `hid_vs`).
