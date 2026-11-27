"""desc_values: the numbers the game's card descriptions show, computed from the game data (issue #55 step 2). Offline: reads the
game CSVs only, no battle, no torch. desc_audit puts them in its table and compares them with the live audits.

A texts.csv description has two kinds of placeholder:
  <!path>   a path through the data, read left to right: a root, links to other rows, a column, then modifiers.
            Roots: card (the cards.csv row), card.accessory (accessories.csv, the card's Skill), card.character (characters.csv,
            the card's Target). Links (LINKS, by the current row's table): accessory -> skill, statusEffectAlly / Enemy / Self,
            areaEffect, customObjectItem / customObjectProjectile; skill -> projectile (the first of Projectiles),
            summonedCharacter, spawnedItem, areaEffect / areaEffectObject2, activationSelfStatusEffect; projectile ->
            statusEffectEnemy / Ally / SelfOnHit, spawnAreaEffectObject; character -> weaponSkill, areaEffect; area ->
            statusEffect (Enemy, else Ally, else Self) and the three by name; item -> triggerAreaEffect, statusEffectAlly / Enemy.
            Columns: any column of the current row by name, case ignored, plus the aliases in ALIAS (duration = DurationTicks,
            maxHealth = Hitpoints, activeTime = ActiveTicks, an accessory's value1 = CustomValue1, healingTotal = the status's
            total heal, below). Modifiers: scaleToLevel / scaleStatToLevel (the power-LEVEL number, `lvl`), ticksAsSeconds
            (/ 20), msAsSeconds (/ 1000), scaleAccessoryValueN (x the accessory's CustomValueN %), scaleCardValueN (x the card's
            ValueN %), scaleWeaponDamageLevel (x the brawler's weapon Damage at LEVEL %).
            Not resolved (None, with the reason): component / trait / arcade roots (brawler-specific components), and names
            the data has no column for (cactusMinionHealing, maxAmmo).
  <VALUEn>  cards.csv Value / Value2 / Value3 is a code, not the number. For an accessory card (a gadget) libg's description
            builder switches on it: 0x90d5ac, halfword jump table 0x1fc2e0 (index code - 1, target 0x90d548 + 4 x entry), read
            in libg v68.279 with every getter mapped to its column (CODES; the mapping is in notes/desc_values.md). The codes
            not in CODES are not decoded (None). A star power's Value is a number its card type reads in its own code: not
            decoded here (None).

Numbers at power LEVEL (11, the sim's brawlers): libg's level scale is x + (level - 1) * (x / 10) with integer division
(0x90eb00, and inline in the code switch), so 1240 -> 2480 at 11. A status effect's total (0xba5510 damage, 0xba5574
healing) is max(0, DurationTicks / TriggerRate + TriggerOnFirstTick) x Damage (or Healing), or TriggerOnFirstTick x it
when TriggerRate < 1. Integer division truncates toward zero, as in C.

values(card_name) -> [{"ph", "n" (VALUE index or None), "value", "unit", "src", "why"}] for the card's EN description
(value None: not resolved, why says so). fill(card_name) -> the text with each resolved placeholder replaced by its number.
python -m desc_values            every gadget and star power description with its numbers
python -m desc_values --check    the formulas on made-up rows, plus known cards when the game data is there"""
import argparse, functools, re

LEVEL = 11      # the sim's brawlers are power 11 (issue #22: libg's level table gives power-11 HP)
TICK_S = 20     # ticks per second (50 ms ticks)
PH_RE = re.compile(r"<!([^>]+)>|<VALUE_?(\d?)>", re.I)


def _num(x):
    try: return float((x or "0").split(";")[0] or 0)
    except ValueError: return None


def _first(x): return (x or "").split(";")[0]
def _tdiv(a, b): return int(a / b) if b else None       # C integer division (toward zero)
def lvl(x, level=LEVEL): return int(x) + (level - 1) * _tdiv(int(x), 10)   # libg 0x90eb00
def status_total(st, col):
    """libg 0xba5510 (col Damage) / 0xba5574 (col Healing): what the status deals or heals in all"""
    tr = _num(st.get("TriggerRate")) or 0; first = 1 if (st.get("TriggerOnFirstTick") or "").lower() == "true" else 0
    n = max(0, _tdiv(_num(st.get("DurationTicks")) or 0, tr) + first) if tr >= 1 else first
    return n * (_num(st.get(col)) or 0)


