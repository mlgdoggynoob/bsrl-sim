"""Super audit: which brawlers' supers work on this host (a client build of the game: server-only code is bare `ret` stubs,
some of it re-implemented in nirkt's env.c / spawnfix.c). Output is a per-brawler checklist for a GitHub tracking issue.

    python -m super_audit [--n 2] [--only BullDude,Sniper]     # live: boots --n hosts (60-90 s each)
    python -m super_audit --check                              # classification self-check, no host
    python -m super_audit --hyper --only Jester,Twins          # the hypercharged supers (hypercharge first, host hyper.c)
    python -m super_audit --attack                             # the main attacks (fire 1 in place of the super)
    python -m super_audit --hyper-desc [--live DIR]            # offline: hypercharge descriptions vs tables and live audits

Setup (one battle per 10 brawlers, map MAP = the most open Showdown map, storm off, every player's native AI off):
players 0-4 shoot in phase A, players 5-9 in phase B; in each phase every shooter stands on its own clear spot (a 3-tile
wide corridor of open tiles in at least two directions, spots >= SPACING apart; A and B use different spots) with one
enemy target at distance d along a corridor. Per phase: teleport + heal everyone and end spawn protection; the target fires
one normal attack at the shooter (so a self-heal is visible); fill the shooters' supers; fire the super (fire 2, aim at the
target, super_dist = d / CastingRange, a charge aims ~1 tile past the target); watch WATCH ticks (LONG_WATCH for Bo's mines and Mico's jump). Bo's mines land in a ring around the aim point
and go off only when an enemy comes within their trigger range, so from TRAP_WALK ticks after the fire the target walks to the
nearest of the shooter's proximity traps (`is_trap`; its push is not read while it walks). A super the player steers
while it runs (FlyJump, Ww) has its shooter walk towards the target once its CastingTime is over (moves sent while it
casts are dropped), so its "move" is plain walking.
A ProjectileShield super (Buster) has its target SHIELD_D away, past the shield line, shooting into it at the first
step POST_HIT_SHIELD ticks or more after the fire. Projectiles end on a PayloadTrack tile on this host (MAP has a loop of
them), so Buster and Bibi (her ball) take a spot and direction with none on the line to past the target (`track_spots`); a type-16 charge (Bonnie, who hits where she lands) is aimed at the target, not past it.
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
from head and legs, the rejoin (also onto water), his head's water walking, the head dying with the legs and the legs
in the storm are charge_check's.
Classes (`classify()`): works = consumed and every expected effect seen; partial = consumed, some effect seen but not all
expected (listed as missing); unverified = consumed, but the super's effect is of a kind not visible here (shield,
invisibility, status buff, a heal when the pre-damage missed); no_effect = consumed, nothing seen; not_fired = charge not
consumed (or the brawler was not spawned); crash = the host died with this brawler as the only shooter; no_hyper (--hyper
only) = consumed, but neither the brawler nor the brawler it is a form of has a hypercharge card (`hyper_owner`: Wendy, Nori,
the SuperNova forms), so there is nothing hypercharged to judge.
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
OverchargedUltimateSkill, else the UltimateSkill's OverchargedVersion, with the row's Overcharged* columns; a negative
OverchargedChargePushback expects a pull, the target ending nearer the shooter), plus hyper_cast
(the host reports a super cast while hypercharged, NbeResp hyp_supers / hyp_super_id, with the OverchargedUltimateSkill's data
where there is one) and hyper (a projectile / summon / area / item only the hypercharged super has, when it has one).
Output: super_audit_hyper.json / .md.
--hyper-desc (offline, no host; issue #56): each hypercharge's game description (texts.csv <card TID>_DESC, `hyper_desc`) as
claims (`desc_claims`: a keyword table HDESC_KEYS -> features: more projectiles / bombs, split, bigger, faster, range, homing,
returns, pierces, bounces, destroys terrain, pull / push, slow / stun / silence / fear, shield, heal, damage, damage over time,
summon health, all-direction shots, new area). `check_claims` compares the feature on the normal super's effect rows and the
hypercharged one's (`effect_tree`: skills.csv row -> projectiles, chain bullets, areas, items, summons, statuses, followed down;
`tree_features`): data_ok (more of it), data_contradicts (the tables carry it, no more of it, a plain overcharge_default card),
no_data (not in the tables, or only in a brawler-specific card type's own code: card=True). `live_claim` maps a claim to a field
the live audits record (objects / projectiles count, damage, push, heal, move): super_audit_hyper.json vs super_audit.json ->
live_ok / live_wrong, else live_unchecked. Output: super_audit_hyper_desc.json / .md (--live: folder of the two audits).
--gadget (gadget round, issue #3): the brawlers with a gadget the host implements and this audit can see (`audit_gadgets`,
`gadget_kind` mirrors nbhost gadget.c's classify functions: area at the brawler, the gadget's own skill shot or area, items,
instant heals, Piper's Auto Aimer, the other repeat_shot / spin_shoot volleys ("repeat", issue #54 redo); R-T's super charge
is gadget_check's). Each shooter gets that gadget card and fires it (fire 3, aimed at the target, super_dist = d / CastingRange as
for a super: a thrown gadget lands there) in place of the super; consumed = the host counted a use (NbeResp gad_used). An
item gadget (a trap, a tornado) acts on an enemy that comes to it, so its target walks to the shooter's spot after the fire
(walk_in; push = how far it is kept from that spot). Expected effects come from the tables and from the card's own
description (`expected_gadget`: damage, push and heal that texts.csv names are expected too, issue #55; the other effects it
names are listed as not checked live). A thrown shot whose projectiles hit nobody in flight and whose areas deal no damage
(Damian's wall, Wendy's grenade, Spike's cactus) does not expect its skill's Damage (`thrown_harms`). --gadget-slot 1 audits
each brawler's second such gadget. Output: super_audit_gadget.json / .md (slot 1: super_audit_gadget_2.*).
--attack (main attack round): the same scene, but each shooter fires its main attack (fire 1, aimed at the target; the host
always throws it at full range) in place of the super, with no super fill. Expected effects come from the brawler's
characters.csv WeaponSkill row read as a super's (`expected(attack=True)`, Meg: her mech's weapon); consumed = the attack's
ammo (state2 skill 0 word, NbeResp ammo) dropped, or damage dealt. A thrown attack (an Indirect projectile: Dynamike, Barley,
Tick, ...) lands at full range, so its target stands at min(CastingRange, DIST_MAX) on both attempts (`throw`). No LONG_WATCH.
Output: super_audit_attack.json / .md."""
import argparse, collections, functools, json, os, re, sys, threading, time
import numpy as np

NIL = -2147483648
MAP = "Survival651"                      # the most open Showdown map (88 % open tiles; others give < 6 clear spots)
TILE = 300
CORR = 8                                 # corridor length in tiles from the shooter's tile: targets up to 7 tiles (2100 u)
SPACING = 13                             # tiles between spot centres (3900 u: a long super past its target stays clear)
WATCH = 50                               # ticks watched after the fire (2.5 s at 20 ticks/s; regen starts 3 s after a hit)
LONG_WATCH = {"BowDude": 160, "Leaper": 160}   # Bo's mines arm and go off after 2.5 s; Mico's jump lasts 6 s: watched 8 s
TRAP_WALK = 40       # ticks after the fire: the target walks to the nearest of the shooter's armed proximity traps (Bo's mines
                     # land in a ring ~500 u around the aim point and arm 25-32 ticks after the fire: host run, items log)
TRAP_RANGE = 10      # items.csv TriggerRangeSubTiles up to this is a proximity trap (Bo's Mine 3; Tick's 200 is a timer)
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
CLASSES = ("works", "partial", "unverified", "no_hyper", "no_effect", "not_fired", "crash")   # best first
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
           ("SpawnedItem", "OverchargedSpawnedItem"), ("ChargePushback", "OverchargedChargePushback"))


def hyper_skill(name):
    """the super a hypercharged brawler casts: (skills.csv row name, row): its OverchargedUltimateSkill (characters.csv; 7
    brawlers) or its UltimateSkill, then that row's OverchargedVersion if it has one, with its Overcharged* columns in
    place of the normal ones"""
    T = _tables(); ch = T["char"][name]; n = ch.get("OverchargedUltimateSkill") or ch.get("UltimateSkill", "")
    s = T["skill"].get(n, {})
    if s.get("OverchargedVersion") in T["skill"]: n = s["OverchargedVersion"]; s = T["skill"][n]
    s = dict(s)
    for k, ko in OC_COLS:
        if s.get(ko) and s[ko] != "0": s[k] = s[ko]   # an empty or 0 overcharged column keeps the normal value
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


def is_trap(did):
    """an items data id -> True for a proximity trap: a TriggerAreaEffect set off by an enemy within TriggerRangeSubTiles"""
    r = _tables()["item"].get(data_name(did), {})
    return bool(r.get("TriggerAreaEffect")) and 0 < _num(r, "TriggerRangeSubTiles") <= TRAP_RANGE


def area_radius(did):
    """area_effects_skin data id -> table radius (units; obs_v5's lookup)"""
    import obs_v5 as O
    lut, na = O._area_lut(); i = int(did) - 16999999
    return int(round(float(lut[i, 0]) * 3000)) if 0 < i < na else 0


def _num(r, k):
    try: return float((r.get(k) or "0").split(";")[0] or 0)
    except ValueError: return 0.0


@functools.lru_cache(None)
def hyper_owner(name):
    """the brawler whose hypercharge card this one gets (hyper.c hyper_card_for): itself when a cards.csv MetaType 6 card
    targets it, else the carded brawler it is a form of (characters.csv Pet or its super's SummonedCharacters: Meg's mech,
    Kaze's GeishaTransformed), else None"""
    import env_v5
    T = _tables(); carded = env_v5.hyper_brawlers()   # the cards the audit equips (env_v5.with_hyper)
    if name in carded: return name
    for b in sorted(carded & set(T["char"])):
        c = T["char"][b]; sc = (T["skill"].get(c.get("UltimateSkill", ""), {}).get("SummonedCharacters") or "").split(";")
        if c.get("Pet") == name or name in sc: return b
    return None


