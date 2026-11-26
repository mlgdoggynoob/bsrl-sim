"""Live check of the supers' extras (issues #5 / #6) that super_audit cannot see: wall breaking, Damian's arena edge,
Berry's paint, Meg's eject and R-T's split. One boot, one battle on super_audit.MAP (storm off, every native AI off), six scenes in a row,
then a second battle (storm on) for R-T's legs in the storm:
  1. Bull charges along a lane whose fourth tile is a destructible wall: the wall tile opens (live map, F_MAP) and Bull
     ends past it;
  2. El Primo lands on an open tile next to a destructible wall: that wall tile opens;
  3. Damian charges at a target; once the arena is up, the target is put just inside its edge: it is knocked back toward
     the centre (EdgeCrossing);
  4. Berry, hurt by one shot, paints a lane through his target: the target keeps losing HP after the charge (HotAndDot
     damage) and Berry, hurt by Crow's super just before and walking back into his paint, gains HP (HotAndDot heal)
     within the 3 s before regen starts;
  5. Meg (who spawns in her mech) is hit by three Shellys' supers until the mech breaks: she goes on as small Meg at full
     HP with an empty super, not out, and her own super then builds the mech again;
  6. R-T splits: his head walks faster than whole, one attack hits an enemy next to the head and one next to the legs
     (Eat Static from both), and his second super, after a Shelly super hurt him, puts him where his legs stood, removes
     them and heals him by the legs' card Value3 (1000). At the map's water band (find_water; none is a failure) whole R-T
     stops at the shore and his split head walks onto the water; a super rejoins (no legs left). Back on his spot he splits again, walks away, and three Shelly supers
     break the legs: his head dies with them (the host logs the linked death), his player is out (solo), one kill is
     credited for both, and the killer's super charge rose no more than the legs' damage charges (the head's hit gave none;
     weak: with env.c's charge restore taken out the rise is 0 too, the root charges nothing for a hit without a projectile);
     then (second battle) he splits on the spot nearest the map edge, his head is put deep inside and a forced storm ring
     covers only the legs: they lose the same 10-25 % of their split HP every storm second, then his head dies with them,
     he is out by the storm (elim_gas) and nobody gets a kill.
Not checked live: the blocked rejoin (superfix_moves.c split_land: the legs' spot is not walkable for him), because R-T split
on water puts his legs on the nearest open spot (libg's summon placement; whole R-T placed on water stays there, his legs
do not), and the legs cannot walk onto water; a head that survives his legs (a full block) on water is put on land
(head_land); a teammate respawning on a split head's water spot goes to land (env.c respawn_tick): those need a duo or a
timed spawn protection.
Wall lanes come from the map reference (tiles.csv BlocksMovement / IsDestructible; spawn digits count as blocked).
python -m charge_check            python -m charge_check --check   (no host: the lane finder and the judging rules)"""
import argparse, sys, time
import numpy as np
import super_audit as SA

TILE = SA.TILE
LANE_OPEN_BEFORE, LANE_OPEN_AFTER = 3, 4   # Bull: open tiles before the wall, open tiles after it
PRIMO_RUN = 4                              # El Primo: open tiles behind the landing tile
EDGE_IN = 100                              # Damian: the target goes this far inside the arena's 1500 u edge
PUSH_IN_MIN = 200                          # ... and must end at least this much farther in (one knockback is 420 u)
WATCH = 40                                 # ticks after a fire (2 s)
EJECT_ROUNDS = 6                           # Meg: volleys of three Shelly supers at most (the mech has 7400 HP; one volley breaks it)
REMECH_TRIES = 10                          # Meg: super fills and fires at most, after the eject's protection
SPLIT_FAST = 1.08                          # R-T: split walk / whole walk at least this (+100 of 720 speed = 1.14)
SPLIT_HEAL_MIN = 900                       # ... and the rejoin heals at least this (SplitterLegs_ulti Value3 1000)
SPLIT_AT = 100                             # ... and puts him within this of where his legs stood
WATER_RUN = 3                              # R-T: water tiles in a row east of the shore tile (20 ticks split ~ 870 u = 2.9 tiles)
WATER_IN = 300                             # ... the split head ends at least this far past the shore line,
WATER_WHOLE_MAX = 50                       # ... whole R-T at most this (his half width can overlap the shore line, his centre not)
STORM_SECS = 15                            # R-T's legs in the storm: seconds watched (7800 HP at ~1100 a second ~ 8 s)
STORM_PCT = (10, 25)                       # ... a storm second takes this % of the legs' HP at the split (20 % of their max HP)
SPLIT_AWAY_STEPS = 20                      # R-T: steps (2 ticks) the head walks away before the Shellys break his legs
NAMES = ["BullDude", "Luchador", "Gladiator", "Painter", "Crow", "MechaDude", "Splitter"]   # shooters 0-6; Crow hurts Berry
TARGET = SA.FILLER


