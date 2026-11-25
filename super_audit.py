"""Super audit: which brawlers' supers work on this host (a client build of the game: server-only code is bare `ret` stubs,
some of it re-implemented in nirkt's env.c / spawnfix.c). Output is a per-brawler checklist for a GitHub tracking issue.

    python -m super_audit [--n 2] [--only BullDude,Sniper]     # live: boots --n hosts (60-90 s each)
    python -m super_audit --check                              # classification self-check, no host
    python -m super_audit --hyper --only Jester,Twins          # the hypercharged supers (hypercharge first, host hyper.c)

Setup (one battle per 10 brawlers, map MAP = the most open Showdown map, storm off, every player's native AI off):
players 0-4 shoot in phase A, players 5-9 in phase B; in each phase every shooter stands on its own clear spot (a 3-tile
wide corridor of open tiles in at least two directions, spots >= SPACING apart; A and B use different spots) with one
enemy target at distance d along a corridor. Per phase: teleport + heal everyone and end spawn protection; the target fires
one normal attack at the shooter (so a self-heal is visible); fill the shooters' supers; fire the super (fire 2, aim at the
target, super_dist = d / CastingRange, a charge aims ~1 tile past the target); watch WATCH ticks. A super the player steers
while it runs (FlyJump, Ww) has its shooter walk towards the target once its CastingTime is over (moves sent while it
casts are dropped), so its "move" is plain walking.
A ProjectileShield super (Buster) has its target SHIELD_D away, past the shield line, shooting into it at the first
step POST_HIT_SHIELD ticks or more after the fire; a type-16 charge (Bonnie, who hits where she lands) is aimed at the target, not past it.
Measured per shooter (state2 dump each step, attributed by owner player index): super consumed (charge < half of max),
damage = target HP lost (or the shooter's NbeResp damage_dealt summed over the watch steps: the host reports it per step), own max displacement (dash / jump / charge; host `leaping` flag), target max
displacement (pushback / pull), own HP gain (only when the pre-damage hit), new projectiles / summons / area effects
(name, table radius) / other items owned by the shooter, a change of the brawler's character (transform), the skill's
"active" word (state2 ultiActive, informational), foreign summons near the pair (contamination from phase A).
Expected effects come from the game's tables (skills.csv UltimateSkill row, its projectiles_logic / projectiles_skin
rows, area_effects_logic): damage, move, push, heal, projectile, summon, area, item, change (`expected()`).
An EdgeCrossing area's PushbackStrength (Damian's arena) is not expected as a push: it pushes only at the arena's edge.
Meg's row is her mech's super (START_FORM: the client spawns her as MechaDudeBig); the eject and small Meg's change back
are charge_check's. R-T's split (Split) shows only its SplitterLegs summon here (unverified); his faster walk, the attack
from head and legs and the rejoin are charge_check's.
Classes (`classify()`): works = consumed and every expected effect seen; partial = consumed, some effect seen but not all
expected (listed as missing); unverified = consumed, but the super's effect is of a kind not visible here (shield,
invisibility, status buff, a heal when the pre-damage missed); no_effect = consumed, nothing seen; not_fired = charge not
consumed (or the brawler was not spawned); crash = the host died with this brawler as the only shooter.
Not detectable: stuns / slows / silences, shields, damage boosts, invisibility, wall breaking, effects that start after
WATCH ticks, effects on allies (every player is solo), how close a re-implementation is to the real game.
Every non-works brawler is retried once (other corridor direction, d from a smaller fraction of its range); the best
attempt counts. A host crash requeues that phase's shooters one at a time (a reboot each) to find the brawler.
Output: $SIM_WORK/super_audit.json (per brawler: name, super, type, class, attempts with measurements) and
$SIM_WORK/super_audit.md (also stdout): a checklist grouped by class then super type. The default list is env_v5.heroes()
(the playable brawlers) then env_v5.forms() (the other forms and event transforms, spawned directly as shooters). With --only the brawlers are
merged into an existing super_audit.json.
--hyper (hypercharge round): every player gets its hypercharge card; each shooter's hypercharge is filled with its super and
activated (fire 4) one tick before the super. The expected effects are the hypercharged super's (`hyper_skill`: characters.csv
OverchargedUltimateSkill, else the UltimateSkill's OverchargedVersion, with the row's Overcharged* columns), plus hyper_cast
(the host reports a super cast while hypercharged, NbeResp hyp_supers / hyp_super_id, with the OverchargedUltimateSkill's data
where there is one) and hyper (a projectile / summon / area / item only the hypercharged super has, when it has one).
Output: super_audit_hyper.json / .md.
--gadget (gadget round, issue #3): the brawlers with a gadget the host implements and this audit can see (`audit_gadgets`,
`gadget_kind` mirrors nbhost gadget.c's classify functions: area at the brawler, the gadget's own skill shot or area, items,
instant heals; R-T's super charge is gadget_check's; repeat_shot / spin_shoot volleys are off, issue #54). Each shooter gets
that gadget card and fires it (fire 3, aimed at the target) in place of the super; consumed = the host counted a use
(NbeResp gad_used). Expected effects come from the tables (`expected_gadget`). --gadget-slot 1 audits each brawler's second
such gadget. Output: super_audit_gadget.json / .md (slot 1: super_audit_gadget_2.*)."""
import argparse, collections, functools, json, os, sys, threading, time
import numpy as np

NIL = -2147483648
MAP = "Survival651"                      # the most open Showdown map (88 % open tiles; others give < 6 clear spots)
TILE = 300
CORR = 8                                 # corridor length in tiles from the shooter's tile: targets up to 7 tiles (2100 u)
SPACING = 13                             # tiles between spot centres (3900 u: a long super past its target stays clear)
WATCH = 50                               # ticks watched after the fire (2.5 s at 20 ticks/s; regen starts 3 s after a hit)
STEP = 2                                 # ticks per env step while watching
POST_HIT = 0                             # --post-hit: tick after the fire at which the target shoots the shooter again (0 off)
POST_HIT_SHIELD = 8                      # ProjectileShield (Buster): the target shoots into the shield at the first step >= this tick
SHIELD_D = 1500.0                        # ProjectileShield: target distance, past the shield line (CastingRange 9 -> 900 u in front)
DIST_F = (0.6, 0.35)                     # target distance per attempt, as a fraction of the super's CastingRange
DIST_MIN, DIST_MAX = 450, (CORR - 1) * TILE
MOVE_MIN, PUSH_MIN, HEAL_MIN = 300, 100, 100   # units / units / HP: above walk jitter, setup rounding and regen ticks
FILLER = "ShotgunGirl"                   # target-only slot filler when a battle has fewer than 10 brawlers to audit
# brawlers the client spawns in another form (the spawner 0xc2806c swaps in the pet form): Meg starts in her mech, so the
# super she casts is the mech's; small Meg's ChangeCharacter (after the mech breaks) is charge_check's "Meg eject" scene
START_FORM = {"MechaDude": "MechaDudeBig"}
CLASSES = ("works", "partial", "unverified", "no_effect", "not_fired", "crash")   # best first
P2, C2, J2, I2, HDR = 8, 23, 18, 12, 8   # state2 row sizes (engine/py/state2.py)
BOX_IDS = {16000120}


# ------------------------------------------------------------------ game tables
@functools.lru_cache(None)
def _tables():
    from nbpc import diversity as D
    named = lambda f: {r[next(iter(r))]: r for r in D._rows(f) if r[next(iter(r))]}
    rows = lambda f: [r for r in D._rows(f) if r[next(iter(r))]]
    return {"char": named("characters.csv"), "skill": named("skills.csv"), "plog": named("projectiles_logic.csv"),
            "pskin": named("projectiles_skin.csv"), "alog": named("area_effects_logic.csv"), "askin": named("area_effects_skin.csv"),
            "item": named("items.csv"), "rows": {6: rows("projectiles_skin.csv"), 16: rows("characters.csv"), 17: rows("area_effects_skin.csv"), 18: rows("items.csv")},
            "skill_rows": rows("skills.csv")}


