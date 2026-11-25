"""Live check of the star power effects the host re-implements (issue #47, engine/native/loader/starfx.c). One boot, one
small scripted battle per card on Survival642 (no gas, native AI off, spawn protection off): the carrier of the card and a
control of the same brawler without it get the same treatment, and the change is compared with what the card's Value
columns say (cards.csv Value .. Value3; the text is TID_SPEC_ABI_..._DESC). A single Piper bullet (one hit, the same
damage every time at the same distance) is the attacker for the cards that change damage taken:
  reduce_all_damage     Driller_unique_2          every hit costs (1 - V1 %) of the control's
  low_health_shield     BullDude_unique_2         below V1 % hp a hit costs (1 - V2 %); above, the same as the control's
  reduce_damage_full_health  DoorMan_unique       the first hit at full hp costs (1 - V1 %); the next ones the same as the control's
  prey_on_the_weak      Crow_unique_2             the carrier's volley on a target at V2 % hp or less does (1 + V1 %) x the control's
  berserker             BullDude_unique           below V1 % hp the ammo is regained twice as fast; above, the same as the control's
  heal_continuous       AssaultShotgun_unique_2   every V2 ticks the carrier regains V1 % of its missing hp
  steal_souls           Undertaker_unique         a brawler it defeats gives it V1 % of its max hp
  steal_souls2          HammerDude_unique         after defeating a brawler its hits do (1 + V1 %) x for V2 s, then the same again
  speed below hp        TrickshotDude_unique_2    below 40 % hp (its component's Values 40 / 35) the walk is 1 + 35 % faster
and, for the cards libg attaches itself (Traits at spawn; the probe's class "generic"), an A/B on the effect their trait
gives: Gunslinger_unique (Colt +13 % speed, status GunslingerStarPowerMovementSpeed) and PowerLeveler_unique_2 (Surge's
super full at spawn, trait InstantChargeSuperPercentAtStart 100).
LIVE is the list of cards this check confirmed (what star_audit.REIMPL / env_v5.with_star_powers hand out; notes/issue47.md).
python -m star_check            python -m star_check --check   (no game: the judging rules and the card table)
python -m star_check --only Driller_unique_2,DoorMan_unique    (a few cards)"""
import argparse, sys, time, numpy as np

MAP = "Survival642"
TICKS = 2             # ticks per step
DMG_TOL = 0.04        # relative: a hit is truncated to whole hp, a status can add a point
HEAL_TOL = 0.05       # of max hp (a kill heal) / of the missing hp (a periodic heal)
SPEED_TOL = 0.06      # relative: the walked distance quantises to the tick ends (as gear_check)
AMMO_TOL = 0.08       # relative
HITS_MAX = 14         # Piper bullets spent walking a victim down

# the cards this check confirmed in the live battle (2026-11-25, notes/issue47.md): what --star-powers 1 hands out besides
# star_audit.LIVE (the 8 host effects of starfx.c, Trickshot's speed there too, and the 2 trait cards libg runs itself)
LIVE = frozenset({
    "Driller_unique_2", "BullDude_unique_2", "DoorMan_unique", "Crow_unique_2", "BullDude_unique", "AssaultShotgun_unique_2",
    "Undertaker_unique", "HammerDude_unique", "TrickshotDude_unique_2", "Gunslinger_unique", "PowerLeveler_unique_2"})

# name -> (effect, [Value1..Value3] from cards.csv, brawler). The values are READ from cards.csv at run time and compared
# with this table by the self-check: a change of the game data shows up there.
CARDS = {
    "Driller_unique_2": ("reduce_all_damage", (20, 0, 0), "Driller"),
    "BullDude_unique_2": ("low_health_shield", (30, 30, 0), "BullDude"),
    "DoorMan_unique": ("reduce_damage_full_health", (50, 0, 0), "DoorMan"),
    "Crow_unique_2": ("prey_on_the_weak", (50, 30, 0), "Crow"),
    "BullDude_unique": ("berserker", (60, 0, 0), "BullDude"),
    "AssaultShotgun_unique_2": ("heal_continuous", (15, 40, 0), "AssaultShotgun"),
    "Undertaker_unique": ("steal_souls", (20, 0, 0), "Undertaker"),
    "HammerDude_unique": ("steal_souls2", (15, 12, 0), "HammerDude"),
}
GENERIC = {"Gunslinger_unique": ("Gunslinger", 13), "PowerLeveler_unique_2": ("PowerLeveler", 100),   # trait effect: % speed / % super at spawn
           "TrickshotDude_unique_2": ("TrickshotDude", 35)}   # component values 40 / 10 / 35 / 60: +35 % speed below 40 % hp (the text: values[2] / values[0])


