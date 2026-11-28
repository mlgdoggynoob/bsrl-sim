"""Intents: per-second goals for the reflex policy (behaviour design 4). The kind specs, the one observation encoder
shared by sim and live, the intent-following reward and the random-valid sampler. Numpy only, no host.

    python -m intent        # self-check (no game)

    blk = encode(kind, dx, dy, radius, left)     # (B, N_INT) intent block; kind 0 (none) = all zeros
    it = new(cand, d0, range_t)                   # an intent episode from a sampler / planner candidate
    rew, end = step_reward(it, ev)                # one env step: reward before --intent-scale, end None | achieved | timeout | invalid
    cand = sample(scene, rng)                     # a random kind among those with a valid target, a random valid target (or None)

Kinds (obs_v5.INTENTS; distances in tiles, true positions in the sim):
  id kind     target                       achieved                                               max
  1  move_to  point, r 1                   d <= r                                                 4 s
  2  avoid    point, R 8                   d >= R                                                 4 s
  3  hold     point, r 1.5                 inside r when the time runs out                        5 s
  4  engage   enemy player (anchored)      the target goes down after my damage in range in the last 2 s (or my kill)  5 s
  5  farm     box or cube (static point)   box: gone after my box damage in the last 2 s; cube: I picked one up within 1.5  5 s
  6  regroup  mate player (anchored)       1.5 <= d <= 4 (the leash band, 450-1200 units)         3 s
  7  hide     bush tile                    on the tile, hidden by it (hid_vs) or no enemy in view 5 s
  8  super    enemy player (anchored)      my super is fired (charge full -> not) and within 2 s the target takes damage
                                           while I deal damage (the host has no per-source damage: shortcut)  3 s
  9  check_bush bush tile within my range  a main attack fired (fire 1, ammo spent) within 15 deg of the tile; if an enemy
                                           hid on / next to it then, wait <= 2 s for it to take my damage (+ bonus)  2 s
Modes (planner role rules, #91 / #92; candidate "mode", "threat" = the enemy player it is about, "near" tiles; not in
the block: the observation is unchanged):
  super, mode escape   point target (the landing tile)   my super is fired and >= ESC_S later I am ESC_GAIN tiles farther
                       from the threat than at the start, or it is down / out of my sight; invalid 2 s after the fire
                       without that (the readiness and the fire as for super)
  engage, mode band    enemy (anchored)                   as engage; the potential is the distance outside band (lo, hi)
                       tiles (snipe_band: Piper 8.5-10), so walking inside lo costs as walking out of hi; radius = hi
  hide, mode quiet     my bush tile                       hidden (as hide; or at the step before, as a threat this close
                       sees me) when the threat comes within near, leaves my sight or the time runs out; invalid: a main attack fired (it reveals me) or the tile no longer a bush
Invalid (no bonus): me knocked out / eliminated; the target player down (engage / super: not after my damage / super);
an anchored or static target not seen by me for 1 s (fair rule); a farm target in the gas or gone without my doing; a
hide / check_bush tile that is no longer a bush; super: fired and 2 s without a hit (readiness: checked at the pick). After any end: none until the next planner tick; achieved -> a re-plan on the next decision (Env).
Block (obs_v5.N_INT = 13): one-hot of kinds 1..9 | dx, dy (target - own position, 10-tile units, clip +-2.5) | radius /
10 tiles (engage / check_bush: 0.8 x own range, super: 0.8 x own super range, regroup: the band's outer edge 4) | time
left 1 -> 0.
Reward per step (signed progress on a potential phi(d), so it telescopes: no dithering profit), c = 0.01 per tile:
  move_to  c * (phi_prev - phi), phi = min(d, 10)                    + 0.03 achieved
  avoid    phi = -min(d, R)                                          + 0.03 achieved
  hold     phi = min(max(d, r), 5), + 0.002 per step inside r        (no bonus)
  engage   phi = min(max(d - 0.8 range, 0), 5), + 0.5 x own damage / 1000 while the target is in range (<= 0.05 per intent)  + 0.05
  farm     phi = min(d, 8), + 0.2 x own box damage / 1000 (box target, <= 0.03 per intent)  + 0.03
  regroup  phi = min(max(d - 4, 0), 10) + max(1.5 - d, 0)             + 0.02
  hide     phi = min(d, 6), + 0.002 on the tile while hidden          + 0.02
  super    phi = min(max(d - 0.8 super range, 0), 5)                 + 0.05
  check_bush phi = min(max(d - 0.8 range, 0), 6)                     + 0.03, + 0.05 more when a hidden enemy is hit
Every intent's total is capped at CAP = 0.15 (min(total + r, CAP) - total: telescoping kept, nothing past the cap), x
--intent-scale (start 0.25): <= 0.04 per intent, < 1/10 of a rank step (0.56). The step an intent goes invalid pays 0.
"""
import sys
import numpy as np
import obs_v5 as O