def skill_name(did):
    """a SkillData's global data id (NbeResp.hyp_super_id) -> skills.csv row name"""
    r = _tables()["skill_rows"]; i = int(did) % 1000000
    return r[i][next(iter(r[i]))] if did and 0 <= i < len(r) else str(did)


# hypercharged super (--hyper): the skills.csv columns the game's own code reads while isOvercharged (host hyper.c)
OC_COLS = (("Projectiles", "OverchargedProjectiles"), ("AreaEffectObject", "OverchargedAreaEffectObject"),
           ("AreaEffectObject2", "OverchargedAreaEffectObject2"), ("SummonedCharacters", "OverchargedSummonedCharacters"),
           ("SpawnedItem", "OverchargedSpawnedItem"))


def hyper_skill(name):
    """the super a hypercharged brawler casts: (skills.csv row name, row): its OverchargedUltimateSkill (characters.csv; 7
    brawlers) or its UltimateSkill, then that row's OverchargedVersion if it has one, with its Overcharged* columns in
    place of the normal ones"""
    T = _tables(); ch = T["char"][name]; n = ch.get("OverchargedUltimateSkill") or ch.get("UltimateSkill", "")
    s = T["skill"].get(n, {})
    if s.get("OverchargedVersion") in T["skill"]: n = s["OverchargedVersion"]; s = T["skill"][n]
    s = dict(s)
    for k, ko in OC_COLS:
        if s.get(ko): s[k] = s[ko]
    return n, s


def data_name(did):
    """global data id (6 projectiles_skin, 16 characters, 17 area_effects_skin, 18 items) -> row name"""
    t, i = divmod(int(did), 1000000); r = _tables()["rows"].get(t)
    if not r or not 0 <= i < len(r): return str(did)
    return r[i][next(iter(r[i]))]


@functools.lru_cache(None)
def _texts():
    from nbpc import diversity as D
    import csv
    p = os.path.join(os.path.dirname(D.ASSETS.rstrip("/")), "assets", "localization", "texts.csv")
    try:
        return {r[0]: r[1] for r in csv.reader(open(p, encoding="utf-8")) if len(r) > 1}
    except OSError:
        return {}


def display(name):
    t = _texts().get(_tables()["char"].get(name, {}).get("TID", ""), "")
    return t.title() if t else name


def area_radius(did):
    """area_effects_skin data id -> table radius (units; obs_v5's lookup)"""
    import obs_v5 as O
    lut, na = O._area_lut(); i = int(did) - 16999999
    return int(round(float(lut[i, 0]) * 3000)) if 0 < i < na else 0


def _num(r, k):
    try: return float((r.get(k) or "0").split(";")[0] or 0)
    except ValueError: return 0.0


def expected(name, hyper=False):
    """the brawler's super from the tables -> dict(skill, type (BehaviorType), kind (finer group label), range (units),
    charge (bool), expect (effects that must be seen), notes). A brawler in START_FORM (Meg: the client spawns her in her
    mech) gets its start form's super, with a note. hyper: its hypercharged super (hyper_skill); expect adds
    hyper_cast (the host cast it while hypercharged, with this skill's data where characters.csv names an
    OverchargedUltimateSkill) and hyper (one of the projectiles / summons / areas / items only the hypercharged super has,
    `hyper_names`, when it has any)"""
    if name in START_FORM:
        out = expected(START_FORM[name], hyper)
        out["notes"].append(f"spawns as {START_FORM[name]}: its super is audited; the eject and the change back: charge_check")
        return out
    T = _tables(); ch = T["char"][name]; sk_name = ch.get("UltimateSkill", ""); s = T["skill"].get(sk_name, {})
    if hyper:
        base = expected(name); sk_name, s = hyper_skill(name)
    out = expected_skill(sk_name, s); ex, notes = out["expect"], out["notes"]
    if hyper:
        names = lambda i: set(i["projectiles"]) | set(i["summons"]) | set(i["areas"]) | set(i["items"])
        out["hyper_names"] = sorted(names(out) - names(base)); out["own_skill"] = bool(ch.get("OverchargedUltimateSkill"))
        ex.append("hyper_cast")
        if out["hyper_names"]: ex.append("hyper")
        else: notes.append("hypercharged super: no projectile / summon / area / item of its own (its difference is not visible here)")
    return out


def expected_skill(sk_name, s):
    """a skills.csv row (name, row) -> expected()'s dict for that skill (a super's, or a gadget's own skill)"""
    T = _tables(); bt = s.get("BehaviorType") or "?"; ex = []; notes = []
    projs = [p for p in (s.get("Projectiles") or "").split(";") if p]
    pl = [T["plog"].get(T["pskin"].get(p, {}).get("LogicProjectile") or p, {}) for p in projs]
    ps = [T["pskin"].get(p, {}) for p in projs]
    areas = [a for a in (s.get("AreaEffectObject"), s.get("AreaEffectObject2")) if a]
    areas += [a for r in ps for a in (r.get("SpawnAreaEffectObject"), r.get("SpawnAreaEffectObject2")) if a]
    alog = [T["alog"].get(T["askin"].get(a, {}).get("Logic") or a, {}) for a in areas]
    chain = [r.get(k) for r in alog for k in ("ChainAreaEffect", "ChainAreaEffect2", "ChainAreaEffect3") if r.get(k)]
    alog += [T["alog"].get(T["askin"].get(a, {}).get("Logic") or a, {}) for a in chain]   # an area's follow-up area
    summons = [x for x in (s.get("SummonedCharacters") or "").split(";") if x] + [r["SpawnCharacter"] for r in pl if r.get("SpawnCharacter")]
    items = [x for x in [s.get("SpawnedItem")] + [r.get("SpawnItem") for r in ps] if x]
    charge = bt == "Charge"
    if charge or bt in ("Blink", "BlinkReturn", "BlinkToPlaceholder", "BlinkToProjectile", "FlyJump"): ex.append("move")
    turns = bt == "ChangeCharacter" or (charge and bool(s.get("SummonedCharacters")))   # Bonnie / Moe: the charge ends in the other form
    if turns: ex.append("change")
    if projs: ex.append("projectile")
    if turns: summons = []   # SummonedCharacters is the character it turns into, not a summon
    if summons: ex.append("summon")
    if areas: ex.append("area")
    if items: ex.append("item")
    leap_bombs = charge and bool(items)          # Piper: the damage is the bombs left at the start point, not on the target
    heals_only = any(_num(r, "HealOwnPercent") > 0 for r in pl)   # Poco: the skill Damage is the heal, enemies are not hit
    if ((_num(s, "Damage") > 0 or any(_num(r, "Damage") > 0 and r.get("Type") not in NO_DAMAGE_AREAS for r in alog)) and not leap_bombs and not heals_only
            and bt not in ("ChangeCharacter", "ProjectileShield")): ex.append("damage")
    # an EdgeCrossing ring (Damian's arena) pushes only who crosses its edge: the target here stands still inside it
    # (charge_check checks the edge)
    if _num(s, "ChargePushback") > 0 or any(_num(r, "PushbackStrength") > 0 and r.get("Type") != "EdgeCrossing" for r in pl + alog):
        ex.append("push")
    if any(r.get("Type") == "EdgeCrossing" for r in alog): notes.append("EdgeCrossing push: only at the arena edge, checked by charge_check")
    if (_num(s, "HealSelfOnActivationPower") > 0 or any(_num(r, "HealOwnPercent") > 0 for r in pl)
            or any(r.get("Type") in ("Heal", "Hot", "HealRegen", "HealAndDamage", "HotAndDot") for r in alog)): ex.append("heal")
    if bt in ("Shield", "Invisibility", "StatusEffect", "ProjectileShield", "MountUp", "Split", "Ww", "RecallWeapon"):
        notes.append(f"{bt}: its main effect is not visible here")
    kind = (f"Charge {s.get('ChargeType') or '?'}" if charge else
            "Attack: summon" if bt == "Attack" and summons else "Attack: area" if bt == "Attack" and areas and not projs else
            "Attack: item" if bt == "Attack" and items else "Attack: projectile" if bt == "Attack" else bt)
    cr = _num(s, "CastingRange") * 100
    ring = max((( _num(r, "InnerRadius") + _num(r, "Radius")) / 2 for r in alog
                if _num(r, "InnerRadius") > 0 and _num(r, "InnerRadiusDamagePercent") == 0), default=0.0)
    if cr <= 0 and not projs and alog and not charge:   # no aim range, the effect is an area at the brawler: the target stands inside it
        cr = max((_num(r, "Radius") for r in alog), default=0.0)
    # a BulletExplosion area at the brawler (Hank) spreads its children over 360 degrees from world angle 0 (spawnfix.c: no
    # parent projectile): the target stands on angle 0, not between two children
    east = not projs and any(r.get("Type") == "BulletExplosion" for r in alog)
    steer = bt in ("FlyJump", "Ww")   # the brawler moves under its player's control while the super runs: walk it to the target
    out = {"skill": sk_name, "type": bt, "kind": kind, "range": cr if cr > 0 else 2600.0, "charge": charge, "ring": ring, "east": east,
           "steer": steer, "cast": _num(s, "CastingTime"), "expect": ex,
           "post_hit": POST_HIT_SHIELD if bt == "ProjectileShield" else 0,
           "land": charge and s.get("ChargeType") == "16",   # Bonnie: she hits where she lands, aimed at the target (not past it)
           "projectiles": projs, "summons": summons, "areas": areas, "items": items, "notes": notes}
    return out


