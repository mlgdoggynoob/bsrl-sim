"""desc_audit: the game's own description of each enabled gadget card and star power card against what the host implements
(issue #55 step 1). Offline: reads the game CSVs and texts.csv only, no battle, no torch.

One row per card (gadgets: super_audit.all_gadgets, in card order; star powers: cards.csv MetaType 4, Target set, not
Disabled): brawler, card name and data id, kind, description TID (the card's TID + "_DESC", or its OverrideDescription) and
its EN text with the <VALUEn> placeholders kept, cards.csv Value / Value2 / Value3, the accessories.csv row, and the
CustomObject projectile / area / item rows it uses.
  kind    a gadget's super_audit.gadget_kind (the Python mirror of gadget.c's classify functions; None = the host does not run
          it), also for a super_audit.MASKED row (masked: the kind it classifies as, left unusable); a star power's "live"
          (star_audit.LIVE: the game's own native reader runs it) or "off"
  flags   on rows with a kind (masked gadgets too, so the table shows why they are masked); the others are listed unflagged
    effect  the text names an effect (heal, shield, speed, stun, slow, push, invisible; EFFECT_WORDS) that the host's effect
            set for the kind lacks, or says it deals damage while the host only heals. The host's set comes from the kind
            plus the data it spawns: area -> its area_effects_logic Type / Damage / PushbackStrength / StunTicks; shot,
            repeat, spin -> damage (the host hands the main attack's damage to repeat / spin) plus the projectile's
            PushbackStrength / StunLengthMS / HealOwnPercent / ConsumableShield; heal_now -> heal; super -> super charge.
            Status effects and items run the game's own data ("status" / "item" cover any text effect: not compared).
    aim     the text says closest / nearest / automatic target (AIM_WORDS) and the kind fires along the policy's aim
            (shot, repeat, spin, and skill_area with an AimableArea skill). No kind picks the closest enemy.
    range   the accessory has RequireEnemyInRange or a Range, which no kind reads
    count   the text describes one shot (ONE_WORDS) and the kind fires several, or the text says several (MULTI_WORDS) and
            the kind fires one. Counts: shot NumBulletsInOneAttack, repeat CustomValue1, spin CustomValue1 per volley.
  Star powers: the host runs the game's own reader, so there is nothing of ours to compare; they are never flagged.

python -m desc_audit            summary and flagged rows; writes notes/desc_audit.md
python -m desc_audit --check    flag rules on made-up rows, plus sanity asserts on the real data when the game data is there
flagged(live_only=True) returns the flagged rows (dicts, "flags" a list) for gadget_check."""
import argparse, os, re, sys

# text -> effect category. Each keyword is a regex on the lower-cased EN text.
EFFECT_WORDS = {
    "heal": r"\bheal|restor|regenerat",          # "heals", "healing", "restores", "regenerates"
    "shield": r"\bshield",
    "speed": r"speed boost|movement speed|faster|\bspeed\b|\bhaste",
    "stun": r"\bstun",
    "slow": r"\bslow",
    "push": r"push|knock",                       # "pushing them back", "knocks back"
    "invisible": r"invisib|\bhide|\bhidden",
}
DAMAGE_RE = r"deal\w*\W+(?:\S+\W+){0,3}?damage"  # "dealing <VALUE2> damage"; not "damage taken"
AIM_WORDS = r"closest enemy|nearest|closest target|automatic|auto-?aim"   # the game picks the target
ONE_WORDS = r"\b(?:a|one|single|an)\s+(?:\w+\s+)?(?:shot|projectile|bullet|missile)\b"   # "a defensive shot"
MULTI_WORDS = r"\b(?:shots|projectiles|bullets|bees|volley|missiles|rounds|barrage)\b|<value1>\s+\w*\s*(?:shots|bullets)"
SPLIT_WORDS = r"splits? into.*?\s(?:bullets|projectiles|shots)\b"   # "splits into <n> smaller bullets": one shot that splits on hit, not several
HARM_KINDS = ("repeat", "spin")                  # fire the CustomObject at the main attack's damage (gadget.c attack_dmg)
WILD = {"status", "item"}                        # host data whose effects the game runs: any text effect passes
AIM_KINDS = ("shot", "repeat", "spin")           # fire along the policy's aim (gadget.c shot_fire / repeat_fire / spin_fire)
FLAGS = ("effect", "aim", "range", "count")


def _num(x):
    try: return float((x or "0").split(";")[0] or 0)
    except ValueError: return 0.0


def text_effects(text):
    t = (text or "").lower()
    out = {k for k, rx in EFFECT_WORDS.items() if re.search(rx, t)}
    if re.search(DAMAGE_RE, t): out.add("damage")
    return out