def expected(name, hyper=False, attack=False):
    """the brawler's super from the tables -> dict(skill, type (BehaviorType), kind (finer group label), range (units),
    charge (bool), expect (effects that must be seen), notes). A brawler in START_FORM (Meg: the client spawns her in her
    mech) gets its start form's super, with a note. hyper: its hypercharged super (hyper_skill); expect adds
    hyper_cast (the host cast it while hypercharged, with this skill's data where characters.csv names an
    OverchargedUltimateSkill) and hyper (one of the projectiles / summons / areas / items only the hypercharged super has,
    `hyper_names`, when it has any); a brawler with no card (`hyper_owner` None) keeps its normal super, no_hyper=True. attack (--attack): its main attack (characters.csv WeaponSkill) in place of its super"""
    if name in START_FORM:
        out = expected(START_FORM[name], hyper, attack)
        out["notes"].append(f"spawns as {START_FORM[name]}: its {'attack' if attack else 'super'} is audited; the eject and the change back: charge_check")
        return out
    T = _tables(); ch = T["char"][name]; sk_name = ch.get("WeaponSkill" if attack else "UltimateSkill", ""); s = T["skill"].get(sk_name, {})
    if attack: return expected_skill(sk_name, s)
    if hyper and not hyper_owner(name):   # no hypercharge card (Wendy, Nori, the SuperNova forms): its normal super, class no_hyper
        out = expected_skill(sk_name, s); out["no_hyper"] = True
        out["notes"].append("no hypercharge card (cards.csv MetaType 6) for it or the brawler it is a form of: no hypercharge")
        return out
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
    if _num(s, "ChargePushback") < 0: ex.append("pull")   # El Primo hypercharged (OverchargedChargePushback -100): hit enemies pulled to the landing point
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
           "throw": any(r.get("Indirect") == "true" for r in pl),   # --attack: a thrown attack lands at full range (env.c fire 1)
           # projectiles end on a PayloadTrack tile on this host (Bibi's ball never leaves one; the targets' shells hit 2 of 13
           # shooters standing on one, 6-10 of 13 elsewhere): Bibi's ball and the shots into Buster's shield need a corridor with
           # none up to past the target (`track_free`, phase())
           "track": bt == "ProjectileShield" or any(r.get("IsBouncing") == "true" and _num(r, "DamagesConstantlyTickDelay") > 0 for r in pl),
           "projectiles": projs, "summons": summons, "areas": areas, "items": items, "notes": notes}
    return out


def super_dist(inf, d):
    """fire 2's super_dist (a fraction of the super's range, `expected()` info inf) for a target d units away: a charge
    aims ~1 tile past the target (not a landing one, Bonnie), a ring super lands its ring on the target"""
    return min(1.0, (d + TILE if inf["charge"] and not inf.get("land") else d + inf.get("ring", 0)) / inf["range"])


# area types whose Damage column hits no one: WallSpawn (the walls' HP), StatusEffect (Max's / Sandy's speed boosts),
# ChargeSuper (Max's drink), EnragerOverchargeSuper (Edgar's hypercharged super: a reload / super charge buff for its owner,
# texts TID_ENRAGER_OVERCHARGE_DESC; its effect is compiled out of this libg)
NO_DAMAGE_AREAS = ("WallSpawn", "StatusEffect", "ChargeSuper", "EnragerOverchargeSuper")
HEAL_TYPES = ("Heal", "Hot", "HealRegen", "HealAndDamage", "HotAndDot")


MASKED = {"BowDude_Totem", "Speedy_Rewind", "HammerDude_Pull", "AssaultShotgun_Bomb", "Ninja_InvisibleArea",
          "Gladiator_Amp", "MagicalGirl_FlyArea",   # gadget.c g_masked: classified, but no effect in this audit
          "BarrelBot_Spin", "KickerDude_Mines", "BeeSniper_ExtraBee", "FireDude_FlameShield"}   # REPEAT rows with no hit seen
# -> not usable
GADGET_KINDS = ("area", "shot", "skill_area", "item", "heal_now", "super", "auto_aim", "repeat")


def gadget_kind(a, masked=True):
    """accessories.csv row -> the host's gadget.c implementation that handles it (GADGET_KINDS), None = not usable
    (masked=False: the kind a MASKED row classifies as).
    Mirrors gadget.c's classify functions (accessory Type, AreaEffect, the Skill's BehaviorType, CustomObject's table)."""
    T = _tables(); t = a.get("Type") or ""; num = lambda k: _num(a, k)
    if masked and a.get("Name") in MASKED: return None
    obj = (a.get("CustomObject") or "").split(";")[0]
    is_proj = obj in T["pskin"] or obj in T["plog"]
    if (not t or (t == "spin_shoot" and not is_proj)) and a.get("AreaEffect"):   # AREA: the area at the brawler (Fang's sweep too), Rosa's WallSpawn left out
        return "area" if T["alog"].get(a["AreaEffect"], {}).get("Type") != "WallSpawn" else None
    if not t and a.get("Skill"):
        sk = T["skill"].get(a["Skill"], {}); bt = sk.get("BehaviorType") or "Attack"   # an empty BehaviorType parses as Attack
        if bt == "Attack" and sk.get("Projectiles"): return "shot"
        if bt in ("Attack", "AimableArea") and not sk.get("Projectiles") and sk.get("AreaEffectObject"): return "skill_area"
        return None
    if a.get("Name") == "Sniper_HandGun" and is_proj and num("Range") > 0: return "auto_aim"   # gadget.c AUTO AIMER (#54 redo)
    if t in ("repeat_shot", "spin_shoot"):   # gadget.c REPEAT / SPIN (#54 redo): ActiveTicks // CustomValue1 shots of the CustomObject
        return "repeat" if is_proj and num("CustomValue1") > 0 and num("ActiveTicks") > 0 and a.get("Name") != "Sniper_HandGun" else None
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


AUDIT_KINDS = ("area", "shot", "skill_area", "item", "heal_now", "auto_aim", "repeat")   # "super" (R-T): gadget_check checks it


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


def thrown_harms(T, e):
    """a SHOT gadget's expected_skill() -> False when its projectiles are all thrown (Indirect) with Radius 0 (they hit nobody
    in flight) and none of its areas has a Damage: the skill's own Damage column then reaches no one (issue #55)"""
    pl = [T["plog"].get(T["pskin"].get(p, {}).get("Logic") or p, {}) for p in e["projectiles"]]
    if not pl or not all(r.get("Indirect") == "true" and _num(r, "Radius") == 0 for r in pl): return True
    al = [T["alog"].get(T["askin"].get(a, {}).get("Logic") or a, {}) for a in e["areas"]]
    return any(_num(r, "Damage") > 0 or r.get("Type") in ("Dot", "HotAndDot") for r in al)


def _expected_gadget(name, slot=0):
    """--gadget: the brawler's audit_gadgets(slot) gadget -> the same dict as expected(). area: area always; damage, push,
    heal from the area's area_effects_logic row, range = its radius (the target stands inside it). shot / skill_area: the
    gadget's own skill as expected_skill() reads a super. item: an item. heal_now: a heal (the target hits the shooter
    first). auto_aim: the CustomObject projectile, damage, and a push when the projectile has PushbackStrength; range = the
    row's Range in tiles (the shot goes at the nearest enemy within it). repeat: the CustomObject projectile and damage (heal for
    a TargetFriends row: Barley's potion), range = the row's Range in tiles, else CustomValue4 (spin_shoot), else 600."""
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
        if kind == "shot" and "damage" in e["expect"] and not thrown_harms(T, e):   # Damian's wall, Wendy's grenade, Spike's cactus
            e = {**e, "expect": [x for x in e["expect"] if x != "damage"],
                 "notes": e["notes"] + ["thrown, lands on nothing that deals damage: the skill's Damage is not expected"]}
        return {**e, "skill": acc, "type": "Gadget", "kind": "Gadget: " + kind, "card": card, "delay": 0.0, "gadget_kind": kind}
    if kind == "auto_aim":
        obj = a["CustomObject"].split(";")[0]; pl = T["plog"].get(T["pskin"].get(obj, {}).get("LogicProjectile") or obj, {})
        ex = ["projectile", "damage"] + (["push"] if _num(pl, "PushbackStrength") > 0 else [])
        return {**base, "kind": "Gadget: auto_aim", "range": _num(a, "Range") * TILE, "expect": ex, "projectiles": [obj]}
    if kind == "repeat":
        obj = a["CustomObject"].split(";")[0]; fr = (a.get("TargetFriends") or "").lower() == "true"
        rng = _num(a, "Range") * TILE or (_num(a, "CustomValue4") if a.get("Type") == "spin_shoot" else 0) or 600.0
        return {**base, "kind": "Gadget: repeat " + a.get("Type", ""), "range": rng, "expect": ["projectile", "heal" if fr else "damage"],
                "projectiles": [obj]}
    if kind == "item":
        return {**base, "kind": "Gadget: item", "range": 600.0, "expect": ["item"], "items": [a["CustomObject"].split(";")[0]],
                "walk_in": True}   # a trap / tornado acts on an enemy that comes to it: the target walks to the shooter
    return {**base, "kind": "Gadget: heal_now", "range": 600.0, "expect": ["heal"]}


TEXT_OBSERVABLE = ("damage", "push", "heal")     # text_effects names this audit measures (observed()): the rest is "not checked live"


@functools.lru_cache(None)
def _gadget_text():
    """(brawler, accessories row name) -> the card's description text (desc_audit.rows())"""
    import desc_audit
    return {(r["brawler"], r["card"]): r["text"] for r in desc_audit.rows() if r["type"] == "gadget"}