# ------------------------------------------------------------------ map
def grid(location=SA.MAP):
    """(H, W) array of 'o' open, 'd' destructible blocking, 'x' other blocking (spawn digits too)"""
    from nbpc import diversity as D
    ids, rows = D.map_reference(location); H, W = len(rows), len(rows[0])
    t = D.table("tiles.csv").items()
    blk = {i for _, (i, r) in t if r.get("BlocksMovement") == "true"}
    des = {i for _, (i, r) in t if r.get("BlocksMovement") == "true" and r.get("IsDestructible") == "true"}
    g = np.full((H, W), "o"); ids = np.asarray(ids).reshape(H, W); raw = np.array([list(r) for r in rows])
    g[np.isin(ids, list(blk))] = "x"; g[np.isin(ids, list(des))] = "d"; g[np.char.isdigit(raw)] = "x"
    return g


def _cells(g, x, y, dx, dy, a, b):   # [(cell, side, side)] for x + k*dx, k in a..b; None when it leaves the map
    H, W = g.shape; out = []
    for k in range(a, b + 1):
        cx, cy = x + k * dx, y + k * dy
        if not (1 <= cx < W - 1 and 1 <= cy < H - 1): return None
        out.append((g[cy, cx], g[cy + dx, cx + dy], g[cy - dx, cx - dy]))
    return out


def find_lane(g):
    """Bull: (x, y, dx, dy) tile of the start with LANE_OPEN_BEFORE open tiles (k 0..2), a destructible wall at k 3 and
    LANE_OPEN_AFTER open tiles after it; no unbreakable tile beside the lane (Bull's 200 u break radius reaches them)"""
    H, W = g.shape; n = LANE_OPEN_BEFORE + 1 + LANE_OPEN_AFTER
    for y in range(H):
        for x in range(W):
            for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
                c = _cells(g, x, y, dx, dy, 0, n - 1)
                if not c: continue
                mid = [k[0] for k in c]
                if mid[:LANE_OPEN_BEFORE] != ["o"] * LANE_OPEN_BEFORE or mid[LANE_OPEN_BEFORE] != "d": continue
                if mid[LANE_OPEN_BEFORE + 1:] != ["o"] * LANE_OPEN_AFTER: continue
                if any("x" in k[1:] for k in c) or any(k[1] != "o" or k[2] != "o" for k in c[:LANE_OPEN_BEFORE]): continue
                return x, y, dx, dy
    return None


def find_landing(g):
    """El Primo: (x, y, dx, dy) open landing tile with a destructible wall at +1 and PRIMO_RUN open tiles behind it"""
    H, W = g.shape
    for y in range(H):
        for x in range(W):
            for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
                c = _cells(g, x, y, dx, dy, -PRIMO_RUN, 1)
                if not c: continue
                mid = [k[0] for k in c]
                if mid[-1] == "d" and mid[:-1] == ["o"] * (PRIMO_RUN + 1) and all(k[1] == "o" and k[2] == "o" for k in c[:-1]):
                    return x, y, dx, dy
    return None


def centre(tx, ty): return (tx + 0.5) * TILE, (ty + 0.5) * TILE


# ------------------------------------------------------------------ judging
def judge_wall(before, after, x0, x1, wall_xy, blocks):
    """before / after live tile ids of the wall cell; x0 / x1 the charger's progress along the lane (tiles) before and
    after; wall_xy its progress at the wall -> failures"""
    bad = []
    if before not in blocks: bad.append("the wall tile was open before the charge (%d)" % before)
    if after in blocks: bad.append("the wall tile still blocks after the charge (%d)" % after)
    if x1 is not None and x1 < wall_xy: bad.append("the charger stopped before the wall (%.1f < %.1f tiles)" % (x1, wall_xy))
    return bad


def judge_edge(d_put, d_end):
    return [] if d_end <= d_put - PUSH_IN_MIN else ["target not pushed back in: %.0f u from the centre -> %.0f" % (d_put, d_end)]


def judge_eject(cid0, after, remech):
    """after: (alive, eliminated, char_id, data, hp, max_hp, super_charge) of Meg's player once her mech broke; remech: her
    brawler's data after her own super -> [problems]"""
    alive, elim, cid, data, hp, mx, sc = after; bad = []
    if not alive or elim: bad.append("Meg is out after her mech broke")
    elif cid == cid0 or data != "MechaDude": bad.append(f"no small Meg after the mech broke (brawler {cid}, {data})")
    elif hp != mx or sc != 0: bad.append(f"small Meg starts at {hp}/{mx} HP, super {sc} (want full HP, an empty super)")
    if not bad and remech != "MechaDudeBig": bad.append(f"her super did not build the mech again ({remech})")
    return bad


