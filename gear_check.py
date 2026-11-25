"""Live check of gears (issue #51): one boot, one scripted battle (no gas, native AI off, spawn protection off) on
Survival642 where each gear in LIVE has a carrier and a control of the same brawler without it. In order:
  1. the host publishes gear state (NbeResp gear_valid), each requested gear reached its player's config (gear_id), a gear
     the brawler may not carry is rejected (div_err bit), the ConsumableShield carrier starts with its 900 shield;
  2. LowHealthDamage (host, gear.c): at full hp the carrier's volley does what the control's does; below 50 % hp it does
     (1 + 15 %) x the control's;
  3. ConsumableShield (host): the first volley the carrier takes costs it 900 less hp than the control (the shield takes
     it), the shield is 0 after; healed to full (a SETUP teleport heals), it is back to 900 SHIELD_REGEN ticks later;
  4. HealthRegen (libg's own regen, 0xb46900): after the same damage the carrier regains (1 + 50 %) x the control's hp;
  5. ForestSpeed (host): on a bush row the carrier walks (1 + 15 %) x the control's distance, on open ground the same;
  6. ReloadSpeed (host): after both emptied their ammo, the carrier (Surge) reloads (1 + 15 %) x the control's ammo;
  7. SuperChargeRate (libg, 0xb4f928): El Primo's punch charges the carrier's super (1 + 10 %) x the control's;
  8. GadgetCooldown (libg, 0xc401e0 -> gadget.c): Maisie's dash, the carrier's gadget cooldown after a use is (1 - 15 %) x the control's.
LIVE (the gears env_v5.with_gears hands out, trainer --gears 1) is the list this check confirmed (2026-11-25, notes/issue51.md).
python -m gear_check            python -m gear_check --check   (no game: the judging rules, the layout helpers)"""
import argparse, sys, time, numpy as np
P = None   # nbpc.proto, imported in main (the self-check needs no host)

# gear_boosts.csv names whose effect this check confirmed in the live battle (2026-11-25): what --gears 1 hands out
LIVE = frozenset({"ForestSpeed", "HealthRegen", "LowHealthDamage", "ConsumableShield", "ReloadSpeed", "SuperChargeRate",
                  "GadgetCooldown"})

MAP = "Survival642"
TILE = 300
TICKS = 2            # ticks per step
DMG_TOL = 0.03       # relative: each pellet's damage is scaled and truncated on its own
SPEED_TOL = 0.06     # relative: the walked distance quantises to the move re-sends and tick ends (as hyper_check)
REGEN_TOL = 0.08     # relative: regen comes in whole ticks of max hp x 13 % / 100 x (100 + 50) / 100, truncated
RELOAD_TOL = 0.05    # relative: the ammo charge gains dt x 1000 / T per tick, T truncated to whole ms
SHIELD_TICK_TOL = 2 * TICKS   # the regeneration is judged at step ends
SHIELD_REGEN = 200   # gear.c: ticks at full hp before the shield is back


def snap(r, p):
    """the fields of player p this check compares, copied out of the (live, shared-memory) response r"""
    pl = r.pl[p]
    return dict(valid=int(getattr(r, "gear_valid", 0)), gear=[int(r.gear_id[p][0]), int(r.gear_id[p][1])],
                shield=int(r.gear_shield[p]), stat=[int(x) for x in r.gear_stat[p]], hp=int(pl.hp), max_hp=int(pl.max_hp),
                x=float(pl.x), y=float(pl.y), ammo=int(pl.ammo), sc=int(pl.super_charge), tick=int(r.tick),
                cd=int(r.gad_cd[p]), kind=int(r.gad_kind[p]), used=int(r.gad_used[p]), alive=int(pl.alive))


def ratio_ok(got, base, want, tol):
    """got / base within tol (relative) of want -> (ok, text)"""
    q = got / base if base else float("nan")
    return bool(base > 0 and abs(q - want) <= tol * want), "%.0f / %.0f = %.3f (want %.3f)" % (got, base, q, want)