def host_effects(kind, area=None, projs=(), skill=None):
    """the effect categories the host's kind produces, from the data rows it spawns (dicts of CSV columns)"""
    ex = set()
    if kind in ("shot", "repeat", "spin"): ex.add("damage")
    if kind == "skill_area" or kind == "area":
        al = area or {}; ty = al.get("Type") or ""
        if _num(al.get("Damage")) > 0 and ty == "Damage": ex.add("damage")
        if ty in ("Heal", "Hot", "HealRegen", "HealAndDamage", "HotAndDot"): ex.add("heal")
        if ty == "Stun": ex.add("stun")              # KickerDude_Sweep: Type Stun, the stun time in CustomValue
        if ty in ("HealAndDamage", "HotAndDot") and _num(al.get("Damage")) > 0: ex.add("damage")
        if _num(al.get("PushbackStrength")) > 0: ex.add("push")
        if _num(al.get("StunTicks")) > 0 or ty == "HpBasedStun": ex.add("stun")
        if ty in ("StatusEffect", "Cleanse") or al.get("StatusEffectEnemy") or al.get("StatusEffectAlly") or al.get("StatusEffectSelf"): ex.add("status")
    for p in projs:
        if _num(p.get("PushbackStrength")) > 0: ex.add("push")
        if _num(p.get("StunLengthMS")) > 0: ex.add("stun")
        if _num(p.get("HealOwnPercent")) > 0 or _num(p.get("LifeStealPercent")) > 0: ex.add("heal")
        if _num(p.get("ConsumableShield")) > 0: ex.add("shield")
        # the projectile skin's on-hit status effects and spawned areas run the game's own data (merged in by rows())
        if any(p.get(k) for k in ("SpawnCharacter", "OnEnemyHitActions", "StatusEffectEnemy", "StatusEffectAlly", "SpawnAreaEffectObject", "StatusEffectSelfOnHit")): ex.add("status")
    if skill and _num(skill.get("ConsumableShieldValue")) > 0: ex.add("shield")
    if kind == "item": ex.add("item")
    if kind == "heal_now": ex.add("heal")
    if kind == "super": ex.add("super")
    return ex