def judge_split(split, d_whole, d_split, hits, rejoin):
    """R-T: split = legs spawned; walks in units over the same ticks; hits = (HP lost by the enemy next to the head, next to the
    legs); rejoin = (distance from where the legs stood, legs still there, HP gained, was hurt) -> [problems]"""
    if not split: return ["no SplitterLegs after the super"]
    bad = []
    if d_split < d_whole * SPLIT_FAST: bad.append(f"split walk {d_split:.0f} u, whole {d_whole:.0f} u (want x{SPLIT_FAST})")
    if hits[0] <= 0: bad.append("no Eat Static hit next to the head")
    if hits[1] <= 0: bad.append("no Eat Static hit next to the legs")
    at, left, heal, hurt = rejoin
    if at > SPLIT_AT: bad.append(f"the rejoin left him {at:.0f} u from his legs")
    if left: bad.append("the legs are still there after the rejoin")
    if hurt and heal < SPLIT_HEAL_MIN: bad.append(f"the rejoin healed {heal} (want >= {SPLIT_HEAL_MIN})")
    return bad


def find_water(rows):
    """R-T: (x, y) of an open shore tile (raw map rows: '.' open, 'W' water) with an open tile west of it and WATER_RUN
    water tiles east of it; None when the map has none"""
    for y, r in enumerate(rows):
        for x in range(1, len(r) - WATER_RUN):
            if r[x - 1] == "." and r[x] == "." and r[x + 1:x + 1 + WATER_RUN] == "W" * WATER_RUN: return x, y
    return None


def judge_water(water):
    """water: None (no water band found: a failure, SA.MAP has one) or (whole R-T's end, the split head's end, units past the
    shore line (negative: on land), legs left after the rejoin) -> [problems]"""
    if water is None: return ["no water band on the map: water walk not checked"]
    bad = []
    if water[0] > WATER_WHOLE_MAX: bad.append("whole R-T walked %.0f u onto the water" % water[0])
    if water[1] < WATER_IN: bad.append("the split head got %.0f u past the shore (want >= %d)" % (water[1], WATER_IN))
    if water[2]: bad.append("the rejoin after the water walk left the legs")
    return bad


def judge_linked(linked):
    """linked: (the legs broke and no shell hit the head, R-T alive, eliminated, kills credited to anyone minus the other
    players who died meanwhile, linked deaths in the host log, the killer's super charge rise on that step, the rise the
    legs' damage allows) after three Shelly supers on his legs -> [problems]"""
    broke, alive, out, kills, logged, rise, allowed = linked
    if not broke: return ["the Shelly supers did not break the legs alone"]
    bad = [] if logged == 1 else [f"{logged} linked deaths in the host log (want 1)"]
    if alive or not out: return bad + ["R-T is not out after his legs broke"]
    if kills != 1: bad.append(f"{kills} kills credited for one R-T (legs + head)")
    if rise > allowed: bad.append(f"the killer's super charge rose {rise} (the legs' damage allows {allowed}): the head's hit charged it")
    return bad


def judge_storm(storm):
    """storm: (the legs' HP at the split, their HP at each storm second until gone, R-T alive, eliminated, by the storm,
    kills credited) -> [problems]"""
    hp0, hps, alive, out, egas, kills = storm
    drops = [a - b for a, b in zip(hps, hps[1:]) if b > 0 and a - b > 0][1:]   # whole storm seconds the legs lived through (the
                                                                             # first can start mid-second)
    bad = []
    if len(drops) < 2: bad.append("the storm took the legs' HP in %d seconds only" % len(drops))
    elif max(drops) > min(drops) * 1.05: bad.append("the legs' storm seconds differ: %s" % drops)
    elif not STORM_PCT[0] <= 100 * min(drops) / hp0 <= STORM_PCT[1]:
        bad.append("a storm second took %.0f %% of the legs' HP (want %d-%d)" % ((100 * min(drops) / hp0,) + STORM_PCT))
    if hps and hps[-1] > 0: bad.append("the legs lived through the storm")
    if alive or not out: bad.append("R-T is not out after his legs died in the storm")
    elif not egas: bad.append("R-T's elimination is not the storm's")
    if kills: bad.append(f"{kills} kills credited for R-T's storm death")
    return bad


def judge_paint(target_loss, heal, pre_damaged):
    bad = []
    if target_loss <= 0: bad.append("the target lost no HP standing in the paint after the charge")
    if pre_damaged and heal <= 0: bad.append("Berry gained no HP in his paint")
    return bad


# ------------------------------------------------------------------ live
class Run:
    def __init__(self, inst):
        from nbpc import proto as P
        self.inst, self.P = inst, P
        self.idle = {i: (-1, 0, 0.0, 0.0) for i in range(10)}
        self.storm = None   # forced storm ring (R-T's storm part)

    def step(self, acts=None, ticks=2, map_=False):
        P = self.P; a = dict(self.idle); a.update(acts or {})
        return self.inst.step(actions=a, ticks=ticks, flags=P.F_STATE | (P.F_MAP if map_ else 0), native_mask=0, storm=self.storm)

    def place(self, pos):
        self.inst.setup(positions={i: (int(x), int(y)) for i, (x, y) in pos.items()}, ai_off=list(range(10)), unprotect=list(range(10)))
        for _ in range(3): r = self.step()
        return r

    def fire(self, s, aim, sd, watch=WATCH):
        self.inst.setup(super_fill=[s]); self.step(ticks=1)
        r = self.step({s: (-1, 2, aim, sd)}, 1); n = 1
        while n < watch: r = self.step(); n += 2
        return r

    def tiles(self):
        r = self.step(map_=True); return self.inst.map_tiles().reshape(r.map_h, r.map_w)