def text_expectation(name, acc):
    """the card's description text -> (effects it names that observed() can measure, notes for the rest / the text itself)"""
    import desc_audit
    text = _gadget_text().get((name, acc), ""); fx = desc_audit.text_effects(text)
    seen = [e for e in TEXT_OBSERVABLE if e in fx]
    rest = sorted(fx - set(TEXT_OBSERVABLE))
    notes = []
    if rest: notes.append("not checked live (text names): " + ", ".join(rest))
    if re.search(r"split|divid|in 2|in two", text.lower()): notes.append("not checked live (text names): split")
    if re.search(r"shield", text.lower()) and "shield" not in rest: notes.append("not checked live (text names): shield")
    if re.search(r"follow|homing|closest|seek", text.lower()): notes.append("not checked live (text names): homing")
    if seen: notes.append("text says: " + ", ".join(seen))
    return seen, notes


def expected_gadget(name, slot=0):
    """_expected_gadget (the data-derived effects) plus the damage / push / heal the card's description text names (text_expect);
    other text effects (slow, speed, invisible, split, homing, stun, ...) go to notes as "not checked live" """
    e = _expected_gadget(name, slot)
    seen, notes = text_expectation(name, e["skill"])
    e["text_expect"] = [x for x in seen if x not in e["expect"]]
    e["expect"] = e["expect"] + e["text_expect"]
    e["notes"] = e["notes"] + notes
    return e


# ------------------------------------------------------------------ classification
def observed(m):
    """measurements -> the set of effects seen"""
    o = set()
    if m.get("damage", 0) > 0 and not m.get("foreign_near"): o.add("damage")
    if m.get("move", 0) >= MOVE_MIN or m.get("leaping"): o.add("move")
    if m.get("push", 0) >= PUSH_MIN: o.add("push")
    if m.get("pull", 0) >= PUSH_MIN: o.add("pull")
    if m.get("heal", 0) >= HEAL_MIN: o.add("heal")
    for k, e in (("projectiles", "projectile"), ("summons", "summon"), ("areas", "area"), ("items", "item")):
        if m.get(k): o.add(e)
    if m.get("changed"): o.add("change")
    if m.get("hyper_cast"): o.add("hyper_cast")
    if m.get("hyper_seen"): o.add("hyper")
    return o


def classify(m, expect, no_hyper=False):
    """(measurements, expected effects) -> (class, missing effects, effects seen); no_hyper (--hyper, a brawler with no
    hypercharge card): a fired super is no_hyper, not judged"""
    if m.get("crashed"): return "crash", [], set()
    if not m.get("spawned", True) or not m.get("consumed"): return "not_fired", [], set()
    if no_hyper: return "no_hyper", [], observed(m)
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
    if not m.get("consumed"): return "attack ammo not used" if m.get("attack") else "super charge not consumed"
    p = []
    if m.get("damage", 0) > 0: p.append("%d damage%s" % (m["damage"], " (foreign summon near: not counted)" if m.get("foreign_near") else ""))
    if m.get("move", 0) >= MOVE_MIN or m.get("leaping"): p.append("moved %d u%s" % (m.get("move", 0), " (leap)" if m.get("leaping") else ""))
    if m.get("pull", 0) >= PUSH_MIN: p.append("target pulled %d u nearer" % m["pull"])
    elif m.get("push", 0) >= PUSH_MIN: p.append("target pushed %d u" % m["push"])
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


TRACK_TILE = "PayloadTrack"   # tiles.csv row that ends projectiles on this host (Survival651 has a loop of it)


@functools.lru_cache(None)
def _track_map(location=MAP):
    from nbpc import diversity as D
    ids, rows = D.map_reference(location); H, W = len(rows), len(rows[0])
    tid = D.table("tiles.csv")[TRACK_TILE][0]
    return (np.asarray(ids) == tid).reshape(H, W)


def track_free(x, y, dx, dy, location=MAP):
    """tiles from the shooter's tile (x, y world units) along (dx, dy) before the first PayloadTrack tile on that line (0: the
    shooter stands on one), at most CORR + 2"""
    trk = _track_map(location); H, W = trk.shape; cx, cy = int(x // TILE), int(y // TILE); k = 0
    while k <= CORR + 1 and 0 <= cx + dx * k < W and 0 <= cy + dy * k < H and not trk[cy + dy * k, cx + dx * k]: k += 1
    return k


def track_spots(spots, d):
    """{spot index: [directions]} with no PayloadTrack on the line from the shooter to 2 tiles past a target d units away
    (expected()'s `track`)"""
    need = int(np.ceil(d / TILE)) + 2
    out = {}
    for i, (x, y, dirs) in enumerate(spots):
        ok = [dv for dv in dirs if track_free(x, y, dv[0], dv[1]) >= need]
        if ok: out[i] = ok
    return out


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
    def __init__(self, names, n=1, retry=True, log_dir=None, seed=0, host_args=(), verbose=True, hyper=False, gadget=False, slot=0, attack=False):
        from nbpc import diversity as D
        self.D = D; self.hyper = hyper; self.gadget = gadget; self.attack = attack; self.retry = retry; self.verbose = verbose
        self.info = {b: expected_gadget(b, slot) if gadget else expected(b, hyper, attack) for b in names}
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
        cls, miss, seen = classify(m, inf["expect"], inf.get("no_hyper", False))
        a = {"attempt": job.attempt, "solo": job.solo, "class": cls, "missing": miss, "seen": sorted(seen), "what": describe(m, miss), "m": m}
        with self.lock:
            self.results[job.name].append(a)
            if self.retry and job.attempt == 0 and cls not in ("works", "unverified", "no_hyper", "crash"):
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
        def boot():   # 1800 s: a loaded machine (other hosts on the same cores) boots well past 300 s
            t = time.time(); inst.start(); inst.wait_ready(timeout=1800); self.log(f"instance {idx} ready in {time.time() - t:.0f} s")
        try:
            boot()
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
        sk = list(range(len(spots)))   # spot of each run position; a `track` super (Bibi, Buster) takes one clear of PayloadTrack
        for a, (j, s, t) in enumerate(run):
            if not self.info[j.name].get("track"): continue
            good = track_spots(spots, DIST_MAX)
            if sk[a] in good: continue
            busy = {sk[b] for b, (jb, _, _) in enumerate(run) if b != a and self.info[jb.name].get("track")}
            free = [b for b in range(len(sk)) if sk[b] in good and sk[b] not in busy]
            if free: b = free[0]; sk[a], sk[b] = sk[b], sk[a]
        for k, (j, s, t) in enumerate(run):
            inf = self.info[j.name]; x, y, dirs = spots[sk[k]]
            if inf.get("track"): dirs = track_spots([spots[sk[k]]], DIST_MAX).get(0, dirs)
            dx, dy = dirs[min(j.attempt, len(dirs) - 1)]
            if inf.get("east") and (1, 0) in dirs: dx, dy = 1, 0
            d = float(np.clip(DIST_F[min(j.attempt, 1)] * inf["range"], DIST_MIN, DIST_MAX))
            if j.attempt and len(dirs) == 1: d = float(np.clip(d * 0.6, DIST_MIN, DIST_MAX))
            if inf["type"] == "ProjectileShield": d = SHIELD_D   # the target shoots from beyond the shield line
            if self.attack and inf.get("throw"): d = float(min(inf["range"], DIST_MAX))   # fire 1 throws at full range
            tx, ty = x + dx * d, y + dy * d
            if inf.get("ring") and inf["range"] > inf["ring"]:   # no damage inside InnerRadius (Kaze): land past the target
                d = float(np.clip(inf["range"] - inf["ring"], DIST_MIN, DIST_MAX))
            sd = super_dist(inf, d)
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
        if self.gadget or self.attack: r = stp(ticks=1); gu0 = {s: int(r.gad_used[s]) for s in sh}   # no super: fired below
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
                        ammo0=int(p.ammo), ammo_min=int(p.ammo), move=0, push=0, pull=0, leaping=False, projectiles={}, summons={}, areas={}, items={},
                        changed=False, data0=int(ch[0, 1]) if len(ch) else NIL, ulti0=int(ch[0, 15]) if len(ch) else NIL,
                        ulti_active=False, foreign_near=False, target_dead=False, s=s, t=t)
        m_x0, m_y0 = (lambda j: M[j]["x0"]), (lambda j: M[j]["y0"])
        acts = dict(idle)
        for j, s, t in run: acts[s] = (-1, 1 if self.attack else 3 if self.gadget else 2, geo[j]["aim"], geo[j]["super_dist"])
        r = stp(acts, 1); n = 1
        if self.hyper:
            for j, s, t in run: M[j]["hyper_on"] = hy0[s][0] > 0
        while True:
            st = parse_state(inst.state_bytes()); bid = brawler_ids(st) if st is not None else {}
            for j, s, t in run:
                m, p, q = M[j], r.pl[s], r.pl[t]
                m["sc_min"] = min(m["sc_min"], int(p.super_charge)); m["hp_max"] = max(m["hp_max"], int(p.hp))
                m["thp_min"] = min(m["thp_min"], int(q.hp) if q.alive else 0); m["target_dead"] |= bool(not q.alive or q.eliminated)
                m["leaping"] |= bool(p.leaping); m["ammo_min"] = min(m["ammo_min"], int(p.ammo))
                if p.alive: m["move"] = max(m["move"], int(np.hypot(p.x - m["x0"], p.y - m["y0"])))
                if q.alive and not q.eliminated:
                    if self.info[j.name].get("walk_in"):   # walking in: pushed back = away from the shooter's spot again
                        rr = float(np.hypot(q.x - m["x0"], q.y - m["y0"])); m["r_min"] = min(m.get("r_min", rr), rr)
                        m["push"] = max(m["push"], int(rr - m["r_min"]))
                    elif not m.get("trap_walk"):   # (a walk-in target ends nearer the shooter by itself: no pull read from it)
                        m["push"] = max(m["push"], int(np.hypot(q.x - m["tx0"], q.y - m["ty0"])))
                        if p.alive and m["push"] >= PUSH_MIN:   # pull: the target ends nearer the shooter than it started from
                            m["pull"] = max(m["pull"], int(np.hypot(m["tx0"] - p.x, m["ty0"] - p.y) - np.hypot(q.x - p.x, q.y - p.y)))
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
            if n >= max([WATCH] + [LONG_WATCH.get(j.name, 0) for j, _, _ in run if not self.attack]): break
            acts = dict(idle)
            for j, s, t in run:   # steered supers (FlyJump, Ww): once cast, the shooter walks to the target (16 joystick directions)
                p, q = r.pl[s], r.pl[t]; inf = self.info[j.name]
                if inf.get("steer") and n * 50 > inf.get("cast", 0) + 100 and q.alive and np.hypot(q.x - p.x, q.y - p.y) > 150:
                    acts[s] = (int(round(np.degrees(np.arctan2(q.y - p.y, q.x - p.x)) / 22.5)) % 16, 0, 0.0, 0.0)
                if inf.get("walk_in") and q.alive and np.hypot(q.x - m_x0(j), q.y - m_y0(j)) > 150:   # item gadgets: the target walks in
                    acts[t] = (int(round(np.degrees(np.arctan2(m_y0(j) - q.y, m_x0(j) - q.x)) / 22.5)) % 16, 0, 0.0, 0.0)
                if not (self.gadget or self.attack) and n >= TRAP_WALK and q.alive and st is not None:   # proximity traps (Bo's mines)
                    tr = [(float(row[3]), float(row[4])) for row in st["it"] if row[2] == s and row[0] not in ids0 and is_trap(row[1])]
                    if tr:
                        x, y = min(tr, key=lambda c: np.hypot(c[0] - q.x, c[1] - q.y)); M[j]["trap_walk"] = True
                        if np.hypot(x - q.x, y - q.y) > 50: acts[t] = (int(round(np.degrees(np.arctan2(y - q.y, x - q.x)) / 22.5)) % 16, 0, 0.0, 0.0)
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
            if self.attack: m.update(consumed=m["ammo_min"] < m["ammo0"] or m.get("dd", 0) > 0, filled=True, attack=True)   # ammo spent
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
                m["hyper_seen"] = sorted(seen & set(inf.get("hyper_names", [])))   # none for a no_hyper brawler
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


