"""Live check of gadget activation (issue #3): one boot, 10 random agents with a gadget loadout (env_v5.with_gadgets).
  1. the host publishes gadget state (NbeResp gad_valid) and the requested card reached it (gad_card = div.gadget);
  2. for each gadget kind the host implements (gad_kind != NONE, nbhost gadget.c), fire it (NbeAction.fire 3) a few
     times and assert, on the next response, that a use was spent (gad_charges - 1, gad_used + 1, gad_cd > 0), and
     SETTLE ticks later that the kind's effect happened (EFFECT; a kind without an effect test fails, so a new kind comes
     with its test). The effect has to show in at least EFFECT_SHARE of the activations of each kind: a dash aimed into
     a wall stops short and enemy fire can outweigh a heal over time, and the check plays random agents in a real battle;
  3. fire 3 on a gadget that is not ready (no use left / cooldown / kind not implemented) spends nothing;
  4. env_v5.Env.gadget (obs_v5 self 3) agrees with the response;
  5. (also --check) no usable gadget disagrees with the game's own description (desc_audit, issue #55) beyond DESC_OPEN.
With no implemented kind in play (an old host build) it checks 1, 3 and 4 and says so.
python -m gadget_check [--minutes 4] [--per-kind 6] [--roster Splitter,Attacher,Samurai]   (--roster: only these brawlers,
e.g. to reach a kind that one brawler has: R-T's SUPER)      python -m gadget_check --check   (no game: the judging rules)"""
import argparse, collections, sys, time, numpy as np
P = None   # nbpc.proto, imported in main / _check (the self-check needs no host)

SETTLE = 6         # ticks from the fire to the effect judgement; a heal over time (60..80 ticks) has given 8..10 % of its hp
DASH_MIN = 400.0   # world units in SETTLE ticks: a walk covers < 220 (720 u/s x 6 ticks x 50 ms), a dash (600..1300 u at
                   # 2000..3500 u/s) 600 unless a wall stops it
EFFECT_SHARE = 0.6
DESC_OPEN = {"Sniper_HandGun": "#54", "Leaper_Shotgun": "#54"}   # desc_audit mismatches with an open fix (repeat_shot aim / count)


def desc_mismatches():
    """usable gadgets whose kind disagrees with the game's own description (desc_audit, issue #55), minus DESC_OPEN. None:
    no game data. A new mismatch fails the check: mask the card (gadget.c g_masked, super_audit.MASKED) or fix its kind."""
    try:
        import desc_audit
        rows = desc_audit.flagged()
    except (OSError, KeyError, StopIteration):
        return None
    return ["%s %s (%s): %s" % (r["brawler"], r["card"], r["kind"], ", ".join(r["flags"])) for r in rows if r["card"] not in DESC_OPEN]


def snap(r, p):
    """the fields of player p this check compares, copied out of the (live, shared-memory) response r"""
    pl = r.pl[p]
    return dict(valid=int(getattr(r, "gad_valid", 0)), card=int(r.gad_card[p]), kind=int(r.gad_kind[p]),
                charges=int(r.gad_charges[p]), cd=int(r.gad_cd[p]), used=int(r.gad_used[p]), tick=int(r.tick),
                x=float(pl.x), y=float(pl.y), hp=int(pl.hp), max_hp=int(pl.max_hp), alive=int(pl.alive),
                sc=int(pl.super_charge), sm=int(pl.super_max),
                out=int(pl.eliminated or pl.reserved[3] > 0))


def ready(s):
    return bool(s["valid"] and s["kind"] != P.GAD_NONE and s["charges"] > 0 and s["cd"] <= 0 and s["alive"] and not s["out"])


def effect_dash(a, b): d = float(np.hypot(b["x"] - a["x"], b["y"] - a["y"])); return d >= DASH_MIN, "moved %.0f" % d
def effect_heal(a, b): return b["hp"] > a["hp"], "hp %d -> %d" % (a["hp"], b["hp"])
def effect_spawn(a, b):   # an area / item (gadget.c AREA, SKILL AREA, ITEM): not in NbeResp; its effects: `super_audit --gadget`
    return True, "use spent (area / item: super_audit --gadget)"
def effect_projectile(a, b):   # projectiles (gadget.c SHOT, REPEAT, SPIN): not in NbeResp; seen by `super_audit --gadget`
    return True, "use spent (projectiles: super_audit --gadget)"
def effect_super(a, b): return b["sc"] > a["sc"], "super %d -> %d of %d" % (a["sc"], b["sc"], b["sm"])
EFFECT = {"DASH": effect_dash, "HEAL": effect_heal, "SPAWN": effect_spawn, "PROJECTILE": effect_projectile,
          "SUPER": effect_super}   # by GAD_* name; add one with each kind gadget.c implements