# ------------------------------------------------------------------ data
@functools.lru_cache(maxsize=None)
def _t():
    from nbpc import diversity as D
    named = lambda f: {r[next(iter(r))]: r for r in D._rows(f) if r.get(next(iter(r)))}
    cards = {}
    for r in D._rows("cards.csv"):
        if r.get("Name"): cards.setdefault(r["Name"], r)
    return {"card": cards, "acc": named("accessories.csv"), "char": named("characters.csv"), "skill": named("skills.csv"),
            "plog": named("projectiles_logic.csv"), "pskin": named("projectiles_skin.csv"), "alog": named("area_effects_logic.csv"),
            "askin": named("area_effects_skin.csv"), "item": named("items.csv"), "status": named("status_effects_logic.csv")}


@functools.lru_cache(maxsize=None)
def _texts():
    import super_audit as S
    return S._texts()


def _get(row, col):
    """a column by name, case ignored"""
    if not row: return None
    if col in row: return row[col]
    lc = col.lower(); return next((v for k, v in row.items() if k.lower() == lc), None)


def area(name):
    T = _t(); name = _first(name); sk = T["askin"].get(name, {}); lg = T["alog"].get(sk.get("Logic") or name, {})
    return {**sk, **lg, "_t": "area"} if (sk or lg) else None
def proj(name):
    T = _t(); name = _first(name); sk = T["pskin"].get(name, {}); lg = T["plog"].get(sk.get("LogicProjectile") or name, {})
    return {**sk, **lg, "_t": "projectile"} if (sk or lg) else None
def _row(kind, name):
    r = _t()[kind].get(_first(name)) if name else None
    return {**r, "_t": kind} if r else None
def status(name): return _row("status", name)
def skill(name): return _row("skill", name)
def char(name): return _row("char", name)
def item(name): return _row("item", name)


def _area_status(a):
    return status(_get(a, "StatusEffectEnemy") or _get(a, "StatusEffectAlly") or _get(a, "StatusEffectSelf"))


# row kind -> link name (lower case) -> next row
LINKS = {
    "card": {"accessory": lambda r: _row("acc", r.get("Skill")), "character": lambda r: char(r.get("Target"))},
    "acc": {"skill": lambda r: skill(r.get("Skill")), "statuseffectally": lambda r: status(r.get("StatusEffectAlly")),
            "statuseffectenemy": lambda r: status(r.get("StatusEffectEnemy")), "statuseffectself": lambda r: status(r.get("StatusEffectSelf")),
            "areaeffect": lambda r: area(r.get("AreaEffect")), "customobjectitem": lambda r: item(r.get("CustomObject")),
            "customobjectprojectile": lambda r: proj(r.get("CustomObject"))},
    "skill": {"projectile": lambda r: proj(r.get("Projectiles")), "summonedcharacter": lambda r: char(r.get("SummonedCharacters")),
              "spawneditem": lambda r: item(r.get("SpawnedItem")), "areaeffect": lambda r: area(r.get("AreaEffectObject")),
              "areaeffectobject": lambda r: area(r.get("AreaEffectObject")), "areaeffectobject2": lambda r: area(r.get("AreaEffectObject2")),
              "activationselfstatuseffect": lambda r: status(r.get("ActivationSelfStatusEffects"))},
    "projectile": {"statuseffectenemy": lambda r: status(r.get("StatusEffectEnemy")), "statuseffectally": lambda r: status(r.get("StatusEffectAlly")),
                   "statuseffectselfonhit": lambda r: status(r.get("StatusEffectSelfOnHit")),
                   "spawnareaeffectobject": lambda r: area(r.get("SpawnAreaEffectObject"))},
    "char": {"weaponskill": lambda r: skill(r.get("WeaponSkill")), "areaeffect": lambda r: area(r.get("AreaEffect"))},
    "area": {"statuseffect": _area_status, "statuseffectenemy": lambda r: status(r.get("StatusEffectEnemy")),
             "statuseffectally": lambda r: status(r.get("StatusEffectAlly")), "statuseffectself": lambda r: status(r.get("StatusEffectSelf"))},
    "item": {"triggerareaeffect": lambda r: area(r.get("TriggerAreaEffect")), "statuseffectally": lambda r: status(r.get("StatusEffectAlly")),
             "statuseffectenemy": lambda r: status(r.get("StatusEffectEnemy"))},
}
ALIAS = {   # (row kind, path word) -> column; None kind = any row
    (None, "duration"): "DurationTicks", (None, "maxhealth"): "Hitpoints", ("acc", "activetime"): "ActiveTicks",
    ("acc", "value1"): "CustomValue1", ("acc", "value2"): "CustomValue2", ("acc", "value3"): "CustomValue3",
    ("area", "customvalue1"): "CustomValue", ("card", "value1"): "Value", ("card", "value"): "Value",
}
def _link_by_column(row, w):
    """a column whose value names a row of another table (a star card's StatusEffect, Projectile, ...): that row"""
    v = _get(row, w)
    if not v or _num(v) is not None: return None
    for f in (status, area, proj, skill, char, item):
        if f(v): return lambda r, f=f, v=v: f(v)
    return None