# ------------------------------------------------------------------ hypercharge descriptions (--hyper-desc, issue #56)
# The game's own text for each hypercharge (texts.csv <card TID>_DESC, the brawler's cards.csv MetaType 6 card) turned into
# checkable claims, each checked against the tables (the normal super's effect rows vs the hypercharged super's) and, where a
# claim maps to a field the live audits record, against super_audit_hyper.json vs super_audit.json. Offline: no host.
HDESC_FEATURES = ("count", "split", "radius", "speed", "range", "duration", "homing", "boomerang", "pierce", "bounce", "destroys",
                  "pull", "push", "slow", "stun", "silence", "fear", "shield", "invisible", "heal", "damage", "dot", "hp", "spray",
                  "new_area", "other")
# claim keywords, first match per feature: (feature, regex on the lower-cased text, tags stripped, VALUEn filled in)
HDESC_KEYS = (
    ("count", r"more (bombs|rats|mines)|instead of|\b(\d+|two|three) (mines|jars|cannonballs|big brews|hurricanes|different "
              r"hands|spiders|hypercharge notes)|double the|fires twice|2 waves|three different directions|extra prototype|"
              r"two active|spawns hatchlings|additional time warp|extra blast"),
    ("split", r"split|cluster|smaller bombs|multiply|secondary explosion|minimines|extra blast"),
    ("radius", r"larger|bigger|wider|increase in size|grows in size|entire circle|360 degrees|surrounds|area is increased"),
    ("speed", r"faster|increased speed|increased movement speed|quickly|more speed"),
    ("range", r"(increased|longer|unlimited) range|farther|further|distance and"),
    ("duration", r"lasts for longer|lingering|keeps burning"),
    ("homing", r"home in|homing|follows the closest|will follow"),   # Spiders that "seek": summon AI, not a table column
    ("boomerang", r"boomerang|returns? to (him|her|ziggy|mortis)|before returning|also returns"),
    ("pierce", r"pierc|through walls|walk through walls"),
    ("bounce", r"\bbounces?\b"),                                      # not Bibi's "bouncing ball" (its name)
    ("destroys", r"destroy|breaks walls"),
    ("pull", r"\bpull|brings enemies to|to the middle"),
    ("push", r"\bpush|knocks? enemies back|knock"),
    ("slow", r"\bslow"),
    ("stun", r"\bstun|freez"),
    ("silence", r"silence"),
    ("fear", r"fear"),
    ("shield", r"shield|invulnerab|reduces damage taken"),
    ("invisible", r"invisible"),
    ("heal", r"\bheal(s|ing)?\b"),
    ("damage", r"more damage|deal(s|ing)? damage(?! over time)|damages|damaging|maximum damage|double damage|stronger"),
    ("dot", r"damage over time|poison|burns on contact|on fire|\bants\b"),
    ("hp", r"more health|increased health|higher health|stronger porters"),
    ("spray", r"all directions|every direction|around (him|her)\b|in three different directions"),
    ("new_area", r"trail|cloud|leaves .*(area|behind)|steam|lasers|slowing area|time warp|sets the ground"),
)
# cards.csv Type of a hypercharge card -> the claim features its own code (libg, keyed on the card) carries with its Value*
HDESC_CARD = {"overcharge_weapon_spread": ("radius",), "overcharge_weapon_offset": ("radius",), "overcharge_area_radius": ("radius",),
              "overcharge_projectile_scale": ("radius",), "overcharge_reduce_all_damage_while_charging": ("shield",),
              "overcharge_global_slow": ("slow",), "overcharge_slowing_area": ("slow",), "overcharge_projectile_spawn": ("count",),
              "overcharge_more_pets": ("count",), "overcharge_pet_buff_stats": ("hp", "damage", "speed", "radius"),
              "overcharge_attack_pattern_override": ("radius", "spray")}
# a claim's live check: the field of the live audits it maps to (super_audit_hyper.json vs super_audit.json)
DMG_AREAS = ("Damage", "Dot", "DelayedDamage", "DamageAndStatusEffect", "HealAndDamage", "HotAndDot", "DamageDrain", "Pushback", "Stun",
             "CrossSlashGround")   # area types that hit enemies (Effect / StatusEffect rows carry a Damage column that hits no one)
# (range / speed: the audit aims at a fixed distance and records no speed, so neither maps to its move field)
HDESC_LIVE = {"count": "objects", "split": "children", "spray": "projectiles", "damage": "damage", "dot": "damage", "push": "push",
              "pull": "pull", "heal": "heal"}


def _hd_rows():
    from nbpc import diversity as D
    T = _tables()
    if "card" not in T:
        named = lambda f: {r[next(iter(r))]: r for r in D._rows(f) if r[next(iter(r))]}
        T["card"] = named("cards.csv"); T["status"] = named("status_effects_logic.csv"); T["action"] = named("character_actions.csv")
    return T


def hyper_card(name):
    """a brawler's hypercharge card row (cards.csv MetaType 6, Target = the brawler), {} if it has none"""
    return next((r for r in _hd_rows()["card"].values() if r.get("MetaType") == "6" and r.get("Target") == name), {})


def hyper_desc(name):
    """the game's description of the brawler's hypercharge (texts.csv <card TID>_DESC), tags stripped, <VALUEn> filled in from
    the card's Value columns, other placeholders as N"""
    import re
    c = hyper_card(name)
    t = _texts().get((c.get("OverrideDescription") or c.get("TID", "") + "_DESC"), "") if c else ""
    for i, k in ((1, "Value"), (2, "Value2"), (3, "Value3")): t = t.replace("<VALUE%d>" % i, c.get(k) or "N")
    t = re.sub(r"<!?[^<>]*>", lambda m: "N" if m.group(0).startswith("<!") else "", t)
    return re.sub(r"\s+", " ", t.replace("\\n", " ").replace("\\q", '"')).strip()


def desc_claims(text):
    """a description -> its claims [(feature, matched words)], one per feature (HDESC_KEYS order); [("other", text)] when
    no keyword matches. "larger area" is a radius claim, not a new area; an "also"/"now" damage on a new area is dot."""
    import re
    t = text.lower(); out = []
    for f, rx in HDESC_KEYS:
        m = re.search(rx, t)
        if not m: continue
        if f == "new_area" and any(g == "radius" for g, _ in out) and "larger area" in t: continue
        if f == "range" and m.group(0) == "distance" and "max distance" not in t: continue
        out.append((f, m.group(0)))
    return out or ([("other", text[:60])] if text else [])


def _status_kinds(name):
    """status_effects_logic row -> the claim features it carries"""
    s = {a: (v or "").lower() for a, v in _hd_rows()["status"].get(name, {}).items()}; k = set(); nm = name.lower()
    if _num(s, "SpeedReducePercent") > 0 or _num(s, "SpeedReduceAbsolute") > 0 or "slow" in nm: k.add("slow")
    if s.get("FullStun") == "true" or s.get("LosePlayerControl") == "true" or s.get("Stasis") == "true" or "stun" in nm or "freez" in nm: k.add("stun")
    if s.get("Silence") == "true" or "silence" in nm: k.add("silence")
    if "fear" in nm or s.get("Taunt") == "true": k.add("fear")
    if _num(s, "ShieldPercent") > 0 or _num(s, "DamageReducePercent") > 0 or "shield" in nm: k.add("shield")
    if s.get("Invisibility") == "true": k.add("invisible")
    if _num(s, "Healing") > 0: k.add("heal")
    if _num(s, "Damage") > 0: k.add("dot")
    if _num(s, "SpeedBoostPercent") > 0 or _num(s, "SpeedBoostAbsolute") > 0: k.add("speed")
    if s.get("MoveThroughWalls") == "true" or s.get("AttackThroughWalls") == "true": k.add("pierce")
    return k


