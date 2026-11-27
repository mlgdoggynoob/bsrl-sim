"""ObsV5.build with its per-agent loops vectorised over the batch (train_fast.py workers); same observations for the
same RNG state: the random draws are obs_v5.ObsV5.build's code unchanged, in the same order.

    ob = FastObsV5(noise=O.NOISE, seed=0)          # drop-in for obs_v5.ObsV5
    o = ob.build(vec, grid, meta, ids, who=who, gadget=gadget, hyper=hyper)   # who / gadget / hyper as ObsV5.build's
    pv = priv_fast(env, ids)                         # == train_ppo.priv(env, ids)

* velocity matching: one (B, N_ENT, N_ENT) distance block instead of a loop over agents;
* latency queue: a ring of LAT + 1 frames per agent in preallocated arrays instead of per-agent dict copies.
Per-agent state lives in slots (one per entry of ObsV5.ep, freed with its eviction rule).

    python -m fast_obs      # self-check vs ObsV5 on synthetic batches (no game); real batches: test_fast.py
"""
import numpy as np
import obs_v5 as O
from obs_v5 import smooth_vel, N_ENT, F_ENT, XY, VEL, G, ENT, from_state2, hud_mask, UNKNOWN, SEG, DROP_CLS, BLEED_ROW, _TALL_M, _BLEED_CLS, _S, RAD, _AREA_C, F as FAIR