UNIT = {"ticksasseconds": "s", "msasseconds": "s"}


def _leaf(kind, row, word):
    """(value, src) of a column word on a row, or (None, why)"""
    if kind == "status" and word == "healingtotal": return status_total(row, "Healing"), "Healing total"
    if kind == "status" and word == "damagetotal": return status_total(row, "Damage"), "Damage total"
    col = ALIAS.get((kind, word)) or ALIAS.get((None, word)) or word
    v = _get(row, col)
    if v is None: return None, f"no column {word} in the {kind} row"
    n = _num(v)
    return (n, col) if n is not None else (None, f"{col} = {v!r} is not a number")


def _modify(v, word, ctx):
    """one modifier; (value, why) with value None when the word is not a modifier this module knows"""
    m = re.fullmatch(r"scale(accessory|card)value(\d)", word)
    if word in ("scaletolevel", "scalestattolevel"): return lvl(v), None
    if word == "ticksasseconds": return v / TICK_S, None
    if word == "msasseconds": return v / 1000.0, None
    if m:
        src = ctx["acc"] if m.group(1) == "accessory" else ctx["card"]
        k = ("CustomValue" if m.group(1) == "accessory" else "Value") + ("" if m.group(1) == "card" and m.group(2) == "1" else m.group(2))
        f = _num(_get(src, k))
        return (v * f / 100.0, None) if f is not None else (None, f"no {k} for {word}")
    if word == "scaleweapondamagelevel":
        w = skill(_get(ctx["char"], "WeaponSkill")); d = _num(_get(w, "Damage")) if w else None
        return (v * lvl(d) / 100.0, None) if d else (None, "no weapon Damage")
    return None, f"modifier {word} not known"


def resolve_path(path, ctx):
    """<!path> -> (value, unit, src, why)"""
    words = [w.lower() for w in path.split(".")]
    if not words or words[0] != "card": return None, "", path, f"root {words[0] if words else ''} not resolved"
    kind, row, src, i = "card", ctx["card"], ["card"], 1
    while i < len(words):
        w = re.sub(r"\[0\]$", "", words[i])
        if "[" in w: return None, "", ".".join(src), f"index {words[i]} not resolved"
        nxt = LINKS.get(kind, {}).get(w) or _link_by_column(row, w)
        if not nxt: break
        r = nxt(row)
        if not r: return None, "", ".".join(src), f"{kind} has no {w} row"
        kind, row = r["_t"], r
        src.append(w); i += 1
    if i >= len(words): return None, "", ".".join(src), "the path ends on a row, not a column"
    v, s = _leaf(kind, row, words[i])
    if v is None: return None, "", ".".join(src), s
    src.append(s); unit = ""
    for w in words[i + 1:]:
        v2, why = _modify(v, w, ctx)
        if v2 is None: return None, unit, ".".join(src), why
        v = v2; unit = UNIT.get(w, unit); src.append(w)
    return v, unit, ".".join(src), None


# ------------------------------------------------------------------ <VALUEn> codes (gadget cards)
def _acc(c, k): return _num(_get(c["acc"], k)) or 0
def _cv(n): return lambda c: _acc(c, f"CustomValue{n}")
def _secs(f): return lambda c: (None if f(c) is None else f(c) / TICK_S)
def _weapon(c): return skill(_get(c["char"], "WeaponSkill")) or {}
def _wdmg(c): return lvl(_num(_get(_weapon(c), "Damage")) or 0)                 # weapon Damage at LEVEL
def _hp(c): return lvl(_num(_get(c["char"], "Hitpoints")) or 0)                  # brawler Hitpoints at LEVEL
def _aarea(c): return area(_get(c["acc"], "AreaEffect")) or {}
def _obj_area(c):   # CustomObject as an area; its ChainAreaEffect when its own Damage is 0 (0x90d548)
    a = area(_get(c["acc"], "CustomObject")) or {}
    if not _num(_get(a, "Damage")) and _get(a, "ChainAreaEffect"): a = area(a["ChainAreaEffect"]) or a
    return a