def effect_tree(sk_name, s, hyper=False):
    """a super's effect rows, followed from its skills.csv row (hyper: the Overcharged* columns of the rows it reaches) ->
    {"skill": row, "proj": [(skin name, skin row, logic row)], "area": [(skin name, logic row)], "item": [(name, row)],
     "summon": [(name, row)], "status": set(names)}"""
    T = _hd_rows(); out = {"skill": s, "proj": [], "area": [], "item": [], "summon": [], "status": set()}; seen = set()
    sp = lambda v: [x for x in (v or "").split(";") if x]
    turns = s.get("BehaviorType") == "ChangeCharacter" or (s.get("BehaviorType") == "Charge" and bool(s.get("SummonedCharacters")))

    def proj(n, d=0):
        if not n or ("p", n) in seen or d > 4: return
        seen.add(("p", n)); sk = T["pskin"].get(n, {}); lg = T["plog"].get(sk.get("LogicProjectile") or n, {})
        out["proj"].append((n, sk, lg))
        for k in ("SpawnAreaEffectObject", "SpawnAreaEffectObject2", "SpawnAreaEffectObjectsAdditional", "SpawnAreaEffectTrail"):
            for a in sp(sk.get(k)): area(a, d + 1)
        for k in ("StatusEffectEnemy", "StatusEffectAlly", "StatusEffectSelfOnHit"): out["status"].update(sp(sk.get(k)))
        if sk.get("SpawnItem"): item(sk["SpawnItem"], d + 1)
        if sk.get("ChainBullet"): proj(sk["ChainBullet"], d + 1)
        if lg.get("SpawnCharacter"): summon(lg["SpawnCharacter"], d + 1)
        for k in ("OnEnemyHitActions", "OnAllyHitActions"):
            for a in sp(lg.get(k)): action(a, d + 1)

    def area(n, d=0):
        if not n or ("a", n) in seen or d > 4: return
        seen.add(("a", n)); lg = T["alog"].get(T["askin"].get(n, {}).get("Logic") or n, {}); out["area"].append((n, lg))
        for k in ("StatusEffectEnemy", "StatusEffectSelf", "StatusEffectAlly"): out["status"].update(sp(lg.get(k)))
        ch = ("OverchargedChainAreaEffect", "OverchargedChainAreaEffect2", "OverchargedChainAreaEffect3")
        for k in ("ChainAreaEffect", "ChainAreaEffect2", "ChainAreaEffect3") + (ch if hyper else ()):
            area(lg.get(k), d + 1)
        for b in sp(lg.get("BulletExplosionBullet")):   # one occurrence per explosion (Grom's second X explosion fires the same row)
            if ("p", b) in seen: out["proj"] += [x for x in out["proj"] if x[0] == b][:1]
            else: proj(b, d + 1)
        for k in ("BulletExplosionItem", "SpawnItem"):
            if lg.get(k): item(lg[k], d + 1)
        for k in ("ActionsSelf", "ActionsAlly", "ActionsEnemy"):
            for a in sp(lg.get(k)): action(a, d + 1)

    def item(n, d=0):
        if not n or ("i", n) in seen or d > 4: return
        seen.add(("i", n)); r = T["item"].get(n, {}); out["item"].append((n, r))
        for k in ("TriggerAreaEffect", "CustomAreaEffect1", "CustomAreaEffect2"): area(r.get(k), d + 1)
        for k in ("StatusEffectAlly", "StatusEffectEnemy"): out["status"].update(sp(r.get(k)))

    def summon(n, d=0):
        if not n or ("c", n) in seen or d > 4: return
        seen.add(("c", n)); c = T["char"].get(n, {}); out["summon"].append((n, c))
        oc = lambda k, ko: (c.get(ko) if hyper and c.get(ko) else c.get(k))
        proj(oc("AutoAttackProjectile", "OverchargedAutoAttackProjectile"), d + 1)
        area(oc("DeathAreaEffect", "DeathOverchargedAreaEffect"), d + 1); area(c.get("AreaEffect"), d + 1)
        w = T["skill"].get(c.get("WeaponSkill"), {})
        if hyper and w.get("OverchargedVersion") in T["skill"]: w = T["skill"][w["OverchargedVersion"]]
        for x in sp(w.get("OverchargedProjectiles") if hyper and w.get("OverchargedProjectiles") else w.get("Projectiles")): proj(x, d + 1)

    def action(n, d=0):
        a = T["action"].get(n, {}); out["status"].update(sp(a.get("StatusEffects")))
        for p in sp(a.get("Projectiles")): proj(p, d + 1)
        for x in sp(a.get("AreaEffects")): area(x, d + 1)

    for p in sp(s.get("Projectiles")): proj(p)
    if hyper and s.get("OverchargedChainProjectile"): proj(s["OverchargedChainProjectile"], 1)
    for k in ("AreaEffectObject", "AreaEffectObject2"): area(s.get(k))
    if s.get("SpawnedItem"): item(s["SpawnedItem"])
    if not turns:
        for c in sp(s.get("SummonedCharacters")): summon(c)
    for k in ("ActivationSelfStatusEffects", "OnChargeHitStatusEffect"):
        out["status"].update(sp(s.get(k + "Overcharged") if hyper and s.get(k + "Overcharged") else s.get(k)))
    return out


def tree_features(tr):
    """effect_tree -> {feature: (value, row that gives it)} for the claim features the tables carry (bigger = more of it)"""
    s = tr["skill"]; P, A, I, C = tr["proj"], tr["area"], tr["item"], tr["summon"]; f = {}
    best = lambda xs: max(xs, key=lambda x: x[0], default=(0.0, ""))
    nb = max(1.0, _num(s, "NumBulletsInOneAttack")); top = len([p for p in (s.get("Projectiles") or "").split(";") if p])
    cnt = top * nb + sum(_num(r, "Value") for n, r in I if _num(r, "Value") > 1) + len(C) * max(1.0, _num(s, "MaxSpawns"))
    cnt += sum(max(1.0, _num(r, "NumBulletsInOneAttack")) for _, c in C for r in [_hd_rows()["skill"].get(c.get("WeaponSkill"), {})])
    f["count"] = (cnt, "%s x%g" % (s.get("Name", ""), nb))
    ba = [n for n, lg in A if lg.get("Type") == "BulletExplosion"]
    f["split"] = (sum(_num(lg, "ChainBullets") + bool(sk.get("ChainBullet")) for n, sk, lg in P) + len(ba) + max(0, len(P) - top),
                  next((n for n, sk, lg in P if _num(lg, "ChainBullets") or sk.get("ChainBullet")), ba[-1] if ba else ""))
    f["radius"] = best([(_num(lg, "Radius"), n) for n, lg in A] + [(_num(lg, "Radius") + _num(sk, "Scale"), n) for n, sk, lg in P]
                       + [(_num(lg, "ScaleEnd"), n) for n, _, lg in P] + [(_num(c, "Scale"), n) for n, c in C])
    f["speed"] = best([(_num(lg, "Speed"), n) for n, _, lg in P] + [(_num(s, "ChargeSpeed"), "ChargeSpeed")] + [(_num(c, "Speed"), n) for n, c in C]
                      + [(1.0, x) for x in tr["status"] if "speed" in _status_kinds(x)])
    f["range"] = best([(_num(s, "CastingRange") * 100 + _num(s, "MaxCastingRange") * 100, "CastingRange")]
                      + [(_num(lg, "DistanceAddFromBounce") * max(1, _num(lg, "MaxDistanceBounces")) + _num(lg, "ChainTravelDistance") * 10, n) for n, _, lg in P])
    f["duration"] = best([(_num(lg, "TimeMs"), n) for n, lg in A] + [(_num(r, "Lifetime"), n) for n, r in I])
    f["homing"] = best([(1.0, n) for n, _, lg in P if lg.get("TravelType") == "4" or lg.get("IsHomingMissile") == "true" or _num(lg, "SteerStrength") > 0])
    f["boomerang"] = best([(_num(lg, "BoomerangType"), n) for n, _, lg in P])
    st = {x: _status_kinds(x) for x in tr["status"]}
    pier = [(sum(lg.get(k) == "true" for k in ("PiercesCharacters", "PiercesEnvironment", "PassesEnvironment", "PiercesEnvironmentLikeButter")), n)
            for n, _, lg in P] + [(1.0, x) for x, ks in st.items() if "pierce" in ks]
    f["pierce"] = (sum(v for v, _ in pier), best(pier)[1])
    f["bounce"] = best([(_num(lg, "MaxDistanceBounces") + (lg.get("IsBouncing") == "true") + _num(lg, "DistanceAddFromBounce") / 1000, n) for n, _, lg in P])
    f["destroys"] = best([(1.0, n) for n, lg in A if "true" in (lg.get("DestroysEnvironment"), lg.get("DestroysDecorations"), lg.get("DestroysOnlyBushes"))]
                         + [(1.0, n) for n, _, lg in P if lg.get("PiercesEnvironmentLikeButter") == "true"])
    push = [(_num(lg, "PushbackStrength"), n) for n, _, lg in P] + [(_num(lg, "PushbackStrength"), n) for n, lg in A if lg.get("Type") != "EdgeCrossing"]
    cp = _num(s, "OverchargedChargePushback") if tr.get("hyper") and s.get("OverchargedChargePushback") else _num(s, "ChargePushback")
    push.append((cp, "ChargePushback"))
    pp = [(v, n) for v, n in push if v > 0]; f["push"] = (sum(v for v, _ in pp), best(pp)[1])   # summed: a second pushing explosion counts
    f["pull"] = best([(-v, n) for v, n in push if v < 0])
    for k in ("slow", "stun", "silence", "fear", "shield", "invisible"):
        f[k] = best([(1.0, x) for x, ks in st.items() if k in ks] + [(_num(lg, "StunTicks") if k == "stun" else 0.0, n) for n, lg in A]
                    + [(_num(lg, "StunLengthMS") if k == "stun" else _num(lg, "SilenceDurationMS") if k == "silence" else 0.0, n) for n, _, lg in P])
    f["shield"] = best([f["shield"]] + [(_num(lg, "MaxOverHeal") + _num(lg, "OverHealTicks"), n) for n, lg in A] + [(_num(s, "ConsumableShieldValue"), "ConsumableShieldValue")])
    boom = lambda lg: 2.0 if _num(lg, "BoomerangType") > 0 else 1.0   # a returning projectile hits again
    f["heal"] = best([(1.0, n) for n, lg in A if lg.get("Type") in HEAL_TYPES]
                     + [((_num(lg, "HealOwnPercent") + _num(lg, "LifeStealPercent")) * boom(lg), n) for n, _, lg in P]
                     + [(_num(s, "HealSelfOnActivationPower"), "HealSelfOnActivationPower")] + [(1.0, x) for x, ks in st.items() if "heal" in ks])
    dmg = [(_num(lg, "Damage") or _num(s, "Damage"), n) for n, lg in A if lg.get("Type") in DMG_AREAS]   # no Damage column: the skill's
    dmg += [(_num(s, "Damage") * boom(lg), n) for n, _, lg in P[:max(1, top)]] or [(_num(s, "Damage"), "Damage")]
    dmg += [(_num(s, "Damage"), n) for n in ba] + [(1.0, x) for x, ks in st.items() if "dot" in ks]
    dmg += [(_num(c, "AutoAttackDamage") + _num(_hd_rows()["skill"].get(c.get("WeaponSkill"), {}), "Damage"), n) for n, c in C]
    f["damage"] = (sum(v for v, _ in dmg), best(dmg)[1])
    f["dot"] = best([(1.0, n) for n, lg in A if lg.get("Type") in DMG_AREAS and _num(lg, "Damage") > 0 and _num(lg, "TimeMs") > 1000]
                    + [(1.0, x) for x, ks in st.items() if "dot" in ks])
    f["hp"] = best([(_num(c, "Hitpoints"), n) for n, c in C])
    f["spray"] = best([(1.0, n) for n, lg in A if lg.get("Type") == "BulletExplosion"] + [(_num(s, "Spread") / 100, "Spread")])
    f["new_area"] = (float(len(A)), A[-1][0] if A else "")
    return f