def host_count(kind, acc=None, skill=None):
    """shots fired per use (None: not a shot kind)"""
    if kind == "shot": return max(1, min(16, int(_num((skill or {}).get("NumBulletsInOneAttack")) or 1)))
    if kind == "repeat": return max(0, min(16, int(_num((acc or {}).get("CustomValue1")))))
    if kind == "spin":   # CustomValue1 shots per volley, a volley every CustomValue3 ms (>= 1 tick) for ActiveTicks (gadget.c spin_volley)
        a = acc or {}; every = max(1, _num(a.get("CustomValue3")) // 50)
        return max(0, min(16, int(_num(a.get("CustomValue1")) * max(1, -(-_num(a.get("ActiveTicks")) // every)))))
    return None


def flags_for(kind, text, acc=None, skill=None, hfx=None, aimable=False):
    """flags of one implemented row (kind not None). hfx: host_effects(); acc: accessories.csv row; skill: the shot's skill"""
    fl = []; te = text_effects(text); hfx = hfx or set(); low = (text or "").lower()
    miss = {e for e in te if e != "damage" and e not in hfx} if not (hfx & WILD) else set()
    harm = "heal" in te and "damage" not in te and kind in HARM_KINDS   # a heal the host fires as main-attack damage (Barley)
    if harm or miss or ("damage" in te and "damage" not in hfx and "status" not in hfx and hfx and "heal" in hfx): fl.append("effect")
    if re.search(AIM_WORDS, low) and (kind in AIM_KINDS or (kind == "skill_area" and aimable)): fl.append("aim")
    a = acc or {}
    if (a.get("RequireEnemyInRange") or "").lower() == "true" or _num(a.get("Range")) > 0: fl.append("range")
    n = host_count(kind, a, skill); low = re.sub(SPLIT_WORDS, "", low)
    if n is not None:
        if re.search(ONE_WORDS, low) and n > 1 or re.search(MULTI_WORDS, low) and n == 1: fl.append("count")
    return fl


def _rows(f):
    from nbpc import diversity as D
    return [r for r in D._rows(f) if r.get(next(iter(r)))]


def _pick(d, **kw):
    return {k: v for k, v in d.items() if v}


def rows():
    """all card rows (dicts), gadgets then star powers"""
    import super_audit as S, star_audit as SA
    T = S._tables(); tx = S._texts()
    acc = {r["Name"]: r for r in _rows("accessories.csv")}
    cards = {}; k = 0; out = []
    from nbpc import diversity as D
    for r in D._rows("cards.csv"):
        if not r[next(iter(r))]: continue
        cards[(r.get("MetaType"), r["Name"])] = (23 * 1000000 + k, r); k += 1
    def desc(r):
        tid = r.get("OverrideDescription") or ((r.get("TID") or "") + "_DESC"); return tid, tx.get(tid, "")
    for b, gs in S.all_gadgets().items():
        for cid, an, kind in gs:
            a = acc.get(an, {}); masked = an in S.MASKED
            if masked and a: kind = S.gadget_kind(a, masked=False)
            r = cards[("5", an)][1] if ("5", an) in cards else next((c for (m, n), (i, c) in cards.items() if i == cid), {})
            tid, text = desc(r)
            obj = (a.get("CustomObject") or "").split(";")[0]
            sk = T["skill"].get(a.get("Skill") or "", {}) if a.get("Skill") else {}
            area = T["alog"].get(T["askin"].get(a.get("AreaEffect"), {}).get("Logic") or a.get("AreaEffect") or "", {})
            projs = []
            pj = lambda p: {**T["pskin"].get(p, {}), **T["plog"].get(T["pskin"].get(p, {}).get("Logic") or p, {})}   # skin + logic columns
            if obj in T["pskin"] or obj in T["plog"]: projs = [pj(obj)]
            if kind == "shot": projs = [pj(p) for p in (sk.get("Projectiles") or "").split(";") if p][:1]
            if kind == "skill_area":
                ao = (sk.get("AreaEffectObject") or ""); area = T["alog"].get(T["askin"].get(ao, {}).get("Logic") or ao, {})
            it = T["item"].get(obj, {}) if kind == "item" else {}
            hfx = host_effects(kind, area, projs, sk) if kind else None
            fl = flags_for(kind, text, a, sk, hfx, sk.get("BehaviorType") == "AimableArea") if kind else []
            out.append({"type": "gadget", "brawler": b, "card": an, "id": cid, "kind": kind, "masked": masked, "tid": tid, "text": text,
                        "values": [r.get("Value", ""), r.get("Value2", ""), r.get("Value3", "")], "accessory": _pick(a),
                        "data": {"projectile": _pick(projs[0]) if projs else {}, "area": _pick(area), "item": _pick(it), "skill": _pick(sk)},
                        "host_effects": sorted(hfx or ()), "host_count": host_count(kind, a, sk) if kind else None, "flags": fl})
    k = 0
    for r in D._rows("cards.csv"):
        if not r[next(iter(r))]: continue
        if r.get("MetaType") == "4" and r.get("Target") and (r.get("Disabled") or "").lower() != "true":
            tid, text = desc(r); live = r["Name"] in SA.LIVE
            out.append({"type": "star", "brawler": r["Target"], "card": r["Name"], "id": 23 * 1000000 + k, "kind": "live" if live else "off", "masked": False,
                        "tid": tid, "text": text, "values": [r.get("Value", ""), r.get("Value2", ""), r.get("Value3", "")],
                        "accessory": {}, "data": {"type": r.get("Type", ""), "projectiles": r.get("Projectiles", "")}, "host_effects": [], "host_count": None, "flags": []})
        k += 1
    return out


def flagged(live_only=True):
    """the rows with at least one flag (live_only: gadgets the host runs, not masked; star powers never flag)"""
    return [r for r in rows() if r["flags"] and (not live_only or r["kind"] not in (None, "off") and not r["masked"])]


def markdown(rs):
    L = ["# desc_audit: card descriptions vs the host", "", "Generated by `python -m desc_audit` (do not edit by hand). Flags: " + ", ".join(FLAGS) + ".", "",
         "| brawler | card | kind | flags | text | Value / 2 / 3 | host effects | host count | accessory | data |", "|---|---|---|---|---|---|---|---|---|---|"]
    cell = lambda x: str(x).replace("|", "\\|").replace("\n", " ")
    for r in rs:
        acc = ", ".join(f"{k}={v}" for k, v in r["accessory"].items() if k in ("Type", "SubType", "Range", "RequireEnemyInRange", "CustomObject", "CustomValue1", "CustomValue2", "CustomValue3", "CustomValue4", "AreaEffect", "Skill", "ActiveTicks"))
        d = "; ".join(f"{k}: " + ", ".join(f"{a}={b}" for a, b in v.items() if a in ("Type", "Damage", "Radius", "PushbackStrength", "StunLengthMS", "StunTicks", "HealOwnPercent", "NumBulletsInOneAttack", "BehaviorType", "Projectiles", "AreaEffectObject")) if isinstance(v, dict) and v else f"{k}: {v}" for k, v in r["data"].items() if v)
        L.append("| " + " | ".join(cell(x) for x in (r["brawler"], f"{r['card']} ({r['id']})", r["kind"] + (" (masked)" if r["masked"] else "") if r["kind"] else r["kind"], " ".join(r["flags"]), f"{r['tid']}: {r['text']}",
                 "/".join(v or "-" for v in r["values"]), " ".join(r["host_effects"]), r["host_count"] if r["host_count"] is not None else "", acc, d)) + " |")
    return "\n".join(L) + "\n"


def _check():
    ok = lambda kind, text, **kw: flags_for(kind, text, **kw)
    # effect: a heal text on a damage shot; damage text on a heal
    assert "effect" in ok("shot", "Throws a healing potion", hfx=host_effects("shot"))
    assert "effect" not in ok("shot", "Fires a shot dealing <VALUE1> damage", hfx=host_effects("shot"))
    assert "effect" in ok("heal_now", "Deals <VALUE1> damage to enemies", hfx=host_effects("heal_now"))
    assert "effect" not in ok("heal_now", "Heals 60% of the damage taken", hfx=host_effects("heal_now"))
    assert "effect" not in ok("area", "Slows enemies", hfx=host_effects("area", {"Type": "StatusEffect"}))
    assert "effect" in ok("area", "Stuns enemies", hfx=host_effects("area", {"Type": "Damage", "Damage": "100"}))
    # aim
    assert "aim" in ok("repeat", "Pops a shot at the closest enemy", hfx={"damage"}, acc={"CustomValue1": "5"})
    assert "aim" not in ok("area", "Hits the closest enemy", hfx={"damage"})
    # range
    assert "range" in ok("shot", "x", acc={"RequireEnemyInRange": "true"}, hfx=set())
    assert "range" not in ok("shot", "x", acc={}, hfx=set())
    # count
    assert "count" in ok("repeat", "Pops a defensive shot", acc={"CustomValue1": "5"}, hfx={"damage"})
    assert "count" in ok("shot", "Fires shots in a row", skill={"NumBulletsInOneAttack": "1"}, hfx={"damage"})
    assert "count" not in ok("shot", "Fires a shot", skill={"NumBulletsInOneAttack": "1"}, hfx={"damage"})
    assert "count" not in ok("shot", "Fires a big bullet that splits into <VALUE1> smaller bullets", skill={}, hfx={"damage"})
    assert "count" not in ok("spin", "Sprays a barrage of shots", acc={"CustomValue1": "1", "CustomValue3": "125", "ActiveTicks": "15"}, hfx={"damage"})
    # a heal the host fires as main-attack damage (repeat / spin), even when the projectile's own data heals
    assert "effect" in ok("repeat", "Throws a healing potion at allies", acc={"CustomValue1": "5"}, hfx={"damage", "status"})
    assert "stun" in host_effects("area", {"Type": "Stun"})
    try:
        rs = rows()
    except Exception as e:
        print(f"desc_audit: flag rules ok; game data not available ({type(e).__name__}), real-data checks skipped"); return
    g = [r for r in rs if r["type"] == "gadget"]
    assert g and len({r["card"] for r in g}) == len(g)
    pi = next(r for r in g if r["card"] == "Sniper_HandGun")
    assert "closest enemy" in pi["text"] and pi["kind"] == "repeat" and {"aim", "count", "range"} <= set(pi["flags"]), pi["flags"]
    # Barley's healing potion: a repeat_shot whose projectile spawns the heal area; the host also fires 5 damage shots
    # at the main attack's damage and ignores its Range / RequireEnemyInRange, so the row must be flagged
    bp = next(r for r in g if r["card"] == "Barkeep_HealPotion")
    assert "healing potion" in bp["text"] and bp["kind"] == "repeat" and "effect" in bp["flags"], bp["flags"]
    assert bp["masked"] and bp not in flagged() and any(r["card"] == bp["card"] for r in flagged(live_only=False))
    for c in ("KickerDude_Sweep", "BarrelBot_Spin", "TrickshotDude_BounceHeal"):   # rules that once flagged them wrongly
        assert not next(r for r in g if r["card"] == c)["flags"], c
    assert all(not r["flags"] for r in rs if r["kind"] in (None, "off"))
    print(f"desc_audit: ok ({len(rs)} rows, {len(flagged())} flagged)")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--check", action="store_true"); a = ap.parse_args()
    if a.check: return _check()
    rs = rows(); fl = [r for r in rs if r["flags"]]
    gd = [r for r in rs if r["type"] == "gadget"]; st = [r for r in rs if r["type"] == "star"]
    print(f"{len(gd)} gadget rows ({sum(r['kind'] is not None for r in gd)} implemented), {len(st)} star rows ({sum(r['kind'] == 'live' for r in st)} live); {len(fl)} flagged")
    for r in fl: print(f"  {r['brawler']:15} {r['card']:28} {r['kind']:10} {' '.join(r['flags'])}" + ("   (masked)" if r["masked"] else ""))
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notes", "desc_audit.md")
    open(p, "w", encoding="utf-8").write(markdown(rs)); print("wrote", p)


if __name__ == "__main__":
    main()