def _obj_char(c): return char(_get(c["acc"], "CustomObject")) or {}
def _obj_char_area(c): return area(_get(_obj_char(c), "AreaEffect")) or {}   # [?] character data +0xb8 read as AreaEffect
def _obj_proj(c): return proj(_get(c["acc"], "CustomObject")) or {}
def _n(row, k): return _num(_get(row, k)) or 0
def _st(c, k): return status(_get(c["acc"], k)) or {}
def _skill_area_dmg(sk):   # 0x90d7c4: skill data +0xa0 read as AreaEffectObject [?]
    a = area(_get(sk, "AreaEffectObject")) or {}
    return _tdiv(_n(a, "Damage") * _n(a, "CustomValue"), 100) if _n(a, "CustomValue") >= 1 else _n(sk, "Damage")
def _named_area_pct(name): return lambda c: _tdiv(-(_n(area(name) or {}, "Damage") * _hp(c)), 100)   # a heal area's negative Damage % of HP


CODES = {   # code -> (formula(ctx) -> number, unit, what libg reads); the case address is the jump table's target
    **{n: ((lambda n: lambda c: abs(_acc(c, f"CustomValue{n}")))(n), "", f"|CustomValue{n}|") for n in range(1, 7)},
    10: (lambda c: _tdiv(_acc(c, "CustomValue6"), 40), "", "CustomValue6 / 40"),
    11: (lambda c: _tdiv(_acc(c, "CustomValue1"), 100), "", "CustomValue1 / 100"),
    12: (lambda c: abs(_n(area(_get(c["acc"], "PetAreaEffect")) or {}, "Damage")), "", "|PetAreaEffect Damage|"),
    13: (_secs(lambda c: _acc(c, "ActivationDelay")), "s", "ActivationDelay ticks"),
    14: (lambda c: _acc(c, "ShieldPercent"), "", "ShieldPercent"),
    15: (_secs(lambda c: _acc(c, "ShieldTicks")), "s", "ShieldTicks"),
    16: (lambda c: abs(_n(_aarea(c), "Damage")), "", "|AreaEffect Damage|"),
    17: (_secs(lambda c: _n(_aarea(c), "CustomValue")), "s", "AreaEffect CustomValue ticks"),
    18: (lambda c: _tdiv(_acc(c, "ActiveTicks"), _acc(c, "CustomValue1")) if _acc(c, "CustomValue1") >= 1 else None, "", "ActiveTicks / CustomValue1"),
    20: (_secs(lambda c: _acc(c, "ActiveTicks")), "s", "ActiveTicks"),
    22: (_secs(lambda c: _acc(c, "SpeedBoostTicks")), "s", "SpeedBoostTicks"),
    23: (lambda c: abs(_n(_obj_area(c), "Damage")), "", "|CustomObject area Damage|"),
    24: (_secs(_cv(2)), "s", "CustomValue2 ticks"), 25: (_secs(_cv(1)), "s", "CustomValue1 ticks"),
    26: (_secs(lambda c: _n(status(_get(_obj_area(c), "StatusEffectEnemy")) or {}, "DurationTicks")), "s", "CustomObject area's StatusEffectEnemy DurationTicks"),
    27: (lambda c: _tdiv(_acc(c, "CustomValue2"), _n(_weapon(c), "MsBetweenAttacks")), "", "CustomValue2 / weapon MsBetweenAttacks"),
    28: (lambda c: _tdiv(_acc(c, "ActiveTicks"), TICK_S), "", "ActiveTicks / 20"),
    29: (lambda c: _n(_obj_char(c), "Hitpoints"), "", "CustomObject character Hitpoints"),
    30: (_secs(_cv(3)), "s", "CustomValue3 ticks"),
    31: (lambda c: _tdiv(_acc(c, "CustomValue1"), 100) + 1, "", "CustomValue1 / 100 + 1"),
    32: (lambda c: _tdiv(_acc(c, "CustomValue3") * 100, _n(_weapon(c), "CastingRange")), "", "CustomValue3 x 100 / weapon CastingRange"),
    37: (lambda c: int(_n(_aarea(c), "TimeMs") * 0.02) / TICK_S, "s", "AreaEffect TimeMs"),
    38: (lambda c: abs(100 - _tdiv(abs(_acc(c, "CustomValue3") + 100) * abs(_acc(c, "CustomValue4") + 100), 100)), "",
         "100 - (100 + CustomValue3) x (100 + CustomValue4) / 100"),
    39: (lambda c: abs(_n(_obj_char_area(c), "Damage")), "", "|CustomObject character's AreaEffect Damage|"),
    40: (lambda c: abs(_n(_obj_char_area(c), "CustomValue2")), "", "|CustomObject character's AreaEffect CustomValue2|"),
    41: (_secs(lambda c: _n(_obj_proj(c), "SteerLifeTime")), "s", "CustomObject projectile SteerLifeTime"),   # +0x22c, issue #63 (Amber)
    42: (lambda c: int(_n(area(_get(_obj_proj(c), "SpawnAreaEffectObject")) or {}, "TimeMs") * 0.02) / TICK_S, "s",
         "CustomObject projectile's SpawnAreaEffectObject TimeMs"),
    44: (_secs(_cv(4)), "s", "CustomValue4 ticks"),
    45: (lambda c: abs(_n(_obj_char_area(c), "CustomValue")), "", "|CustomObject character's AreaEffect CustomValue|"),
    48: (lambda c: _acc(c, "CustomValue1") + 100, "", "CustomValue1 + 100"),
    **{k: ((lambda n: lambda c: _tdiv(_wdmg(c) * _acc(c, f"CustomValue{n}"), 100))(n), "", f"weapon Damage at power {LEVEL} x CustomValue{n} %")
       for k, n in ((50, 1), (51, 2), (68, 2), (54, 3), (66, 4))},
    52: (_named_area_pct("MinigunDudeTowerBurstHeal"), "", "MinigunDudeTowerBurstHeal heal % of Hitpoints"),
    53: (_named_area_pct("PocoRegenArea"), "", "PocoRegenArea heal % of Hitpoints"),
    55: (lambda c: _tdiv(abs(_n(_aarea(c), "Damage")) * _wdmg(c), 100), "", "|AreaEffect Damage| % of weapon Damage"),
    56: (lambda c: _tdiv(_hp(c) * _acc(c, "CustomValue1"), 100), "", f"Hitpoints at power {LEVEL} x CustomValue1 %"),
    57: (lambda c: _tdiv(_hp(c) * _acc(c, "CustomValue4"), 100), "", f"Hitpoints at power {LEVEL} x CustomValue4 %"),
    58: (_named_area_pct("CactusCoverHeal"), "", "CactusCoverHeal heal % of Hitpoints"),
    59: (lambda c: abs(_tdiv(_hp(c) * _acc(c, "CustomValue2"), 100)), "", f"Hitpoints at power {LEVEL} x |CustomValue2| %"),
    61: (lambda c: _tdiv(abs(_n(_aarea(c), "Damage")) * _hp(c), 100), "", "|AreaEffect Damage| % of Hitpoints"),
    62: (lambda c: _tdiv(abs(_n(_obj_area(c), "Damage")) * _wdmg(c), 100), "", "|CustomObject area Damage| % of weapon Damage"),
    63: (lambda c: _tdiv(abs(_n(_obj_char_area(c), "Damage")) * _wdmg(c), 100), "", "|CustomObject character's AreaEffect Damage| % of weapon Damage"),
    70: (_cv(1), "%", "CustomValue1"),
    71: (lambda c: abs(lvl(_skill_area_dmg(skill(_get(c["acc"], "CustomObject")) or {}))), "",
         "CustomObject skill Damage, or its AreaEffectObject's Damage x CustomValue % when that is set"),
    72: (lambda c: _tdiv(_acc(c, "CustomValue3"), 100), "", "CustomValue3 / 100"),
    73: (lambda c: _tdiv(abs(_n(_aarea(c), "Damage")) * _hp(c), 100), "", "|AreaEffect Damage| % of Hitpoints"),
    74: (lambda c: _tdiv(lvl(status_total(status(_get(area(_get(proj(_get(_weapon(c), "Projectiles")) or {}, "SpawnAreaEffectObject")) or {},
                                                      "StatusEffectEnemy")) or {}, "Damage")) * _acc(c, "CustomValue1"), 100), "",
         "weapon projectile's area status total damage x CustomValue1 %"),
    77: (lambda c: lvl(status_total(_st(c, "StatusEffectEnemy"), "Damage")), "", "StatusEffectEnemy total damage"),
    78: (lambda c: lvl(status_total(_st(c, "StatusEffectAlly"), "Healing")), "", "StatusEffectAlly total healing"),
    79: (_secs(lambda c: _n(status(_get(_aarea(c), "StatusEffectEnemy")) or {}, "DurationTicks")), "s", "AreaEffect's StatusEffectEnemy DurationTicks"),
    80: (_secs(lambda c: _n(_st(c, "StatusEffectEnemy"), "DurationTicks")), "s", "StatusEffectEnemy DurationTicks"),
    81: (lambda c: lvl(_n(skill(_get(c["acc"], "CustomObject")) or {}, "Damage")), "", "CustomObject skill Damage"),
    82: (_secs(lambda c: _n(_st(c, "StatusEffectAlly"), "DurationTicks")), "s", "StatusEffectAlly DurationTicks"),
    83: (lambda c: _n(_st(c, "StatusEffectAlly"), "SpeedBoostPercent"), "", "StatusEffectAlly SpeedBoostPercent"),
    85: (lambda c: lvl(_n(skill(_get(c["acc"], "Skill")) or {}, "Damage")), "", "Skill Damage"),
}
for _a, _b in ((19, 18), (46, 11), (84, 82), (86, 23), (64, 59)): CODES[_a] = CODES[_b]
NO_VALUE = (33, 69)   # the case shows nothing (0x90d5a4)


