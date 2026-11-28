"""Super roles and bush play per brawler (#91 / #92): what the rule planner's role rules read (planner.RulePlanner(roles=
True), trainer --plan-roles 1). Every playable brawler gets a profile: its class default (the game's ClassArchetype and
the super's BehaviorType), overridden field by field for the brawlers researched in notes/super_research/.

    python -m roles               # self-check (needs the game files: characters.csv / skills.csv)
    python -m roles --checklist   # writes notes/super_research/CHECKLIST.md (the per-brawler status table)

    pf = profile("Sniper")        # {cls, roles, ambush, trigger, lurk, src, ...}

Profile fields:
  cls      characters.csv ClassArchetype: damage_dealer, tank, assassin, support, controller, marksman, artillery
  roles    of ROLES; the rules use finisher (super at a low enemy: planner rule super), engage_dash (super_engage, and the
           ambush spring with the super ready), escape_dash (super_escape; holds the super for it). The others are
           recorded for the brawler rules below (heal_self: super_finish heals; heal_team, shield, zone, summon, stealth,
           utility: description only, the plays sit in `rules`).
  ambush   True: from a bush, wait quietly for an enemy it out-duels and spring at `trigger` tiles (engage), or at its
           super range with an engage_dash super ready (super)
  trigger  tiles: the ambush spring distance without the super (shotgun: the full-damage range; melee: reach + 1 tile)
  lurk     True: hidden in a bush, hold fire while a diver / short-range enemy that wins up close is in view (> 3 tiles)
  rules    brawler-specific planner rules this brawler runs (planner.RULES names, plus the guards planner.GUARDS that
           change a shared rule; the class default switches some on from the game tables, research adds the others;
           planner module doc "Brawler rules"):
             dash_escape     a main attack that dashes (skills.csv weapon BehaviorType Charge: Mortis, Mico, Kaze, Alli,
                             Samurai): dash away at low hp / from a much stronger enemy
             snipe_band      damage that grows with distance: hold `band` tiles from the target (Piper), also stepping
                             back from an even enemy that walks within 6 tiles
             point_blank     a shotgun super: fire it within `trigger` tiles (the full-damage range), as a knockback at
                             low hp; rule 4 (super) beyond that only on a finish (Shelly)
             charge_cover    hold a charge super in the open vs an enemy that out-ranges me: bush / wall cover (Bull)
             avoid_brawl     stay away from a close fighter (shotgun / tank) at about even strength (Edgar, Mortis)
             dive_ranged     jump super onto a ranged enemy I nearly match (R < 0.9) at hp >= 60 % (Edgar)
             heal_mate       heal super on a hurt mate in its range, through walls (Poco)
             heal_panic      heal super on myself at low hp with an enemy close and no bush to hide in (Poco)
             cloak_escape    cloak super behind me at low hp with no enemy within its 4-tile reveal distance (Sandy)
             cloak_engage    cloak super ahead of the team toward an enemy we engage (Sandy, team modes)
             cloak_endgame   cloak super on the endgame hold tile (Sandy)
             barrel_zone     area super at a pinned enemy: a second enemy next to it, the gas behind it, or a walled
                             pocket, at any hp (Dynamike)
             super_finish    attack super where `sdmg` kills (absolute hp, known stats), or as a heal at < 50 % hp;
                             replaces rule 4 for the brawler (Mortis)
             finish_jump     a dash attack (`admg`) that kills an enemy within one dash (Mico)
             no_dive_grouped (guard) no ambush / super dive onto a full-hp enemy with another enemy within 4 tiles (Mico)
  band     (lo, hi) tiles for snipe_band, else None
  lane     dash_escape: prefer a straight lane for the first dash (a wall cuts the dash short: Mortis), default False
  sreach   tiles the planner takes as the super's reach when the table's super range does not say it (Mico's steered
           flight: CastingRange 0), else 0 (= the observation's super range)
  sdmg     the super's skills.csv Damage (a heal amount for Poco), admg the main attack's Damage when it dashes (else 0);
           the planner scales both by its POWER as it does hit points
  src      "class default" or the research note the override came from
Class defaults (from the research pilot, applied to the brawlers not researched yet):
  roles    super BehaviorType Attack -> finisher; Charge -> escape_dash for the squishy classes (marksman, artillery,
           support, controller), engage_dash for the others; anything else -> utility
  ambush   tank, assassin, and a short-range damage dealer (<= 5.5 tiles); the rest lurk instead
  trigger  a range <= 2.5 tiles (punch / swing): range + 1 tile; else half the range, clipped to 2.5-3.5 tiles (a
           shotgun's full-damage part, #92)
Status columns of the checklist (STATUS per brawler, the rest is computed): researched (a notes/super_research file),
checked (its numbers compared with the game tables: range, super range, super damage / heal), scene (a planner
self-check scene), trained (runs that had it in the pool).
"""
import functools, os, sys
import numpy as np