def _hd_skills(name):
    """(normal (name, row), hypercharged (name, row)) of the brawler whose card it is (its own super, not START_FORM's)"""
    T = _tables(); n = T["char"][name].get("UltimateSkill", "")
    return (n, T["skill"].get(n, {})), hyper_skill(name)


def check_claims(name):
    """the brawler's description claims, each checked against the tables -> [dict(feature, words, data, why, normal, hyper,
    row, card)]: data_ok (the hypercharged rows have more of it; or no row does but the card's own code type carries it:
    card=True, the host runs it only if libg's card code survived), data_contradicts (the tables carry the feature, the
    hypercharged rows have no more of it and the card is a plain overcharge_default / one whose code is for another feature),
    no_data (not a table feature, or only a brawler-specific card type's code, e.g. overcharge_sniper)"""
    (nn, ns), (hn, hs) = _hd_skills(name); c = hyper_card(name); ctype = c.get("Type", "")
    tn = effect_tree(nn, ns); th = effect_tree(hn, hs, hyper=True); th["hyper"] = True
    fn, fh = tree_features(tn), tree_features(th); out = []
    for feat, words in desc_claims(hyper_desc(name)):
        r = {"feature": feat, "words": words, "card": False, "row": ""}
        if feat in fn:
            vn, vh = fn[feat][0], fh[feat][0]; r.update(normal=round(vn, 2), hyper=round(vh, 2), row=fh[feat][1])
            if vh > vn: r.update(data="data_ok", why="%s %g -> %g (%s)" % (feat, vn, vh, fh[feat][1]))
            elif feat in HDESC_CARD.get(ctype, ()):
                r.update(data="data_ok", card=True, why="no row change; card %s %s" % (ctype, "/".join(c.get(k) for k in ("Value", "Value2", "Value3") if c.get(k)) or "-"))
            elif ctype in ("overcharge_default", "") or ctype in HDESC_CARD:
                r.update(data="data_contradicts", why="%s %g -> %g: the hypercharged rows have no more of it (card %s)" % (feat, vn, vh, ctype or "none"))
            else:
                r.update(data="no_data", card=True, why="%s %g -> %g; left to the card's own code %s" % (feat, vn, vh, ctype))
        else:
            r.update(data="no_data", why="not a table feature" + (" (card %s)" % ctype if ctype not in ("overcharge_default", "") else ""),
                     card=ctype not in ("overcharge_default", ""))
        out.append(r)
    return out


def _live_m(rows, name):
    r = rows.get(name)
    if not r or not r.get("attempts"): return None
    return next((a["m"] for a in r["attempts"] if a["class"] == r["class"]), r["attempts"][0]["m"])


def live_claim(claim, mh, mn, name):
    """one claim vs the live audits: mh = the hypercharged run's measurements (super_audit_hyper.json best attempt), mn = the
    normal run's (super_audit.json) or None -> (live_ok / live_wrong / live_unchecked, why). Without a normal run, a count
    compares with the hypercharged table count, and a damage / push / heal the normal super's tables do not expect compares
    with 0"""
    fld = HDESC_LIVE.get(claim["feature"])
    if not fld: return "live_unchecked", "no recorded field"
    if not mh: return "live_unchecked", "no hypercharged run"
    if not mh.get("consumed") or not mh.get("hyper_cast"): return "live_unchecked", "super not cast hypercharged"
    if fld == "heal" and not mh.get("pre_damaged"): return "live_unchecked", "heal not testable (pre-damage missed)"
    n_obj = lambda m: sum(len(m.get(k, [])) for k in ("projectiles", "items", "summons", "areas"))
    # children: a split's parts are projectiles or, from a BulletExplosion area's BulletExplosionItem, items (Tick's minimines)
    get = {"objects": n_obj, "projectiles": lambda m: len(m.get("projectiles", [])),
           "children": lambda m: len(m.get("projectiles", [])) + len(m.get("items", [])), "damage": lambda m: m.get("damage", 0),
           "push": lambda m: m.get("push", 0), "pull": lambda m: m.get("pull", 0), "heal": lambda m: m.get("heal", 0)}[fld]
    vh = get(mh)
    if fld == "pull":   # the normal super never pulls: judged on the hypercharged run alone
        return ("live_ok" if vh >= PUSH_MIN else "live_wrong"), "target pulled %d u nearer the shooter" % vh
    if mn is not None and mn.get("consumed"):
        vn = get(mn); why = "%s %g -> %g (normal run -> hypercharged run)" % (fld, vn, vh)
        if fld == "heal" and vh == vn: return "live_unchecked", why + ": equal, capped by the pre-damage"
        if vh == vn == 0: return "live_unchecked", why + ": none in either run (the setup does not reach it)"
        return ("live_ok" if vh > vn else "live_wrong"), why
    ex = expected(name)["expect"]
    if fld in ("damage", "push", "pull", "heal") and fld not in ex:
        return ("live_ok" if vh > {"damage": 0, "push": PUSH_MIN, "pull": PUSH_MIN, "heal": HEAL_MIN}[fld] - (fld == "damage") else "live_wrong",
                "%s %g (the normal super's tables expect none)" % (fld, vh))
    if fld == "objects" and claim.get("hyper"):
        return ("live_ok" if n_obj(mh) >= claim["hyper"] else "live_wrong"), "%d objects seen, hypercharged tables %g" % (n_obj(mh), claim["hyper"])
    if fld in ("projectiles", "children") and claim.get("hyper", 0) > claim.get("normal", 0):
        top = len([p for p in (hyper_skill(name)[1].get("Projectiles") or "").split(";") if p]) * max(1.0, _num(hyper_skill(name)[1], "NumBulletsInOneAttack"))
        return ("live_ok" if vh > top else "live_wrong"), "%d %s seen, %g fired (children expected)" % (vh, fld, top)
    return "live_unchecked", "no normal run (super_audit.json) to compare %s with" % fld


def hyper_desc_report(live_dirs=()):
    """per brawler with a hypercharge card: its description, claims with the table result and the live result -> rows"""
    import env_v5
    def load(stem):
        for d in live_dirs:
            p = os.path.join(d, stem + ".json")
            if d and os.path.exists(p): return {r["name"]: r for r in json.load(open(p)).get("brawlers", [])}, p
        return {}, None
    hyp, hp = load("super_audit_hyper"); nor, np_ = load("super_audit")
    rows = []
    names = set(env_v5.hyper_brawlers()) | set(env_v5.heroes()) | set(env_v5.forms())
    for b in sorted(names, key=lambda x: (display(x), x)):
        own = hyper_owner(b); lc = (hyp.get(b) or {}).get("class", "not_run")
        if own != b:   # no card of its own: a form (described under its brawler) or no hypercharge at all (no_hyper)
            rows.append({"name": b, "display": display(b), "card": "", "card_type": "", "skill": "", "claims": [],
                         "desc": "form of %s: described under it" % own if own else "no hypercharge card",
                         "status": "form" if own else "no_hyper", "live_class": lc if own or lc == "not_run" else "no_hyper"})
            continue
        cl = check_claims(b); mh, mn = _live_m(hyp, b), _live_m(nor, b)
        for c in cl: c["live"], c["live_why"] = live_claim(c, mh, mn, b)
        rows.append({"name": b, "display": display(b), "card": hyper_card(b).get("Name", ""), "card_type": hyper_card(b).get("Type", ""),
                     "desc": hyper_desc(b), "skill": _hd_skills(b)[1][0], "claims": cl, "status": "card", "live_class": lc})
    return rows, {"hyper_json": hp, "normal_json": np_}