def shield_hit_ok(taken_gear, taken_ctl, shield_before, shield_after, tol=DMG_TOL):
    """the carrier's hp loss = the control's minus what the shield held (min(volley, shield)), the shield spent by that"""
    held = min(taken_ctl, shield_before)
    ok = abs(taken_gear - (taken_ctl - held)) <= tol * max(taken_ctl, 1) and shield_after == shield_before - held
    return ok, "hp lost %d vs control %d, shield %d -> %d (held %d)" % (taken_gear, taken_ctl, shield_before, shield_after, held)


def regen_tick_ok(t_full, t_back, want=SHIELD_REGEN, tol=SHIELD_TICK_TOL):
    return t_full is not None and t_back is not None and abs((t_back - t_full) - want) <= tol, \
        "full at %s, shield back at %s (want +%d)" % (t_full, t_back, want)


def runs(mask, n):
    """(y, x0) of each horizontal run of >= n True tiles in mask (H, W), one per run (its left end)"""
    out = []
    for y in range(mask.shape[0]):
        x = 0
        while x < mask.shape[1]:
            if mask[y, x]:
                x1 = x
                while x1 < mask.shape[1] and mask[y, x1]: x1 += 1
                if x1 - x >= n: out.append((y, x))
                x = x1
            else: x += 1
    return out


def layout(location=MAP):
    """-> (bush row, open rows) of the location's map: a run of 7 bush tiles with open tiles left of it, and open runs of
    8 tiles (world (x, y) of each run's right end), from maps.csv (D.map_reference)"""
    from nbpc import diversity as D
    ids, rows = D.map_reference(location); H, W = len(rows), len(rows[0]); T = D.table("tiles.csv")
    g = np.array(ids).reshape(H, W); raw = np.array([list(r) for r in rows])
    bush = np.isin(g, [i for _, (i, r) in T.items() if r.get("IsForest") == "true"])
    free = np.isin(g, [i for _, (i, r) in T.items() if r.get("BlocksMovement") != "true" and r.get("BlocksProjectiles") != "true"]) \
        & ~np.char.isdigit(raw)
    return pick_runs(bush, free & ~bush, free)


def pick_runs(bush, walk, free=None):
    """bush / walk / free (H, W) bool: bush tiles, open ground, anything a brawler and a shot pass (open or bush): -> the
    second tile from the right of the first 7-tile bush run with free rows above and below, and the right ends of 8-tile
    open runs with free rows above and below"""
    free = walk if free is None else free
    c = lambda y, x: ((x + 0.5) * TILE, (y + 0.5) * TILE)
    b = [(y, x) for y, x in runs(bush, 7) if 1 <= y < bush.shape[0] - 1 and free[y - 1, x:x + 7].all() and free[y + 1, x:x + 7].all()]
    o = [(y, x) for y, x in runs(walk, 8) if 1 <= y < walk.shape[0] - 1 and free[y - 1, x:x + 8].all() and free[y + 1, x:x + 8].all()]
    picked = []   # open runs at least 6 tiles apart (vertically or horizontally), so the pairs stay out of each other's way
    for y, x in o:
        if all(abs(y - y2) >= 6 or abs(x - x2) >= 12 for y2, x2 in picked): picked.append((y, x))
    return (c(b[0][0], b[0][1] + 5) if b else None), [c(y, x + 7) for y, x in picked]   # a tile in: no wall pushes it out


def card_id(name):
    """cards.csv data id of a card by name (ids count the named rows, as env_v5.gadget_cards)"""
    from nbpc import diversity as D
    import env_v5 as E
    names = [r["Name"] for r in D._rows("cards.csv") if r[next(iter(r))]]
    return E.T_CARD * 1000000 + names.index(name)