class FastObsV5(O.ObsV5):
    def __init__(self, noise=O.NOISE, seed=0, ticks=2, cap=4097 + 2048):   # ep max + one batch (slots are freed after the build)
        super().__init__(noise, seed, ticks)
        R = (noise["latency"][1] if noise else 0) + 1; self.R = R
        self.free = list(range(cap - 1, -1, -1)); self.unfree = []
        self.t = np.zeros(cap, np.int64); self.has = np.zeros(cap, bool)
        self.pon = np.zeros((cap, N_ENT), bool); self.pcls = np.zeros((cap, N_ENT), np.int64)
        self.pxy = np.zeros((cap, N_ENT, 2), np.float32); self.pn = np.zeros((cap, N_ENT, 2), np.float32)
        self.pest = np.zeros((cap, N_ENT, 2), np.float32); self.page = np.zeros((cap, N_ENT), np.int64)   # obs_v5.smooth_vel
        self.ring = {"self": np.zeros((cap, R, O.N_SELF), np.float32), "ent": np.zeros((cap, R, N_ENT, F_ENT), np.float32),
                     "grid": np.zeros((cap, R, G, G), np.uint8)}

    def _episode(self, aid):
        """ObsV5._episode (same draws, same eviction; e[9] = the identity draws) + a state slot as e[10]; evicted slots
        are freed after this build"""
        e = self.ep.get(aid)
        if e is None:
            n, r = self.noise, self.rng
            e = self.ep[aid] = [r.uniform(*n["jitter"]), r.uniform(*n["drop"]), r.uniform(*n["fp"]), r.uniform(*n["seg"]),
                                int(r.integers(n["latency"][0], n["latency"][1] + 1)), None, None, r.uniform(*n.get("bleed", (0, 0))),
                                r.uniform(*n.get("drop_cls", (0, 0))), O.id_draws(n, r), self.free.pop()]
            self.t[e[10]] = 0; self.has[e[10]] = False
            if len(self.ep) > 4096:   # shortcut (ObsV5's): ended episodes are never reported here, so drop the oldest half
                for k in list(self.ep)[:2048]: self.unfree.append(self.ep.pop(k)[10])
        return e

    def build(self, vec, grid, meta, ids, cmd=None, who=None, gadget=None, hyper=None):
        o = from_state2(vec, grid, meta, who, derived=self.noise is None or not len(ids), gadget=gadget, hyper=hyper)
        if self.noise is None or not len(ids):
            return o
        r, B = self.rng, len(ids)
        err = np.zeros((B, 2), np.float32)
        if cmd is not None:   # = ObsV5.build: own velocity = commanded move, entity velocities carry its error
            err = (np.asarray(cmd, np.float32) - o["self"][:, 6:8]).astype(np.float32); o["self"][:, 6:8] = cmd
        eps = [self._episode(int(a)) for a in ids]
        # ---- unchanged from ObsV5.build (the random draws, in order)
        jit, drop, fp, seg = (np.array([e[i] for e in eps], np.float32) for i in range(4))
        ent, g = o["ent"], o["grid"]
        here = ent[..., 0] > 0.5
        false = ~here & (r.random(here.shape) < fp[:, None])
        dcf = np.array([e[8] for e in eps], np.float32)
        pd = drop[:, None] + DROP_CLS[ent[..., 1:1 + len(ENT)].argmax(-1)] * dcf[:, None]
        ent[here & (r.random(here.shape) < pd)] = 0.0
        nse = r.normal(size=(B, N_ENT, 2)).astype(np.float32) * jit[:, None, None] * ent[..., :1]
        ent[..., XY:XY + 2] += nse
        rj = r.normal(size=(B, N_ENT)).astype(np.float32) * jit[:, None] * (ent[..., RAD] > 0)   # radius from the drawn ring:
        ent[..., RAD] = np.maximum(ent[..., RAD] + rj, 0.0)                                       # the centre's sigma (not measured)
        n = int(false.sum())
        if n:
            row = np.zeros((n, F_ENT), np.float32); row[:, 0] = 1.0
            fc = r.integers(len(ENT), size=n); row[np.arange(n), 1 + fc] = 1.0
            row[:, XY] = r.uniform(-1.5, 1.5, n); row[:, XY + 1] = r.uniform(-FAIR.VIEW_UP, FAIR.VIEW_DOWN, n) / FAIR.R
            row[:, O.HP] = r.random(n)
            row[:, O.RAD] = np.isin(fc, _AREA_C) * r.uniform(0.1, 0.5, n)   # a false area effect: a 300-1500 radius, no kind
            ent[false] = row
        hud = hud_mask(meta, r); g[hud] = UNKNOWN
        bl = np.array([e[7] for e in eps], np.float32)
        front = np.full_like(g, UNKNOWN); front[:, :-1] = g[:, 1:]
        bleed = ~_TALL_M[g] & (g != _S("out_of_bounds")) & (g != UNKNOWN) & _TALL_M[front]
        bleed &= r.random(g.shape) < BLEED_ROW[None, :, None] * _BLEED_CLS[front] * bl[:, None, None]
        g[bleed] = front[bleed]
        wrong = (g != UNKNOWN) & (r.random(g.shape) < seg[:, None, None])
        g[wrong] = r.integers(len(SEG), size=int(wrong.sum()))
        link = r.random((B, N_ENT))                       # identity (v5.6) and power cubes (v5.10): ObsV5.build's, already batched
        cu = r.random((B, N_ENT, 2))
        if who is None: ent[..., O.ID0:O.ID0 + O.N_ID] = 0.0; ent[..., O.CUB:O.CUB + 2] = 0.0
        else:
            wh = np.where(here[..., None], who, -1)
            O.noisy_id(ent, wh, [e[9] for e in eps], link); O.noisy_cubes(ent, wh, [e[9] for e in eps], cu)
        ent[..., O.LOS:O.LOS + 2] = O.los(ent, g)
        # ---- velocity (vectorised): difference of two noisy detections, 0 for one not matched to the last decision
        sl = np.array([e[10] for e in eps], np.int64)
        on, cls = ent[..., 0] > 0.5, ent[..., 1:1 + len(ENT)].argmax(-1)
        move = (ent[..., VEL:VEL + 2] - o["self"][:, None, 6:8]) * (self.ticks / 10)
        pon, pcls, pxy, pn = self.pon[sl], self.pcls[sl], self.pxy[sl], self.pn[sl]
        d = np.linalg.norm(ent[:, :, None, XY:XY + 2] - move[:, :, None] - pxy[:, None], axis=3)
        d[~(on[:, :, None] & pon[:, None] & (cls[:, :, None] == pcls[:, None]))] = np.inf
        m = (d.min(2) < self.GATE) & self.has[sl][:, None]; j = d.argmin(2)
        pj = np.take_along_axis(pn, j[..., None], 1)
        raw = ent[..., VEL:VEL + 2] + (nse - pj) * (10 / self.ticks) + err[:, None]
        v, age = smooth_vel(raw, m, np.take_along_axis(self.pest[sl], j[..., None], 1), np.take_along_axis(self.page[sl], j, 1))
        self.pon[sl], self.pcls[sl], self.pxy[sl], self.pn[sl], self.has[sl] = on, cls, ent[..., XY:XY + 2], nse, True
        self.pest[sl], self.page[sl] = v, age
        ent[..., VEL:VEL + 2] = v
        # ---- latency (ring of R frames): the policy acts on the frame of e[4] decisions ago (the first one until then)
        t = self.t[sl]; lat = np.array([e[4] for e in eps], np.int64)
        w, rd = t % self.R, np.maximum(t - lat, 0) % self.R
        for k in o:
            self.ring[k][sl, w] = o[k]; o[k] = self.ring[k][sl, rd]
        self.t[sl] = t + 1
        if self.unfree: self.free += self.unfree; self.unfree = []
        return o