ROLES = ("finisher", "engage_dash", "escape_dash", "heal_team", "heal_self", "shield", "zone", "summon", "stealth", "utility")
CLASSES = ("damage_dealer", "tank", "assassin", "support", "controller", "marksman", "artillery")
SQUISHY = ("marksman", "artillery", "support", "controller")   # a dash / jump super on these is an escape
SHORT = 5.5               # tiles: short range (planner keep_away's line; Bull 5.3)
NOTE = "notes/super_research/"

# researched brawlers (notes/super_research/<file>): overrides of the class default. Numbers checked against the game
# tables on 2026-11-28 (range, super range, super damage: skills.csv CastingRange / 3 = tiles)
BRAWLERS = {
    "Sniper": dict(roles=("escape_dash", "utility"), ambush=False, lurk=True, rules=("snipe_band",), band=(8.5, 10.0),
                   file="piper.md",   # band: full damage in the last 15 % of her 10-tile range (piper.md, wiki)
                   why="Poppin' (8.67 tiles, ~2 s immune in the air) is her escape from divers; up close she does 20 %"),
    "ShotgunGirl": dict(roles=("finisher", "utility"), ambush=True, trigger=3.0, lurk=False, rules=("point_blank",), file="shelly.md",
                        why="bush ambush at ~3 tiles (full shotgun damage); Super Shell 7.67 tiles finishes and breaks walls"),
    "BullDude": dict(roles=("engage_dash", "escape_dash", "utility"), ambush=True, trigger=3.0, lurk=False, rules=("charge_cover",),
                     file="bull.md",
                     why="charge 11 tiles through walls engages (escape second); shells full damage ~3 tiles"),
    "Enrager": dict(roles=("engage_dash", "escape_dash"), ambush=True, trigger=3.0, lurk=False, rules=("avoid_brawl", "dive_ranged"),
                    file="edgar.md",
                    why="Vault 6.67 tiles over walls onto a low or squishy target; punch reach 2 tiles"),
    "DeadMariachi": dict(roles=("heal_team", "heal_self"), ambush=False, lurk=True, rules=("heal_mate", "heal_panic"), file="poco.md",
                         why="Encore heals himself and allies (2100, 9.33 tiles, through walls), no damage: not a finisher"),
    "Sandstorm": dict(roles=("stealth", "utility"), ambush=False, lurk=True, rules=("cloak_escape", "cloak_engage", "cloak_endgame"),
                      file="sandy.md",
                      why="Sandstorm cloaks (r 6.67 tiles, 9 s; seen within 4 tiles), no damage: not a finisher"),
    "Undertaker": dict(roles=("finisher", "heal_self"), ambush=True, trigger=3.0, lurk=False, lane=True,
                       rules=("super_finish", "avoid_brawl"), file="mortis.md",
                       why="the dash (2.67 tiles) is his MAIN attack: escape / engage with it (dash_escape); a wall cuts it short;"
                           " the bats super finishes and heals him"),
    "Leaper": dict(roles=("engage_dash", "escape_dash"), ambush=True, trigger=3.5, lurk=False, sreach=10.0,
                   rules=("finish_jump", "no_dive_grouped"), file="mico.md",
                   why="main attack = a 4-tile jump over walls, untouchable in the air; super = 1 s windup, then up to 6 s"
                       " of steered invulnerable flight (table range 0: sreach)"),
    "TntDude": dict(roles=("zone", "finisher"), ambush=False, lurk=True, rules=("barrel_zone",), file="dynamike.md",
                    why="barrel lobs over walls (1.3 s fuse): zone / finish; no dash, so he lurks vs divers"),
}
STATUS = {   # checklist columns that are not computed: checked (numbers vs game tables), scene (planner self-check), trained
    "Sniper": dict(checked=True, scene=True, trained="r51, r52"),
    "ShotgunGirl": dict(checked=True, scene=True),
    "BullDude": dict(checked=True, scene=True),
    "Enrager": dict(checked=True, scene=True),
    "DeadMariachi": dict(checked=True, scene=True),
    "Sandstorm": dict(checked=True, scene=False),
    "TntDude": dict(checked=True, scene=True),
    "Undertaker": dict(checked=True, scene=True),
    "Leaper": dict(checked=True, scene=True),
}


