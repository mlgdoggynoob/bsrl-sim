"""Imitation rows (issue #49, Brawl TV pro play): the dataset format, a writer, a loader and a sequence sampler for
train_ppo's --imit-data / --imit-updates / --imit-w. No game needed.

    import imitation as I
    I.write_shard("rec_0001.npz", s, ent, grid, act, w, ep, source="brawltv:abc123")   # step 3 calls this per recording
    ds = I.load("path/to/dir_or_shard.npz")                                          # a folder of *.npz or one file
    idx, tmask = ds.sample(rng, n=64, L=8, burn=16)                                  # (n, burn + L) row indices, -1 = pad
    b = ds.batch(idx, tmask)                                                         # numpy dict, see below

    python -m imitation      # self-check (synthetic shards in a temp dir, no game)

Format: one .npz per recording (one battle seen from one player; several players of a battle = several shards). Row j is
one policy decision, in time order; every array has N rows:

    key          shape / dtype                 meaning
    format       0-d str                       "imit1"
    obs_version  0-d str                       obs_v5.OBS_VERSION when the rows were built; load() refuses any other
    s            (N, obs_v5.N_S) float16       the policy's vector input cat[self, cond, intent] (train_ppo.policy_s)
    ent          (N, N_ENT, F_ENT) float16     the entity rows (obs_v5.ObsV5.build o["ent"])
    grid         (N, G, G) uint8               the seg-class grid (o["grid"])
    act          (N, 4) int16                  the label in the policy's heads: move 0-16, fire class 0..len(obs_v5.FIRE)-1,
                                               aim 0-359 (degrees bin; only read when the fire class aims, obs_v5.FIRE_AIM),
                                               distance 0-7 (only read for a super); unused values still in range (0)
    w            (N,) float32                  label quality 0..1 (0 = ignore the row; step 3's labels are noisy)
    ep           (N,) int32                    episode id: contiguous rows with the same id are one sequence; the GRU
                                               state starts at zero where an id starts (as in a live battle)
    source       0-d str                       free text (recording id), not used

The rows hold exactly what the policy takes (train_ppo.Buffer's s / ent / grid, same dtypes) and the labels are the
act columns train_ppo's BC rows hold, so the loss is train_ppo's BC loss (net.seq -> dist_logp_ent -> weighted mean,
train_ppo.imit_nll) with weight w per row. There is no stored GRU state: a sampled window starts `burn` rows before its
target rows (or at the episode start, where the state is zero) and only the target rows count. A row whose fire class
the policy would mask (a super / gadget / hypercharge without its self column set) cannot be imitated: write_shard sets
its w to 0 and reports the count; the loss also skips it.
Changing the observation (obs_v5.OBS_VERSION) invalidates every shard: they must be rebuilt from the recordings.
"""
import glob, os, sys, tempfile
import numpy as np
import obs_v5 as O

FORMAT = "imit1"
KEYS = {"s": ((O.N_S,), np.float16), "ent": ((O.N_ENT, O.F_ENT), np.float16), "grid": ((O.G, O.G), np.uint8),
        "act": ((4,), np.int16), "w": ((), np.float32), "ep": ((), np.int32)}
ACT_MAX = (17, len(O.FIRE), 360, 8)                    # exclusive bounds of the four label columns (model.NVEC)


def illegal_fire(s, act):
    """(N,) bool: rows whose fire class model.mask_fire would mask (class needs a self column >= 0.5 that is not set)"""
    bad = np.zeros(len(act), bool)
    for c, k in enumerate(O.FIRE_READY):
        if k is not None: bad |= (act[:, 1] == c) & (np.asarray(s[:, k], np.float32) < 0.5)
    return bad


def write_shard(path, s, ent, grid, act, w, ep, source=""):
    """validate and write one recording -> {"rows": N, "episodes": n, "zero_w": rows with w 0, "illegal_fire": rows whose w
    was set to 0 because the label's fire class is masked}. Raises ValueError on a wrong shape, a label out of range, a w
    outside 0..1 or an episode id that comes back after another one (rows of an episode must be contiguous)."""
    a = {"s": s, "ent": ent, "grid": grid, "act": act, "w": w, "ep": ep}; N = len(act)
    for k, (shape, dt) in KEYS.items():
        a[k] = np.asarray(a[k])
        if a[k].shape != (N,) + shape: raise ValueError("%s: shape %s, want %s" % (k, a[k].shape, (N,) + shape))
        if k in ("s", "ent") and not np.isfinite(a[k].astype(np.float32)).all(): raise ValueError(k + ": not finite")
        a[k] = a[k].astype(dt)
    if N and ((a["act"] < 0).any() or (a["act"] >= np.array(ACT_MAX)).any()): raise ValueError("act out of range %s" % (ACT_MAX,))
    if not np.isfinite(a["w"]).all() or (a["w"] < 0).any() or (a["w"] > 1).any(): raise ValueError("w must be in 0..1")
    first = np.r_[0, np.flatnonzero(np.diff(a["ep"]) != 0) + 1] if N else np.zeros(0, int)
    if len(set(a["ep"][first].tolist())) != len(first): raise ValueError("episode ids must be contiguous")
    bad = illegal_fire(a["s"], a["act"]); n_bad = int((bad & (a["w"] > 0)).sum()); a["w"][bad] = 0
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    np.savez_compressed(path, format=FORMAT, obs_version=O.OBS_VERSION, source=str(source), **a)
    return {"rows": N, "episodes": len(first), "zero_w": int((a["w"] == 0).sum()), "illegal_fire": n_bad}