# area types whose Damage column hits no one: WallSpawn (the walls' HP), StatusEffect (Max's / Sandy's speed boosts),
# ChargeSuper (Max's drink), EnragerOverchargeSuper (Edgar's hypercharged super: a reload / super charge buff for its owner,
# texts TID_ENRAGER_OVERCHARGE_DESC; its effect is compiled out of this libg)
NO_DAMAGE_AREAS = ("WallSpawn", "StatusEffect", "ChargeSuper", "EnragerOverchargeSuper")
HEAL_TYPES = ("Heal", "Hot", "HealRegen", "HealAndDamage", "HotAndDot")


MASKED = {"BowDude_Totem", "Speedy_Rewind", "HammerDude_Pull", "HookDude_Homing", "AssaultShotgun_Bomb", "Ninja_InvisibleArea",
          "Gladiator_Amp", "MagicalGirl_FlyArea"}   # gadget.c g_masked: classified, but no effect in this audit -> not usable
GADGET_KINDS = ("area", "shot", "skill_area", "item", "heal_now", "super")


def gadget_kind(a):
    """accessories.csv row -> the host's gadget.c implementation that handles it (GADGET_KINDS), None = not usable.
    Mirrors gadget.c's classify functions (accessory Type, AreaEffect, the Skill's BehaviorType, CustomObject's table)."""
    T = _tables(); t = a.get("Type") or ""; num = lambda k: _num(a, k)
    if a.get("Name") in MASKED: return None
    obj = (a.get("CustomObject") or "").split(";")[0]
    is_proj = obj in T["pskin"] or obj in T["plog"]
    if (not t or (t == "spin_shoot" and not is_proj)) and a.get("AreaEffect"):   # AREA: the area at the brawler (Fang's sweep too), Rosa's WallSpawn left out
        return "area" if T["alog"].get(a["AreaEffect"], {}).get("Type") != "WallSpawn" else None
    if not t and a.get("Skill"):
        sk = T["skill"].get(a["Skill"], {}); bt = sk.get("BehaviorType") or "Attack"   # an empty BehaviorType parses as Attack
        if bt == "Attack" and sk.get("Projectiles"): return "shot"
        if bt in ("Attack", "AimableArea") and not sk.get("Projectiles") and sk.get("AreaEffectObject"): return "skill_area"
        return None
    if t in ("repeat_shot", "spin_shoot"): return None   # issue #54: gadget.c's REPEAT / SPIN are off (N main attacks at full damage)
    if t == "spawn" and obj in T["item"]: return "item"
    if t in ("heal_attached_and_self", "heal_damage_taken") and num("CustomValue1") > 0: return "heal_now"
    if t == "charge_ulti" and num("CustomValue1") > 0: return "super"
    return None


@functools.lru_cache(None)
def all_gadgets():
    """brawler -> [(cards.csv data id, accessories.csv row name, gadget_kind or None)] of its enabled gadget cards, in card
    order. Card ids count the named cards.csv rows, as env_v5.gadget_cards."""
    from nbpc import diversity as D
    acc = {r["Name"]: r for r in D._rows("accessories.csv") if r.get("Name")}
    out, k = {}, 0
    for r in D._rows("cards.csv"):
        if not r[next(iter(r))]: continue
        a = acc.get(r.get("Skill") or "")
        if r.get("MetaType") == "5" and r.get("Target") and (r.get("Disabled") or "").lower() != "true":
            out.setdefault(r["Target"], []).append((23 * 1000000 + k, a["Name"] if a else r.get("Skill"), gadget_kind(a) if a else None))
        k += 1
    return out


AUDIT_KINDS = ("area", "shot", "skill_area", "item", "heal_now")   # "super" (R-T): gadget_check checks it


@functools.lru_cache(None)
def audit_gadgets(slot=0):
    """--gadget: brawler -> (card, accessories.csv row name, kind) of its slot-th gadget (0 = first) that the host implements
    with an effect this audit can see (AUDIT_KINDS)"""
    out = {}
    for b, gs in all_gadgets().items():
        ok = [g for g in gs if g[2] in AUDIT_KINDS]
        if slot < len(ok): out[b] = ok[slot]
    return out


def area_gadgets():
    """brawler -> (card, row name) of its first AREA gadget (gadget.c AREA)"""
    return {b: next((c, n) for c, n, k in gs if k == "area") for b, gs in all_gadgets().items() if any(k == "area" for _, _, k in gs)}


def expected_gadget(name, slot=0):
    """--gadget: the brawler's audit_gadgets(slot) gadget -> the same dict as expected(). area: area always; damage, push,
    heal from the area's area_effects_logic row, range = its radius (the target stands inside it). shot / skill_area: the
    gadget's own skill as expected_skill() reads a super. item: an item. heal_now: a heal (the target hits the shooter
    first)."""
    from nbpc import diversity as D
    T = _tables(); card, acc, kind = audit_gadgets(slot)[name]
    a = {r["Name"]: r for r in D._rows("accessories.csv") if r.get("Name")}[acc]
    base = {"skill": acc, "type": "Gadget", "charge": False, "ring": 0.0, "east": False, "steer": False, "cast": 0.0, "card": card,
            "delay": _num(a, "ActivationDelay"), "projectiles": [], "summons": [], "areas": [], "items": [], "notes": [], "gadget_kind": kind}
    if kind == "area":
        area = a["AreaEffect"]; al = T["alog"].get(T["askin"].get(area, {}).get("Logic") or area, {})
        ex = ["area"]
        if _num(al, "Damage") > 0 and al.get("Type") == "Damage": ex.append("damage")
        if _num(al, "PushbackStrength") > 0: ex.append("push")
        if al.get("Type") in HEAL_TYPES: ex.append("heal")
        if al.get("Type") in ("StatusEffect", "Cleanse", "HpBasedStun"): base["notes"].append(f"{al['Type']}: its main effect is not visible here")
        return {**base, "kind": "Gadget: area " + (al.get("Type") or "?"), "range": _num(al, "Radius") or 1000.0, "expect": ex, "areas": [area]}
    if kind in ("shot", "skill_area"):
        e = expected_skill(a["Skill"], T["skill"].get(a["Skill"], {}))
        return {**e, "skill": acc, "type": "Gadget", "kind": "Gadget: " + kind, "card": card, "delay": 0.0, "gadget_kind": kind}
    if kind == "item":
        return {**base, "kind": "Gadget: item", "range": 600.0, "expect": ["item"], "items": [a["CustomObject"].split(";")[0]]}
    return {**base, "kind": "Gadget: heal_now", "range": 600.0, "expect": ["heal"]}