@functools.lru_cache(None)
def _rows():
    from nbpc import diversity as D
    import obs_v5 as O
    return D.table("characters.csv"), O._tables()[0]


def facts(name):
    """game-table facts of a brawler: cls, display name, super BehaviorType, range / super range (tiles), melee"""
    ch, sk = _rows(); c = ch[name][1]
    w, u = sk.get(c.get("WeaponSkill"), {}), sk.get(c.get("UltimateSkill"), {})
    import obs_v5 as O
    st = O.brawler_stats(name)
    return dict(cls=c.get("ClassArchetype") or "damage_dealer", display=(c.get("ItemName") or name).replace("_", " ").title(),
                beh=u.get("BehaviorType") or "", range=float(w.get("CastingRange") or 0) / 3.0,
                srange=float(u.get("CastingRange") or 0) / 3.0, melee=bool(st[7] > 0.5),
                adash=float(w.get("CastingRange") or 0) / 3.0 if w.get("BehaviorType") == "Charge" else 0.0,   # attack dash, tiles
                sdmg=float(u.get("Damage") or 0),
                admg=float(w.get("Damage") or 0) if w.get("BehaviorType") == "Charge" else 0.0)


def default(f):
    """the class default profile of facts f (module doc)"""
    cls, beh = f["cls"], f["beh"]
    roles = ("finisher",) if beh == "Attack" else (("escape_dash",) if cls in SQUISHY else ("engage_dash",)) if beh == "Charge" else ("utility",)
    ambush = cls in ("tank", "assassin") or (cls == "damage_dealer" and f["range"] <= SHORT)
    reach = f["range"] <= 2.5                     # a punch / swing (Edgar 2 tiles): its reach + 1 tile
    trigger = (f["range"] + 1.0 if reach else float(np.clip(0.5 * f["range"], 2.5, 3.5))) if ambush else 0.0
    rules = ("dash_escape",) if f.get("adash", 0.0) > 0 else ()
    return dict(cls=cls, roles=roles, ambush=ambush, trigger=trigger, lurk=not ambush, rules=rules, band=None, lane=False,
                sreach=0.0, src="class default")


@functools.lru_cache(None)
def profile(name):
    """the planner profile of a brawler (module doc): the class default with the research overrides on top"""
    f = facts(name); p = default(f); o = BRAWLERS.get(name)
    if o:
        p.update({k: v for k, v in o.items() if k in ("roles", "ambush", "trigger", "lurk", "band", "lane", "sreach")})
        p["rules"] = tuple(dict.fromkeys(p["rules"] + tuple(o.get("rules", ()))))   # table-derived + researched
        if not p["ambush"]: p["trigger"] = 0.0
        p["src"] = NOTE + o["file"]
    p["roles"] = tuple(p["roles"]); p["adash"], p["sdmg"], p["admg"] = f["adash"], f["sdmg"], f["admg"]
    return p