def read_shard(path):
    """one shard -> dict of its arrays; ValueError when the format / observation version / shapes do not match this code"""
    z = np.load(path, allow_pickle=False)
    if "format" not in z or str(z["format"]) != FORMAT: raise ValueError("%s: not an %s shard" % (path, FORMAT))
    if str(z["obs_version"]) != O.OBS_VERSION:
        raise ValueError("%s: observation %s, this code %s: rebuild the shard from its recording" % (path, z["obs_version"], O.OBS_VERSION))
    out = {k: z[k] for k in KEYS}; N = len(out["act"])
    for k, (shape, dt) in KEYS.items():
        if out[k].shape != (N,) + shape or out[k].dtype != dt: raise ValueError("%s: %s is %s %s, want %s %s" % (path, k, out[k].dtype, out[k].shape, np.dtype(dt), (N,) + shape))
    return out


class Dataset:
    """all shards of a path concatenated (episode ids made unique across shards); .n rows, .eps = (start, end) per episode"""
    def __init__(self, shards):
        self.a = {k: np.concatenate([sh[k] for sh in shards]) if shards else np.zeros((0,) + KEYS[k][0], KEYS[k][1]) for k in KEYS}
        off = 0; ep = []
        for sh in shards: ep.append(sh["ep"].astype(np.int64) + off - (sh["ep"].min() if len(sh["ep"]) else 0)); off = (ep[-1].max() + 1) if len(ep[-1]) else off
        self.ep = np.concatenate(ep) if ep else np.zeros(0, np.int64); self.n = len(self.ep)
        cut = np.r_[0, np.flatnonzero(np.diff(self.ep) != 0) + 1, self.n] if self.n else np.zeros(1, int)
        self.eps = np.stack([cut[:-1], cut[1:]], 1)                       # (episodes, 2): [start, end)
        self.e_of = np.repeat(np.arange(len(self.eps)), np.diff(cut)) if self.n else np.zeros(0, int)   # row -> episode
        self.w_sum = float(self.a["w"].sum())

    def sample(self, rng, n, L, burn):
        """n windows -> (idx, tmask), both (n, burn + L): the target rows are L consecutive rows of one episode from a
        uniformly drawn row (clipped at the episode end); the window starts up to `burn` rows earlier (the GRU runs over
        them from a zero state, no loss), never before the episode start. idx = row index, -1 = padding (after the end);
        tmask = 1 on target rows. Weights w are applied in the loss, not here."""
        t = rng.integers(0, self.n, n); es, ee = self.eps[self.e_of[t]].T
        st = np.maximum(es, t - burn); en = np.minimum(ee, t + L); pos = st[:, None] + np.arange(burn + L)[None]
        idx = np.where(pos < en[:, None], pos, -1); tm = (idx >= t[:, None]) & (idx >= 0)
        return idx, tm.astype(np.float32)

    def batch(self, idx, tmask):
        """numpy tensors of windows (n, W, ...): s, ent, grid (padding rows = 0), act (n, W, 4), w = label weight x tmask
        (n, W): 0 on context / padding rows and on rows whose fire class is masked"""
        r = np.maximum(idx, 0); ok = (idx >= 0)
        b = {k: self.a[k][r] * ok.reshape(ok.shape + (1,) * (self.a[k].ndim - 1)) for k in ("s", "ent", "grid", "act")}
        b["w"] = self.a["w"][r] * tmask * ok * ~illegal_fire(b["s"].reshape(-1, O.N_S), b["act"].reshape(-1, 4)).reshape(ok.shape)
        return b


def load(path):
    """a shard file or a folder of *.npz (sorted) -> Dataset; ValueError on a bad shard, FileNotFoundError when empty"""
    files = sorted(glob.glob(os.path.join(path, "*.npz"))) if os.path.isdir(path) else [path]
    if not files or not all(os.path.exists(f) for f in files): raise FileNotFoundError("no imitation shards at " + path)
    return Dataset([read_shard(f) for f in files])