KINDS = O.INTENTS
K = {k: i for i, k in enumerate(KINDS)}
C = 0.01                  # reward per tile of progress
CAP = 0.15                # per-intent total (design 4.3: <= c x start distance + bonus <= ~0.15)
SEEN_S, HIT_S = 1.0, 2.0  # s: an unseen target is lost after 1 s; "my damage in the last 2 s" (engage / farm a box)
ESC_S, ESC_GAIN = 1.0, 3.0   # super escape: >= 1 s after the fire, 3 tiles farther from the threat (Piper ~2 s airborne)
PICK = 1.5                # tiles: a cube picked up this close to the target is the target
TILE, VIEW = 300.0, (4500.0, 3500.0, 2900.0)   # camera rule of nbpc.fair / env_v5.slider_terms: |dx| < 4500 from the
                                               # clamped camera x, -3500 < dy < 2900
# per kind: radius r (tiles), max seconds, end bonus, distance cap of the potential (tiles), per-step pay while there
SPEC = {
    "move_to": dict(r=1.0, max_s=4, bonus=0.03, dcap=10.0),
    "avoid":   dict(r=8.0, max_s=4, bonus=0.03, dcap=8.0),
    "hold":    dict(r=1.5, max_s=5, bonus=0.0, dcap=5.0, stay=0.002),
    "engage":  dict(r=None, max_s=5, bonus=0.05, dcap=5.0, dk=0.5, dk_cap=0.05),   # r = 0.8 x own range
    "farm":    dict(r=1.0, max_s=5, bonus=0.03, dcap=8.0, box=0.2, box_cap=0.03),
    "regroup": dict(r=4.0, max_s=3, bonus=0.02, dcap=10.0, band=(1.5, 4.0)),
    "hide":    dict(r=0.5, max_s=5, bonus=0.02, dcap=6.0, stay=0.002),
    "super":   dict(r=None, max_s=3, bonus=0.05, dcap=5.0),                        # r = 0.8 x own super range
    "check_bush": dict(r=None, max_s=2, bonus=0.03, dcap=6.0, hit=0.05, ang=15.0),  # r = 0.8 x own range; ang: degrees
}
_NEAR = ("engage", "super", "check_bush")        # potential = distance beyond r (in range = 0)
END = ("achieved", "timeout", "invalid")      # episode counts per kind: [started, achieved, timeout, invalid]


def encode(kind, dx, dy, radius, left):
    """(B, N_INT) float32 intent blocks. kind (B,) ints (0 = none -> the row is all zeros), dx, dy = target - own
    position in tiles (x right, y down), radius in tiles, left = time left 1 -> 0"""
    kind = np.asarray(kind, np.int64).reshape(-1); B = len(kind); out = np.zeros((B, O.N_INT), np.float32)
    on = kind > 0
    if not on.any(): return out
    out[on, kind[on] - 1] = 1.0
    out[:, O.I_XY] = np.clip(np.broadcast_to(np.asarray(dx, np.float64), (B,)) / 10.0, -2.5, 2.5)
    out[:, O.I_XY + 1] = np.clip(np.broadcast_to(np.asarray(dy, np.float64), (B,)) / 10.0, -2.5, 2.5)
    out[:, O.I_RAD] = np.broadcast_to(np.asarray(radius, np.float64), (B,)) / 10.0
    out[:, O.I_LEFT] = np.clip(np.broadcast_to(np.asarray(left, np.float64), (B,)), 0.0, 1.0)
    out[~on] = 0.0
    return out