def ratio_ok(got, base, want, tol):
    """got / base within tol (relative) of want -> (ok, text)"""
    q = got / base if base else float("nan")
    return bool(base > 0 and abs(q - want) <= tol * want), "%.0f / %.0f = %.3f (want %.3f)" % (got, base, q, want)


def hit_expect(effect, v, hp_before, max_hp, first):
    """the fraction of the control's damage a hit costs the carrier of a damage-taken card, from its Values: hp_before = the
    carrier's hp before the hit, first = the first hit of the battle. -> 1.0 when the card does nothing for this hit"""
    if effect == "reduce_all_damage": return 1 - v[0] / 100
    if effect == "low_health_shield": return 1 - v[1] / 100 if hp_before * 100 < v[0] * max_hp else 1.0
    if effect == "reduce_damage_full_health": return 1 - v[0] / 100 if hp_before >= max_hp else 1.0
    return 1.0


def judge_hits(effect, v, carrier, control, tol=DMG_TOL):
    """carrier / control: [(hp_before, max_hp, lost)] of the same hits (the control takes the plain damage). Hits that killed
    the carrier are not judged (the loss is cut off at 0). -> (ok, text, n reduced hits judged)"""
    bad, n_red, n = [], 0, 0
    d = control[0][2] if control else 0       # the plain damage of one hit (the control's first hit is whole)
    for k, (hb, mx, lost) in enumerate(carrier):
        if lost >= hb: continue                # the hit killed it
        want = hit_expect(effect, v, hb, mx, k == 0); n += 1; n_red += want < 1.0
        if abs(lost - d * want) > tol * d + 1: bad.append((k, hb, lost, round(d * want)))
    return not bad and n > 0, "%d hits judged, %d reduced, plain hit %d%s" % (n, n_red, d, ("; off: %s" % bad) if bad else ""), n_red


def snap(r, p):
    pl = r.pl[p]
    return dict(hp=int(pl.hp), max_hp=int(pl.max_hp), x=float(pl.x), y=float(pl.y), ammo=int(pl.ammo), sc=int(pl.super_charge),
                alive=int(pl.alive), tick=int(r.tick), valid=int(getattr(r, "star_valid", 0)), card=int(r.star_card[p]),
                kind=int(r.star_kind[p]), stat=[int(x) for x in r.star_stat[p]])