def value_code(code, ctx):
    """a gadget card's Value code -> (value, unit, src, why)"""
    try: k = int(code)
    except (TypeError, ValueError): return None, "", "", f"no Value code ({code!r})"
    if k in NO_VALUE: return None, "", f"code {k}", "the code shows no number"
    if k not in CODES: return None, "", f"code {k}", f"code {k} not decoded"
    f, unit, src = CODES[k]
    try: v = f(ctx)
    except (TypeError, ZeroDivisionError): v = None
    return (v, unit, f"code {k}: {src}", None) if v is not None else (None, unit, f"code {k}: {src}", "the data it reads is missing")


# ------------------------------------------------------------------ per card
@functools.lru_cache(maxsize=None)
def _card(name):
    """a cards.csv row by its Name, or a gadget card by its accessory (desc_audit's rows name gadgets by accessory)"""
    T = _t()
    return T["card"].get(name) or next((c for c in T["card"].values() if c.get("MetaType") == "5" and c.get("Skill") == name), {})


def ctx_for(card_name):
    T = _t(); c = _card(card_name)
    return {"card": c, "acc": T["acc"].get(c.get("Skill") or "") or {}, "char": char(c.get("Target")) or {}}


def desc(card_name):
    c = _card(card_name)
    return _texts().get(c.get("OverrideDescription") or ((c.get("TID") or "") + "_DESC"), "")