def radius(kind, range_t=None, super_t=None):
    """encoded / achieving radius in tiles of a kind (engage / check_bush: 0.8 x own range, super: 0.8 x own super range)"""
    if kind == "super": return 0.8 * float(super_t if super_t is not None else range_t or 0.0)
    return 0.8 * float(range_t) if kind in ("engage", "check_bush") else SPEC[kind]["r"]


def phi(it, d):
    """the kind's potential at distance d (tiles): reward = C x (phi_prev - phi)"""
    k, sp = it["kind"], SPEC[it["kind"]]; cap = sp["dcap"]
    if k == "avoid": return -min(d, sp["r"])
    if k == "hold": return min(max(d, sp["r"]), cap)
    if it.get("band"): lo, hi = it["band"]; return min(max(d - hi, 0.0) + max(lo - d, 0.0), cap)   # engage, mode band
    if k in _NEAR: return min(max(d - it["r"], 0.0), cap)
    if k == "regroup": lo, hi = sp["band"]; return min(max(d - hi, 0.0), cap) + max(lo - d, 0.0)
    return min(d, cap)


def new(cand, d0, range_t=None, steps_per_s=10, super_t=None):
    """an intent episode from a candidate {kind, q (anchored player, -1 none), pt (x, y units, static), obj ('box' / 'cube'
    / None)}: d0 = the start distance (tiles), range_t = own range (tiles), steps_per_s = env steps per second, super_t =
    own super range (tiles; super)"""
    k = cand["kind"]
    it = {"kind": k, "q": int(cand.get("q", -1)), "pt": cand.get("pt"), "obj": cand.get("obj"), "r": radius(k, range_t, super_t),
          "range": float(range_t or 0.0), "t": 0, "T": int(round(SPEC[k]["max_s"] * steps_per_s)), "sps": int(steps_per_s),
          "tot": 0.0, "dk": 0.0, "box": 0.0, "unseen": 0, "hit_t": -10 ** 6, "box_t": -10 ** 6, "fire_t": None, "shot_t": None,
          "reason": cand.get("reason", "random"), "mode": cand.get("mode"), "threat": int(cand.get("threat", -1)),
          "near": cand.get("near"), "td0": None, "hid": False, "band": cand.get("band")}
    if it["band"]: it["r"] = float(it["band"][1])       # engage band: the encoded radius = its outer edge
    it["phi"] = phi(it, d0)
    return it


def left(it):
    """time left 1 -> 0"""
    return 1.0 - it["t"] / max(1, it["T"])