def hyper_desc_markdown(rows, src):
    cnt = collections.Counter(c["data"] for r in rows for c in r["claims"]); lc = collections.Counter(c["live"] for r in rows for c in r["claims"])
    L = ["# Hypercharge descriptions vs data (issue #56)", "",
         "Each brawler's hypercharge text (texts.csv <card TID>_DESC) as claims (`desc_claims`), checked against the tables (normal "
         "super's effect rows vs the hypercharged super's, `check_claims`) and the live audits (`live_claim`: %s vs %s). "
         "card = only the card's own code type carries it (the host runs it only if libg kept that code)." %
         (src.get("hyper_json") or "no super_audit_hyper.json", src.get("normal_json") or "no super_audit.json"), "",
         "Claims: " + ", ".join("%s %d" % kv for kv in sorted(cnt.items())) + "; live: " + ", ".join("%s %d" % kv for kv in sorted(lc.items())), ""]
    bad = [r for r in rows if any(c["data"] == "data_contradicts" or c["live"] == "live_wrong" for c in r["claims"])]
    L += ["## Contradicted by the data or wrong live (%d)" % len(bad), ""]
    line = lambda c: "%s [%s%s, %s]: %s; %s" % (c["feature"], c["data"], " card" if c["card"] else "", c["live"], c["why"], c["live_why"])
    for r in bad:
        L.append("- **%s** (`%s`, %s, live %s): \"%s\"" % (r["display"], r["name"], r["card_type"], r["live_class"], r["desc"]))
        L += ["  - " + line(c) for c in r["claims"] if c["data"] == "data_contradicts" or c["live"] == "live_wrong"]
    nh = [r for r in rows if r["status"] != "card"]
    L += ["", "## No card of their own (%d)" % len(nh), ""] + ["- %s (`%s`): %s, live %s" % (r["display"], r["name"], r["desc"], r["live_class"]) for r in nh]
    L += ["", "## All brawlers with a card", ""]
    for r in rows:
        if r["status"] != "card": continue
        L.append("- %s (`%s`, %s): %s" % (r["display"], r["name"], r["card_type"], "; ".join(
            "%s %s%s/%s" % (c["feature"], c["data"].replace("data_", ""), "(card)" if c["card"] else "", c["live"].replace("live_", "")) for c in r["claims"])))
    return "\n".join(L)


def hyper_desc_main(out, live):
    rows, src = hyper_desc_report([d for d in (live, out, os.environ.get("SIM_WORK", "work")) if d])
    os.makedirs(out, exist_ok=True)
    json.dump({"meta": {**src, "time": time.strftime("%F %T")}, "brawlers": rows}, open(os.path.join(out, "super_audit_hyper_desc.json"), "w"), indent=1)
    md = hyper_desc_markdown(rows, src); open(os.path.join(out, "super_audit_hyper_desc.md"), "w").write(md + "\n")
    cnt = collections.Counter(c["data"] for r in rows for c in r["claims"]); lc = collections.Counter(c["live"] for r in rows for c in r["claims"])
    print("hyper-desc: %d brawlers, %d claims: %s; live: %s; wrote %s/super_audit_hyper_desc.md / .json" % (
        len(rows), sum(cnt.values()), dict(cnt), dict(lc), out))