def priv_fast(env, ids):
    """train_ppo.priv vectorised over the battles of the batch: (B, PRIV) true offset (/ 6000), hp fraction, alive"""
    from model import PRIV
    ids = np.asarray(ids, np.int64); B = len(ids)
    if not B: return np.zeros((0, PRIV), np.float32)
    by = {s.battle: s for s in env.I}; bat = ids >> 4; ub, inv = np.unique(bat, return_inverse=True)
    tab = np.zeros((len(ub), 10, 4), np.float32)
    for u, k in enumerate(ub):
        pl = by[int(k)].inst.resp.pl
        tab[u] = [[pl[q].x, pl[q].y, pl[q].hp / max(1, pl[q].max_hp), bool(pl[q].alive) and not pl[q].eliminated] for q in range(10)]
    c = tab[inv]; me = c[np.arange(B), ids & 15, :2]
    c[..., :2] = (c[..., :2] - me[:, None]) / 6000.0; c[c[..., 3] < 0.5] = 0
    return c.reshape(B, PRIV)


def same(a, b):
    """bit-equality of two observation dicts"""
    return all(a[k].dtype == b[k].dtype and np.array_equal(a[k], b[k]) for k in a) and a.keys() == b.keys()


def _synthetic(rng, B, n_ids=40):
    vec = np.zeros((B, 436), np.float32); grid = np.zeros((B, 6, 25, 25), np.uint8)
    vec[:, 0] = rng.random(B); vec[:, 12:14] = rng.normal(size=(B, 2))
    for k in range(FAIR.EN_K):                           # a few enemies / projectiles drifting around
        o = FAIR.EN0 + k * FAIR.EN_F; vec[:, o] = rng.random(B) < 0.5; vec[:, o + 1:o + 3] = rng.normal(size=(B, 2)) * 0.4
        vec[:, o + 3:o + 5] = rng.normal(size=(B, 2)) * 0.2; vec[:, o + 5] = rng.random(B)
    for k in range(FAIR.PJ_K):
        o = FAIR.PJ0 + k * FAIR.PJ_F; vec[:, o] = rng.random(B) < 0.3; vec[:, o + 1:o + 3] = rng.normal(size=(B, 2)) * 0.4
    for k in range(FAIR.IT_K):                           # area effects of both sides (radius / kind columns)
        o = FAIR.IT0 + k * FAIR.IT_F; vec[:, o] = rng.random(B) < 0.3; vec[:, o + 1:o + 3] = rng.normal(size=(B, 2)) * 0.4
        vec[:, o + 4] = rng.choice([-1.0, 1.0], B); vec[:, o + 5] = rng.integers(1, 1320, B)
    grid[:, 0] = rng.integers(0, 30, (B, 25, 25))
    meta = np.stack([rng.integers(300, 17000, B), rng.integers(300, 17000, B), np.full(B, 100), np.full(B, 60), np.full(B, 60)], 1).astype(np.int32)
    ids = 16 + rng.choice(n_ids, B, replace=False)
    return vec, grid, meta, ids


def _who(rng, vec):
    """a synthetic `who` for _synthetic's rows: enemy-block / projectile rows owned by random players, sides, brawlers, cubes"""
    B = len(vec); w = np.full((B, N_ENT, 4), -1, np.int16); nh = len(O.id_lut()[0])
    for blk, off, K, Fn in ((0, FAIR.EN0, FAIR.EN_K, FAIR.EN_F), (FAIR.EN_K, FAIR.PJ0, FAIR.PJ_K, FAIR.PJ_F)):
        on = vec[:, off:off + K * Fn].reshape(B, K, Fn)[..., 0] > 0.5
        q = rng.integers(0, 10, (B, K)); w[:, blk:blk + K] = np.stack([q, (q * 7 + 3) % nh, q % 3 if blk else q % 2, (q * 5) % 13], -1)
        w[:, blk:blk + K][~on] = -1
    return w