def synthetic(rng, n_ep=3, steps=40, battle=0):
    """random rows for tests / the trainer smoke: (s, ent, grid, act, w, ep) of n_ep episodes of `steps` rows. Fire class
    0 / 1 only (no gate column needed); a given label is a function of the row's first self value so a net can learn it"""
    N = n_ep * steps
    s = rng.normal(size=(N, O.N_S)).astype(np.float16); ent = np.zeros((N, O.N_ENT, O.F_ENT), np.float16)
    ent[:, :3, 0] = 1; ent[:, :3, 1 + O.ENT.index("enemy")] = 1; ent[:, :3, O.XY:O.XY + 2] = rng.uniform(-1, 1, (N, 3, 2))
    grid = rng.integers(0, len(O.SEG), (N, O.G, O.G)).astype(np.uint8)
    act = np.stack([rng.integers(0, 17, N), rng.integers(0, 2, N), rng.integers(0, 360, N), np.zeros(N, int)], 1).astype(np.int16)
    return s, ent, grid, act, rng.uniform(0.2, 1, N).astype(np.float32), np.repeat(np.arange(n_ep) + 100 * battle, steps).astype(np.int32)


def _check():
    rng = np.random.default_rng(0)
    with tempfile.TemporaryDirectory() as d:
        s, ent, grid, act, w, ep = synthetic(rng, 3, 40); w[:10] = 0
        s2 = s.copy(); act2 = act.copy(); act2[50, 1] = 2; s2[50, O.FIRE_READY[2]] = 0     # a super label without a charged super
        info = write_shard(os.path.join(d, "a.npz"), s2, ent, grid, act2, w, ep, source="t")
        assert info == {"rows": 120, "episodes": 3, "zero_w": 11, "illegal_fire": 1}, info
        write_shard(os.path.join(d, "b.npz"), *synthetic(rng, 2, 25, battle=1))                    # same ids as shard a's would clash
        ds = load(d); assert ds.n == 170 and len(ds.eps) == 5 and ds.eps[3, 1] - ds.eps[3, 0] == 25, ds.eps
        assert ds.a["s"].dtype == np.float16 and ds.a["act"].dtype == np.int16 and ds.a["grid"].shape == (170, O.G, O.G)
        assert len(set(ds.ep.tolist())) == 5 and ds.a["w"][50] == 0 and (ds.a["w"][:10] == 0).all()
        # sampler: windows stay inside one episode, targets are L consecutive rows, context only before them, zero state at starts
        idx, tm = ds.sample(np.random.default_rng(1), 500, 8, 16); assert idx.shape == tm.shape == (500, 24)
        for i, m in zip(idx, tm):
            v = i[i >= 0]; assert (np.diff(v) == 1).all() and len(set(ds.e_of[v])) == 1 and (i[i < 0] == -1).all()
            tg = i[m > 0]; assert 1 <= len(tg) <= 8 and (np.diff(tg) == 1).all() and (v[:len(v) - len(tg)] < tg[0]).all()
            assert v[0] == ds.eps[ds.e_of[v[0]], 0] or v[0] + 16 == tg[0]       # starts at the episode start, or exactly burn rows early
        b = ds.batch(idx, tm); assert b["s"].shape == (500, 24, O.N_S) and b["act"].shape == (500, 24, 4) and b["w"].shape == (500, 24)
        assert (b["w"][idx < 0] == 0).all() and (b["w"][tm == 0] == 0).all() and (b["s"][idx < 0] == 0).all()
        j = np.argwhere(idx == 50); assert len(j) and (b["w"][tuple(j.T)] == 0).all()             # the masked-fire row never counts
        k = np.argwhere((idx >= 0) & (tm > 0) & (idx != 50) & (idx >= 10))[0]; assert b["w"][tuple(k)] == ds.a["w"][idx[tuple(k)]]
        # refusals: observation version, format, bad labels / weights / non-contiguous episodes
        z = dict(np.load(os.path.join(d, "a.npz"))); z["obs_version"] = np.array("v0.0"); np.savez(os.path.join(d, "old.npz"), **z)
        for bad, why in ((os.path.join(d, "old.npz"), "observation v0.0"),):
            try: read_shard(bad); raise AssertionError("old version loaded")
            except ValueError as e: assert why in str(e), e
        z["obs_version"] = np.array(O.OBS_VERSION); z["format"] = np.array("imit0"); np.savez(os.path.join(d, "fmt.npz"), **z)
        try: read_shard(os.path.join(d, "fmt.npz")); raise AssertionError("old format loaded")
        except ValueError: pass
        S = synthetic(rng, 1, 10); ref = os.path.join(d, "x.npz")
        col = {"s": 0, "act": 3, "w": 4, "ep": 5}
        for k, f in (("act", lambda x: x + 400), ("w", lambda x: x + 2), ("ep", lambda x: np.array([0, 1] * 5, np.int32)), ("s", lambda x: x[:, :5])):
            args = list(S); args[col[k]] = f(S[col[k]])
            try: write_shard(ref, *args); raise AssertionError("bad %s written" % k)
            except ValueError: pass
        try: load(os.path.join(d, "none")); raise AssertionError("missing path loaded")
        except FileNotFoundError: pass
        assert load(os.path.join(d, "b.npz")).n == 50                                              # a single file works too
    print("imitation ok")


if __name__ == "__main__":
    _check() if len(sys.argv) == 1 or "--check" in sys.argv else sys.exit("usage: python -m imitation [--check]")