WANT = {"HEAL": lambda s: s["hp"] < 0.9 * s["max_hp"],   # judged only when the effect can show (a heal needs missing hp,
        "SUPER": lambda s: s["sc"] < s["sm"]}             # a super charge a super that is not full)


def judge(a, b):
    """snapshots before / on the next response after a fire 3 -> list of failures of the bookkeeping (empty = fine)"""
    bad = []
    if not ready(a):
        if b["used"] != a["used"] or b["charges"] > a["charges"]: bad.append("not ready, yet a use was spent")
        return bad
    if b["used"] != a["used"] + 1 or b["charges"] != a["charges"] - 1: bad.append("use not spent: charges %d -> %d, used %d -> %d" % (a["charges"], b["charges"], a["used"], b["used"]))
    if b["cd"] <= 0 and a["charges"] > 1: bad.append("no cooldown started")
    if EFFECT.get(KIND[a["kind"]]) is None: bad.append("no effect test for kind %s (add one to gadget_check.EFFECT)" % KIND[a["kind"]])
    return bad


def effect(a, c):
    """snapshot before a (spent) fire 3, snapshot SETTLE ticks later -> (effect happened, what was measured)"""
    return EFFECT[KIND[a["kind"]]](a, c)


KIND = {}


def _load_proto():
    global P, KIND
    from nbpc import proto
    P = proto; KIND = {getattr(P, n): n[4:] for n in dir(P) if n.startswith("GAD_")}