# ------------------------------------------------------------------ classification
def observed(m):
    """measurements -> the set of effects seen"""
    o = set()
    if m.get("damage", 0) > 0 and not m.get("foreign_near"): o.add("damage")
    if m.get("move", 0) >= MOVE_MIN or m.get("leaping"): o.add("move")
    if m.get("push", 0) >= PUSH_MIN: o.add("push")
    if m.get("heal", 0) >= HEAL_MIN: o.add("heal")
    for k, e in (("projectiles", "projectile"), ("summons", "summon"), ("areas", "area"), ("items", "item")):
        if m.get(k): o.add(e)
    if m.get("changed"): o.add("change")
    if m.get("hyper_cast"): o.add("hyper_cast")
    if m.get("hyper_seen"): o.add("hyper")
    return o


def classify(m, expect):
    """(measurements, expected effects) -> (class, missing effects, effects seen)"""
    if m.get("crashed"): return "crash", [], set()
    if not m.get("spawned", True) or not m.get("consumed"): return "not_fired", [], set()
    ex = [e for e in expect if e != "heal" or m.get("pre_damaged")]
    seen = observed(m); missing = [e for e in ex if e not in seen]
    if not ex: return "unverified", [], seen
    if not missing: return "works", [], seen
    return ("partial" if seen else "no_effect"), missing, seen


def describe(m, missing=()):
    """what was seen, short (the checklist line)"""
    if m.get("crashed"): return "host crashed with it as the only shooter"
    if not m.get("spawned", True): return "brawler not spawned (host rejected it)"
    if not m.get("filled", True): return "super could not be filled (super max %s)" % m.get("super_max")
    if not m.get("consumed"): return "super charge not consumed"
    p = []
    if m.get("damage", 0) > 0: p.append("%d damage%s" % (m["damage"], " (foreign summon near: not counted)" if m.get("foreign_near") else ""))
    if m.get("move", 0) >= MOVE_MIN or m.get("leaping"): p.append("moved %d u%s" % (m.get("move", 0), " (leap)" if m.get("leaping") else ""))
    if m.get("push", 0) >= PUSH_MIN: p.append("target pushed %d u" % m["push"])
    if m.get("heal", 0) >= HEAL_MIN: p.append("healed %d" % m["heal"])
    cnt = lambda xs: ", ".join("%s x%d" % (k, v) if v > 1 else k for k, v in collections.Counter(xs).items())
    if m.get("projectiles"): p.append("projectiles: " + cnt(m["projectiles"]))
    if m.get("summons"): p.append("summons: " + cnt(m["summons"]))
    if m.get("areas"): p.append("areas: " + cnt("%s r%d" % (a["name"], a["radius"]) for a in m["areas"]))
    if m.get("items"): p.append("items: " + cnt(m["items"]))
    if m.get("changed"): p.append("character changed")
    if "hyper_on" in m:
        p.append(("hypercharged super cast (%s)" % m.get("hyper_skill", "?")) if m.get("hyper_cast") else
                 "hypercharge %s, super cast %s" % ("on" if m["hyper_on"] else "OFF", m.get("hyper_skill") or "not hypercharged"))
    s = "; ".join(p) if p else "nothing seen"
    if missing: s += "; missing: " + ", ".join(missing)
    if "heal" in m.get("expect", []) and not m.get("pre_damaged"): s += "; heal not testable (pre-damage missed)"
    return s


def best(attempts):
    return min(attempts, key=lambda a: CLASSES.index(a["class"]))


# ------------------------------------------------------------------ map spots
def find_spots(location=MAP, n=10, seed=0, tries=400):
    """clear spots on the location's map: [(x, y world units of the shooter, [unit direction vectors with a clear corridor])],
    >= SPACING tiles apart; the A / B halves (first / second n/2) sorted by x so the two phases are far apart"""
    from nbpc import diversity as D
    ids, rows = D.map_reference(location); H, W = len(rows), len(rows[0])
    blk = {i for _, (i, r) in D.table("tiles.csv").items() if r.get("BlocksMovement") == "true" or r.get("BlocksProjectiles") == "true"}
    raw = np.array([list(r) for r in rows])
    b = np.isin(ids, list(blk)).reshape(H, W) | np.char.isdigit(raw)   # digits: spawn points and power-cube boxes
    b = np.pad(b, CORR + 2, constant_values=True); o = CORR + 2
    dirs = ((1, 0), (0, 1), (-1, 0), (0, -1))
    cand = []
    for cy in range(H):
        for cx in range(W):
            y, x = cy + o, cx + o
            if b[y - 2:y + 3, x - 2:x + 3].any(): continue
            ok = []
            for dx, dy in dirs:
                xs, ys = sorted((x, x + dx * CORR)), sorted((y, y + dy * CORR))
                if not b[ys[0] - (dx != 0):ys[1] + 1 + (dx != 0), xs[0] - (dy != 0):xs[1] + 1 + (dy != 0)].any(): ok.append((dx, dy))
            if len(ok) >= 2: cand.append((cx, cy, ok))
    rng, top = np.random.default_rng(seed), []
    for t in range(tries):
        order = cand if t == 0 else [cand[i] for i in rng.permutation(len(cand))]
        got = []
        for c in order:
            if all(max(abs(c[0] - g[0]), abs(c[1] - g[1])) >= SPACING for g in got): got.append(c)
            if len(got) == n: break
        if len(got) > len(top): top = got
        if len(top) == n: break
    top = sorted(top, key=lambda c: (c[0], c[1]))
    return [((c[0] + 0.5) * TILE, (c[1] + 0.5) * TILE, c[2]) for c in top]


# ------------------------------------------------------------------ live
def parse_state(buf):
    a = np.frombuffer(buf, "<i4")
    if len(a) < HDR or a[0] != 0x4E423253: return None
    npl, nch, npj, nit = (int(x) for x in a[3:7]); k = HDR
    pl = a[k:k + npl * P2].reshape(npl, P2); k += npl * P2
    ch = a[k:k + nch * C2].reshape(nch, C2); k += nch * C2
    pj = a[k:k + npj * J2].reshape(npj, J2); k += npj * J2
    it = a[k:k + nit * I2].reshape(nit, I2)
    return {"tick": int(a[2]), "pl": pl, "ch": ch, "pj": pj, "it": it}


def brawler_ids(st):
    return {int(p[0]): (int(p[3]) if int(p[3]) not in (0, NIL) else int(p[2])) for p in st["pl"]}


class Job:
    def __init__(self, name, attempt=0, solo=False):
        self.name, self.attempt, self.solo, self.requeues = name, attempt, solo, 0