def _form(inst, i):
    """the data name of player i's brawler (None: none)"""
    st = SA.parse_state(inst.state_bytes()); bid = SA.brawler_ids(st).get(i) if st is not None else None
    rows = [x for x in st["ch"] if int(x[0]) == bid] if bid is not None else []
    return SA.data_name(int(rows[0][1])) if rows else None


def _parts(inst, i):
    """{data name: (x, y, hp)} of player i's living characters (R-T's head and legs)"""
    st = SA.parse_state(inst.state_bytes())
    return {SA.data_name(int(x[1])): (int(x[3]), int(x[4]), int(x[6])) for x in st["ch"] if int(x[2]) == i and int(x[6]) > 0}


def _linked_logs(inst):
    """R-T's linked deaths so far: the host log's "rt legs down" lines (env.c split_link, the first 100 a run)"""
    try: return sum("rt legs down" in l for l in open(inst.log_path, errors="replace"))
    except (OSError, AttributeError, TypeError): return -1


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="self-check of the lane finder and the judging (no host)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--host-args", default="", help="extra game host arguments, e.g. '--native-charge 2'")
    a = ap.parse_args()
    if a.check: return _check()
    from nbpc import diversity as D
    from nbpc.instance import Instance
    g = grid(); lane, land = find_lane(g), find_landing(g)
    if not lane or not land: sys.exit(f"{SA.MAP}: no wall lane ({lane}) or landing ({land}) on the map")
    spots = SA.find_spots(SA.MAP)
    blocks = {i for _, (i, r) in D.table("tiles.csv").items() if r.get("BlocksMovement") == "true"}
    info = {n: SA.expected(n) for n in NAMES}
    inst = Instance(0, tag="cc", extra_args=a.host_args.split()); t0 = time.time(); inst.start(); inst.wait_ready()
    print("charge_check: host ready in %.0f s" % (time.time() - t0), flush=True)
    fails = {}
    try:
        names = NAMES + [TARGET] * (10 - len(NAMES))   # shooters 0-6, targets 7-9
        inst.reset(93500000 + a.seed, gas=0, flags=0, native_mask=0, obs_mask=0, div=D.make_div(location=SA.MAP, chr=names))
        R = Run(inst); R.step(ticks=10)
        ref = np.asarray(D.map_reference(SA.MAP)[0]).reshape(g.shape); live = R.tiles()
        same = float(np.mean(live == ref)) if live.shape == ref.shape else 0.0
        if same < 0.9: sys.exit("charge_check: the live map does not match the map reference (%.0f %% equal)" % (100 * same))
        R.place({i: spots[i][:2] for i in range(10)})   # everyone on a clear spot of their own; a scene moves only its pair

        # 1. Bull's lane
        x, y, dx, dy = lane; sx, sy = centre(x, y); wx, wy = x + 3 * dx, y + 3 * dy; tx, ty = centre(x + 6 * dx, y + 6 * dy)
        R.place({0: (sx, sy), 9: (tx, ty)})
        before = int(R.tiles()[wy, wx]); aim = float(np.degrees(np.arctan2(dy, dx)))
        r = R.fire(0, aim, min(1.0, (7 * TILE) / info["BullDude"]["range"]))
        prog = ((r.pl[0].x - sx) * dx + (r.pl[0].y - sy) * dy) / TILE if r.pl[0].alive else None
        fails["Bull wall lane"] = judge_wall(before, int(R.tiles()[wy, wx]), 0, prog, 3, blocks)

        # 2. El Primo's landing
        x, y, dx, dy = land; lx, ly = centre(x, y); sx, sy = lx - PRIMO_RUN * TILE * dx, ly - PRIMO_RUN * TILE * dy
        R.place({1: (sx, sy), 8: (lx + 100 * dx, ly + 100 * dy)})
        before = int(R.tiles()[y + dy, x + dx]); aim = float(np.degrees(np.arctan2(dy, dx)))
        R.fire(1, aim, min(1.0, (PRIMO_RUN * TILE + 100) / info["Luchador"]["range"]))
        fails["El Primo landing wall"] = judge_wall(before, int(R.tiles()[y + dy, x + dx]), 0, None, 0, blocks)

        # 3. Damian's arena edge (spot 0, corridor 0)
        (sx, sy, dirs) = spots[0]; dx, dy = dirs[0]; tx, ty = sx + dx * 1200, sy + dy * 1200
        R.place({2: (sx, sy), 7: (tx, ty)})
        r = R.fire(2, float(np.degrees(np.arctan2(dy, dx))), min(1.0, 1500 / info["Gladiator"]["range"]), watch=20)
        cx, cy = r.pl[2].x, r.pl[2].y
        R.place({7: (cx - dx * (1500 - EDGE_IN), cy - dy * (1500 - EDGE_IN)), 2: (cx, cy)})
        d_put = 1500.0 - EDGE_IN   # the push starts within the placement steps, so the requested distance counts
        for _ in range(10): r = R.step()
        fails["Damian arena edge"] = judge_edge(d_put, float(np.hypot(r.pl[7].x - cx, r.pl[7].y - cy)))

        # 4. Berry's paint (spot 1)
        (sx, sy, dirs) = spots[1]; dx, dy = dirs[0]; tx, ty = sx + dx * 900, sy + dy * 900; aim = float(np.degrees(np.arctan2(dy, dx)))
        # pre-damage: Crow's super lands on Berry from 900 u behind him (a normal attack does not land in this harness)
        R.place({3: (sx, sy), 9: (tx, ty), 4: (sx - dx * 900, sy - dy * 900)})   # target 9: 7 still carries Damian's arena side
        R.fire(4, aim, min(1.0, 1000 / info["Crow"]["range"]), watch=24)
        r = R.place({4: spots[4][:2]}); pre = r.pl[3].alive and r.pl[3].hp < r.pl[3].max_hp
        r = R.fire(3, aim, 1.0, watch=18)   # the charge is over (2500 u at 3000 u/s ~ 17 ticks)
        thp = r.pl[9].hp; hp_low = r.pl[3].hp
        back = int(round(((aim + 180) % 360) / 22.5)) % 16
        for _ in range(5): r = R.step({3: (back, 0, 0.0, 0.0)})   # Berry walks back into his paint
        for _ in range(10): r = R.step(); hp_low = min(hp_low, r.pl[3].hp)
        print("charge_check: Berry hp %d -> %d after his paint, target lost %d after the charge" % (hp_low, r.pl[3].hp, thp - r.pl[9].hp), flush=True)
        fails["Berry paint"] = judge_paint(thp - r.pl[9].hp if r.pl[9].alive else thp, r.pl[3].hp - hp_low, pre)
        R.place({9: spots[9][:2]})
        if not pre: print("charge_check: Berry's pre-damage missed: heal not checked", flush=True)

        # 5. Meg's eject (her own spot): Shellys 7-9 stand 350 u in front of her, side by side, and super her until the mech breaks
        meg, att = 5, (7, 8, 9); (sx, sy, dirs) = spots[meg]; dx, dy = dirs[0]
        pos = {meg: (sx, sy)}
        for k, q in enumerate(att): pos[q] = (sx + dx * 350 + (k - 1) * dy * 150, sy + dy * 350 + (k - 1) * dx * 150)
        r = R.place(pos); cid0 = r.pl[meg].char_id; back = (float(np.degrees(np.arctan2(dy, dx))) + 180) % 360
        for _ in range(EJECT_ROUNDS):
            inst.setup(super_fill=list(att)); R.step(ticks=1)
            r = R.step({q: (-1, 2, back, 0.15) for q in att}, 1)
            for _ in range(6):
                r = R.step()
                if not r.pl[meg].alive or r.pl[meg].char_id != cid0: break
            if not r.pl[meg].alive or r.pl[meg].char_id != cid0: break
        R.place({q: spots[q][:2] for q in att})   # the Shellys leave: small Meg is not hit again
        p = r.pl[meg]; after = (bool(p.alive), bool(p.eliminated), int(p.char_id), _form(inst, meg), int(p.hp), int(p.max_hp), int(p.super_charge))
        print("charge_check: Meg after her mech broke: alive %d out %d brawler %d %s %d/%d HP super %d" % after, flush=True)
        remech = None
        if after[0] and after[3] == "MechaDude":
            for _ in range(REMECH_TRIES):   # the eject's protection can swallow a fire: fill and fire again
                R.fire(meg, back, 0.5, watch=30); remech = _form(inst, meg)
                if remech != "MechaDude": break
        fails["Meg eject"] = judge_eject(cid0, after, remech)

        # 6. R-T's split (his own spot): whole walk, split, split walk, Eat Static from head and legs, hurt, rejoin
        rt = 6; (sx, sy, dirs) = spots[rt]; dx, dy = dirs[0]; aim = float(np.degrees(np.arctan2(dy, dx)))
        fwd = int(round((aim % 360) / 22.5)) % 16
        def walk():
            x0 = _parts(inst, rt)["Splitter"][:2]
            for _ in range(10): R.step({rt: (fwd, 0, 0.0, 0.0)})
            x1 = _parts(inst, rt)["Splitter"][:2]; return float(np.hypot(x1[0] - x0[0], x1[1] - x0[1]))
        R.place({rt: (sx, sy)}); d_whole = walk()
        R.place({rt: (sx, sy)}); R.fire(rt, (aim + 180) % 360, 0.5, watch=10)
        legs0 = _parts(inst, rt).get("SplitterLegs"); d_split = walk() if legs0 else 0.0
        hits = (0, 0)
        if legs0:
            h, L = _parts(inst, rt)["Splitter"], _parts(inst, rt)["SplitterLegs"]
            r = R.place({8: (h[0] + dx * 400, h[1] + dy * 400), 9: (L[0] - dx * 400, L[1] - dy * 400)}); hp8, hp9 = r.pl[8].hp, r.pl[9].hp
            R.step({rt: (-1, 1, aim, 0.5)}, 1)
            for _ in range(15): r = R.step()
            hits = (hp8 - r.pl[8].hp, hp9 - r.pl[9].hp)
            h = _parts(inst, rt)["Splitter"]
            R.place({8: (h[0] + dx * 300, h[1] + dy * 300), 9: spots[9][:2]})
            R.fire(8, (aim + 180) % 360, 0.3, watch=10)
            r = R.place({8: spots[8][:2]}); hp_hurt = r.pl[rt].hp; L = _parts(inst, rt).get("SplitterLegs")
            R.fire(rt, aim, 0.5, watch=6)
            r = R.step(); p = _parts(inst, rt); h = p["Splitter"]
            at = float(np.hypot(h[0] - L[0], h[1] - L[1])) if L else 1e9
            rejoin = (at, "SplitterLegs" in p, r.pl[rt].hp - hp_hurt, hp_hurt < r.pl[rt].max_hp)
        else: rejoin = (1e9, True, 0, True)
        print("charge_check: R-T walk %.0f whole, %.0f split; Eat Static head %d legs %d; rejoin %.0f u from the legs, legs left %d, "
              "heal %d" % (d_whole, d_split, hits[0], hits[1], rejoin[0], rejoin[1], rejoin[2]), flush=True)
        # water: whole and split walks east from a shore tile, then a super rejoins
        water, wat = None, find_water(D.map_reference(SA.MAP)[1])
        if legs0 and wat:
            wx, wy = centre(*wat); shore = (wat[0] + 1) * TILE
            def east():
                for _ in range(10): R.step({rt: (0, 0, 0.0, 0.0)})
                return _parts(inst, rt)["Splitter"][0] - shore
            R.place({rt: (wx, wy)}); e_whole = east()
            R.place({rt: (wx, wy)}); R.fire(rt, 180.0, 0.5, watch=10)
            e_split = east() if "SplitterLegs" in _parts(inst, rt) else -1e9
            if "SplitterLegs" in _parts(inst, rt): R.fire(rt, 0.0, 0.5, watch=6)   # rejoin: back on the shore
            water = (float(e_whole), float(e_split), "SplitterLegs" in _parts(inst, rt))
            print("charge_check: R-T at the water (tile %s): whole %.0f u past the shore, split head %.0f u; after the rejoin legs %s"
                  % ((wat,) + water), flush=True)
        elif not wat: print("charge_check: no water band on %s" % SA.MAP, flush=True)
        # linked death: split on his spot, walk away, three Shellys beside the legs super them
        linked = (False, True, False, 0, 0, 0, 0)
        if legs0:
            ex, ey = -dy, dx   # the Shellys stand beside the legs, square to the head's way: their shells pass away from him
            R.place({rt: (sx, sy)}); R.fire(rt, (aim + 180) % 360, 0.5, watch=10)
            L = _parts(inst, rt).get("SplitterLegs")
            if L:
                for _ in range(SPLIT_AWAY_STEPS): r = R.step({rt: (fwd, 0, 0.0, 0.0)})
                hp_head = r.pl[rt].hp   # the head's HP from here on: a drop while the legs stand is a shell on him
                # 350 u off the legs, 400 u apart (150 u apart their supers hit each other), each aiming at the legs
                pos = {q: (L[0] + ex * 350 + (k - 1) * dx * 400, L[1] + ey * 350 + (k - 1) * dy * 400) for k, q in enumerate((7, 8, 9))}
                r = R.place(pos); at = {q: float(np.degrees(np.arctan2(L[1] - y, L[0] - x))) for q, (x, y) in pos.items()}
                up0 = [q for q in range(10) if q != rt and r.pl[q].hp > 0]   # by HP: a target out earlier stands again after R.place
                kills = 0; kl = lambda r: sum(int(p.kills) for p in r.pl)   # NbePlayer.kills: per step
                head_hit = False; legs_up = lambda: "SplitterLegs" in _parts(inst, rt)
                logs0 = _linked_logs(inst)
                rate = [0, 0]   # the Shellys' super charge rise and damage dealt on steps without a kill (charge per damage)
                rise = allowed = 0; hp_prev = r.pl[rt].hp
                def watch(r0, r):
                    nonlocal kills, rise, allowed, hp_prev
                    k = [q for q in (7, 8, 9) if r.pl[q].kills]; kills += kl(r)
                    for q in (7, 8, 9):
                        dc, dd = int(r.pl[q].super_charge) - int(r0.pl[q].super_charge), int(r.pl[q].damage_dealt)
                        if q in k:   # the kill step: the head's HP (his linked hit) is in dealt, not in what may charge
                            rise = dc; allowed = int(np.ceil(max(dd - hp_prev, 0) * rate[0] / max(rate[1], 1) * 1.25)) + 2
                        elif dc >= 0 and dd > 0: rate[0] += dc; rate[1] += dd
                    hp_prev = r.pl[rt].hp
                for _ in range(EJECT_ROUNDS):
                    inst.setup(super_fill=[7, 8, 9]); r0 = R.step(ticks=1); kills += kl(r0)
                    r = R.step({q: (-1, 2, at[q], 0.15) for q in (7, 8, 9)}, 1); kills += kl(r)
                    for _ in range(6):
                        r0, r = r, R.step(); watch(r0, r); up = legs_up()
                        head_hit |= up and r.pl[rt].hp < hp_head   # a shell on the head itself: not a linked death
                        if not up or not r.pl[rt].alive: break
                    if not up or not r.pl[rt].alive: break
                for _ in range(8): r0, r = r, R.step(); watch(r0, r)   # shells in flight land, a death shows a step late
                died = sum(r.pl[q].hp <= 0 for q in up0)
                linked = (not legs_up() and not head_hit, bool(r.pl[rt].alive), bool(r.pl[rt].eliminated), kills - died,
                          _linked_logs(inst) - logs0, rise, allowed)
                print("charge_check: R-T legs broken by Shelly supers: broke %d (head hit directly %d), alive %d, out %d, kills credited %d"
                      " (all %d, other deaths %d; Shellys 7-9 hp %s); linked deaths logged %d; killer's super charge +%d (allowed %d)"
                      % ((linked[0], head_hit) + linked[1:4] + (kills, died, [int(r.pl[q].hp) for q in (7, 8, 9)]) + linked[4:]), flush=True)
            else: print("charge_check: R-T split again: no legs", flush=True)
        fails["R-T split"] = judge_split(legs0 is not None, d_whole, d_split, hits, rejoin) + judge_water(water) + judge_linked(linked)

        # 6b. R-T's legs in the storm (second battle, storm on): split on the spot nearest the map edge, the head deep inside,
        # a forced storm ring over the legs only
        inst.reset(93600000 + a.seed, gas=1, flags=0, native_mask=0, obs_mask=0, div=D.make_div(location=SA.MAP, chr=names))
        R.step(ticks=10); H, W = g.shape
        marg = lambda x, y: min(int(x // TILE), int(y // TILE), W - 1 - int(x // TILE), H - 1 - int(y // TILE))
        order = sorted(range(10), key=lambda k: marg(*spots[k][:2])); edge, deep = spots[order[0]][:2], spots[order[-1]][:2]
        pos = {q: (deep[0] + (k % 4 - 1.5) * 200, deep[1] + (k // 4) * 200 + 600) for k, q in enumerate(q for q in range(10) if q != rt)}
        pos[rt] = edge; R.place(pos); R.fire(rt, 0.0, 0.5, watch=10)
        L = _parts(inst, rt).get("SplitterLegs"); storm = None; kl = lambda r: sum(int(p.kills) for p in r.pl)
        if L:
            R.place({rt: deep}); R.storm = marg(L[0], L[1]) + 1   # the ring covers tiles with a margin below it
            hps, kills = [_parts(inst, rt).get("SplitterLegs", (0, 0, 0))[2]], 0
            for _ in range(STORM_SECS):
                for _ in range(10): r = R.step(); kills += kl(r)
                hps.append(_parts(inst, rt).get("SplitterLegs", (0, 0, 0))[2])
                if not hps[-1]: break
            for _ in range(4): r = R.step(); kills += kl(r)   # the head's elimination shows a step late
            storm = (L[2], hps, bool(r.pl[rt].alive), bool(r.pl[rt].eliminated), bool(r.pl[rt].elim_gas), kills)
            print("charge_check: R-T legs in the storm (ring %d, legs margin %d, head margin %d): legs hp %s; alive %d out %d by gas %d, kills %d"
                  % (R.storm, marg(L[0], L[1]), marg(r.pl[rt].x, r.pl[rt].y), hps, storm[2], storm[3], storm[4], kills), flush=True)
            R.storm = None
        fails["R-T legs in the storm"] = judge_storm(storm) if storm else ["no SplitterLegs after the super"]
    finally:
        inst.close()
    bad = 0
    for k, v in fails.items():
        print("%-22s %s" % (k, "ok" if not v else "FAIL: " + "; ".join(v))); bad += bool(v)
    print("charge_check: %d of %d scenes ok" % (len(fails) - bad, len(fails)))
    sys.exit(1 if bad else 0)


def _check():
    g = np.full((12, 14), "o"); g[0, :] = g[-1, :] = "x"; g[:, 0] = g[:, -1] = "x"
    g[5, 5] = "d"                                         # a wall in an open field
    x, y, dx, dy = find_lane(g)
    assert g[y + 3 * dy, x + 3 * dx] == "d" and all(g[y + k * dy, x + k * dx] == "o" for k in (0, 1, 2, 4, 5, 6, 7)), (x, y, dx, dy)
    g2 = g.copy(); g2[4, :] = "x"; g2[6, :] = "x"         # unbreakable rows beside the only east-west lane
    l2 = find_lane(g2); assert l2 is None or l2[2] == 0, l2   # any lane left runs north-south
    x, y, dx, dy = find_landing(g)
    assert g[y + dy, x + dx] == "d" and all(g[y - k * dy, x - k * dx] == "o" for k in range(PRIMO_RUN + 1))
    assert find_landing(np.full((8, 8), "o")) is None and find_lane(np.full((8, 8), "x")) is None
    B = {1}
    assert judge_wall(1, 0, 0, 5.0, 3, B) == [] and len(judge_wall(1, 1, 0, 5.0, 3, B)) == 1
    assert len(judge_wall(0, 0, 0, 5.0, 3, B)) == 1 and len(judge_wall(1, 0, 0, 2.0, 3, B)) == 1 and judge_wall(1, 0, 0, None, 0, B) == []
    assert judge_edge(1400, 1000) == [] and judge_edge(1400, 1350)
    assert judge_paint(200, 100, True) == [] and len(judge_paint(0, 0, True)) == 2 and judge_paint(200, 0, False) == []
    ok = (True, False, 7, "MechaDude", 4800, 4800, 0)
    assert judge_eject(1, ok, "MechaDudeBig") == [] and len(judge_eject(1, ok, "MechaDude")) == 1
    assert len(judge_eject(1, (False, True, 1, None, 0, 0, 0), None)) == 1 and len(judge_eject(7, ok, "MechaDudeBig")) == 1
    assert len(judge_eject(1, ok[:4] + (100, 4800, 0), "MechaDudeBig")) == 1
    good = (True, 756, 867, (2480, 2480), (0.0, False, 1000, True))
    assert judge_split(*good) == [] and judge_split(False, 0, 0, (0, 0), good[4]) == ["no SplitterLegs after the super"]
    assert len(judge_split(True, 756, 756, (2480, 0), (500.0, True, 0, True))) == 5
    assert judge_split(True, 756, 867, (1, 1), (0.0, False, 0, False)) == []   # not hurt: the heal is not judged
    rows = ["..........", "x...WWWW..", "..WW......"]
    assert find_water(rows) == (3, 1) and find_water(["..WW......"]) is None and find_water(["WWW...."]) is None and find_water(["...WWW"]) == (2, 0)
    assert len(judge_water(None)) == 1 and judge_water((-120.0, 700.0, False)) == []
    assert len(judge_water((300.0, 700.0, False))) == 1 and len(judge_water((-120.0, -120.0, False))) == 1
    assert len(judge_water((-120.0, 700.0, True))) == 1
    ok = (True, False, True, 1, 1, 30, 40)
    assert judge_linked(ok) == [] and len(judge_linked((False, True, False, 0, 0, 0, 0))) == 1
    assert len(judge_linked((True, True, False, 1, 1, 0, 0))) == 1 and len(judge_linked((True, False, True, 2, 1, 0, 0))) == 1
    assert len(judge_linked((True, False, True, 0, 1, 0, 0))) == 1 and len(judge_linked((True, False, True, 1, 0, 0, 0))) == 1
    assert len(judge_linked((True, False, True, 1, 1, 900, 40))) == 1
    good = (7800, [7800, 7000, 5908, 4816, 3724, 2632, 1540, 448, 0], False, True, True, 0)
    assert judge_storm(good) == []
    assert len(judge_storm((7800, [7800, 7800], False, True, True, 0))) == 2   # no storm seconds, the legs lived
    assert len(judge_storm((7800, [7800, 6708, 5000, 2000, 0], False, True, True, 0))) == 1   # a ramp
    assert len(judge_storm((7800, [7800, 7700, 7600, 7500, 0], False, True, True, 0))) == 1   # too little
    assert len(judge_storm(good[:2] + (True, False, False, 0))) == 1 and len(judge_storm(good[:4] + (False, 0))) == 1
    assert len(judge_storm(good[:5] + (1,))) == 1
    print("charge_check ok: lane finder, landing finder, water finder, judging (walls, edge, paint, eject, split, water,"
          " linked death, storm)")


if __name__ == "__main__":
    main()