def values(card_name, text=None):
    """the card's description placeholders with their numbers (see the module docstring)"""
    ctx = ctx_for(card_name); c = ctx["card"]; text = desc(card_name) if text is None else text
    gadget = c.get("MetaType") == "5" and (c.get("Type") or "") == "accessory"
    out = []
    for m in PH_RE.finditer(text or ""):
        if m.group(1):
            v, unit, src, why = resolve_path(m.group(1), ctx); n = None
        else:
            n = int(m.group(2) or 1)
            code = c.get("Value" if n == 1 else f"Value{n}")
            if gadget: v, unit, src, why = value_code(code, ctx)
            else: v, unit, src, why = None, "", f"Value{'' if n == 1 else n} {code}", f"{c.get('Type') or 'card'} values are not decoded"
        if v is not None and float(v).is_integer(): v = int(v)
        out.append({"ph": m.group(0), "n": n, "value": v, "unit": unit, "src": src, "why": why, "at": m.start()})
    return out


def fmt(v):
    return "?" if v is None else (str(int(v)) if float(v).is_integer() else f"{v:g}")


def fill(card_name, text=None):
    text = desc(card_name) if text is None else text
    vs = values(card_name, text); out, k = [], 0
    for x in vs:
        out.append(text[k:x["at"]]); out.append(fmt(x["value"]) if x["value"] is not None else x["ph"]); k = x["at"] + len(x["ph"])
    return re.sub(r"</?c[0-9a-f]*>", "", "".join(out) + text[k:])