def _check():
    assert ratio_ok(1150.0, 1000.0, 1.15, DMG_TOL)[0] and not ratio_ok(1000.0, 1000.0, 1.15, DMG_TOL)[0]
    assert not ratio_ok(3.0, 0.0, 1.0, DMG_TOL)[0]
    assert shield_hit_ok(1500, 2400, 900, 0)[0] and shield_hit_ok(0, 600, 900, 300)[0]
    assert not shield_hit_ok(2400, 2400, 900, 900)[0] and not shield_hit_ok(1500, 2400, 900, 900)[0]
    assert regen_tick_ok(1000, 1200)[0] and regen_tick_ok(1000, 1203)[0] and not regen_tick_ok(1000, 1100)[0] and not regen_tick_ok(None, 5)[0]
    m = np.zeros((6, 20), bool); m[2, 3:12] = True; m[4, 0:7] = True
    assert runs(m, 7) == [(2, 3), (4, 0)] and runs(m, 8) == [(2, 3)]
    w = np.ones((30, 30), bool); bu = np.zeros((30, 30), bool); bu[5, 10:17] = True; w[5, 10:17] = False
    bp, op = pick_runs(bu, w)
    assert bp == ((15 + 0.5) * TILE, 5.5 * TILE) and len(op) >= 4 and all(np.hypot(a[0] - b[0], a[1] - b[1]) >= 6 * TILE
                                                                           for i, a in enumerate(op) for b in op[:i])
    import env_v5 as E
    assert card_id("Maisie_Dash") in E.gadget_cards()["Maisie"]
    g = {r["name"]: r for r in E.gear_rows()}
    assert LIVE <= set(g) and all(g[n]["type"] in (0, 1, 2, 4, 5, 6, 17) for n in LIVE)
    print("gear_check self-check ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="the judging rules on made-up numbers (no game)")
    ap.add_argument("--log-dir", default=None)
    a = ap.parse_args()
    if a.check: return _check()
    global P
    from nbpc.instance import Instance
    from nbpc import proto, diversity as D
    import env_v5 as E
    P = proto
    G = {r["name"]: r["id"] for r in E.gear_rows()}
    # players: 0 / 9 Surge (reload), 1 / 2 Shelly (low-hp damage, shield) with targets 5 / 6 (Maisie: also the gadget
    # cooldown pair; 6's gear is one Maisie may not carry), 3 / 4 Shelly (regen, bush speed), 7 / 8 El Primo (super charge)
    names = ["ElectroSniper", "ShotgunGirl", "ShotgunGirl", "ShotgunGirl", "ShotgunGirl", "Maisie", "Maisie",
             "Luchador", "Luchador", "ElectroSniper"]
    gear = {0: [G["ReloadSpeed"]], 1: [G["LowHealthDamage"], G["ConsumableShield"]], 3: [G["ForestSpeed"], G["HealthRegen"]],
            5: [G["GadgetCooldown"]], 6: [G["SuperHealth"]], 7: [G["SuperChargeRate"]]}
    want_ids = {p: sorted(v) for p, v in gear.items() if p != 6}
    dash = card_id("Maisie_Dash")   # a gadget kind the host implements (gadget.c DASH), cooldown 320 ticks
    bush_xy, opens = layout()
    if bush_xy is None or len(opens) < 6: raise SystemExit("%s: no bush row / not enough open rows for the layout" % MAP)
    fails, info = [], []
    inst = Instance(0, tag="gear_check", log_dir=a.log_dir); t0 = time.time(); inst.start(); inst.wait_ready()
    print("host ready in %.0f s" % (time.time() - t0), flush=True)

    def need(ok, what):
        (info if ok else fails).append(what); print(("ok   " if ok else "FAIL ") + what, flush=True)

    try:
        div = D.make_div(location=MAP, chr=names); div["gear"] = gear; div["gadget"] = {5: dash, 6: dash}
        inst.reset(7, gas=0, flags=P.F_STATE, native_mask=0, obs_mask=0, div=div)
        bi = inst.battle_info() or {}
        allp = list(range(10)); idle = {i: (-1, 0, 0.0, 0.0) for i in allp}

        def stp(acts=None, k=TICKS):
            return inst.step(actions={**idle, **(acts or {})}, ticks=k, flags=P.F_STATE, native_mask=0)

        def S(p): return snap(inst.resp, p)
        # each pair on its own open row: the gear player at the run's right end - 300, its partner 300 units to its right
        # would leave the run, so the partner stands 300 to the left (aim 180 / 0 degrees)
        rowp = {(1, 5): opens[0], (2, 6): opens[1], (3, 4): opens[2], (7, 8): opens[3], (0, 9): opens[4]}
        home = {}
        for (p, q), (x, y) in rowp.items(): home[p] = (x - 300, y); home[q] = (x, y)
        home[9] = (opens[5][0], opens[5][1])     # the Surge pair on two rows: their shots fly up, into nothing
        inst.setup(positions=home, ai_off=allp, unprotect=allp)
        r = stp(k=1); s = {p: S(p) for p in allp}
        # 1. equip
        need(s[1]["valid"] == 1, "host publishes gear state (gear_valid %d)" % s[1]["valid"])
        if not s[1]["valid"]: raise SystemExit("rebuild the host with native/loader/gear.c (SETUP.md)")
        got = {p: sorted(x for x in s[p]["gear"] if x) for p in allp}
        need(all(got[p] == want_ids.get(p, []) for p in allp), "gears in the configs %s (want %s)" % (
            {p: v for p, v in got.items() if v}, want_ids))
        err = int(bi.get("err", 0))
        need(err & (1 << 6) and not err & 0x3bf, "SuperHealth on Maisie rejected (div_err %#x)" % err)
        need(s[1]["shield"] == 900 and all(s[p]["shield"] == 0 for p in allp if p != 1), "shield 900 at the start (%d)" % s[1]["shield"])
        # 2. low-hp damage at full hp: 1 shoots 5, 2 shoots 6 (aim 0: to the right)
        def volley(shooters, aims, n=6):
            h0 = {p: S(p)["hp"] for p in allp}
            stp({p: (-1, 1, aims[p], 0.0) for p in shooters})
            for _ in range(n): stp()
            return {p: h0[p] - S(p)["hp"] for p in allp}
        dm = volley((1, 2), {1: 0.0, 2: 0.0})
        ok, txt = ratio_ok(dm[5], dm[6], 1.0, DMG_TOL); need(ok and S(1)["stat"][0] == 0, "LowHealthDamage at full hp: " + txt)
        # 3. the shield: 5 shoots 1, 6 shoots 2 (aim 180)
        for _ in range(10): stp()                # ammo back
        sh0 = S(1)["shield"]; dm = volley((5, 6), {5: 180.0, 6: 180.0})
        ok, txt = shield_hit_ok(dm[1], dm[2], sh0, S(1)["shield"]); need(ok, "ConsumableShield takes the first hit: " + txt)
        # more volleys until 1 and 2 are below 50 %
        for _ in range(6):
            if S(1)["hp"] * 2 < S(1)["max_hp"] and S(2)["hp"] * 2 < S(2)["max_hp"]: break
            for _ in range(10): stp()
            volley(tuple(p for p in (5, 6) if S(p - 4)["hp"] * 2 >= S(p - 4)["max_hp"]), {5: 180.0, 6: 180.0})
        lo = S(1)["hp"] * 2 < S(1)["max_hp"] and S(2)["hp"] * 2 < S(2)["max_hp"] and S(1)["alive"] and S(2)["alive"]
        need(lo, "1 and 2 below 50 %% hp (%d / %d, %d / %d)" % (S(1)["hp"], S(1)["max_hp"], S(2)["hp"], S(2)["max_hp"]))
        # 2b. low-hp damage below 50 %: 5 and 6 healed first (a teleport heals) so neither dies
        inst.setup(positions={5: home[5], 6: home[6]}); stp(k=1)
        n0 = S(1)["stat"][0]; dm = volley((1, 2), {1: 0.0, 2: 0.0})
        ok, txt = ratio_ok(dm[5], dm[6], 1.15, DMG_TOL); need(ok and S(1)["stat"][0] > n0, "LowHealthDamage below 50 %: " + txt)
        # 4. regen: 3 and 4 shoot each other once (the same damage), then no one shoots; 5. the shield back meanwhile
        inst.setup(positions={1: home[1]}); stp(k=1)        # 1 healed to full: its shield regenerates from here
        t_full, t_back = int(inst.resp.tick), None
        dm = volley((3, 4), {3: 0.0, 4: 180.0}, n=2)
        need(dm[3] > 0 and abs(dm[3] - dm[4]) <= DMG_TOL * dm[4], "3 and 4 took the same volley (%d, %d)" % (dm[3], dm[4]))
        hist = []
        for _ in range(400):
            r = stp(); hist.append((S(3)["hp"], S(4)["hp"], S(3)["max_hp"]))
            if t_back is None and S(1)["shield"] == 900: t_back = int(r.tick)
            if t_back is not None and hist[-1][0] >= hist[-1][2] and hist[-1][1] >= hist[-1][2]: break
        ok, txt = regen_tick_ok(t_full, t_back); need(ok, "ConsumableShield back at full hp: " + txt)
        h = np.array(hist); start = h[0, :2]
        k = next((i for i in range(len(h)) if h[i, 0] >= h[i, 2]), len(h) - 1)   # until the carrier is full
        g3, g4 = h[k - 1, 0] - start[0] if k > 0 else 0, h[k - 1, 1] - start[1] if k > 0 else 0
        ok, txt = ratio_ok(g3, g4, 1.5, REGEN_TOL); need(ok, "HealthRegen: hp regained " + txt)
        # 5. bush speed: 3 then 4 walk left (move_dir 8) from the bush row's right end, then on open ground
        def walk(p, xy, n=8):   # -> the path length (a teleport can leave a short drift before the walk turns left)
            inst.setup(positions={p: xy}); stp(k=1); pts = [(S(p)["x"], S(p)["y"])]
            for _ in range(n): stp({p: (8, 0, 0.0, 0.0)}); pts.append((S(p)["x"], S(p)["y"]))
            stp({p: (-1, 0, 0.0, 0.0)}); return float(np.hypot(*np.diff(np.array(pts), axis=0).T).sum())
        n0 = S(3)["stat"][2]
        b3, b4 = walk(3, bush_xy), walk(4, bush_xy)
        ok, txt = ratio_ok(b3, b4, 1.15, SPEED_TOL); need(ok and S(3)["stat"][2] > n0, "ForestSpeed in a bush: " + txt)
        o3, o4 = walk(3, opens[2]), walk(4, opens[2])
        ok, txt = ratio_ok(o3, o4, 1.0, SPEED_TOL); need(ok, "ForestSpeed on open ground: " + txt)
        # 6. reload: 0 and 9 fire up (aim 270) until empty, then the ammo regained in the same ticks
        for _ in range(4):
            stp({0: (-1, 1, 270.0, 0.0), 9: (-1, 1, 270.0, 0.0)})
            for _ in range(3): stp()
        a0 = (S(0)["ammo"], S(9)["ammo"])
        for _ in range(6): stp()
        a1 = (S(0)["ammo"], S(9)["ammo"])
        ok, txt = ratio_ok(a1[0] - a0[0], a1[1] - a0[1], 1.15, RELOAD_TOL)
        need(ok and S(0)["stat"][3] > 0, "ReloadSpeed: ammo regained %s (ammo %s -> %s)" % (txt, a0, a1))
        # 7. super charge: 7 and 8 punch each other
        c0 = (S(7)["sc"], S(8)["sc"]); volley((7, 8), {7: 0.0, 8: 180.0}, n=10)
        ok, txt = ratio_ok(S(7)["sc"] - c0[0], S(8)["sc"] - c0[1], 1.10, DMG_TOL); need(ok, "SuperChargeRate: super charge " + txt)
        # 8. gadget cooldown: 5 and 6 use their gadget (a dash away from each other)
        k5 = S(5)["kind"]
        stp({5: (-1, 3, 0.0, 0.0), 6: (-1, 3, 180.0, 0.0)})
        c5, c6 = S(5), S(6)
        ok, txt = ratio_ok(c5["cd"], c6["cd"], 0.85, DMG_TOL)
        need(ok and k5 and c5["used"] == 1 and c6["used"] == 1, "GadgetCooldown: cooldown after a use " + txt)
    finally:
        inst.close()
    for f in fails[:20]: print("FAIL", f)
    assert not fails, "%d failures" % len(fails)
    print("gear_check ok")


if __name__ == "__main__":
    sys.exit(main())
