"""Live check of hypercharge (issue #4): one boot, one scripted battle (10 of --brawler, default Shelly, no gas, native AI off), players 1 and 3
with their hypercharge card (div "hyper"), 2 and 4 without; 1 / 2 shoot at 5 / 6, which shoot back. In order:
  1. the host publishes hypercharge state (NbeResp hyp_valid), the card reached players 1 and 3 and no one else, with the
     brawler's characters.csv buff percents;
  2. charging: player 1 shoots 5 once; its charge (NbePlayer.reserved[0]) grows (libg's own charging, card holders
     only); player 2 (no card) is reported;
  3. fire 4 with a part-full charge does nothing;
  4. the charges are filled (SETUP hyper_fill), fire 4 for 1 and 2: 1 becomes active (hyp_left ~ 100 ticks), 2 (no card)
     does not; env_v5.Env.hyper (obs_v5 self 4) agrees with the response at every step;
  5. while active: 1 walks SPEED_TOL-close to (1 + speed%) x the distance it walked in the same ticks before, shot damage
     is (1 + damage%) x 2's, and damage taken (5 shoots 1, 6 shoots 2) is (1 - shield%) x 2's;
  6. the hypercharge ends after max / 40 ticks (+-2), the charge is 0, and 1 walks at its normal speed again;
  7. supers (both filled, healed targets 1 tile away): 1 hypercharges (fire 4) then fires its super at 5, 2 fires its
     normal super at 6 in the same ticks; the target HP lost (or the shooter's damage_dealt, summed) over super_audit.WATCH
     ticks must be > 0 for 2 and at least as much for 1 (`super_ok`, no tolerance below: the hypercharge adds damage).
     A dud hypercharged super (Piper's bombs that never explode) fails here: python -m hyper_check --brawler Piper.
     Aim and super_dist as super_audit's (`super_dist`); a super steered while it runs (FlyJump, Ww) is not walked here.
python -m hyper_check [--brawler Piper]            python -m hyper_check --check   (no game: the judging rules)"""
import argparse, sys, time, numpy as np
P = None   # nbpc.proto, imported in main / _check (the self-check needs no host)

SPEED_TOL = 0.06   # relative: the walked distance quantises to the move re-sends (env.c 225-unit rule) and tick ends
DMG_TOL = 0.02     # relative: each pellet's damage is scaled and truncated on its own
END_TOL = 2        # ticks: the drain runs after each tick, responses come every TICKS ticks
TICKS = 2          # ticks per step


def snap(r, p):
    """the fields of player p this check compares, copied out of the (live, shared-memory) response r"""
    pl = r.pl[p]
    return dict(valid=int(getattr(r, "hyp_valid", 0)), card=int(r.hyp_card[p]), left=int(r.hyp_left[p]), used=int(r.hyp_used[p]),
                dmg=int(r.hyp_damage_pct[p]), speed=int(r.hyp_speed_pct[p]), shield=int(r.hyp_shield_pct[p]),
                charge=int(pl.reserved[0]), max=int(pl.reserved[1]), x=float(pl.x), y=float(pl.y), hp=int(pl.hp),
                tick=int(r.tick), alive=int(pl.alive), out=int(pl.eliminated or pl.reserved[3] > 0))


def ready(s):
    """the rule env_v5.hyper_ready applies to the response"""
    return bool(s["valid"] and s["card"] and s["left"] <= 0 and s["max"] > 0 and s["charge"] >= s["max"] and s["alive"] and not s["out"])


def ratio_ok(got, base, want, tol):
    """got / base within tol (relative) of want -> (ok, text)"""
    q = got / base if base else float("nan")
    return bool(base > 0 and abs(q - want) <= tol * want), "%.0f / %.0f = %.3f (want %.3f)" % (got, base, q, want)


def end_ok(active_ticks, mx, drain=40):
    want = mx / drain
    return abs(active_ticks - want) <= END_TOL, "active %d ticks (want %.0f)" % (active_ticks, want)


def super_ok(hyper, normal):
    """the hypercharged super's damage to its target is at least the normal super's -> (ok, text); a normal super that
    dealt nothing (not fired, out of range) fails too, since then the comparison says nothing"""
    txt = "hypercharged %d vs normal %d" % (hyper, normal) + ("" if normal > 0 else " (the normal super dealt none)")
    return bool(normal > 0 and hyper >= normal), txt