def step_reward(it, ev):
    """one env step of intent `it` (updated in place) -> (reward before --intent-scale, end or None). ev: d (tiles, true
    distance to the target after the step), out (I am knocked out / eliminated), lost (the target is lost: down, unseen
    for SEEN_S, in the gas, gone without me, not a bush any more), got (engage: down after my damage; farm: box broken
    by me / cube picked; super: landed; check_bush: the hidden enemy hit), dk (own damage dealt / 1000), box (own box
    damage / 1000), in_range (engage), on (hide: on the tile), hid (hide: hidden by it or no enemy in view), shot
    (check_bush: a main attack toward the tile this step), wait (check_bush: a hidden enemy was there, its hit pending),
    near / gone (hide quiet: the threat within near / out of my sight or down); super escape: got = the escape held"""
    if ev.get("out") or ev.get("lost"): return 0.0, "invalid"
    k, sp, d = it["kind"], SPEC[it["kind"]], float(ev["d"]); it["t"] += 1
    p = phi(it, d); r = C * (it["phi"] - p); it["phi"] = p
    ach = False
    if k == "move_to": ach = d <= sp["r"]
    elif k == "avoid": ach = d >= sp["r"]
    elif k == "hold": r += sp["stay"] * (d <= sp["r"])
    elif k == "engage":
        if ev.get("in_range"):
            g = min(sp["dk"] * float(ev.get("dk", 0.0)), sp["dk_cap"] - it["dk"]); it["dk"] += g; r += g
        ach = bool(ev.get("got"))
    elif k == "farm":
        if it["obj"] == "box":
            g = min(sp["box"] * float(ev.get("box", 0.0)), sp["box_cap"] - it["box"]); it["box"] += g; r += g
        ach = bool(ev.get("got"))
    elif k == "regroup": ach = sp["band"][0] <= d <= sp["band"][1]
    elif k == "hide":
        hid = bool(ev.get("on")) and bool(ev.get("hid")); r += sp["stay"] * hid
        if it["mode"] == "quiet":                        # hidden until the threat came near (it sees me then) or left
            ach = (hid or it["hid"]) and bool(ev.get("near") or ev.get("gone"))
        else: ach = hid
        it["hid"] = hid
    elif k == "super": ach = bool(ev.get("got"))
    elif k == "check_bush":
        if ev.get("shot") and it["shot_t"] is None: it["shot_t"] = it["t"]
        ach = it["shot_t"] is not None and (bool(ev.get("got")) or not ev.get("wait"))
        if ach and ev.get("got"): r += sp["hit"]
    end = "achieved" if ach else None
    if end is None and it["t"] >= it["T"]:                # hold: inside at the end; check_bush: shot, the hit still pending
        end = "achieved" if ((k == "hold" and d <= sp["r"]) or (k == "check_bush" and it["shot_t"] is not None)
                             or (k == "hide" and it["mode"] == "quiet" and it["hid"])) else "timeout"
    if end == "achieved": r += sp["bonus"]
    r = min(it["tot"] + r, CAP) - it["tot"]; it["tot"] += r
    return float(r), end


# ------------------------------------------------------------------ random valid intents (training, design 4.4)
def on_screen(mx, my, x, y, W):
    """(x, y) on the screen of a player at (mx, my) on a W-tile-wide map (the fair camera rule)"""
    camx = np.clip(mx, 3000.0, W * TILE - 3000.0)
    return (np.abs(np.asarray(x) - camx) < VIEW[0]) & (np.asarray(y) - my > -VIEW[1]) & (np.asarray(y) - my < VIEW[2])


def gas_margin_t(tx, ty, ring, W, H):
    """tiles from the gas edge of tile (tx, ty) (< 0 = in the gas; env_v5.gas_margin's rule)"""
    return np.minimum(np.minimum(tx, ty), np.minimum(W - 1 - tx, H - 1 - ty)) - ring