def checklist(names):
    """the markdown status table of the brawlers `names` (module doc)"""
    yes = lambda b: "x" if b else " "
    out = ["# Brawler research checklist (#91 / #92)", "",
           "Generated by `python -m roles --checklist` from roles.py (BRAWLERS, STATUS) and the game tables: edit those, not",
           "this file. Workflow: notes/super_research/WORKFLOW.md. Class default = the profile the planner uses until the",
           "brawler is researched (roles.py module doc).", ""]
    done = [n for n in names if n in BRAWLERS]
    out += ["Researched %d / %d playable brawlers; per class:" % (len(done), len(names)), ""]
    out += ["| class | brawlers | researched |", "|---|---|---|"]
    for c in CLASSES:
        ns = [n for n in names if facts(n)["cls"] == c]
        out.append("| %s | %d | %s |" % (c, len(ns), ", ".join(facts(n)["display"] for n in ns if n in BRAWLERS) or "-"))
    out += ["", "| brawler | codename | class | super | roles | ambush / lurk | own rules | researched | checked | scene | trained |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in CLASSES:
        for n in sorted((n for n in names if facts(n)["cls"] == c), key=lambda n: (n not in BRAWLERS, facts(n)["display"])):
            f, p, st = facts(n), profile(n), STATUS.get(n, {})
            bush = ("ambush %.1f" % p["trigger"]) if p["ambush"] else "lurk" if p["lurk"] else "-"
            res = "[%s](%s)" % (BRAWLERS[n]["file"], BRAWLERS[n]["file"]) if n in BRAWLERS else "[ ] class default"
            out.append("| %s | %s | %s | %s %.1f | %s | %s | %s | %s | [%s] | [%s] | %s |" % (
                f["display"], n, c, f["beh"] or "-", f["srange"], ", ".join(p["roles"]), bush, ", ".join(p["rules"]) or "-", res, yes(st.get("checked")),
                yes(st.get("scene")), st.get("trained", "")))
    return "\n".join(out) + "\n"


def _check():
    import env_v5 as E
    names = E.heroes()
    assert set(BRAWLERS) <= set(names) and set(STATUS) <= set(BRAWLERS), set(BRAWLERS) - set(names)
    for n in names:
        p = profile(n); assert p["cls"] in CLASSES and p["roles"] and set(p["roles"]) <= set(ROLES), (n, p)
        assert not (p["ambush"] and p["lurk"]) and (p["trigger"] > 0) == p["ambush"], (n, p)
    # the research numbers the rules lean on match the game tables (notes/super_research, "checked")
    f = {n: facts(n) for n in BRAWLERS}
    assert [f[n]["cls"] for n in ("Sniper", "ShotgunGirl", "BullDude", "Enrager", "DeadMariachi", "Sandstorm", "TntDude")] == [
        "marksman", "damage_dealer", "tank", "assassin", "support", "controller", "artillery"]   # one per class
    assert np.isclose(f["Sniper"]["range"], 10) and np.isclose(f["Sniper"]["srange"], 26 / 3) and f["Sniper"]["beh"] == "Charge"
    assert np.isclose(f["BullDude"]["srange"], 11) and np.isclose(f["Enrager"]["srange"], 20 / 3) and f["Enrager"]["range"] == 2.0
    assert f["DeadMariachi"]["beh"] == f["Sandstorm"]["beh"] == "Attack"   # BehaviorType alone would call these finishers
    assert "finisher" not in profile("DeadMariachi")["roles"] and "finisher" not in profile("Sandstorm")["roles"]
    # class defaults: Charge on a squishy class = escape, on a diver = engage; Attack = finisher
    assert default(dict(cls="marksman", beh="Charge", range=10, srange=8, melee=False))["roles"] == ("escape_dash",)
    assert default(dict(cls="assassin", beh="Charge", range=2, srange=7, melee=False)) == dict(
        cls="assassin", roles=("engage_dash",), ambush=True, trigger=3.0, lurk=False, rules=(), band=None, lane=False, sreach=0.0,
        src="class default")
    dashers = sorted(n for n in names if facts(n)["adash"] > 0)        # attack dashes in the tables -> dash_escape
    assert dashers == ["Geisha", "Leaper", "Samurai", "Stalker", "Undertaker"] and all("dash_escape" in profile(n)["rules"] for n in dashers), dashers
    # Mortis / Mico (mortis.md, mico.md): the dash is the main attack; Mico's super has no table range (steered flight)
    _, sk = _rows(); ch = _rows()[0]; skl = lambda n, s: sk[ch[n][1][s]]
    assert np.isclose(f["Undertaker"]["adash"], 8 / 3) and f["Undertaker"]["beh"] == "Attack" and np.isclose(f["Undertaker"]["srange"], 10)
    assert skl("Undertaker", "UltimateSkill")["Damage"] == "900" and ch["Undertaker"][1]["Hitpoints"] == "4000"
    assert np.isclose(f["Leaper"]["adash"], 4) and f["Leaper"]["beh"] == "FlyJump" and f["Leaper"]["srange"] == 0
    assert skl("Leaper", "UltimateSkill")["ActiveTime"] == "6000" and skl("Leaper", "UltimateSkill")["CastingTime"] == "1000"
    assert profile("Leaper")["sreach"] == 10.0 and profile("Undertaker")["lane"] and profile("Undertaker")["trigger"] == 3.0
    assert profile("Sniper")["rules"] == ("snipe_band",) and profile("Sniper")["band"] == (8.5, 10.0)
    # brawler rules: every name is a planner rule or guard, every researched brawler has its own; table numbers they use
    import planner as PL
    import obs_v5 as O
    assert CLASSES == O.CLASSES and all(np.array_equal(O.brawler_class(n), np.eye(len(CLASSES))[CLASSES.index(facts(n)["cls"])]) for n in names)
    for n in names: assert set(profile(n)["rules"]) <= set(PL.RULES) | set(PL.GUARDS), (n, profile(n)["rules"])
    assert all(len(profile(n)["rules"]) for n in BRAWLERS), [n for n in BRAWLERS if not profile(n)["rules"]]
    assert profile("Undertaker")["rules"] == ("dash_escape", "super_finish", "avoid_brawl") and profile("Leaper")["rules"][0] == "dash_escape"
    assert profile("Undertaker")["sdmg"] == 900 and profile("Undertaker")["admg"] == 1000 and profile("Leaper")["admg"] == 1140
    assert profile("DeadMariachi")["sdmg"] == 2100 and profile("TntDude")["sdmg"] == 2200 and profile("Sniper")["admg"] == 0
    assert default(dict(cls="damage_dealer", beh="Attack", range=9, srange=9, melee=False))["lurk"]        # a long-range DD lurks
    assert not default(dict(cls="damage_dealer", beh="Attack", range=7.67, srange=7, melee=False))["ambush"]   # 7.67 > SHORT
    assert np.isclose(default(dict(cls="tank", beh="Attack", range=5.33, srange=5, melee=False))["trigger"], 2.665)
    assert profile("Sniper")["src"] == NOTE + "piper.md" and not profile("Sniper")["ambush"] and profile("Sniper")["lurk"]
    assert profile("ShotgunGirl")["ambush"] and profile("ShotgunGirl")["trigger"] == 3.0 and not profile("TntDude")["ambush"]
    md = checklist(names); assert md.count("\n| ") == len(CLASSES) + 1 + len(names) + 1, md.count("\n| ")
    n_def = sum(profile(n)["src"] == "class default" for n in names)
    print("roles ok: %d playable brawlers, %d researched, %d on class defaults" % (len(names), len(BRAWLERS), n_def))


if __name__ == "__main__":
    if "--checklist" in sys.argv:
        import env_v5 as E
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), NOTE, "CHECKLIST.md")
        with open(p, "w") as fh: fh.write(checklist(E.heroes()))
        print("wrote", p)
    else:
        sys.exit(_check())