def _check():
    base = dict(valid=1, card=23000777, left=0, used=0, dmg=5, speed=20, shield=5, charge=4000, max=4000, x=0.0, y=0.0,
                hp=7800, tick=100, alive=1, out=0)
    s = lambda **o: {**base, **o}
    assert ready(s()) and not ready(s(valid=0)) and not ready(s(card=0)) and not ready(s(left=50)) and not ready(s(charge=3999))
    assert not ready(s(max=0, charge=0)) and not ready(s(alive=0)) and not ready(s(out=1))
    assert ratio_ok(1200.0, 1000.0, 1.2, SPEED_TOL)[0] and not ratio_ok(1000.0, 1000.0, 1.2, SPEED_TOL)[0]
    assert not ratio_ok(5.0, 0.0, 1.0, SPEED_TOL)[0]
    assert ratio_ok(3150.0, 3000.0, 1.05, DMG_TOL)[0] and not ratio_ok(3000.0, 3000.0, 1.05, DMG_TOL)[0]
    assert end_ok(100, 4000)[0] and end_ok(102, 4000)[0] and not end_ok(110, 4000)[0] and not end_ok(10**6, 4000)[0]
    assert super_ok(3780, 3600)[0] and super_ok(3600, 3600)[0] and not super_ok(3599, 3600)[0] and not super_ok(0, 3600)[0]
    assert not super_ok(0, 0)[0] and not super_ok(500, 0)[0]
    print("hyper_check self-check ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="the judging rules on made-up responses (no game)")
    ap.add_argument("--log-dir", default=None)
    ap.add_argument("--brawler", default="ShotgunGirl")
    a = ap.parse_args()
    if a.check: return _check()
    global P
    from nbpc.instance import Instance
    from nbpc import proto, diversity as D
    import env_v5 as E
    P = proto
    names = [a.brawler] * 10; fails = []; info = []
    HC, NC, T1, T2 = 1, 2, 5, 6          # hypercharged player, its no-card control, their targets (3 / 4: card / no card, idle)
    inst = Instance(0, tag="hyper_check", log_dir=a.log_dir); t0 = time.time(); inst.start(); inst.wait_ready()
    print("host ready in %.0f s" % (time.time() - t0), flush=True)

    def need(ok, what):
        (info if ok else fails).append(what); print(("ok   " if ok else "FAIL ") + what, flush=True)

    try:
        div = D.make_div(location="Survival651", chr=names); div["hyper"] = [HC, 3]
        inst.reset(5, gas=0, flags=P.F_STATE, native_mask=0, obs_mask=0, div=div)
        allp = list(range(10)); idle = {i: (-1, 0, 0.0, 0.0) for i in allp}

        def stp(acts=None, k=TICKS):
            r = inst.step(actions={**idle, **(acts or {})}, ticks=k, flags=P.F_STATE, native_mask=0)
            for p in (HC, NC):                       # Env.hyper's rule = the response's, at every step
                if E.hyper_ready(r, p) != ready(snap(r, p)): fails.append("step %d: hyper_ready(%d) disagrees" % (r.tick, p))
            return r
        # 1 / 2 face their targets 300 units to the right (aim 0 degrees); the targets aim back (180)
        pos = {HC: (9000, 17400), T1: (9300, 17400), NC: (9000, 600), T2: (9300, 600), 3: (3000, 9000), 4: (15000, 9000)}
        for p in (0, 7, 8, 9): pos[p] = (1500 + 1500 * (p % 4), 3000 if p < 8 else 15000)
        inst.setup(positions=pos, ai_off=allp, unprotect=allp)
        r = stp(k=1)
        h = {p: snap(r, p) for p in allp}
        need(h[HC]["valid"] == 1, "host publishes hypercharge state (hyp_valid %d)" % h[HC]["valid"])
        if not h[HC]["valid"]: raise SystemExit("rebuild the host with native/loader/hyper.c (SETUP.md)")
        cards = [p for p in allp if h[p]["card"]]
        need(cards == [HC, 3], "card on players %s (want [%d, 3]), card id %d" % (cards, HC, h[HC]["card"]))
        need(h[HC]["speed"] > 0 and h[HC]["dmg"] > 0 and h[HC]["shield"] > 0,
             "buffs speed +%d%%, damage +%d%%, shield %d%%" % (h[HC]["speed"], h[HC]["dmg"], h[HC]["shield"]))
        # 2. charging by damage (libg's own, OverchargeChargeMul)
        c0 = (h[HC]["charge"], h[NC]["charge"])
        r = stp({HC: (-1, 1, 0.0, 0.0), NC: (-1, 1, 0.0, 0.0)})   # one shot each (the targets must live through the checks below)
        for _ in range(8): r = stp()
        c1 = (snap(r, HC)["charge"], snap(r, NC)["charge"])
        need(c1[0] > c0[0], "charge from hits: card %d -> %d of %d; no card %d -> %d" % (c0[0], c1[0], snap(r, HC)["max"], c0[1], c1[1]))
        # 3. not full: fire 4 does nothing
        if c1[0] < snap(r, HC)["max"]:
            r = stp({HC: (-1, 4, 0.0, 0.0)}); s = snap(r, HC)
            need(s["left"] == 0 and s["used"] == 0, "fire 4 at charge %d/%d: not activated" % (s["charge"], s["max"]))
        # baseline walk (inactive), back, then fill and activate
        inst.setup(positions={HC: (9000, 17400), NC: (9000, 600)}); stp(k=1)
        def walk(p, d, n=4):
            x0 = snap(inst.resp, p)["x"]
            for _ in range(n): r = stp({p: (d, 0, 0.0, 0.0)})
            r = stp({p: (-1, 0, 0.0, 0.0)}); return abs(snap(r, p)["x"] - x0)
        base = walk(HC, 8)   # move_dir 8 = 180 degrees (left, away from the target)
        inst.setup(positions={HC: (9000, 17400), NC: (9000, 600), T1: (9300, 17400), T2: (9300, 600)}, hyper_fill=[HC, NC]); stp(k=1)
        r = stp({HC: (-1, 4, 0.0, 0.0), NC: (-1, 4, 0.0, 0.0)}); t_on = int(r.tick); s1, s2 = snap(r, HC), snap(r, NC)
        need(s1["left"] > 0 and s1["used"] == 1, "fire 4 at a full charge: active, %d ticks left" % s1["left"])
        need(s2["left"] == 0 and s2["used"] == 0, "fire 4 without a card: not active")
        r = stp({HC: (-1, 4, 0.0, 0.0)}); need(snap(r, HC)["used"] == 1, "fire 4 while active: no second activation")
        # 5. buffs
        fast = walk(HC, 8); ok, txt = ratio_ok(fast, base, 1 + s1["speed"] / 100, SPEED_TOL); need(ok, "speed while active: " + txt)
        inst.setup(positions={HC: (9000, 17400), NC: (9000, 600), T1: (9300, 17400), T2: (9300, 600)}); stp(k=1)
        hp0 = (snap(inst.resp, T1)["hp"], snap(inst.resp, T2)["hp"])
        r = stp({HC: (-1, 1, 0.0, 0.0), NC: (-1, 1, 0.0, 0.0)})
        for _ in range(6): r = stp()
        d1, d2 = hp0[0] - snap(r, T1)["hp"], hp0[1] - snap(r, T2)["hp"]
        ok, txt = ratio_ok(d1, d2, 1 + s1["dmg"] / 100, DMG_TOL); need(ok, "damage dealt while active: " + txt)
        hp0 = (snap(r, HC)["hp"], snap(r, NC)["hp"])
        r = stp({T1: (-1, 1, 180.0, 0.0), T2: (-1, 1, 180.0, 0.0)})
        for _ in range(6): r = stp()
        d1, d2 = hp0[0] - snap(r, HC)["hp"], hp0[1] - snap(r, NC)["hp"]
        ok, txt = ratio_ok(d1, d2, 1 - s1["shield"] / 100, DMG_TOL); need(ok, "damage taken while active: " + txt)
        # 6. the end
        t_off = None
        for _ in range(200):
            r = stp(); s = snap(r, HC)
            if s["left"] == 0: t_off = int(r.tick); break
        ok, txt = end_ok((t_off or 10 ** 6) - t_on, s1["max"]); need(ok, "ends: " + txt + ", charge then %d" % s["charge"])
        need(s["charge"] == 0, "charge 0 after the end (%d)" % s["charge"])
        inst.setup(positions={HC: (9000, 17400)}); stp(k=1)
        after = walk(HC, 8); ok, txt = ratio_ok(after, base, 1.0, SPEED_TOL); need(ok, "speed after the end: " + txt)
        # 7. hypercharged super vs normal super, same distance, same ticks
        import super_audit as SA
        d_sup = 300.0   # the targets' offset below: 1 tile
        sd = {HC: SA.super_dist(SA.expected(a.brawler, hyper=True), d_sup), NC: SA.super_dist(SA.expected(a.brawler), d_sup)}
        inst.setup(positions={HC: (9000, 17400), NC: (9000, 600), T1: (9300, 17400), T2: (9300, 600)}, super_fill=[HC, NC],
                   hyper_fill=[HC]); stp(k=1)
        r = stp({HC: (-1, 4, 0.0, 0.0)}, k=1); s = snap(r, HC)
        need(s["left"] > 0, "hypercharge active for the super (%d ticks left)" % s["left"])
        pair = ((HC, T1), (NC, T2)); hp0 = {t: snap(r, t)["hp"] for _, t in pair}; low = dict(hp0); dd = {p: 0 for p, _ in pair}
        sc = {p: [int(r.pl[p].super_charge), int(r.pl[p].super_max), int(r.pl[p].super_charge)] for p, _ in pair}
        r = stp({p: (-1, 2, 0.0, sd[p]) for p, _ in pair}, k=1)   # aim 0 degrees: at the target
        for n in range(SA.WATCH // TICKS + 1):
            for p, t in pair:
                low[t] = min(low[t], int(r.pl[t].hp) if r.pl[t].alive else 0); dd[p] += int(r.pl[p].damage_dealt)   # cleared per response
                sc[p][2] = min(sc[p][2], int(r.pl[p].super_charge))
            if n < SA.WATCH // TICKS: r = stp()
        dmg = {p: max(hp0[t] - low[t], dd[p]) for p, t in pair}
        ok, txt = super_ok(dmg[HC], dmg[NC])
        need(ok, "super damage at %d units: %s; super charge %s, super_dist %s" % (d_sup, txt, {p: "%d/%d -> %d" % tuple(v) for p, v in sc.items()},
                                                                               {p: round(v, 3) for p, v in sd.items()}))
    finally:
        inst.close()
    for f in fails[:20]: print("FAIL", f)
    assert not fails, "%d failures" % len(fails)
    print("hyper_check ok")


if __name__ == "__main__":
    sys.exit(main())