def _check():
    import gear_check, env_v5 as E
    assert ratio_ok(1150.0, 1000.0, 1.15, DMG_TOL)[0] and not ratio_ok(1000.0, 1000.0, 1.15, DMG_TOL)[0] and not ratio_ok(1, 0, 1, .1)[0]
    # the per-hit expectation from the Values
    assert hit_expect("reduce_all_damage", (20, 0, 0), 5000, 9000, False) == 0.8
    assert hit_expect("low_health_shield", (30, 30, 0), 2000, 9000, False) == 0.7 and hit_expect("low_health_shield", (30, 30, 0), 3000, 9000, False) == 1.0
    assert hit_expect("reduce_damage_full_health", (50, 0, 0), 9000, 9000, True) == 0.5 and hit_expect("reduce_damage_full_health", (50, 0, 0), 8000, 9000, False) == 1.0
    ok, t, nr = judge_hits("low_health_shield", (30, 30, 0), [(9000, 9000, 2000), (7000, 9000, 2000), (5000, 9000, 2000), (3000, 9000, 2000), (1000, 9000, 1000)],
                           [(9000, 9000, 2000)] * 4)
    assert ok and nr == 0, t       # never below 30 %: nothing reduced, the card did nothing -> n_red 0 (the caller wants >= 1)
    ok, t, nr = judge_hits("low_health_shield", (30, 30, 0), [(9000, 9000, 2000), (2500, 9000, 1400)], [(9000, 9000, 2000)] * 2)
    assert ok and nr == 1, t
    ok, t, nr = judge_hits("low_health_shield", (30, 30, 0), [(9000, 9000, 2000), (2500, 9000, 2000)], [(9000, 9000, 2000)] * 2)
    assert not ok, t
    ok, t, nr = judge_hits("reduce_damage_full_health", (50, 0, 0), [(9000, 9000, 1000), (8000, 9000, 2000)], [(9000, 9000, 2000)] * 2)
    assert ok and nr == 1, t
    # the card table against the game's data: names, Values, the brawler
    from nbpc import diversity as D
    rows = {r["Name"]: r for r in D._rows("cards.csv") if r[next(iter(r))]}
    for n, (eff, v, b) in CARDS.items():
        r = rows[n]; assert r["Type"] == eff and r["Target"] == b, (n, r["Type"], r["Target"])
        got = tuple(int(r.get(c) or 0) for c in ("Value", "Value2", "Value3")); assert got == tuple(v), (n, got, v)
        assert gear_check.card_id(n) in E.star_cards(live_only=False).get(b, []), n
    for n, (b, x) in GENERIC.items(): assert rows[n]["Target"] == b and (rows[n]["Traits"] or rows[n]["Components"]), n
    assert LIVE <= set(CARDS) | set(GENERIC)
    print("star_check self-check ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="the judging rules and the card table (no game)")
    ap.add_argument("--only", default="", help="cards (comma separated) to run; default all")
    ap.add_argument("--log-dir", default=None)
    a = ap.parse_args()
    if a.check: return _check()
    from nbpc.instance import Instance
    from nbpc import proto as P, diversity as D
    import gear_check, env_v5 as E
    want = set(a.only.split(",")) if a.only else set(CARDS) | set(GENERIC)
    bush_xy, opens = gear_check.layout()
    if len(opens) < 6: raise SystemExit("%s: not enough open rows for the layout" % MAP)
    inst = Instance(0, tag="star_check", log_dir=a.log_dir); t0 = time.time(); inst.start(); inst.wait_ready()
    print("host ready in %.0f s" % (time.time() - t0), flush=True)
    fails, ok_cards = [], set()
    cid = gear_check.card_id
    PIPER, SLOT = "Sniper", 9     # the shooter of the damage-taken checks sits in slot 9

    class Bat:
        """one scripted battle: names per slot (10), star cards {slot: card name}"""
        def __init__(self, names, star, seed=7):
            self.names = names + [PIPER] * (10 - len(names)) if len(names) < 10 else names
            div = D.make_div(location=MAP, chr=self.names); div["star"] = {s: cid(n) for s, n in star.items()}
            inst.reset(seed, gas=0, flags=P.F_STATE, native_mask=0, obs_mask=0, div=div)
            self.allp = list(range(10)); self.idle = {i: (-1, 0, 0.0, 0.0) for i in self.allp}
            self.park(self.allp); self.step(k=1)
        def step(self, acts=None, k=TICKS):
            return inst.step(actions={**self.idle, **(acts or {})}, ticks=k, flags=P.F_STATE, native_mask=0)
        def S(self, p): return snap(inst.resp, p)
        def park(self, ps):    # everybody far from the action: run 5's row, 8 tiles of room, spread 300 apart
            x, y = opens[5]; pos = {p: (x - 300 * (i % 8), y) for i, p in enumerate(ps)}
            inst.setup(positions=pos, ai_off=self.allp, unprotect=self.allp)
        def put(self, p, xy): inst.setup(positions={p: xy}); self.step(k=1)

    def need(ok, what):
        (ok_list if ok else fails).append(what); print(("ok   " if ok else "FAIL ") + what, flush=True)
    ok_list = []

    def equip_ok(bt, slot, name):
        s = bt.S(slot); eff = CARDS[name][0]
        need(s["valid"] == 1 and s["card"] == cid(name) and s["kind"] != 0, "%s reached player %d and the host re-implements it (card %d, kind %d)" % (name, slot, s["card"], s["kind"]))
        return s["valid"] == 1 and s["kind"] != 0

    def piper_hit(bt, victim, xy, n_wait=40):
        """Piper (slot 9) stands 600 left of the victim at xy and fires once -> hp lost (0 if no hit in n_wait ticks)"""
        bt.put(victim, xy); bt.put(SLOT, (xy[0] - 600, xy[1])); hp0 = bt.S(victim)["hp"]
        bt.step({SLOT: (-1, 1, 0.0, 0.0)})
        for _ in range(n_wait // TICKS):
            bt.step()
            if bt.S(victim)["hp"] < hp0: break
        return hp0 - bt.S(victim)["hp"]
    # the victim keeps its hp between hits: piper_hit would heal it by the teleport, so the walk below places the pair once
    # and fires again and again

    def walk_down(bt, victim, xy, n):
        """Piper hits the victim n times (or until it dies) with no teleport in between -> [(hp_before, max_hp, lost)]"""
        bt.put(victim, xy); bt.put(SLOT, (xy[0] - 600, xy[1])); out = []
        for _ in range(n):
            s = bt.S(victim)
            if not s["alive"]: break
            hp0 = s["hp"]; t = 0
            while bt.S(SLOT)["ammo"] < 1000 and t < 200: bt.step(); t += TICKS     # reload
            bt.step({SLOT: (-1, 1, 0.0, 0.0)})
            for _ in range(30 // TICKS):
                bt.step()
                if bt.S(victim)["hp"] < hp0: break
            for _ in range(4): bt.step()                                              # the bullet's effects settle
            out.append((hp0, s["max_hp"], hp0 - bt.S(victim)["hp"]))
        return out

    try:
        # ------------------------------------------------------------ damage taken: Driller, Bull, DoorMan
        for name, nhit in (("Driller_unique_2", 3), ("BullDude_unique_2", HITS_MAX), ("DoorMan_unique", 3)):
            if name not in want: continue
            eff, v, br = CARDS[name]
            bt = Bat([br, br], {0: name}); equip_ok(bt, 0, name)
            hc = walk_down(bt, 0, opens[0], nhit); hk = walk_down(bt, 1, opens[1], nhit)
            ok, txt, nred = judge_hits(eff, v, hc, hk)
            ok = ok and nred >= 1 and bt.S(0)["stat"][0] >= nred
            need(ok, "%s (%s %s): %s; host reduced %d hits" % (name, eff, v[:2], txt, bt.S(0)["stat"][0]))
            if ok: ok_cards.add(name)

        def down_to(bt, victim, xy, pct, n=HITS_MAX):
            """Piper hits until the victim's hp is below pct % of its max (or one more hit would kill it) -> its hits"""
            bt.put(victim, xy); bt.put(SLOT, (xy[0] - 600, xy[1])); out = []
            for _ in range(n):
                s = bt.S(victim)
                if not s["alive"] or s["hp"] * 100 < pct * s["max_hp"] or (out and s["hp"] <= 1.3 * out[-1][2]): break
                out += shoot_once(bt, victim)
            return out

        def down_both(bt, pa, xa, pb, xb, pct):
            """two Pipers (slots 9 and 8) hit the victims pa / pb together, each on its own cadence, until both are below pct %
            hp or one more hit would kill one of them -> {victim: its hits}"""
            bt.put(pa, xa); bt.put(pb, xb); bt.put(SLOT, (xa[0] - 600, xa[1])); bt.put(8, (xb[0] - 600, xb[1]))
            out = {pa: [], pb: []}; shooter = {pa: SLOT, pb: 8}
            for _ in range(HITS_MAX):
                todo = [p for p in (pa, pb) if bt.S(p)["alive"] and bt.S(p)["hp"] * 100 >= pct * bt.S(p)["max_hp"]]
                if not todo or any(out[p] and bt.S(p)["hp"] <= 1.3 * out[p][-1][2] for p in todo): break
                t = 0
                while any(bt.S(shooter[p])["ammo"] < 1000 for p in todo) and t < 300: bt.step(); t += TICKS
                hp0 = {p: bt.S(p)["hp"] for p in todo}
                bt.step({shooter[p]: (-1, 1, 0.0, 0.0) for p in todo})
                for _ in range(30 // TICKS):
                    bt.step()
                    if all(bt.S(p)["hp"] < hp0[p] for p in todo): break
                for _ in range(4): bt.step()
                for p in todo: out[p].append((hp0[p], bt.S(p)["max_hp"], hp0[p] - bt.S(p)["hp"]))
            return out

        def shoot_once(bt, victim):
            s = bt.S(victim); hp0 = s["hp"]; t = 0
            while bt.S(SLOT)["ammo"] < 1000 and t < 300: bt.step(); t += TICKS
            bt.step({SLOT: (-1, 1, 0.0, 0.0)})
            for _ in range(30 // TICKS):
                bt.step()
                if bt.S(victim)["hp"] < hp0: break
            for _ in range(4): bt.step()
            return [(hp0, s["max_hp"], hp0 - bt.S(victim)["hp"])]

        def ammo_gain(bt, p):
            """empty p's ammo by firing up (aim 270), then the ammo it regains in 12 ticks"""
            for _ in range(4):
                bt.step({p: (-1, 1, 270.0, 0.0)})
                for _ in range(3): bt.step()
            a0 = bt.S(p)["ammo"]
            for _ in range(6): bt.step()
            return bt.S(p)["ammo"] - a0

        # ------------------------------------------------------------ berserker: Bull reloads twice as fast below V1 % hp
        if "BullDude_unique" in want:
            eff, v, br = CARDS["BullDude_unique"]
            bt = Bat([br, br], {0: "BullDude_unique"}); equip_ok(bt, 0, "BullDude_unique")
            bt.put(0, opens[0]); bt.put(1, opens[1])
            g0, g1 = ammo_gain(bt, 0), ammo_gain(bt, 1)
            ok0, t0_ = ratio_ok(g0, g1, 1.0, AMMO_TOL); need(ok0, "BullDude_unique above %d %% hp: ammo regained %s" % (v[0], t0_))
            hh = down_both(bt, 0, opens[0], 1, opens[1], v[0])
            print("   bull hits %s" % hh, flush=True)
            lo = all(bt.S(p)["alive"] and bt.S(p)["hp"] * 100 < v[0] * bt.S(p)["max_hp"] for p in (0, 1))
            need(lo, "both Bulls below %d %% hp (%d / %d, %d / %d)" % (v[0], bt.S(0)["hp"], bt.S(0)["max_hp"], bt.S(1)["hp"], bt.S(1)["max_hp"]))
            g0, g1 = ammo_gain(bt, 0), ammo_gain(bt, 1)
            ok1, t1_ = ratio_ok(g0, g1, 2.0, AMMO_TOL); need(ok1 and lo and bt.S(0)["stat"][2] > 0, "BullDude_unique below %d %% hp: ammo regained %s" % (v[0], t1_))
            if ok0 and ok1 and lo: ok_cards.add("BullDude_unique")

        # ------------------------------------------------------------ heal_continuous: Griff regains V1 % of the missing hp every V2 ticks
        if "AssaultShotgun_unique_2" in want:
            eff, v, br = CARDS["AssaultShotgun_unique_2"]
            bt = Bat([br, br], {0: "AssaultShotgun_unique_2"}); equip_ok(bt, 0, "AssaultShotgun_unique_2")
            hh = down_both(bt, 0, opens[0], 1, opens[1], 70); h0, h1 = hh[0], hh[1]
            ser = []
            print("   griff hits carrier %s control %s; hp %s %s tick %d" % (h0, h1, bt.S(0)["hp"], bt.S(1)["hp"], bt.S(0)["tick"]), flush=True)
            for _ in range(3 * v[1] + 10):
                bt.step(k=1); ser.append((bt.S(0)["hp"], bt.S(1)["hp"], bt.S(0)["max_hp"], bt.S(0)["tick"]))
            jumps = []   # (tick, jump of the carrier over the control, its missing hp before)
            for k in range(1, len(ser)):
                dj = (ser[k][0] - ser[k - 1][0]) - (ser[k][1] - ser[k - 1][1])
                if dj > 0.03 * (ser[k][2] - ser[k - 1][0]): jumps.append((ser[k][3], dj, ser[k][2] - ser[k - 1][0]))
            print("   griff series (carrier, control) every 10th: %s" % ser[::10], flush=True)
            want_j = [round(m * v[0] / 100) for _, _, m in jumps]
            good = len(jumps) >= 2 and all(abs(dj - w) <= HEAL_TOL * m + 2 for (_, dj, m), w in zip(jumps, want_j)) \
                and all(abs((jumps[i + 1][0] - jumps[i][0]) - v[1]) <= 2 for i in range(len(jumps) - 1))
            need(good and bt.S(0)["stat"][2] >= 2, "AssaultShotgun_unique_2: heals (tick, jump, missing) %s (want %d %% of missing every %d ticks)" % (jumps, v[0], v[1]))
            if good: ok_cards.add("AssaultShotgun_unique_2")

        # ------------------------------------------------------------ prey_on_the_weak: Crow's volley on a target at V2 % hp or less
        if "Crow_unique_2" in want:
            eff, v, br = CARDS["Crow_unique_2"]
            bt = Bat([br, br, "FishTank", "FishTank"], {0: "Crow_unique_2"}); equip_ok(bt, 0, "Crow_unique_2")
            bt.put(2, opens[0]); bt.put(3, opens[1]); bt.put(0, (opens[0][0] - 600, opens[0][1])); bt.put(1, (opens[1][0] - 600, opens[1][1]))
            vol = {0: [], 1: []}      # per tick hp drops of the targets: (hp before, max hp, drop)
            for _ in range(HITS_MAX):
                if not all(bt.S(t)["alive"] for t in (2, 3)): break
                for t in range(300 // TICKS):
                    if bt.S(0)["ammo"] >= 1000 and bt.S(1)["ammo"] >= 1000: break
                    bt.step()
                bt.step({0: (-1, 1, 0.0, 0.0), 1: (-1, 1, 0.0, 0.0)}, k=1)
                last = {c: bt.S(c + 2)["hp"] for c in (0, 1)}
                for _ in range(40):
                    bt.step(k=1)
                    for c in (0, 1):
                        hp = bt.S(c + 2)["hp"]
                        if hp < last[c]: vol[c].append((last[c], bt.S(c + 2)["max_hp"], last[c] - hp, hp)); last[c] = hp
            print("   crow hits carrier's target %s; control's target %s" % (vol[0], vol[1]), flush=True)
            base = sorted({e[2] for e in vol[1] if e[0] * 100 > v[1] * e[1]})   # the control's hit sizes while its target is above V2 %: a volley, a poison tick
            first = vol[1][0][2] if vol[1] else 0
            pairs = [e for e in vol[0] if e[0] * 100 <= v[1] * e[1] and e[3] > 0]    # the carrier's hits on a target at <= V2 % hp that it survived
            hi = [e for e in vol[0] if e[0] == e[1]]
            r_hi = [ratio_ok(e[2], first, 1.0, DMG_TOL) for e in hi[:1]]
            r_lo = []
            for e in pairs:     # a boosted hit is (1 + V1 %) x one of the plain hit sizes
                best = min(base, key=lambda d: abs(e[2] - d * (1 + v[0] / 100)), default=0)
                r_lo.append(ratio_ok(e[2], best, 1 + v[0] / 100, DMG_TOL))
            need(bool(r_hi) and all(o for o, _ in r_hi), "Crow_unique_2 at full hp: first hit %s" % [t for _, t in r_hi])
            need(bool(pairs) and all(o for o, _ in r_lo) and bt.S(0)["stat"][1] > 0, "Crow_unique_2 on a target at <= %d %% hp: hit damage %s (plain hit sizes %s; host boosted %d hits)" % (v[1], [t for _, t in r_lo], base, bt.S(0)["stat"][1]))
            full, pairs = r_hi, r_lo
            if full and pairs and all(o for o, _ in r_hi + r_lo): ok_cards.add("Crow_unique_2")

        # ------------------------------------------------------------ kills: Mortis heals V1 % of its max hp, Frank hits harder
        def kill_setup(bt, hunter, victim, xr):
            """hunter 450 left of the victim on one open run. Piper 8 (right of the victim, aim 180) hits the victim until it is
            below 40 % hp, then two more rounds in which Piper 9 (left of the hunter) hits the hunter too: the victim is low,
            the hunter has missing hp and has not regenerated when the strike comes"""
            rx, ry = xr; bt.put(hunter, (rx - 1350, ry)); bt.put(victim, (rx - 900, ry)); bt.put(8, (rx - 300, ry)); bt.put(SLOT, (rx - 1950, ry))
            out = []
            def rounds(who):
                t = 0
                while any(bt.S(p)["ammo"] < 1000 for p in who) and t < 300: bt.step(); t += TICKS
                hp0 = {p: bt.S(p)["hp"] for p in (victim, hunter)}
                bt.step({8: (-1, 1, 180.0, 0.0), **({SLOT: (-1, 1, 0.0, 0.0)} if SLOT in who else {})})
                for _ in range(40 // TICKS): bt.step()
                for _ in range(4): bt.step()
                out.append(hp0[victim] - bt.S(victim)["hp"])
            for _ in range(HITS_MAX):
                s_ = bt.S(victim)
                if not s_["alive"] or s_["hp"] * 100 < 40 * s_["max_hp"]: break
                rounds((8,))
            for _ in range(2):
                if bt.S(victim)["alive"] and bt.S(victim)["hp"] > 1.3 * (out[-1] if out else 0): rounds((8, SLOT))
            return bt.S(victim)

        def strike(bt, hunter, victim, aim=0.0, wait=24):
            bt.step({hunter: (-1, 1, aim, 0.0)})
            for _ in range(wait // TICKS): bt.step()
            return bt.S(victim)

        if "Undertaker_unique" in want:
            eff, v, br = CARDS["Undertaker_unique"]
            bt = Bat([br, br, "ShotgunGirl", "ShotgunGirl"], {0: "Undertaker_unique"}); equip_ok(bt, 0, "Undertaker_unique")
            res = []
            for h, vi, run in ((0, 2, opens[0]), (1, 3, opens[1])):
                sv = kill_setup(bt, h, vi, run); hb = bt.S(h)["hp"]
                for _ in range(4):
                    if not bt.S(vi)["alive"]: break
                    strike(bt, h, vi)
                res.append((bt.S(h)["hp"] - hb, hb, bt.S(h)["max_hp"], int(bt.S(vi)["alive"]), sv["hp"]))
            gain_c, gain_k = res[0][0], res[1][0]; mx = res[0][2]
            killed = res[0][3] == 0 and res[1][3] == 0
            good = killed and abs((gain_c - gain_k) - mx * v[0] / 100) <= HEAL_TOL * mx and bt.S(0)["stat"][3] >= 1
            need(good, "Undertaker_unique: hp gained on a kill %d vs control %d (want +%d = %d %% of %d; victims dead %s)" % (gain_c, gain_k, mx * v[0] // 100, v[0], mx, killed))
            if good: ok_cards.add("Undertaker_unique")

        if "HammerDude_unique" in want:
            eff, v, br = CARDS["HammerDude_unique"]
            bt = Bat([br, br, "ShotgunGirl", "ShotgunGirl", "FishTank", "FishTank"], {0: "HammerDude_unique"}); equip_ok(bt, 0, "HammerDude_unique")
            def swing(h, tgt):    # the target 400 to the hunter's right, one swing -> the hp it lost
                x, y = bt.S(h)["x"], bt.S(h)["y"]; bt.put(tgt, (x + 400, y)); hp0 = bt.S(tgt)["hp"]; tr = []
                bt.step({h: (-1, 1, 0.0, 0.0)}, k=1)
                for _ in range(30):
                    bt.step(k=1); tr.append(bt.S(tgt)["hp"])
                dd = [a_ - b_ for a_, b_ in zip([hp0] + tr, tr) if a_ != b_]
                # a kill drops a power cube; the target may pick it up (+400 hp): count the drops only
                print("   swing by %d: hp changes %s (max hp %d)" % (h, dd, bt.S(tgt)["max_hp"]), flush=True); return sum(x for x in dd if x > 0)
            res = {}
            for h, vi, tgt, run in ((0, 2, 4, opens[0]), (1, 3, 5, opens[1])):
                kill_setup(bt, h, vi, run)
                for _ in range(4):
                    if not bt.S(vi)["alive"]: break
                    strike(bt, h, vi)
                t_kill = bt.S(h)["tick"]; killed = not bt.S(vi)["alive"]
                d_in = swing(h, tgt)                                       # within V2 s of the kill
                for _ in range((v[1] * 20 + 60) // TICKS): bt.step()        # past V2 seconds (20 ticks a second)
                late = bt.S(h)["tick"] - t_kill
                for _ in range(10): bt.step()
                res[h] = (killed, d_in, swing(h, tgt), late)
            # a kill also drops a power cube (+10 % damage once picked up): each Frank is compared with itself after the buff ended
            ok_in, t_in = ratio_ok(res[0][1], res[0][2], 1 + v[0] / 100, DMG_TOL)
            ok_k, t_k = ratio_ok(res[1][1], res[1][2], 1.0, DMG_TOL)
            need(res[0][0] and ok_in and bt.S(0)["stat"][3] >= 1, "HammerDude_unique: swing within %d s of a kill vs %d ticks after it: %s (kill %s)" % (v[1], res[0][3], t_in, res[0][0]))
            need(res[1][0] and ok_k and res[0][3] > v[1] * 20, "HammerDude_unique control (no card): the same two swings %s" % t_k)
            if res[0][0] and ok_in and ok_k: ok_cards.add("HammerDude_unique")

        # ------------------------------------------------------------ generic cards (libg attaches their Traits itself)
        if "Gunslinger_unique" in want:
            b, pct = GENERIC["Gunslinger_unique"]
            bt = Bat([b, b], {0: "Gunslinger_unique"})
            def walked(p, xy, n=10):
                bt.put(p, xy); pts = [(bt.S(p)["x"], bt.S(p)["y"])]
                for _ in range(n): bt.step({p: (8, 0, 0.0, 0.0)}); pts.append((bt.S(p)["x"], bt.S(p)["y"]))
                bt.step({p: (-1, 0, 0.0, 0.0)}); return float(np.hypot(*np.diff(np.array(pts), axis=0).T).sum())
            w0, w1 = walked(0, opens[0]), walked(1, opens[1])
            ok, txt = ratio_ok(w0, w1, 1 + pct / 100, SPEED_TOL); need(ok, "Gunslinger_unique (trait ColtSpeedSp): walked distance " + txt)
            if ok: ok_cards.add("Gunslinger_unique")
        if "TrickshotDude_unique_2" in want:
            b, pct = GENERIC["TrickshotDude_unique_2"]
            bt = Bat([b, b], {0: "TrickshotDude_unique_2"})
            def walked2(p, n=10):
                pts = [(bt.S(p)["x"], bt.S(p)["y"])]
                for _ in range(n): bt.step({p: (8, 0, 0.0, 0.0)}); pts.append((bt.S(p)["x"], bt.S(p)["y"]))
                bt.step({p: (-1, 0, 0.0, 0.0)}); return float(np.hypot(*np.diff(np.array(pts), axis=0).T).sum())
            bt.put(0, opens[0]); bt.put(1, opens[1]); w0, w1 = walked2(0), walked2(1)
            ok_hi, t_hi = ratio_ok(w0, w1, 1.0, SPEED_TOL); need(ok_hi, "TrickshotDude_unique_2 above 40 %% hp: walked distance %s" % t_hi)
            down_both(bt, 0, opens[0], 1, opens[1], 40)
            bt.put(SLOT, opens[5]); lo = all(bt.S(q)["alive"] and bt.S(q)["hp"] * 100 < 40 * bt.S(q)["max_hp"] for q in (0, 1))
            w0, w1 = walked2(0), walked2(1)
            ok_lo, t_lo = ratio_ok(w0, w1, 1 + pct / 100, SPEED_TOL); need(ok_lo and lo, "TrickshotDude_unique_2 below 40 %% hp (%s): walked distance %s" % (lo, t_lo))
            if ok_hi and ok_lo and lo: ok_cards.add("TrickshotDude_unique_2")
        if "PowerLeveler_unique_2" in want:
            b, pct = GENERIC["PowerLeveler_unique_2"]
            bt = Bat([b, b], {0: "PowerLeveler_unique_2"})
            c0, c1 = bt.S(0)["sc"], bt.S(1)["sc"]
            need(c0 > 0 and c1 == 0, "PowerLeveler_unique_2 (trait InstantChargeSuperPercentAtStart %d): super charge at the start %d vs control %d" % (pct, c0, c1))
            if c0 > 0 and c1 == 0: ok_cards.add("PowerLeveler_unique_2")
    finally:
        inst.close()
    for f in fails[:30]: print("FAIL", f)
    print("confirmed:", sorted(ok_cards))
    assert not fails, "%d failures" % len(fails)
    print("star_check ok")


if __name__ == "__main__":
    sys.exit(main())