def _check():
    _load_proto()
    base = dict(valid=1, card=23000001, kind=P.GAD_DASH, charges=3, cd=0, used=0, tick=100, x=0.0, y=0.0, hp=3000, max_hp=4000, alive=1, out=0,
                sc=0, sm=3000)
    s = lambda **o: {**base, **o}
    assert ready(s()) and not ready(s(cd=4)) and not ready(s(charges=0)) and not ready(s(kind=P.GAD_NONE)) and not ready(s(valid=0)) and not ready(s(out=1))
    assert judge(s(), s(charges=2, used=1, cd=100)) == []
    assert effect(s(), s(x=900.0)) == (True, "moved 900") and effect(s(), s(x=50.0)) == (False, "moved 50")
    assert judge(s(), s(x=900.0))[0].startswith("use not spent")
    assert judge(s(), s(charges=2, used=1)) == ["no cooldown started"]
    assert judge(s(charges=1), s(charges=0, used=1)) == []                            # last use: no cooldown needed
    assert judge(s(kind=P.GAD_HEAL), s(kind=P.GAD_HEAL, charges=2, used=1, cd=9)) == []
    assert effect(s(kind=P.GAD_HEAL), s(hp=3500))[0] and not effect(s(kind=P.GAD_HEAL), s(hp=2900))[0]
    assert not WANT["HEAL"](s(hp=4000)) and WANT["HEAL"](s(hp=3000))                    # fired at full hp: nothing to show
    assert judge(s(kind=P.GAD_SPAWN), s(kind=P.GAD_SPAWN, charges=2, used=1, cd=9)) == []
    assert judge(s(kind=P.GAD_SHIELD), s(kind=P.GAD_SHIELD, charges=2, used=1, cd=9))[0].startswith("no effect test")
    assert judge(s(kind=P.GAD_PROJECTILE), s(kind=P.GAD_PROJECTILE, charges=2, used=1, cd=9)) == []
    assert effect(s(kind=P.GAD_SUPER, sc=500), s(sc=3000))[0] and not effect(s(kind=P.GAD_SUPER, sc=500), s(sc=500))[0]
    assert WANT["SUPER"](s(sc=0)) and not WANT["SUPER"](s(sc=3000))
    assert judge(s(cd=5), s(cd=4)) == [] and judge(s(cd=5), s(cd=4, used=1)) == ["not ready, yet a use was spent"]
    assert judge(s(kind=P.GAD_NONE, charges=0), s(kind=P.GAD_NONE, charges=0)) == []
    bad = desc_mismatches()
    assert not bad, "gadgets that disagree with their description: " + "; ".join(bad)
    print("gadget_check self-check ok" + ("" if bad is not None else " (no game data: description audit skipped)"))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--minutes", type=float, default=4)
    ap.add_argument("--per-kind", type=int, default=6, help="activations to judge per implemented kind")
    ap.add_argument("--roster", default="", help="comma-separated brawlers (characters.csv Name) to draw from (default: all)")
    ap.add_argument("--check", action="store_true", help="the judging rules on made-up responses (no game)")
    a = ap.parse_args()
    if a.check: return _check()
    bad = desc_mismatches(); assert not bad, "gadgets that disagree with their description: " + "; ".join(bad)
    _load_proto(); import env_v5 as E
    env = E.Env(1, E.make_battle_fn(10, roster=[x for x in a.roster.split(",") if x] or None, gadgets=True), ticks=2, fair=True, max_ticks=4000)
    rng = np.random.default_rng(0); pend = {}; fails = []; done = collections.Counter(); refused = collections.Counter()
    settle = {}; eff = collections.Counter(); eff_ok = collections.Counter(); eff_what = collections.defaultdict(list)
    seen = collections.Counter(); t0 = None; steps = 0
    by = lambda aid: {s.battle: s for s in env.I}.get(int(aid) >> 4)
    try:
        while t0 is None or time.time() - t0 < a.minutes * 60:
            obs, ids, _ = env.poll(min_ready=1, max_wait=0.01)
            if not len(ids): continue
            t0 = t0 or time.time(); B = len(ids); steps += B; g = env.gadget(ids)
            act = np.stack([rng.integers(0, 17, B), rng.integers(0, 2, B), rng.integers(0, 360, B), rng.integers(0, 8, B)], 1)
            for k, aid in enumerate(ids):
                s = by(aid)
                if s is None: continue
                p = int(aid) & 15; r = s.inst.resp; now = snap(r, p)
                if not now["valid"]: fails.append("host publishes no gadget state (gad_valid 0): rebuild nbhost with gadget.c"); break
                req = s.cfg["div"].get("gadget", [0] * 16)[p]
                if req and now["card"] not in (0, req): fails.append("player %d: requested card %d, host has %d" % (p, req, now["card"]))
                seen[("card" if now["card"] else "no card", KIND[now["kind"]])] += 1
                if g[k] != ready(now): fails.append("Env.gadget %s but the response says %s" % (g[k], ready(now)))
                if aid in pend:
                    b0 = pend.pop(aid)
                    if b0["tick"] < now["tick"] and not now["out"] and now["card"] == b0["card"]:   # same battle, still in play
                        bad = judge(b0, now)
                        fails += ["player %d %s: %s" % (p, KIND[b0["kind"]], m) for m in bad]
                        (done if ready(b0) else refused)[KIND[b0["kind"]]] += 1
                        if ready(b0) and not bad: settle[aid] = b0
                if aid in settle and now["tick"] - settle[aid]["tick"] >= SETTLE:
                    b0 = settle.pop(aid)
                    if now["card"] == b0["card"] and now["alive"] and not now["out"]:
                        ok, what = effect(b0, now); kn = KIND[b0["kind"]]; eff[kn] += 1; eff_ok[kn] += ok; eff_what[kn].append(what)
                kind = KIND[now["kind"]]
                want = WANT.get(kind, lambda s: True)(now)
                if aid not in settle and ((ready(now) and want and eff[kind] < a.per_kind) or (not ready(now) and rng.random() < 0.05)):
                    act[k, 1] = 3; pend[aid] = now
            if fails: break
            env.send(ids, act)
            impl = {k for (c, k) in seen if k != "NONE"}
            if impl and all(eff[k] >= a.per_kind for k in impl) and sum(refused.values()) >= 5: break
    finally:
        env.close()
    print("agent-steps %d | loadouts seen (agent-steps): %s | checked activations %s, fire 3 while not ready %s"
          % (steps, dict(seen), dict(done), dict(refused)))
    for k in sorted(eff): print("  %s effect after %d ticks in %d of %d: %s" % (k, SETTLE, eff_ok[k], eff[k], ", ".join(eff_what[k][:12])))
    for f in fails[:20]: print("FAIL", f)
    assert not fails, "%d failures" % len(fails)
    assert any(c == "card" for c, _ in seen), "no player got a gadget card (loadout request lost?)"
    impl = sorted({k for (c, k) in seen if k != "NONE"})
    if not impl:
        print("no implemented gadget kind showed up (an old host build, or no player drew a dash / heal gadget): nothing activated")
    for k in impl:
        assert eff[k] >= a.per_kind, "kind %s: only %d activations judged in %.0f min" % (k, eff[k], a.minutes)
        assert eff_ok[k] >= EFFECT_SHARE * eff[k], "kind %s: effect in only %d of %d activations" % (k, eff_ok[k], eff[k])
    assert sum(refused.values()) > 0, "fire 3 while not ready was never tried"
    print("gadget_check ok: kinds", impl or "none")


if __name__ == "__main__":
    sys.exit(main())