# ------------------------------------------------------------------ check
def _check():
    assert lvl(1240) == 2480 and lvl(1000) == 2000 and lvl(500) == 1000 and lvl(-10) == -20 and lvl(1235) == 2465
    assert status_total({"DurationTicks": "2", "TriggerOnFirstTick": "TRUE", "Healing": "1600"}, "Healing") == 1600   # no TriggerRate: once
    assert status_total({"DurationTicks": "80", "TriggerRate": "20", "Damage": "100"}, "Damage") == 400
    assert status_total({"DurationTicks": "80", "TriggerRate": "20", "TriggerOnFirstTick": "true", "Damage": "100"}, "Damage") == 500
    assert _tdiv(-7, 2) == -3 and _tdiv(7, 0) is None
    c = {"acc": {"CustomValue1": "-5", "CustomValue2": "40", "CustomValue3": "-20", "CustomValue4": "-20", "CustomValue6": "140", "ActiveTicks": "16"},
         "card": {}, "char": {}}
    assert value_code(1, c)[0] == 5 and value_code(10, c)[0] == 3 and value_code(24, c)[0] == 2.0 and value_code(28, c)[0] == 0
    assert value_code(38, c)[0] == 36              # two 20 % cuts: 100 - 80 x 80 / 100
    assert value_code(19, {**c, "acc": {"ActiveTicks": "16", "CustomValue1": "4"}})[0] == 4   # Bea: 16 / 4 bees
    assert value_code(7, c)[3] and value_code(33, c)[3] and value_code("", c)[3]
    try:
        _t()
    except Exception as e:
        print(f"desc_values: formulas ok; game data not available ({type(e).__name__}), card checks skipped"); return
    v = lambda card, i=0: values(card)[i]["value"]
    # paths
    assert v("BowDude_Totem") == 50                                   # summonedCharacter.areaEffect.customValue1
    assert v("Speedy_Rewind") == 3                                    # spawnAreaEffectObject.timems.msasseconds: 3000 ms
    assert v("HammerDude_Pull") == 2480 and v("AssaultShotgun_Bomb") == 1600   # skill.damage.scaleToLevel
    assert v("Mender_DashHeal") == 2500                               # areaEffectObject2.statusEffect.healingTotal.scaleToLevel
    assert v("Gladiator_Amp") == 3200                                 # spawneditem.statuseffectally.healing.scaletolevel
    assert v("TrickshotDude_ShootAround") == 2000                     # summonedcharacter.maxhealth (not scaled)
    assert v("Shaman_Shield") == 3 and v("Shaman_Shield", 1) == 35    # activeTime.ticksAsSeconds, accessory.value1
    # codes
    assert v("JetpackGirl_DamageTower") == 200                        # 63: the speaker area's 10 % of 2000
    assert v("Ruffs_Cover") == 3 and v("Ruffs_Cover", 1) == 40        # 1 / 4
    assert v("InsectMan_Fly") == 1 and v("InsectMan_Fly", 1) == 660  # 20 ticks; 71: 2200 x 15 % at power 11
    assert v("Sniper_HandGun") == 180 and v("BeeSniper_ExtraBee") == 4 and v("BlackHole_Shadows") == 6   # 50, 19, 30
    print("desc_values: ok")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--check", action="store_true"); ap.add_argument("--card", default="")
    a = ap.parse_args()
    if a.check: return _check()
    T = _t(); n = res = 0
    for name, c in T["card"].items():
        if c.get("MetaType") not in ("4", "5") or not c.get("Target") or (c.get("Disabled") or "").lower() == "true": continue
        if a.card and name != a.card: continue
        vs = values(name)
        if not vs: continue
        n += len(vs); res += sum(x["value"] is not None for x in vs)
        print(f"{name}: {fill(name)}")
        for x in vs: print(f"    {x['ph']:12.80} = {fmt(x['value'])}{x['unit']}   {x['src']}" + (f"   ({x['why']})" if x["why"] else ""))
    print(f"{res} of {n} placeholders resolved")


if __name__ == "__main__":
    main()