def _tiles(scene, lo, hi, mask=None, screen=False, margin=1):
    """tile centres (n, 2) units with lo <= distance <= hi tiles from me, inside the map, gas margin >= margin, mask[ty, tx]"""
    mx, my = scene["me"]; W, H = scene["W"], scene["H"]; tx0, ty0 = int(mx // TILE), int(my // TILE); n = int(np.ceil(hi)) + 1
    ty, tx = np.mgrid[max(ty0 - n, 0):min(ty0 + n + 1, H), max(tx0 - n, 0):min(tx0 + n + 1, W)]
    cx, cy = (tx + 0.5) * TILE, (ty + 0.5) * TILE; d = np.hypot(cx - mx, cy - my) / TILE
    ok = (d >= lo) & (d <= hi) & (gas_margin_t(tx, ty, scene["ring"], W, H) >= margin)
    if mask is not None: ok &= mask[ty, tx]
    if screen: ok &= on_screen(mx, my, cx, cy, W)
    return np.stack([cx[ok], cy[ok]], 1)


def candidates(scene):
    """{kind: [candidate, ...]} of every kind with a valid target. scene: me (x, y) units, range (units), W, H, ring
    (storm step), walk / bush (H, W) bool, foes / mates (n, 3) [player, x, y] of the enemies I see (fair rule) / the mates
    on my screen (both alive, not respawning), boxes / cubes (n, 2) in my view (x, y units); optional: super (my super is
    ready), super_range (units), ammo (0-1, self 1; check_bush needs a shot: > 0.3)"""
    mx, my = scene["me"]; W, H = scene["W"], scene["H"]; out = {}
    dist = lambda xy: np.hypot(np.asarray(xy, np.float64)[..., 0] - mx, np.asarray(xy, np.float64)[..., 1] - my) / TILE
    pts = lambda kind, xy, **kw: [dict(kind=kind, q=-1, pt=(float(x), float(y)), obj=None, **kw) for x, y in xy]
    out["move_to"] = pts("move_to", _tiles(scene, 3, 8, scene["walk"]))             # 3-8 tiles, walkable, out of the gas
    foes = np.asarray(scene["foes"], np.float64).reshape(-1, 3); mates = np.asarray(scene["mates"], np.float64).reshape(-1, 3)
    near = foes[dist(foes[:, 1:]) < SPEC["avoid"]["r"] - 1] if len(foes) else foes   # an enemy within 7 tiles: away from it
    out["avoid"] = pts("avoid", near[:, 1:]) if len(near) else pts("avoid", _tiles(scene, 2, 5, margin=-99))
    out["hold"] = pts("hold", _tiles(scene, 2, 4, scene["walk"]))
    out["engage"] = [dict(kind="engage", q=int(q), pt=None, obj=None) for q, x, y in foes if dist((x, y)) <= 12]
    lo, hi = SPEC["regroup"]["band"]
    out["regroup"] = [dict(kind="regroup", q=int(q), pt=None, obj=None) for q, x, y in mates if not lo <= dist((x, y)) <= hi]
    farm = []
    for obj, key in (("box", "boxes"), ("cube", "cubes")):
        for x, y in np.asarray(scene[key], np.float64).reshape(-1, 2):
            tx, ty = min(max(int(x // TILE), 0), W - 1), min(max(int(y // TILE), 0), H - 1)
            if gas_margin_t(tx, ty, scene["ring"], W, H) >= 0: farm.append(dict(kind="farm", q=-1, pt=(float(x), float(y)), obj=obj))
    out["farm"] = farm
    out["hide"] = pts("hide", _tiles(scene, 1, 6, scene["bush"], screen=True))
    sr = float(scene.get("super_range", 0.0)) / TILE
    out["super"] = [dict(kind="super", q=int(q), pt=None, obj=None) for q, x, y in foes
                    if scene.get("super") and dist((x, y)) <= min(sr + 4, 12)] if sr > 0 else []
    rt = float(scene["range"]) / TILE
    out["check_bush"] = pts("check_bush", _tiles(scene, 1, max(rt, 1.0), scene["bush"], screen=True)) if scene.get("ammo", 1.0) > 0.3 else []
    return {k: v for k, v in out.items() if v}


def sample(scene, rng):
    """a random kind among those with a valid target, then a random valid target of it; None when there is none"""
    c = candidates(scene)
    if not c: return None
    ks = sorted(c, key=K.get); k = ks[int(rng.integers(len(ks)))]
    return dict(c[k][int(rng.integers(len(c[k])))])


# ------------------------------------------------------------------ self-check
def _check():
    # encode: none = zeros, one-hot, clipping, layout
    z = encode([0, 0], [5, 1], [3, 2], [1, 1], [1, 1]); assert z.shape == (2, O.N_INT) and not z.any()
    b = encode([1, 4, 0, 7], [3.0, 40.0, 2.0, -1.0], [-2.0, 0.0, 1.0, 0.5], [1.0, 2.4, 1.0, 0.5], [1.0, 0.5, 1.0, 0.0])
    X = O.I_XY
    assert b[0, 0] == 1 and b[0, 1:X].sum() == 0 and b[1, 3] == 1 and b[3, 6] == 1 and not b[2].any()
    assert np.allclose(b[0, X:], [0.3, -0.2, 0.1, 1.0]) and b[1, X] == 2.5 and np.isclose(b[1, X + 2], 0.24) and b[3, X + 3] == 0
    assert (encode(np.arange(1, len(KINDS)), 0, 0, 1, 1)[:, :X] == np.eye(X)).all() and X == len(KINDS) - 1 == 9
    rng = np.random.default_rng(0)

    def run(cand, ds, evs=None, rt=6.0):
        it = new(cand, ds[0], rt); tot, ends = 0.0, []
        for j, d in enumerate(ds[1:]):
            ev = {"d": d, **((evs or {}).get(j, {}))}; r, e = step_reward(it, ev); tot += r; ends.append(e)
            if e: break
        return it, tot, ends

    P = lambda k, **kw: {**dict(kind=k, q=-1, pt=(0.0, 0.0), obj=None), **kw}
    # telescoping: a random walk that never arrives pays C x (phi(d0) - phi(d_end)) whatever the path
    for k in ("move_to", "hold", "farm", "hide", "regroup"):
        ds = np.r_[7.0, 7.0 + np.cumsum(rng.choice([-0.3, 0.3], 30))]; ds = np.maximum(ds, 4.6)   # stays > every r / band
        it, tot, ends = run(P(k), ds)
        assert abs(tot - C * (phi(new(P(k), 7.0), 7.0) - phi(new(P(k), 7.0), ds[len(ends)]))) < 1e-9, (k, tot)
        assert ends[-1] in (None, "timeout") and (ends[-1] == "timeout") == (len(ends) == it["T"])
    it, tot, _ = run(P("move_to"), [5.0] + [5.3, 5.0] * 19 + [5.0]); assert abs(tot) < 1e-12           # dithering earns nothing
    it, tot, ends = run(P("move_to"), [5.0, 4.0, 3.0, 2.0, 1.0, 0.8, 0.5])                           # arrives: progress + bonus once
    assert ends == [None, None, None, "achieved"] and np.isclose(tot, C * 4 + 0.03) and it["tot"] == tot
    it, tot, ends = run(P("avoid"), [3.0, 5.0, 7.0, 9.5]); assert ends[-1] == "achieved" and np.isclose(tot, C * 5 + 0.03)   # min(d, R)
    it, tot, ends = run(P("hold"), [3.0, 1.0] + [1.2] * 60)                                          # inside until the time runs out
    assert ends[-1] == "achieved" and len(ends) == 50 and np.isclose(tot, C * 1.5 + 0.002 * 50)
    it, tot, ends = run(P("hold"), [3.0, 1.0] + [1.2] * 10 + [3.0] * 60); assert ends[-1] == "timeout"
    it, tot, ends = run(P("regroup"), [8.0, 6.0, 3.0]); assert ends[-1] == "achieved" and np.isclose(tot, C * 4 + 0.02)
    it, tot, ends = run(P("regroup"), [0.5, 0.5, 1.6]); assert ends[-1] == "achieved" and np.isclose(tot, C * 1.0 + 0.02)   # away from a clump
    it, tot, ends = run(P("hide"), [3.0, 1.0, 0.0, 0.0], {1: {"on": True, "hid": False}, 2: {"on": True, "hid": True}})
    assert ends == [None, None, "achieved"] and np.isclose(tot, C * 3 + 0.002 + 0.02)
    # hide quiet (lurk / ambush wait): hidden is not enough; achieved when the threat comes near / leaves, or hidden at
    # the time limit; a shot (env: lost) is invalid
    Q = P("hide", mode="quiet", threat=4, near=3.0); H_ = {"on": True, "hid": True}
    it, tot, ends = run(Q, [0.0, 0.0, 0.0, 0.0], {0: H_, 1: H_, 2: {**H_, "near": True}})
    assert ends == [None, None, "achieved"] and np.isclose(tot, 3 * 0.002 + 0.02) and it["threat"] == 4, (ends, tot)
    it, tot, ends = run(Q, [0.0] * 60, {j: H_ for j in range(60)}); assert ends[-1] == "achieved" and len(ends) == 50
    it, tot, ends = run(Q, [0.0] * 60, {j: (H_ if j < 49 else {"on": True}) for j in range(60)}); assert ends[-1] == "timeout"
    it, tot, ends = run(Q, [0.0] * 5, {0: H_, 1: {**H_, "gone": True}}); assert ends == [None, "achieved"]
    it, tot, ends = run(Q, [0.0] * 5, {0: H_, 1: {"on": True, "near": True}}); assert ends == [None, "achieved"]   # seen as it arrives
    it, tot, ends = run(Q, [0.0] * 5, {0: {"on": True}, 1: {"on": True, "near": True}}); assert not any(ends)   # never hidden
    it, tot, ends = run(Q, [0.0] * 5, {0: H_, 1: {"lost": True}}); assert ends == [None, "invalid"] and np.isclose(tot, 0.002)
    assert new(P("hide"), 1.0)["mode"] is None and new(P("hide"), 1.0)["threat"] == -1
    # engage, mode band (8.5-10): from 5 tiles back to 9 pays 3.5 tiles of progress; walking in from 9 to 6 costs 2.5
    Bd = dict(kind="engage", q=3, pt=None, obj=None, mode="band", band=(8.5, 10.0))
    it, tot, ends = run(Bd, [5.0, 7.0, 9.0, 9.0]); assert it["r"] == 10.0 and np.isclose(tot, C * 3.5) and not any(ends), tot
    it, tot, ends = run(Bd, [9.0, 6.0]); assert np.isclose(tot, -C * 2.5) and np.isclose(run(Bd, [12.0, 9.0])[1], C * 2.0)
    # engage: closing to 0.8 range, damage in range (capped), achieved once; then nothing more
    E = dict(kind="engage", q=3, pt=None, obj=None)
    it, tot, ends = run(E, [9.0, 6.0, 4.0, 4.0, 4.0], {1: {"in_range": True, "dk": 0.06}, 2: {"in_range": True, "dk": 5.0}, 3: {"got": True}})
    assert ends == [None, None, None, "achieved"] and np.isclose(tot, C * (9.0 - 4.8) + 0.05 + 0.05), tot
    # super: closing to 0.8 super range, achieved when it lands (+ 0.05); missing (env: lost) pays no bonus
    S_ = dict(kind="super", q=3, pt=None, obj=None)
    it, tot, ends = run(S_, [9.0, 7.0, 6.0, 6.0], {2: {"got": True}}, rt=4.0)
    assert np.isclose(it["r"], 3.2) and ends == [None, None, "achieved"] and np.isclose(tot, C * (5.0 - 2.8) + 0.05), tot   # phi capped at 5
    it = new(S_, 9.0, 4.0, super_t=10.0); assert np.isclose(it["r"], 8.0) and it["T"] == 30
    # check_bush: a shot toward the tile ends it (+ 0.03); with a hidden enemy, it waits for the hit (+ 0.05 more) or
    # ends at the time limit with the shot's bonus only; no shot by then: timeout
    B_ = P("check_bush")
    it, tot, ends = run(B_, [7.0, 6.0, 5.0], {1: {"shot": True}}, rt=5.0); assert ends == [None, "achieved"] and np.isclose(tot, C * (3.0 - 1.0) + 0.03), tot   # r 4
    it, tot, ends = run(B_, [7.0, 6.0, 5.0, 5.0], {1: {"shot": True, "wait": True}, 2: {"got": True}}, rt=5.0)
    assert ends == [None, None, "achieved"] and np.isclose(tot, C * 2 + 0.03 + 0.05), tot
    it, tot, ends = run(B_, [7.0] + [4.0] * 30, {j: {"shot": j == 1, "wait": True} for j in range(30)}, rt=5.0)
    assert ends[-1] == "achieved" and len(ends) == 20 and np.isclose(tot, C * 3 + 0.03), (tot, ends)
    it, tot, ends = run(B_, [7.0] + [4.0] * 30, rt=5.0); assert ends[-1] == "timeout" and len(ends) == 20
    # invalid on target loss / knocked out: no bonus, pays 0 that step
    for ev in ({"lost": True}, {"out": True}):
        it, tot, ends = run(E, [9.0, 8.0, 7.0], {1: ev}); assert ends == [None, "invalid"] and np.isclose(tot, C * 1.0)
    # the per-intent cap holds for every kind under the best case (start far, damage every step, bonus)
    for k in SPEC:
        cand = E if k == "engage" else S_ if k == "super" else P(k, **({"obj": "box"} if k == "farm" else {}))
        best = {"move_to": [50.0, 0.0], "avoid": [0.0, 20.0], "hold": [50.0] + [0.0] * 60, "engage": [50.0] + [0.0] * 60,
                "farm": [50.0] + [0.0] * 60, "regroup": [50.0, 3.0], "hide": [50.0] + [0.0] * 60, "super": [50.0] + [0.0] * 60,
                "check_bush": [50.0] + [0.0] * 60}[k]
        at = 15 if k in ("super", "check_bush") else 40       # inside their 3 s / 2 s
        ev = {j: {"in_range": True, "dk": 9.0, "box": 9.0, "got": j == at, "on": True, "hid": j == at, "shot": j == at, "wait": True} for j in range(60)}
        it, tot, ends = run(cand, best, ev, rt=30.0); assert 0 < tot <= CAP + 1e-12 and ends[-1] == "achieved", (k, tot, ends)
    # the sampler only returns valid targets
    W = H = 40; walk = np.ones((H, W), bool); walk[:, 22] = False; bush = np.zeros((H, W), bool); bush[18, 17] = bush[25, 20] = True
    scene = dict(me=(20.5 * TILE, 20.5 * TILE), range=2400.0, W=W, H=H, ring=2, walk=walk, bush=bush, super=True, super_range=1800.0, ammo=1.0,
                 foes=[[3, 22.5 * TILE, 20.5 * TILE], [4, 40 * TILE, 5 * TILE]], mates=[[1, 21.0 * TILE, 20.5 * TILE], [2, 28.5 * TILE, 20.5 * TILE]],
                 boxes=[[18.5 * TILE, 21.5 * TILE], [20.5 * TILE, 1.0 * TILE]], cubes=[[23.5 * TILE, 23.5 * TILE]])
    c = candidates(scene); mx, my = scene["me"]
    assert set(c) == set(SPEC), set(c)
    tile = lambda pt: (int(pt[0] // TILE), int(pt[1] // TILE)); dd = lambda pt: np.hypot(pt[0] - mx, pt[1] - my) / TILE
    assert all(3 <= dd(x["pt"]) <= 8 and walk[tile(x["pt"])[::-1]] and gas_margin_t(*tile(x["pt"]), 2, W, H) >= 1 for x in c["move_to"])
    assert [x["pt"] for x in c["avoid"]] == [(22.5 * TILE, 20.5 * TILE)]                              # the enemy 2 tiles away
    assert [x["q"] for x in c["engage"]] == [3] and [x["q"] for x in c["regroup"]] == [1, 2]           # q 4 is 25 tiles off
    assert sorted((x["obj"], x["pt"]) for x in c["farm"]) == [("box", (18.5 * TILE, 21.5 * TILE)), ("cube", (23.5 * TILE, 23.5 * TILE))]   # box 2: in the gas
    assert sorted(tile(x["pt"]) for x in c["hide"]) == [(17, 18), (20, 25)]
    assert [x["q"] for x in c["super"]] == [3] and sorted(tile(x["pt"]) for x in c["check_bush"]) == [(17, 18), (20, 25)]   # range 8
    assert "super" not in candidates(dict(scene, super=False)) and "check_bush" not in candidates(dict(scene, ammo=0.2))
    seen = {}
    for _ in range(400):
        x = sample(scene, rng); seen[x["kind"]] = seen.get(x["kind"], 0) + 1
        assert any(x == y for y in c[x["kind"]]), x
    assert set(seen) == set(c) and min(seen.values()) > 20, seen                                       # every valid kind drawn
    empty = dict(scene, foes=[], mates=[], boxes=[], cubes=[], walk=np.zeros((H, W), bool), bush=np.zeros((H, W), bool))
    assert set(candidates(empty)) == {"avoid"} and all(2 <= dd(x["pt"]) <= 5 for x in candidates(empty)["avoid"])
    assert candidates(dict(empty, ring=30)) == {"avoid": candidates(empty)["avoid"]} and sample(dict(empty, ring=30), rng)["kind"] == "avoid"
    print("intent ok: %d kinds, encode, telescoping progress, bonus once, invalid on target loss, hide quiet, cap %.2f, sampler valid" % (len(SPEC), CAP))


if __name__ == "__main__":
    sys.exit(_check())