class Auditor:
    def __init__(self, names, n=1, retry=True, log_dir=None, seed=0, host_args=(), verbose=True, hyper=False, gadget=False, slot=0):
        from nbpc import diversity as D
        self.D = D; self.hyper = hyper; self.gadget = gadget; self.retry = retry; self.verbose = verbose
        self.info = {b: expected_gadget(b, slot) if gadget else expected(b, hyper) for b in names}
        self.results = {b: [] for b in names}; self.lock = threading.Lock(); self.inflight = 0
        self.queue = collections.deque(Job(b) for b in names); self.seed = 93000000 + seed
        self.spots = find_spots(MAP)
        if len(self.spots) < 2: raise RuntimeError(f"{MAP}: no clear spots")
        self.npair = min(5, len(self.spots) // 2)
        self.log_dir = log_dir or os.path.join(os.environ.get("SIM_WORK", "work"), "super_audit_logs")
        self.n, self.host_args, self.t0 = n, list(host_args), time.time(); self.timing = []

    def log(self, *a):
        if self.verbose: print("[%5.0f s]" % (time.time() - self.t0), *a, flush=True)

    # one attempt's record + the follow-up job
    def record(self, job, m):
        inf = self.info[job.name]; m["expect"] = inf["expect"]
        cls, miss, seen = classify(m, inf["expect"])
        a = {"attempt": job.attempt, "solo": job.solo, "class": cls, "missing": miss, "seen": sorted(seen), "what": describe(m, miss), "m": m}
        with self.lock:
            self.results[job.name].append(a)
            if self.retry and job.attempt == 0 and cls not in ("works", "unverified", "crash"):
                self.queue.append(Job(job.name, 1, solo=job.solo))
        self.log("%-22s try %d %-10s %s" % (job.name, job.attempt, cls, a["what"]))

    def take(self):
        with self.lock:
            if not self.queue: return None
            if self.queue[0].solo: jobs = [self.queue.popleft()]
            else:
                jobs = []
                for j in list(self.queue):
                    if not j.solo and j.name not in {x.name for x in jobs}: jobs.append(j); self.queue.remove(j)
                    if len(jobs) == 2 * self.npair: break
            self.inflight += 1
            return jobs

    def done(self):
        with self.lock: self.inflight -= 1

    def worker(self, idx):
        from nbpc.instance import Instance, InstanceDead
        inst = Instance(idx, tag=f"sa{os.getpid()}", log_dir=self.log_dir, bell=True, extra_args=self.host_args)
        def boot():
            t = time.time(); inst.start(); inst.wait_ready(); self.log(f"instance {idx} ready in {time.time() - t:.0f} s")
        boot()
        try:
            while True:
                jobs = self.take()
                if jobs is None:
                    with self.lock: idle = self.inflight == 0 and not self.queue
                    if idle: return
                    time.sleep(0.5); continue
                try:
                    t = time.time(); self.battle(inst, jobs); self.timing.append((len(jobs), time.time() - t))
                except InstanceDead as e:
                    self.log(f"instance {idx} died: {str(e)[:160]}")
                    self.crashed(jobs)
                    try: inst.close()
                    except Exception: pass
                    boot()
                finally:
                    self.done()
        finally:
            inst.close()

    def crashed(self, jobs):
        """the running phase's shooters (self.cur) go one at a time; a solo crash is final; unrun jobs requeue"""
        undone = [j for j in jobs if not getattr(j, "_done", False)]
        cur = list(getattr(threading.current_thread(), "phase_jobs", ())) or undone   # outside a phase: all suspects
        final = []
        with self.lock:
            for j in undone:
                if j not in cur: self.queue.appendleft(Job(j.name, j.attempt, j.solo))
                elif j.solo: final.append(j)
                else: self.queue.appendleft(Job(j.name, j.attempt, solo=True))
        for j in final: self.record(j, {"crashed": True})

    def battle(self, inst, jobs):
        from nbpc import proto as P
        th = threading.current_thread(); th.phase_jobs = list(jobs)   # a crash in reset: every brawler is a suspect
        A = jobs[:self.npair]; B = jobs[self.npair:2 * self.npair]
        names = [j.name for j in A] + [FILLER] * (self.npair - len(A)) + [j.name for j in B]
        names += [FILLER] * (10 - len(names))
        self.seed += 1
        div = self.D.make_div(location=MAP, chr=names)
        if self.hyper: div["hyper"] = list(range(10))   # every player's hypercharge card (only the shooters activate)
        if self.gadget: div["gadget"] = [self.info[x]["card"] if x in self.info else 0 for x in names]   # fillers: none
        inst.reset(self.seed, gas=0, flags=P.F_STATE, native_mask=0, obs_mask=0, div=div)
        info = inst.battle_info(); got = info["chr"][:10] if info else None
        want = [self.D.cid(x) for x in names]
        inst.step(ticks=10, flags=0, native_mask=0)
        th.phase_jobs = []
        pairs = [(A, list(range(len(A))), [i + 5 for i in range(len(A))], self.spots[:self.npair]),
                 (B, [i + 5 for i in range(len(B))], list(range(len(B))), self.spots[self.npair:2 * self.npair])]
        for js, sh, tg, spots in pairs:
            if not js: continue
            run = []
            for j, s, t in zip(js, sh, tg):
                if got is not None and got[s] != want[s]: j._done = True; self.record(j, {"spawned": False}); continue
                if not inst.resp.pl[s].alive or inst.resp.pl[s].hp <= 0:   # killed as an earlier phase's target: again later
                    with self.lock: self.queue.appendleft(Job(j.name, j.attempt, j.solo))
                    j._done = True; continue
                run.append((j, s, t))
            if run:
                th.phase_jobs = [r[0] for r in run]
                for (j, m) in self.phase(inst, run, spots):
                    j._done = True; self.record(j, m)
                th.phase_jobs = []

    def phase(self, inst, run, spots):
        from nbpc import proto as P
        geo, pos = {}, {}
        for k, (j, s, t) in enumerate(run):
            inf = self.info[j.name]; x, y, dirs = spots[k]
            dx, dy = dirs[min(j.attempt, len(dirs) - 1)]
            if inf.get("east") and (1, 0) in dirs: dx, dy = 1, 0
            d = float(np.clip(DIST_F[min(j.attempt, 1)] * inf["range"], DIST_MIN, DIST_MAX))
            if j.attempt and len(dirs) == 1: d = float(np.clip(d * 0.6, DIST_MIN, DIST_MAX))
            if inf["type"] == "ProjectileShield": d = SHIELD_D   # the target shoots from beyond the shield line
            tx, ty = x + dx * d, y + dy * d
            if inf.get("ring") and inf["range"] > inf["ring"]:   # no damage inside InnerRadius (Kaze): land past the target
                d = float(np.clip(inf["range"] - inf["ring"], DIST_MIN, DIST_MAX))
            sd = min(1.0, (d + TILE if inf["charge"] and not inf.get("land") else d + inf.get("ring", 0)) / inf["range"])
            aim = float(np.degrees(np.arctan2(dy, dx)))
            geo[j] = dict(d=round(d), aim=aim, super_dist=round(sd, 3), spot=[round(x), round(y)])
            pos[s] = (int(x), int(y)); pos[t] = (int(tx), int(ty))
        allp = list(range(10)); idle = {i: (-1, 0, 0.0, 0.0) for i in allp}
        stp = lambda acts=None, ticks=STEP: inst.step(actions=acts or idle, ticks=ticks, flags=P.F_STATE, native_mask=0)
        inst.setup(positions=pos, ai_off=allp, unprotect=allp)
        for _ in range(4): stp()
        acts = dict(idle)
        for j, s, t in run: acts[t] = (-1, 1, (geo[j]["aim"] + 180.0) % 360, 0.0)   # pre-damage: the target shoots the shooter once
        stp(acts, 1)
        for _ in range(12): stp()
        sh = [s for _, s, _ in run]
        if self.gadget: r = stp(ticks=1); gu0 = {s: int(r.gad_used[s]) for s in sh}   # no super: the gadget is fired below
        else: inst.setup(super_fill=sh, hyper_fill=sh if self.hyper else ()); r = stp(ticks=1)
        if self.hyper:   # --hyper: activate (fire 4), then the super below is the hypercharged one
            acts = dict(idle)
            for s in sh: acts[s] = (-1, 4, 0.0, 0.0)
            r = stp(acts, 1)
            hy0 = {s: (int(r.hyp_left[s]), int(r.hyp_supers[s])) for s in sh}
        st = parse_state(inst.state_bytes())
        if st is None: raise RuntimeError("no state2 dump in the response (host without F_STATE?)")
        ids0 = set(st["pj"][:, 0].tolist()) | set(st["it"][:, 0].tolist()) | set(st["ch"][:, 0].tolist())
        bid0 = brawler_ids(st)
        M = {}
        for j, s, t in run:
            p, q = r.pl[s], r.pl[t]; ch = st["ch"][st["ch"][:, 0] == bid0.get(s, -1)]
            M[j] = dict(geo[j], spawned=True, filled=bool(p.super_max > 0 and p.super_charge >= p.super_max), super_max=int(p.super_max),
                        sc0=int(p.super_charge), sc_min=int(p.super_charge), hp0=int(p.hp), hp_max=int(p.hp), max_hp=int(p.max_hp),
                        pre_damaged=bool(p.hp < p.max_hp), x0=int(p.x), y0=int(p.y), tx0=int(q.x), ty0=int(q.y), thp0=int(q.hp), thp_min=int(q.hp),
                        move=0, push=0, leaping=False, projectiles={}, summons={}, areas={}, items={},
                        changed=False, data0=int(ch[0, 1]) if len(ch) else NIL, ulti0=int(ch[0, 15]) if len(ch) else NIL,
                        ulti_active=False, foreign_near=False, target_dead=False, s=s, t=t)
        acts = dict(idle)
        for j, s, t in run: acts[s] = (-1, 3, geo[j]["aim"], 0.0) if self.gadget else (-1, 2, geo[j]["aim"], geo[j]["super_dist"])
        r = stp(acts, 1); n = 1
        if self.hyper:
            for j, s, t in run: M[j]["hyper_on"] = hy0[s][0] > 0
        while True:
            st = parse_state(inst.state_bytes()); bid = brawler_ids(st) if st is not None else {}
            for j, s, t in run:
                m, p, q = M[j], r.pl[s], r.pl[t]
                m["sc_min"] = min(m["sc_min"], int(p.super_charge)); m["hp_max"] = max(m["hp_max"], int(p.hp))
                m["thp_min"] = min(m["thp_min"], int(q.hp) if q.alive else 0); m["target_dead"] |= bool(not q.alive or q.eliminated)
                m["leaping"] |= bool(p.leaping)
                if p.alive: m["move"] = max(m["move"], int(np.hypot(p.x - m["x0"], p.y - m["y0"])))
                if q.alive and not q.eliminated: m["push"] = max(m["push"], int(np.hypot(q.x - m["tx0"], q.y - m["ty0"])))
                m["dd"] = m.get("dd", 0) + int(p.damage_dealt)   # per step (the host clears it after every response)
                if st is None: continue
                if bid.get(s) != bid0.get(s): m["changed"] = True
                for row in st["pj"]:
                    if row[2] == s and row[0] not in ids0: m["projectiles"][int(row[0])] = data_name(row[1])
                for row in st["it"]:
                    if row[2] == s and row[0] not in ids0:
                        if int(row[1]) // 1000000 == 17: m["areas"][int(row[0])] = {"name": data_name(row[1]), "radius": area_radius(row[1])}
                        else: m["items"][int(row[0])] = data_name(row[1])
                for row in st["ch"]:
                    own = int(row[2]); cid = int(row[0])
                    if row[18] != 0 or int(row[1]) in BOX_IDS or own < 0: continue
                    if cid == bid.get(s):
                        if m["data0"] != NIL and int(row[1]) != m["data0"]: m["changed"] = True
                        if row[15] not in (NIL, m["ulti0"]): m["ulti_active"] = True
                    elif own == s and cid not in bid.values() and cid not in ids0: m["summons"][cid] = data_name(row[1])
                    elif own not in (s, t) and cid not in bid.values():   # someone else's summon near this pair
                        if min(np.hypot(row[3] - m["tx0"], row[4] - m["ty0"]), np.hypot(row[3] - m["x0"], row[4] - m["y0"])) < 2000:
                            m["foreign_near"] = True
            if n >= WATCH: break
            acts = dict(idle)
            for j, s, t in run:   # steered supers (FlyJump, Ww): once cast, the shooter walks to the target (16 joystick directions)
                p, q = r.pl[s], r.pl[t]; inf = self.info[j.name]
                if inf.get("steer") and n * 50 > inf.get("cast", 0) + 100 and q.alive and np.hypot(q.x - p.x, q.y - p.y) > 150:
                    acts[s] = (int(round(np.degrees(np.arctan2(q.y - p.y, q.x - p.x)) / 22.5)) % 16, 0, 0.0, 0.0)
            # shield / status supers: the target shoots the shooter again (--post-hit for all; a ProjectileShield always)
            due = [(j, s, t) for j, s, t in run if "ph_hp0" not in M[j] and (POST_HIT or self.info[j.name].get("post_hit"))
                   and n >= (POST_HIT or self.info[j.name]["post_hit"])]
            if due:
                for j, s, t in due:
                    M[j]["ph_hp0"] = int(r.pl[s].hp); M[j]["ph_hp_min"] = int(r.pl[s].hp); M[j]["ph_tick"] = n
                    acts[t] = (-1, 1, (geo[j]["aim"] + 180.0) % 360, 0.0)
                r = stp(acts, 1); n += 1
            else:
                r = stp(acts); n += STEP
            for j, s, t in run:
                if "ph_hp0" in M[j]: M[j]["ph_hp_min"] = min(M[j]["ph_hp_min"], int(r.pl[s].hp))
        out = []
        for j, s, t in run:
            m = M[j]
            m["consumed"] = bool(m["filled"] and m["sc_min"] < m["super_max"] / 2)
            if self.gadget: m["consumed"] = int(r.gad_used[s]) > gu0[s]; m["filled"] = True   # the host counted a use
            m["damage"] = max(m["thp0"] - m["thp_min"], m.get("dd", 0))
            m["heal"] = m["hp_max"] - m["hp0"]
            m["pre_hit"] = m["max_hp"] - m["hp0"]                     # the target's shot before the super
            if "ph_hp0" in m: m["post_hit"] = m["ph_hp0"] - m["ph_hp_min"]   # its shot POST_HIT ticks after the fire
            for k in ("projectiles", "summons", "items"): m[k] = sorted(m[k].values())
            m["areas"] = sorted(m["areas"].values(), key=lambda a: a["name"])
            if self.hyper:   # the fire reaches the game one step later (env.c g_fire_delay): counted after the watch
                m.update(hyper_supers=int(r.hyp_supers[s]) - hy0[s][1], hyper_id=int(r.hyp_super_id[s]))
                inf = self.info[j.name]; seen = set(m["projectiles"]) | set(m["summons"]) | set(m["items"]) | {a["name"] for a in m["areas"]}
                m["hyper_skill"] = skill_name(m["hyper_id"]) if m["hyper_supers"] > 0 else ""
                m["hyper_cast"] = bool(m["hyper_on"] and m["hyper_supers"] > 0 and (not inf["own_skill"] or m["hyper_skill"] == inf["skill"]))
                m["hyper_seen"] = sorted(seen & set(inf["hyper_names"]))
            out.append((j, m))
        return out

    def run(self):
        ths = [threading.Thread(target=self.worker, args=(i,), daemon=True) for i in range(self.n)]
        for i, t in enumerate(ths):
            t.start()
            if i + 1 < self.n: time.sleep(2)
        for t in ths: t.join()
        return self.results


# ------------------------------------------------------------------ output
def summary(names, results, info):
    out = []
    for b in names:
        at = results.get(b) or []
        inf = info[b]
        row = {"name": b, "display": display(b), "skill": inf["skill"], "type": inf["type"], "kind": inf["kind"],
               "expect": inf["expect"], "notes": inf["notes"], "attempts": at}
        if at:
            bb = best(at); row.update({"class": bb["class"], "what": bb["what"], "missing": bb["missing"]})
            if any(a["class"] == "crash" for a in at) and bb["class"] != "crash": row["what"] += " (one attempt crashed the host)"
        else:
            row.update({"class": "not_run", "what": "not run", "missing": []})
        out.append(row)
    return out


def markdown(rows, hyper=False):
    L = ["# Super audit" + (" (hypercharged)" if hyper else ""), "", "One battle per 10 brawlers on %s, native AI off: each brawler fires its super at one enemy %s-%d units "
         "away and is watched for %.1f s (`python -m super_audit`). Expected effects come from the game's tables (skills.csv "
         "UltimateSkill + its projectile / area rows). Classes: works (every expected effect seen), partial (some), unverified "
         "(effect not visible to the audit), no_effect, not_fired (charge not consumed), crash. Not visible: stuns, slows, "
         "shields, buffs, wall breaking, ally effects." % (MAP, DIST_MIN, DIST_MAX, WATCH / 20.0), ""]
    if hyper: L[2:2] = ["--hyper: every shooter activates its hypercharge first; expected: the hypercharged super (characters.csv "
                        "OverchargedUltimateSkill, else the UltimateSkill's OverchargedVersion and Overcharged* columns), cast by the "
                        "host while hypercharged (hyper_cast), and one of its own projectiles / summons / areas / items (hyper) where "
                        "it has any.", ""]
    cnt = collections.Counter(r["class"] for r in rows)
    L += ["Totals: " + ", ".join("%s %d" % (c, cnt[c]) for c in CLASSES + ("not_run",) if cnt[c]), ""]
    for c in CLASSES + ("not_run",):
        rs = [r for r in rows if r["class"] == c]
        if not rs: continue
        L += ["## %s (%d)" % (c, len(rs)), ""]
        for kind in sorted({r["kind"] for r in rs}):
            L += ["### %s" % kind, ""]
            for r in sorted((r for r in rs if r["kind"] == kind), key=lambda r: r["display"]):
                box = "x" if c == "works" else " "
                tail = "" if c == "works" else ": " + r["what"]
                if c == "works" and r["what"] != "nothing seen": tail = " (" + r["what"] + ")"
                L.append("- [%s] %s (`%s`, %s): %s%s" % (box, r["display"], r["name"], r["kind"], c, tail))
            L.append("")
    return "\n".join(L)


# ------------------------------------------------------------------ self-check
def _check():
    # classification on synthetic measurements
    base = dict(spawned=True, filled=True, consumed=True, damage=0, move=0, push=0, heal=0, pre_damaged=True, projectiles=[],
                summons=[], areas=[], items=[], changed=False, leaping=False, foreign_near=False)
    m = lambda **k: dict(base, **k)
    assert classify(m(), ["damage"])[0] == "no_effect"
    assert classify(m(consumed=False, damage=500), ["damage"])[0] == "not_fired"
    assert classify(m(spawned=False), ["damage"])[0] == "not_fired"
    assert classify({"crashed": True}, ["damage"])[0] == "crash"
    assert classify(m(damage=900, projectiles=["P"]), ["projectile", "damage"])[0] == "works"
    c, miss, seen = classify(m(projectiles=["P"]), ["projectile", "damage"])
    assert c == "partial" and miss == ["damage"] and seen == {"projectile"}
    c, miss, _ = classify(m(move=2100, damage=1960), ["move", "damage", "push", "area"])   # Bull: env charge, no pushback
    assert c == "partial" and miss == ["push", "area"]
    assert classify(m(move=MOVE_MIN - 1), ["move"])[0] == "no_effect" and classify(m(leaping=True), ["move"])[0] == "works"
    assert classify(m(push=PUSH_MIN), ["push"])[0] == "works" and classify(m(push=PUSH_MIN - 1), ["push"])[0] == "no_effect"
    assert classify(m(summons=["ShamanPet"], projectiles=["X"]), ["projectile", "summon"])[0] == "works"
    assert classify(m(areas=[{"name": "A", "radius": 300}]), ["area"])[0] == "works"
    assert classify(m(items=["BoxOfBombs"], move=2000), ["move", "item"])[0] == "works"
    assert classify(m(changed=True), ["change"])[0] == "works"
    assert classify(m(), [])[0] == "unverified" and classify(m(damage=5), [])[0] == "unverified"
    # heal: only checked when the pre-damage landed
    assert classify(m(heal=HEAL_MIN, damage=10, projectiles=["P"]), ["projectile", "damage", "heal"])[0] == "works"
    assert classify(m(damage=10, projectiles=["P"]), ["projectile", "damage", "heal"])[0] == "partial"
    assert classify(m(pre_damaged=False, damage=10, projectiles=["P"]), ["projectile", "damage", "heal"])[0] == "works"
    assert classify(m(pre_damaged=False), ["heal"])[0] == "unverified"
    # damage next to a foreign summon is not counted
    assert classify(m(damage=800, foreign_near=True), ["damage"])[0] == "no_effect"
    # --hyper: the host's hypercharged cast and a hypercharged-only effect
    assert classify(m(projectiles=["P"], hyper_cast=True, hyper_seen=["P"]), ["projectile", "hyper_cast", "hyper"])[0] == "works"
    c, miss, _ = classify(m(projectiles=["P"]), ["projectile", "hyper_cast", "hyper"])
    assert c == "partial" and miss == ["hyper_cast", "hyper"]
    assert "hypercharged super cast (S)" in describe(m(hyper_on=True, hyper_cast=True, hyper_skill="S"))
    assert "hypercharge OFF" in describe(m(hyper_on=False, hyper_skill=""))
    # best attempt, descriptions, checklist
    at = [{"class": "no_effect"}, {"class": "works"}]
    assert best(at)["class"] == "works" and best([{"class": "crash"}, {"class": "not_fired"}])["class"] == "not_fired"
    d = describe(m(damage=1960, move=2100, areas=[{"name": "BullSlowArea", "radius": 300}], expect=["move"]), ["push"])
    assert "1960 damage" in d and "moved 2100" in d and "BullSlowArea r300" in d and d.endswith("missing: push"), d
    assert describe(m(consumed=False)) == "super charge not consumed" and "not testable" in describe(m(pre_damaged=False, expect=["heal"]))
    rows = [{"name": "BullDude", "display": "Bull", "kind": "Charge 1", "class": "partial", "what": d},
            {"name": "Shaman", "display": "Nita", "kind": "Attack: summon", "class": "works", "what": "summons: ShamanPet"},
            {"name": "Rosa", "display": "Rosa", "kind": "Shield", "class": "unverified", "what": "nothing seen"}]
    md = markdown(rows)
    assert "- [ ] Bull (`BullDude`, Charge 1): partial: " in md and "- [x] Nita (`Shaman`, Attack: summon): works (summons: ShamanPet)" in md
    assert md.index("## works") < md.index("## partial") < md.index("## unverified") and "Totals: works 1, partial 1, unverified 1" in md
    n_tab = 0
    try:                                                     # the tables (game files from setup.sh), when present
        import env_v5
        hs = env_v5.heroes() + env_v5.forms(); _tables()
    except Exception as e:
        print("super_audit: game tables not available (%s): table checks skipped" % type(e).__name__)
    else:
        inf = {h: expected(h) for h in hs}; n_tab = len(hs)
        b = inf["BullDude"]
        assert b["type"] == "Charge" and b["kind"] == "Charge 1" and {"move", "damage", "push"} <= set(b["expect"]) and b["range"] == 3300, b
        assert {"projectile", "summon"} <= set(inf["Shaman"]["expect"]) and "damage" not in inf["Shaman"]["expect"]
        assert inf["Sniper"]["expect"] == ["move", "item"], inf["Sniper"]            # leap: bombs at the start, no target damage
        assert {"projectile", "area", "damage"} <= set(inf["TntDude"]["expect"])
        assert "heal" in inf["DeadMariachi"]["expect"] and inf["Rosa"]["expect"] == [] and "change" in inf["CannonGirlSmall"]["expect"]
        assert inf["MechaDude"]["skill"] == "MechaDudeBigUlti" and "damage" in inf["MechaDude"]["expect"]   # Meg starts in her mech
        assert all(i["range"] > 0 and i["skill"] for i in inf.values())
        assert inf["Gladiator"]["expect"] == ["move", "area"] and any("EdgeCrossing" in x for x in inf["Gladiator"]["notes"]), inf["Gladiator"]
        assert inf["ShieldTank"]["post_hit"] == POST_HIT_SHIELD and inf["BullDude"]["post_hit"] == 0
        assert "MechaDudeBig" in inf and len(env_v5.forms()) == 9 and "MechaDudeBig" not in env_v5.heroes()   # forms audited, never picked
        assert display("BullDude") == "Bull" and data_name(16000000 + list(_tables()["char"]).index("BullDude")) == "BullDude"
        hy = {h: expected(h, hyper=True) for h in ("Jester", "Beamer", "Twins", "Skater", "Domain", "Dancer", "MechaDudeBig", "ShotgunGirl", "PowerLeveler")}
        assert hy["Jester"]["skill"] == "JesterOverchargedUlti" and "ChesterOverchargedUltiProjectile" in hy["Jester"]["hyper_names"]
        assert {"TwinsHCUltiProjectile", "TwinsPetHyper"} <= set(hy["Twins"]["hyper_names"]) and hy["Twins"]["own_skill"]
        assert hy["Skater"]["hyper_names"] == ["SkaterUltiLandingOvercharged"] and "hyper" in hy["Skater"]["expect"]
        assert hy["Domain"]["hyper_names"] == [] and "hyper" not in hy["Domain"]["expect"] and "hyper_cast" in hy["Domain"]["expect"]
        assert hy["PowerLeveler"]["skill"] == "PowerLevelerUltiOvercharged" and not hy["PowerLeveler"]["own_skill"]
        assert hy["ShotgunGirl"]["skill"] == "ShotgunGirlUlti" and "hyper_cast" in hy["ShotgunGirl"]["expect"]
        assert "hyper_cast" not in inf["Jester"]["expect"]
        ag = area_gadgets()   # --gadget: the host's AREA gadgets, Rosa's WallSpawn left out
        assert {"Barkeep", "DeadMariachi", "ClusterBombDude", "Ghost", "Domain", "Meeple", "KickerDude"} <= set(ag) and "Rosa" not in ag, sorted(ag)
        assert all(c // 1000000 == 23 for c, _ in ag.values())
        tk = expected_gadget("ClusterBombDude")
        assert tk["skill"] == "ClusterBombDude_Explosion" and tk["expect"] == ["area", "damage", "push"] and tk["delay"] == 20, tk
        assert expected_gadget("DeadMariachi")["expect"] == ["area", "heal"] and expected_gadget("Ghost")["expect"] == ["area"]
        kinds = collections.Counter(k for gs in all_gadgets().values() for _, _, k in gs)   # gadget.c's coverage of the enabled cards
        assert sum(kinds.values()) == 213 and kinds["shot"] == 25 and not {"repeat", "spin"} & set(kinds), kinds
        assert kinds["item"] == 2 and kinds["heal_now"] == 2 and kinds["super"] == 1 and kinds["skill_area"] == 2, kinds
        assert audit_gadgets(0)["Gunslinger"][1] == "Gunslinger_Reload" and audit_gadgets(1)["Gunslinger"][1] == "Gunslinger_BigBullet"
        assert expected_gadget("Gunslinger")["expect"][:1] == ["projectile"] and expected_gadget("Gunslinger", 1)["gadget_kind"] == "shot"
        assert not {"BowDude", "HookDude"} & set(audit_gadgets(0))
        assert "Barkeep" not in audit_gadgets(1) and expected_gadget("ElectroSniper")["expect"] == ["item"]   # HealPotion: repeat_shot, off (#54)
        assert expected_gadget("BullDude", 1)["gadget_kind"] == "skill_area" and "area" in expected_gadget("BullDude", 1)["expect"]
        assert expected_gadget("Samurai")["expect"] == ["heal"] and "Splitter" not in audit_gadgets(0)
        sp = find_spots(MAP)
        assert len(sp) == 10 and all(len(d) >= 2 for _, _, d in sp), len(sp)
        assert min(max(abs(a[0] - c[0]), abs(a[1] - c[1])) for i, a in enumerate(sp) for c in sp[i + 1:]) >= SPACING * TILE
    print("super_audit ok: classification%s" % (", tables of %d brawlers and forms, %d spots on %s" % (n_tab, 10, MAP) if n_tab else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="self-check of the classification (no host)")
    ap.add_argument("--n", type=int, default=1, help="game host instances")
    ap.add_argument("--only", default="", help="comma-separated brawler names (characters.csv Name); merged into an existing json")
    ap.add_argument("--no-retry", action="store_true", help="no second attempt for non-works brawlers")
    ap.add_argument("--out", default=os.environ.get("SIM_WORK", "work"), help="folder of super_audit.json / .md")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--watch", type=int, default=WATCH, help="ticks watched after the fire (default %d)" % WATCH)
    ap.add_argument("--post-hit", type=int, default=0, help="the target shoots the shooter again this many ticks after the fire "
                    "(pre_hit / post_hit HP in the json: shields, damage reduction); 0 = off")
    ap.add_argument("--host-args", default="", help="extra game host arguments, e.g. '--native-charge 0'")
    ap.add_argument("--hyper", action="store_true", help="the hypercharged supers: hypercharge each shooter first (fire 4), expect "
                    "the hypercharged super's effects; writes super_audit_hyper.json / .md")
    ap.add_argument("--gadget", action="store_true", help="the gadgets the host implements (gadget.c, audit_gadgets): fire each brawler's "
                    "gadget (fire 3) in place of the super; writes super_audit_gadget.json / .md")
    ap.add_argument("--gadget-slot", type=int, default=0, help="--gadget: which of a brawler's implemented gadgets (0 = first, 1 = "
                    "second: Gene, Colt, ...); slot 1 writes super_audit_gadget_2.json / .md")
    a = ap.parse_args()
    if a.check: return _check()
    globals()["WATCH"] = a.watch; globals()["POST_HIT"] = a.post_hit
    import env_v5
    roster, forms = env_v5.heroes(), env_v5.forms()     # forms (Meg's mech, event transforms): never a pick, audited after
    if a.gadget: roster, forms = sorted(b for b in audit_gadgets(a.gadget_slot) if b in roster), []
    names = [x for x in a.only.split(",") if x] or roster + forms
    bad = [x for x in names if x not in _tables()["char"] or (a.gadget and x not in audit_gadgets(a.gadget_slot))]
    if bad: sys.exit(f"unknown brawlers{' (or no implemented gadget in that slot)' if a.gadget else ''}: {bad}")
    au = Auditor(names, n=a.n, retry=not a.no_retry, seed=a.seed, host_args=a.host_args.split(), hyper=a.hyper, gadget=a.gadget,
                 slot=a.gadget_slot)
    stem = ("super_audit_gadget" + ("_%d" % (a.gadget_slot + 1) if a.gadget_slot else "")) if a.gadget else "super_audit_hyper" if a.hyper else "super_audit"
    nf = sum(x in forms for x in names)
    au.log(f"{len(names) - nf} brawlers + {nf} forms, {a.n} instances, {au.npair} pairs per phase on {MAP}")
    res = au.run()
    rows = summary(names, res, au.info)
    os.makedirs(a.out, exist_ok=True); jp = os.path.join(a.out, stem + ".json")
    if a.only and os.path.exists(jp):
        old = {r["name"]: r for r in json.load(open(jp)).get("brawlers", [])}
        old.update({r["name"]: r for r in rows}); rows = [old[k] for k in sorted(old)]
    bt = [t / max(k, 1) for k, t in au.timing]
    meta = {"map": MAP, "hyper": a.hyper, "watch_ticks": WATCH, "instances": a.n, "seconds": round(time.time() - au.t0),
            "battles": len(au.timing), "battle_s": round(float(sum(t for _, t in au.timing)), 2),
            "battle_s_per_brawler": round(float(np.mean(bt)), 3) if bt else None, "host_args": a.host_args, "time": time.strftime("%F %T")}
    json.dump({"meta": meta, "brawlers": rows}, open(jp, "w"), indent=1)
    md = markdown(rows, a.hyper)
    if a.gadget: md = md.replace("# Super audit", "# Gadget audit (gadget slot %d, fire 3 in place of the super)" % (a.gadget_slot + 1), 1)
    open(os.path.join(a.out, stem + ".md"), "w").write(md + "\n")
    print(md)
    au.log(f"wrote {jp} and {stem}.md; {meta['battles']} battles in {meta['battle_s']} s ({meta['battle_s_per_brawler']} s per brawler-attempt)")


if __name__ == "__main__":
    main()