def _check(steps=300):
    rng = np.random.default_rng(1)
    a, b = O.ObsV5(seed=5), FastObsV5(seed=5)
    base = _synthetic(rng, 30); bw = _who(rng, base[0]); n_id = n_gad = n_cub = 0
    for t in range(steps):                               # the same agents drift; random subsets per poll; new agents now and then
        vec, grid, meta, ids = base
        vec = vec + rng.normal(size=vec.shape).astype(np.float32) * 0.01 * (vec != 0)
        pick = rng.random(len(ids)) < 0.7
        ids2 = ids[pick] + 16 * (t // 50)                # every 50 polls a fresh set of agent ids
        x = (vec[pick], grid[pick], meta[pick], ids2)
        cmd = rng.normal(size=(int(pick.sum()), 2)).astype(np.float32) * 0.12 if t % 2 else None   # A2 path every other poll
        w = bw[pick] if t % 3 else None                  # identities given on 2 of 3 polls
        gd = (rng.random(len(ids2)) < 0.5).astype(np.float32) if t % 4 else None   # gadget ready (self 3, v5.7) on 3 of 4
        hy = (rng.random(len(ids2)) < 0.5).astype(np.float32) if t % 3 else None   # hypercharge ready (self 4, v5.8) on 2 of 3
        oa, ob = (m.build(*[y.copy() for y in x], cmd=cmd, who=w, gadget=gd, hyper=hy) for m in (a, b))
        assert same(oa, ob), t
        n_id += int(oa["ent"][..., O.ID_KNOWN].sum()); n_gad += int(oa["self"][:, 3].sum()); n_cub += int(oa["ent"][..., O.CUB + 1].sum())
    assert n_id > 1000 and n_gad > 100 and n_cub > 300, (n_id, n_gad, n_cub)   # identity path ran (known rows, wrong picks, links), self 3 set, cubes read
    # eviction path: > 4096 agents
    a, b = O.ObsV5(seed=6), FastObsV5(seed=6)
    for t in range(250):
        vec, grid, meta, _ = _synthetic(rng, 40)
        ids = np.arange(40) + 16 + 40 * (t // 2) * 16 if t % 3 else np.arange(40) * 16 + 16   # the first set keeps coming back
        w = _who(rng, vec)
        assert same(a.build(vec.copy(), grid.copy(), meta.copy(), ids, who=w), b.build(vec, grid, meta, ids, who=w)), t
    assert len(a.ep) == len(b.ep) and list(a.ep) == list(b.ep)
    # A2: no noise, no latency; we stand still, the commanded move says 0.12 tiles / tick right -> self = cmd and a still
    # enemy reads -(true own - cmd) = +0.12 x (as the agent: matched position difference + commanded own velocity)
    quiet = {k: (0.0, 0.0) for k in O.NOISE}; quiet["latency"] = (0, 0)
    vec, grid, meta, ids = _synthetic(np.random.default_rng(3), 4); vec[:, 12:14] = 0
    for k in range(FAIR.EN_K): vec[:, FAIR.EN0 + k * FAIR.EN_F + 3:FAIR.EN0 + k * FAIR.EN_F + 5] = 0
    cmd = np.tile(np.float32([0.12, 0.0]), (4, 1))
    for ob in (O.ObsV5(noise=quiet, seed=1), FastObsV5(noise=quiet, seed=1)):
        ob.build(vec.copy(), grid.copy(), meta.copy(), ids, cmd=cmd); o = ob.build(vec.copy(), grid.copy(), meta.copy(), ids, cmd=cmd)
        on = o["ent"][:, :FAIR.EN_K, 0] > 0.5
        assert np.allclose(o["self"][:, 6:8], cmd) and on.any()
        assert np.allclose(o["ent"][:, :FAIR.EN_K][on][:, O.VEL:O.VEL + 2], [0.12, 0.0], atol=1e-6), o["ent"][:, :FAIR.EN_K][on][:, O.VEL:O.VEL + 2]
    print("fast_obs ok: synthetic batches bit-equal to ObsV5 (%d polls + eviction), A2 commanded velocity" % steps)


if __name__ == "__main__":
    _check()