# ------------------------------------------------------------------ self-check
def _check():
    # classification on synthetic measurements
    base = dict(spawned=True, filled=True, consumed=True, damage=0, move=0, push=0, heal=0, pre_damaged=True, projectiles=[],
                summons=[], areas=[], items=[], changed=False, leaping=False, foreign_near=False)
    m = lambda **k: dict(base, **k)
    assert classify(m(), ["damage"])[0] == "no_effect"
    assert classify(m(push=300, pull=300), ["pull"])[0] == "works" and classify(m(push=780), ["pull"])[:2] == ("partial", ["pull"])   # El Primo hyper: a push is not a pull
    assert classify(m(consumed=False, damage=500), ["damage"])[0] == "not_fired"
    assert classify(m(spawned=False), ["damage"])[0] == "not_fired"
    assert classify({"crashed": True}, ["damage"])[0] == "crash"
    sd = lambda **k: super_dist({"charge": False, "range": 3000.0, **k}, 600.0)
    assert sd() == 0.2 and sd(charge=True) == 0.3 and sd(charge=True, land=True) == 0.2 and sd(ring=600.0) == 0.4 and sd(range=500.0) == 1.0
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
    # --hyper: a brawler with no hypercharge card is no_hyper once its super fired, not partial
    assert classify(m(projectiles=["P"]), ["projectile"], no_hyper=True)[0] == "no_hyper"
    assert classify(m(consumed=False), ["projectile"], no_hyper=True)[0] == "not_fired" and best([{"class": "no_hyper"}, {"class": "not_fired"}])["class"] == "no_hyper"
    # --hyper-desc: the description claim parser (pure) and the live comparison
    fs = lambda t: [f for f, _ in desc_claims(t)]
    assert fs("Piper drops even more bombs as she departs at an increased speed! She also destroys terrain when she lands.") == ["count", "speed", "destroys"]
    assert fs("Belle's spotting shot automatically follows the closest target") == ["homing"]
    assert fs("Bibi's bouncing ball splits when hitting an enemy") == ["split"]   # "bouncing ball" is its name, not a bounce claim
    assert fs("Stick Around has 20% larger area.") == ["radius"] and fs("Bo's Super deploys 5 mines instead of 3.") == ["count"]
    assert fs("Kenji pulls nearby enemies to the middle of his Super") == ["pull"] and fs("Leon stays invisible while attacking his enemies.") == ["invisible"]
    assert fs("Jessie's turret has 50% more health and deals 20% more damage.") == ["damage", "hp"]   # "health" is not a heal claim
    assert fs("Trunk's Super causes them to leave ants on enemies which deal damage over time.") == ["dot"] and fs("Jae is boosted.") == ["other"]
    assert desc_claims("") == []
    hm = m(hyper_cast=True, items=["B"] * 7, damage=900, push=0)
    assert live_claim({"feature": "count"}, hm, m(items=["B"] * 5), "x")[0] == "live_ok"
    assert live_claim({"feature": "count"}, hm, m(items=["B"] * 7), "x")[0] == "live_wrong"
    assert live_claim({"feature": "pull"}, hm, m(push=780), "x")[0] == "live_wrong" and live_claim({"feature": "radius"}, hm, None, "x")[0] == "live_unchecked"
    assert live_claim({"feature": "pull"}, m(hyper_cast=True, push=300, pull=300), m(push=780), "x")[0] == "live_ok"
    assert live_claim({"feature": "push"}, hm, m(), "x")[0] == "live_unchecked"           # nothing in either run: the setup does not reach it
    assert live_claim({"feature": "count"}, m(items=["B"]), m(), "x") == ("live_unchecked", "super not cast hypercharged")
    assert live_claim({"feature": "split"}, m(hyper_cast=True, projectiles=["P"], items=["M"] * 6), m(projectiles=["P"]), "x")[0] == "live_ok"   # Tick's minimines
    # best attempt, descriptions, checklist
    at = [{"class": "no_effect"}, {"class": "works"}]
    assert best(at)["class"] == "works" and best([{"class": "crash"}, {"class": "not_fired"}])["class"] == "not_fired"
    d = describe(m(damage=1960, move=2100, areas=[{"name": "BullSlowArea", "radius": 300}], expect=["move"]), ["push"])
    assert "1960 damage" in d and "moved 2100" in d and "BullSlowArea r300" in d and d.endswith("missing: push"), d
    assert describe(m(consumed=False, attack=True)) == "attack ammo not used"
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
        iid = {r[next(iter(r))]: 18000000 + i for i, r in enumerate(_tables()["rows"][18])}
        assert is_trap(iid["Mine"]) and is_trap(iid["OverchargedMine"]) and not is_trap(iid["BoxOfMines"]) and not is_trap(iid["ClusterMine"])
        assert "MechaDudeBig" in inf and len(env_v5.forms()) == 9 and "MechaDudeBig" not in env_v5.heroes()   # forms audited, never picked
        assert display("BullDude") == "Bull" and data_name(16000000 + list(_tables()["char"]).index("BullDude")) == "BullDude"
        hy = {h: expected(h, hyper=True) for h in ("Jester", "Beamer", "Twins", "Skater", "Domain", "Dancer", "MechaDudeBig", "ShotgunGirl", "PowerLeveler")}
        lh = expected("Luchador", hyper=True)   # El Primo's hypercharged landing pulls
        assert "pull" in lh["expect"] and "push" not in lh["expect"] and "push" in inf["Luchador"]["expect"], lh["expect"]
        assert hy["Jester"]["skill"] == "JesterOverchargedUlti" and "ChesterOverchargedUltiProjectile" in hy["Jester"]["hyper_names"]
        assert {"TwinsHCUltiProjectile", "TwinsPetHyper"} <= set(hy["Twins"]["hyper_names"]) and hy["Twins"]["own_skill"]
        assert hy["Skater"]["hyper_names"] == ["SkaterUltiLandingOvercharged"] and "hyper" in hy["Skater"]["expect"]
        assert hy["Domain"]["hyper_names"] == [] and "hyper" not in hy["Domain"]["expect"] and "hyper_cast" in hy["Domain"]["expect"]
        assert hy["PowerLeveler"]["skill"] == "PowerLevelerUltiOvercharged" and not hy["PowerLeveler"]["own_skill"]
        assert hy["ShotgunGirl"]["skill"] == "ShotgunGirlUlti" and "hyper_cast" in hy["ShotgunGirl"]["expect"]
        assert "hyper_cast" not in inf["Jester"]["expect"]
        at = {h: expected(h, attack=True) for h in ("ShotgunGirl", "TntDude", "Undertaker", "MechaDude", "Rock")}   # --attack: WeaponSkill
        assert at["ShotgunGirl"]["skill"] == "ShotgunGirlWeapon" and at["ShotgunGirl"]["expect"] == ["projectile", "damage"], at["ShotgunGirl"]
        assert at["TntDude"]["throw"] and not at["ShotgunGirl"]["throw"] and {"move", "damage"} <= set(at["Undertaker"]["expect"])
        assert at["MechaDude"]["skill"] == _tables()["char"]["MechaDudeBig"]["WeaponSkill"] and at["Rock"]["expect"] == [], at["Rock"]
        assert hyper_owner("Sniper") == "Sniper" and hyper_owner("MechaDudeBig") == "MechaDude" and hyper_owner("GeishaTransformed") == "Geisha"
        assert hyper_owner("FutureGirl") is None and hyper_owner("KatanaKid") is None and hyper_owner("SuperNovaCactus") is None
        assert expected("FutureGirl", hyper=True).get("no_hyper") and "hyper_cast" not in expected("FutureGirl", hyper=True)["expect"]
        assert not expected("GeishaTransformed", hyper=True).get("no_hyper") and "hyper_cast" in expected("GeishaTransformed", hyper=True)["expect"]
        assert hyper_desc("Sniper").startswith("Piper drops even more bombs") and hyper_desc("Knight") == "Little Helper spawns 5 more rats!"
        cc = {c["feature"]: c for c in check_claims("Sniper")}   # box Value 4 -> 6; the speed and the terrain are the card's own code
        assert cc["count"]["data"] == "data_ok" and "4 -> 6" in cc["count"]["why"] and cc["speed"]["data"] == "no_data" and cc["destroys"]["card"]
        assert [c["data"] for c in check_claims("ElectroSniper")] == ["data_ok"]   # TravelType 4
        k = check_claims("Knight")[0]; assert k["data"] == "data_ok" and k["card"], k   # overcharge_more_pets 5: no row change
        assert {c["feature"]: c["data"] for c in check_claims("Luchador")}["pull"] == "data_ok"   # OverchargedChargePushback -100
        assert all(c["data"] in ("data_ok", "data_contradicts", "no_data") for b in env_v5.hyper_brawlers() for c in check_claims(b))
        ag = area_gadgets()   # --gadget: the host's AREA gadgets, Rosa's WallSpawn left out
        assert {"Barkeep", "DeadMariachi", "Ghost", "Domain", "Meeple", "KickerDude"} <= set(ag) and "Rosa" not in ag, sorted(ag)
        assert all(c // 1000000 == 23 for c, _ in ag.values())
        eb = expected_gadget("ClusterBombDude")   # Tick's: the host also gives the 50 % shield, which observed() cannot see
        assert "ClusterBombDude" in ag and eb["skill"] == "ClusterBombDude_Explosion" and {"area", "damage", "push"} <= set(eb["expect"]) and eb["delay"] == 20, eb
        assert expected_gadget("DeadMariachi")["expect"] == ["area", "heal"] and expected_gadget("Ghost")["expect"] == ["area"]
        kinds = collections.Counter(k for gs in all_gadgets().values() for _, _, k in gs)   # gadget.c's coverage of the enabled cards
        assert sum(kinds.values()) == 213 and kinds["shot"] == 25 and kinds["repeat"] == 4 and "spin" not in kinds, kinds
        assert kinds["item"] == 2 and kinds["heal_now"] == 2 and kinds["super"] == 1 and kinds["skill_area"] == 2, kinds   # Gale's WindWall: item
        assert audit_gadgets(0)["Gunslinger"][1] == "Gunslinger_Reload" and audit_gadgets(1)["Gunslinger"][1] == "Gunslinger_BigBullet"
        assert expected_gadget("Gunslinger")["expect"][:1] == ["projectile"] and expected_gadget("Gunslinger")["gadget_kind"] == "shot"
        assert "BowDude" not in audit_gadgets(0) and audit_gadgets(0)["HookDude"][2] == "repeat"   # Gene's homing hand: repeat (#54 redo)
        assert kinds["auto_aim"] == 1 and audit_gadgets(0)["Sniper"][1:] == ("Sniper_HandGun", "auto_aim"), kinds
        pa = expected_gadget("Sniper")
        assert pa["expect"] == ["projectile", "damage", "push"] and pa["range"] == 2100 and pa["projectiles"] == ["PiperHandgunProjectile"], pa
        assert audit_gadgets(1)["Barkeep"][1] == "Barkeep_HealPotion" and expected_gadget("ElectroSniper")["expect"][:1] == ["item"]
        eh = _expected_gadget("Barkeep", 1)   # the potion: TargetFriends -> a heal, range Range 10 tiles
        assert eh["gadget_kind"] == "repeat" and eh["expect"] == ["projectile", "heal"] and eh["range"] == 3000, eh
        ed = _expected_gadget("TntDude")   # Dynamike's spin: no Range -> CustomValue4
        assert ed["expect"] == ["projectile", "damage"] and ed["range"] == 700 and ed["projectiles"] == ["TntDudeProjectile"], ed
        assert expected_gadget("BullDude", 1)["gadget_kind"] == "skill_area" and "area" in expected_gadget("BullDude", 1)["expect"]
        eg = expected_gadget("ElectroSniper")   # text effects: damage the data did not give goes to text_expect, the unmeasurable to notes
        assert eg["text_expect"] == ["damage"] and "damage" in eg["expect"] and any("slow" in x for x in eg["notes"]), eg
        assert expected_gadget("DeadMariachi")["text_expect"] == [] and any("not checked live" in x and "slow" in x for x in expected_gadget("Ghost")["notes"])
        assert any("slow, stun" in x for x in expected_gadget("BullDude", 1)["notes"])
        assert eg.get("walk_in") and audit_gadgets(0)["Blower"][1:] == ("Blower_Stopper", "item")   # item gadgets: the target walks in
        fg = expected_gadget("FutureGirl")   # Wendy's grenade: thrown, its areas deal no damage -> its skill's Damage is not expected
        assert "damage" not in fg["expect"] and any("thrown" in x for x in fg["notes"]), fg
        assert "damage" in expected_gadget("AssaultShotgun")["expect"]   # Griff's coins land on a damage area: still expected
        assert expected_gadget("Samurai")["expect"] == ["heal"] and "Splitter" not in audit_gadgets(0)
        sp = find_spots(MAP)
        assert len(sp) == 10 and all(len(d) >= 2 for _, _, d in sp), len(sp)
        assert min(max(abs(a[0] - c[0]), abs(a[1] - c[1])) for i, a in enumerate(sp) for c in sp[i + 1:]) >= SPACING * TILE
        assert expected("Baseball")["track"] and expected("Baseball", True)["track"] and expected("ShieldTank")["track"]
        assert not expected("TrickshotDude")["track"] and not expected("ShotgunGirl")["track"]
        assert track_free(1950, 4650, 0, 1) == 0 and track_free(3450, 750, 1, 0) == CORR + 2   # Bibi's ball: on / clear of the track
        assert track_spots(sp[:5], DIST_MAX) and track_spots(sp[5:], DIST_MAX)   # each phase has a spot for it
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
    ap.add_argument("--attack", action="store_true", help="the main attacks: fire each brawler's attack (fire 1) in place of the "
                    "super, expect its WeaponSkill's effects; writes super_audit_attack.json / .md")
    ap.add_argument("--hyper-desc", action="store_true", help="offline (no host): each hypercharge's game description as claims, "
                    "checked against the tables and the live --hyper / normal audits; writes super_audit_hyper_desc.json / .md")
    ap.add_argument("--live", default="", help="--hyper-desc: folder of super_audit.json / super_audit_hyper.json (default --out, "
                    "then $SIM_WORK)")
    a = ap.parse_args()
    if a.check: return _check()
    if a.hyper_desc: return hyper_desc_main(a.out, a.live)
    globals()["WATCH"] = a.watch; globals()["POST_HIT"] = a.post_hit
    import env_v5
    roster, forms = env_v5.heroes(), env_v5.forms()     # forms (Meg's mech, event transforms): never a pick, audited after
    if a.gadget: roster, forms = sorted(b for b in audit_gadgets(a.gadget_slot) if b in roster), []
    names = [x for x in a.only.split(",") if x] or roster + forms
    bad = [x for x in names if x not in _tables()["char"] or (a.gadget and x not in audit_gadgets(a.gadget_slot))]
    if bad: sys.exit(f"unknown brawlers{' (or no implemented gadget in that slot)' if a.gadget else ''}: {bad}")
    au = Auditor(names, n=a.n, retry=not a.no_retry, seed=a.seed, host_args=a.host_args.split(), hyper=a.hyper, gadget=a.gadget,
                 slot=a.gadget_slot, attack=a.attack)
    stem = ("super_audit_gadget" + ("_%d" % (a.gadget_slot + 1) if a.gadget_slot else "")) if a.gadget else "super_audit_hyper" if a.hyper else "super_audit_attack" if a.attack else "super_audit"
    nf = sum(x in forms for x in names)
    au.log(f"{len(names) - nf} brawlers + {nf} forms, {a.n} instances, {au.npair} pairs per phase on {MAP}")
    res = au.run()
    rows = summary(names, res, au.info)
    os.makedirs(a.out, exist_ok=True); jp = os.path.join(a.out, stem + ".json")
    if a.only and os.path.exists(jp):
        old = {r["name"]: r for r in json.load(open(jp)).get("brawlers", [])}
        old.update({r["name"]: r for r in rows}); rows = [old[k] for k in sorted(old)]
    bt = [t / max(k, 1) for k, t in au.timing]
    meta = {"map": MAP, "hyper": a.hyper, "attack": a.attack, "watch_ticks": WATCH, "instances": a.n, "seconds": round(time.time() - au.t0),
            "battles": len(au.timing), "battle_s": round(float(sum(t for _, t in au.timing)), 2),
            "battle_s_per_brawler": round(float(np.mean(bt)), 3) if bt else None, "host_args": a.host_args, "time": time.strftime("%F %T")}
    json.dump({"meta": meta, "brawlers": rows}, open(jp, "w"), indent=1)
    md = markdown(rows, a.hyper)
    if a.gadget: md = md.replace("# Super audit", "# Gadget audit (gadget slot %d, fire 3 in place of the super)" % (a.gadget_slot + 1), 1)
    if a.attack: md = md.replace("# Super audit", "# Main attack audit (fire 1 in place of the super; expected: the WeaponSkill row)", 1)
    open(os.path.join(a.out, stem + ".md"), "w").write(md + "\n")
    print(md)
    au.log(f"wrote {jp} and {stem}.md; {meta['battles']} battles in {meta['battle_s']} s ({meta['battle_s_per_brawler']} s per brawler-attempt)")


if __name__ == "__main__":
    main()
