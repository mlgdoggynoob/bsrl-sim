"""Acting for train_fast.py: one batched forward over several Policies, with the stacked weights kept between calls.

    actor = StackedActor(dev)
    A, lp, v, h2 = actor(nets, gidx, s, ent, grid, h, priv)     # numpy in, numpy out; gidx (B,) = index into nets
    A, lp, v, h2 = actor.act_block(nets, gidx, X, h)             # X (B, OBS_W) = s | ent | grid | priv rows (worker shm)

Same math as model.act_stacked (HISTORY 68: one forward for learner / eval copy / base / league slots), but:
* the stacked weights are cached per net set and rebuilt only when a weight changed (torch's in-place version
  counters: optimizer step, load_state_dict), not on every poll;
* the forward is written out on the stacked weights (baddbmm per layer, the linears that read cat[x, h] fused into
  one matmul, index tensors kept on the GPU = no hidden host syncs): far fewer ops than vmap (dispatch-bound on ROCm);
* rows are grouped and padded on the CPU into ONE pinned float32 block = one upload;
* sampling = Gumbel-max on log_softmax (the distribution of torch Categorical.sample, without its validation
  overhead); log-prob masking as model.dist_logp_ent (aim only for an aiming fire class, distance only for a super);
* the outputs (action, logp, value, next h) come back as ONE (N, 6 + HID) download;
* only acting parameters are stacked (model.acting_params: the heads in model.NONACT, e.g. the live value, are skipped,
  so they cost no stacked memory and their updates do not rebuild the stack).

    python -m fast_act      # allclose check vs model.act_stacked + timing (GPU shared with a live run = inflated)
"""
import time
import numpy as np
import torch
import torch.nn.functional as F
import obs_v5 as O
from model import Policy, HID, PRIV, _CAND, _FOE, mask_fire, lead, lead_deg, hero_index, F_IN, HMAX, NONACT, acting_params, N_FX, _SUPER

NS = O.N_S                                              # s = self | cond | intent (obs v5.5)
_W = [NS, O.N_ENT * O.F_ENT, O.G * O.G, PRIV, HID]      # block layout: s | ent | grid | priv | h
_OFF = np.cumsum([0] + _W)
OBS_W = int(_OFF[4])                                     # what a worker writes per row (all but h)
_HEADS = ["pi", "v", "free", "free_score", "fire_x"]     # 28 | 1 | 360 | 1 | N_FX outputs (fire_x: obs v5.7 extra fire classes)


class StackedActor:
    def __init__(self, dev, cap=2048):
        self.dev, self.cache = dev, {}
        self.cand = torch.as_tensor(_CAND, device=dev); self.foe = torch.as_tensor(_FOE, device=dev)
        self.bins = torch.arange(360, device=dev).float()
        self._alloc(cap)

    def _alloc(self, cap):
        self.inp = torch.zeros((cap, int(_OFF[-1])), pin_memory=self.dev.type == "cuda"); self.inp_np = self.inp.numpy()

    def _stack(self, nets):
        """stacked weights of these nets (+ the fused head matrix), rebuilt only when any of their parameters changed"""
        key = tuple(id(n) for n in nets)
        ver = tuple(sum(t._version for t in acting_params(n).values()) + n.hero_stats._version + n.aim_lead._version for n in nets)
        hit = self.cache.get(key)
        if hit is not None and hit[0] == ver: return hit[1]
        if len(self.cache) > 32: self.cache.clear()
        with torch.no_grad():
            sd = [acting_params(n) for n in nets]
            P = {k: torch.stack([d[k].detach() for d in sd]) for k in sd[0]}
            d = P["pi.weight"].shape[-1]; c1, vp1 = P["cand.0.weight"], P["vp.0.weight"]
            # one matmul for every linear that reads cat[x, h]: pi | v | free | free_score | fire_x | cand.0 (x part) | vp.0 (x part)
            P["headW"] = torch.cat([P[n + ".weight"] for n in _HEADS] + [c1[..., :d], vp1[..., :d]], 1).transpose(1, 2).contiguous()
            P["headb"] = torch.cat([P[n + ".bias"] for n in _HEADS] + [P["cand.0.bias"], P["vp.0.bias"]], 1)[:, None]
            P["candE"], P["vpP"] = c1[..., d:].transpose(1, 2).contiguous(), vp1[..., d:].transpose(1, 2).contiguous()
            for k in ("ent.0", "ent.2", "grid.5", "vec.0", "trunk.0", "cand.2", "vp.2"): P[k + ".T"] = P[k + ".weight"].transpose(1, 2).contiguous()
            for k in ("ih", "hh"): P["gru.T" + k] = P["gru.weight_" + k].transpose(1, 2).contiguous()
            P["embf"] = P["emb.weight"].reshape(-1, P["emb.weight"].shape[-1])
            P["hembf"] = P["hemb.weight"].reshape(-1, P["hemb.weight"].shape[-1])
            P["hero_stats"] = torch.stack([n.hero_stats for n in nets])[:, None]       # (G, 1, HMAX, 13)
            P["aim_lead"] = torch.stack([n.aim_lead for n in nets])[:, None, None]       # (G, 1, 1): model.lead_deg per net
        self.cache[key] = (ver, P)
        return P

    def forward_padded(self, nets, X):
        """X: (G, Bm, width) device block -> logits (move, fire, aim, dist), v, h with a leading net axis: the math of
        model.act_stacked / Policy.forward with priv"""
        P = self._stack(nets); G, Bm = X.shape[:2]
        lin = lambda x, n: torch.baddbmm(P[n + ".bias"][:, None], x, P[n + ".T"])     # x (G, rows, in)
        s, ent, grid, pv, h = (X[..., _OFF[i]:_OFF[i + 1]] for i in range(5))
        ent = ent.reshape(G, Bm, O.N_ENT, O.F_ENT); ent = torch.cat([ent, lead(ent, s)], -1)   # + model.lead columns
        # encode. Entity set: max over present slots (ReLU >= 0, so masked_fill 0 + amax == Policy.encode)
        e = F.relu(lin(F.relu(lin(ent.reshape(G, Bm * O.N_ENT, F_IN), "ent.0")), "ent.2")).view(G, Bm, O.N_ENT, -1)
        e = e.masked_fill(ent[..., :1] < 0.5, 0.0).amax(2)
        nemb = P["emb.weight"].shape[1]
        ix = grid.long().reshape(G, Bm * O.G * O.G) + (torch.arange(G, device=X.device) * nemb)[:, None]
        g = F.embedding(ix, P["embf"]).view(G * Bm, O.G, O.G, -1).permute(0, 3, 1, 2)
        for n in ("grid.0", "grid.2"):                           # UnfoldConv2d(k 3, stride 2, pad 1) = unfold + matmul
            cols = F.unfold(g, 3, padding=1, stride=2); L = cols.shape[-1]; Ho = int(round(L ** 0.5))
            W = P[n + ".weight"]; Co = W.shape[1]
            y = torch.matmul(W.view(G, 1, Co, -1), cols.view(G, Bm, cols.shape[1], L)) + P[n + ".bias"][:, None, :, None]
            g = F.relu(y).view(G * Bm, Co, Ho, Ho)
        g = F.relu(lin(g.reshape(G, Bm, -1), "grid.5"))
        hid = hero_index(s, P["hero_stats"]) + (torch.arange(G, device=X.device) * (HMAX + 1))[:, None]   # model.hemb
        x = F.relu(lin(torch.cat([F.relu(lin(s, "vec.0")), e, g], -1), "trunk.0") + F.embedding(hid, P["hembf"]))
        # GRU step (nn.GRUCell math)
        ir, iz, i_n = torch.baddbmm(P["gru.bias_ih"][:, None], x, P["gru.Tih"]).chunk(3, -1)
        hr, hz, h_n = torch.baddbmm(P["gru.bias_hh"][:, None], h, P["gru.Thh"]).chunk(3, -1)
        r, z = torch.sigmoid(ir + hr), torch.sigmoid(iz + hz); h = (1 - z) * torch.tanh(i_n + r * h_n) + z * h
        xc = torch.cat([x, h], -1)
        # heads (Policy.heads: nirkt's PointerAim + value + the critic's priv branch)
        pi, v, free, fsc, fx, cx, vx = torch.split(torch.baddbmm(P["headb"], xc, P["headW"]), [28, 1, 360, 1, N_FX, 128, P["vpP"].shape[-1]], -1)
        mv, fi, di = torch.split(pi, [17, 3, 8], -1); fi = torch.cat([fi, fx], -1)
        c = ent.index_select(2, self.cand); K = c.shape[2]
        here = (c[..., 0] > 0.5) & (c.index_select(3, self.foe).sum(-1) > 0.5)
        o = F.relu(cx[:, :, None] + torch.bmm(c.reshape(G, Bm * K, -1), P["candE"]).view(G, Bm, K, -1))
        o = lin(o.view(G, Bm * K, -1), "cand.2").view(G, Bm, K, 3)
        mu = torch.rad2deg(torch.atan2(c[..., O.XY + 1], c[..., O.XY])) % 360.0 + lead_deg(c, P["aim_lead"]) + 25.0 * torch.tanh(o[..., 1])
        dd = (self.bins - mu[..., None]).abs() % 360.0; dd = torch.minimum(dd, 360.0 - dd)
        bump = torch.log_softmax(-0.5 * (dd / (F.softplus(o[..., 2]) + 0.7)[..., None]) ** 2, -1)
        mix = torch.log_softmax(torch.cat([o[..., 0].masked_fill(~here, -1e9), fsc], -1), -1)
        comp = torch.cat([bump, torch.log_softmax(free, -1)[:, :, None]], 2)
        aim = torch.logsumexp(mix[..., None] + comp, 2)
        v = v[..., 0] + lin(F.relu(torch.baddbmm(vx, pv, P["vpP"])), "vp.2")[..., 0]
        return (mv, mask_fire(fi, X[..., :NS]), aim, di), v, h

    def layout(self, gidx):
        """(B,) group per row -> used groups, rows per group (padded), flat destination row of each input row"""
        gidx = np.asarray(gidx, np.int64); used = np.unique(gidx)
        slot = np.zeros(int(used.max()) + 1, np.int64); slot[used] = np.arange(len(used))
        cnt = np.bincount(gidx); Bm = int(cnt.max())
        order = np.argsort(gidx, kind="stable"); start = np.cumsum(cnt) - cnt
        pos = np.empty(len(gidx), np.int64); pos[order] = np.arange(len(gidx)) - start[gidx[order]]
        return used, Bm, slot[gidx] * Bm + pos

    def __call__(self, nets, gidx, s, ent, grid, h, pv):
        B = len(gidx)
        return self.act_block(nets, gidx, np.concatenate([np.asarray(a, np.float32).reshape(B, -1) for a in (s, ent, grid, pv)], 1), h)

    @torch.no_grad()
    def act_block(self, nets, gidx, X, h):
        used, Bm, dest = self.layout(gidx); N = len(used) * Bm; B = len(dest)
        if N > len(self.inp): self._alloc(2 * N)
        x = self.inp_np[:N]
        if N > B: x[:] = 0                                       # padding rows: zeros
        x[dest, :OBS_W] = X; x[dest, OBS_W:] = h
        Xd = self.inp[:N].to(self.dev, non_blocking=True).view(len(used), Bm, -1)
        lg, v, h2 = self.forward_padded([nets[g] for g in used], Xd)
        A, lp = sample([l.flatten(0, 1) for l in lg])
        out = torch.cat([A.float(), lp[:, None], v.flatten()[:, None], h2.flatten(0, 1)], 1).cpu().numpy()[dest]   # sync: the pinned block is free again
        return out[:, :4].astype(np.int64), out[:, 4].copy(), out[:, 5].copy(), np.ascontiguousarray(out[:, 6:])


_AIM = {}   # device -> obs_v5.FIRE_AIM as a float tensor (kept on the device: no upload per call)


def sample(logits):
    """Gumbel-max sample per head + masked log-prob (model.dist_logp_ent's rule) -> (N, 4) long, (N,)"""
    lps, acts = [], []
    for lg in logits:
        ls = F.log_softmax(lg.float(), -1)
        a = (ls - torch.empty_like(ls).exponential_().log()).argmax(-1)
        acts.append(a); lps.append(ls.gather(-1, a[:, None])[:, 0])
    fire = acts[1]; dev = fire.device
    if dev not in _AIM: _AIM[dev] = torch.as_tensor(O.FIRE_AIM, dtype=torch.float32, device=dev)
    lp = lps[0] + lps[1] + _AIM[dev][fire] * lps[2] + (fire == _SUPER) * lps[3]
    return torch.stack(acts, -1), lp


def _rand_batch(B, rng):
    s = rng.normal(size=(B, NS)).astype(np.float32); ent = np.zeros((B, O.N_ENT, O.F_ENT), np.float32)
    on = rng.random((B, O.N_ENT)) < 0.3; ent[..., 0] = on; ent[np.arange(B)[:, None], np.arange(O.N_ENT)[None], 1 + rng.integers(0, len(O.ENT), (B, O.N_ENT))] = 1
    ent[..., O.XY:O.XY + 4] = rng.normal(size=(B, O.N_ENT, 4)) * [1, 1, 0.1, 0.1]   # + velocity (lead)
    ent[..., O.ID0:] = rng.random((B, O.N_ENT, O.F_ENT - O.ID0)) < 0.5; ent *= ent[..., :1]   # identity / line of sight (v5.6)
    grid = rng.integers(0, O.UNKNOWN + 1, (B, O.G, O.G)).astype(np.uint8)
    return s, ent, grid, rng.normal(size=(B, HID)).astype(np.float32) * 0.3, rng.normal(size=(B, PRIV)).astype(np.float32)


def compare(nets, gidx, s, ent, grid, h, pv, actor=None):
    """max |difference| of logits / v / h between model.act_stacked (the train_ppo path) and StackedActor on the same
    rows, and of the log-prob of StackedActor's sampled actions under act_stacked's logits"""
    from model import act_stacked, dist_logp_ent
    dev = next(nets[0].parameters()).device; B = len(gidx); actor = actor or StackedActor(dev)
    T = lambda x, dt=torch.float32: torch.as_tensor(x, device=dev).to(dt)
    grp = [(nets[g], np.flatnonzero(gidx == g)) for g in range(len(nets)) if (gidx == g).any()]
    D_ = [T(s), T(ent), T(grid, torch.uint8), T(h), T(pv)]
    with torch.no_grad():
        lgS, vS, hS = act_stacked([g for g, _ in grp], [[d[torch.as_tensor(ix, device=dev)] for d in D_] for _, ix in grp])
        used, Bm, dest = actor.layout(gidx)
        x = np.zeros((len(used) * Bm, int(_OFF[-1])), np.float32)
        for i, a_ in enumerate((s, ent, grid, pv, h)): x[dest, _OFF[i]:_OFF[i + 1]] = np.asarray(a_, np.float32).reshape(B, -1)
        lg2, v2, h2 = actor.forward_padded([nets[g] for g in used], T(x).view(len(used), Bm, -1))
        Bm0 = vS.shape[1]; inv = np.empty(B, np.int64)
        inv[np.concatenate([ix for _, ix in grp])] = np.concatenate([np.arange(len(ix)) + k * Bm0 for k, (_, ix) in enumerate(grp)])
        f0 = lambda t: t.flatten(0, 1)[torch.as_tensor(inv, device=dev)]; f1 = lambda t: t.flatten(0, 1)[torch.as_tensor(dest, device=dev)]
        pairs = [(f0(a_), f1(b_)) for a_, b_ in zip(lgS, lg2)] + [(f0(vS), f1(v2)), (f0(hS), f1(h2))]
        d_fwd = max((x - y).abs().max().item() for x, y in pairs)
        # allclose(atol 1e-4, rtol 1e-5): the aim log-probs reach -1e2 and beyond, where float32 rounding alone is ~1e-4
        d_rel = max(((x - y).abs() / (1e-4 + 1e-5 * x.abs())).max().item() for x, y in pairs)
        A, lp, v, hh = actor(nets, gidx, s, ent, grid, h, pv)
        lpr = dist_logp_ent([f0(l) for l in lgS], torch.as_tensor(A, device=dev))[0].cpu().numpy()
    return {"fwd": d_fwd, "fwd_allclose_ratio": d_rel, "logp": float(np.abs(lpr - lp).max()), "v": float(np.abs(f0(vS).cpu().numpy() - v).max()), "h": float(np.abs(f0(hS).cpu().numpy() - hh).max())}


def ok(d):
    """compare() passed: logits / v / h allclose(atol 1e-4, rtol 1e-5), sampled-action logp / v / h within 1e-4"""
    return d["fwd_allclose_ratio"] <= 1.0 and max(d["logp"], d["v"], d["h"]) < 1e-4


def _check(B=70, G=4, iters=100):
    from model import act_stacked, dist_logp_ent
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu"); torch.manual_seed(0); rng = np.random.default_rng(0)
    nets = [Policy().to(dev).eval() for _ in range(G)]
    for n in nets:
        torch.nn.init.normal_(n.vp[2].weight, std=0.1); torch.nn.init.normal_(n.free.weight, std=0.05); torch.nn.init.normal_(n.pi.weight, std=0.1)
        torch.nn.init.normal_(n.fire_x.weight, std=0.3); torch.nn.init.normal_(n.fire_x.bias, std=0.3)   # the gadget class live (v5.7)
        with torch.no_grad(): n.vec[0].weight[:, 3].normal_(0, 0.3)                                     # and its ready input
    s, ent, grid, h, pv = _rand_batch(B, rng); gidx = rng.choice(G, B, p=[0.55, 0.2, 0.15, 0.1] if G == 4 else None)
    s[:, 3] = rng.random(B) < 0.5                                     # gadget ready on half the rows (the rest: masked)
    s[:, O.N_SELF + 3] = np.abs(s[:, O.N_SELF + 3])                   # projectile speed > 0: lead columns live
    for k, n in enumerate(nets):                                      # stage 2 parts non-zero: hero rows (net 3 has none), lead weights
        if k < 3: n.add_heroes(s[k * 20:k * 20 + 30, O.N_SELF:O.N_SELF + 13])
        with torch.no_grad():
            n.hemb.weight.normal_(0, 0.1); n.ent[0].weight[:, O.F_ENT:].normal_(0, 0.3); n.cand[0].weight[:, -2:].normal_(0, 0.3)
            n.vec[0].weight[:, O.S_INT:].normal_(0, 0.3)                  # the intent columns (zero in a fresh Policy)
            n.ent[0].weight[:, O.ID0:O.F_ENT].normal_(0, 0.3); pre = n.cand[0].weight.shape[1] - O.F_ENT - 2   # identity / LOS (v5.6)
            n.cand[0].weight[:, pre + O.ID0:pre + O.F_ENT].normal_(0, 0.3)
    actor = StackedActor(dev)
    d = compare(nets, gidx, s, ent, grid, h, pv, actor)
    print("fast_act vs act_stacked (random weights): max |d|", {k: "%.1e" % x for k, x in d.items()})
    assert ok(d), d
    gad = O.FIRE.index("gadget"); fa = np.concatenate([actor(nets, gidx, s, ent, grid, h, pv)[0][:, 1] for _ in range(20)])
    ready = np.tile(s[:, 3] > 0.5, 20)
    assert (fa == gad).any() and not (fa[~ready] == gad).any(), "gadget sampled only while self 3 (gadget ready) is set"
    with torch.no_grad(): nets[0].fire_x.bias += 0.5              # a fire_x change must reach the cached stack too
    d = compare(nets, gidx, s, ent, grid, h, pv, actor); assert ok(d), ("stale cache (fire_x)", d)
    with torch.no_grad(): nets[0].pi.bias += 0.5                  # a weight change must reach the cached stack
    d = compare(nets, gidx, s, ent, grid, h, pv, actor); assert ok(d), ("stale cache", d)
    with torch.no_grad(): nets[0].aim_lead.fill_(1.0); nets[2].aim_lead.fill_(1.0)   # model.lead_deg on 2 of the 4 nets (--aim-lead)
    d = compare(nets, gidx, s, ent, grid, h, pv, actor); assert ok(d), ("aim_lead", d)
    X = np.concatenate([np.asarray(x_, np.float32).reshape(B, -1) for x_ in (s, ent, grid, pv)], 1)
    used, Bm, dest = actor.layout(gidx); xb = np.zeros((len(used) * Bm, int(_OFF[-1])), np.float32); xb[dest, :OBS_W] = X; xb[dest, OBS_W:] = h
    fw = lambda: actor.forward_padded([nets[g] for g in used], torch.as_tensor(xb, device=dev).view(len(used), Bm, -1))
    with torch.no_grad():                                         # the non-acting heads (model.NONACT) change nothing here
        r0 = fw(); [p.normal_(0, 0.5) for n in nets for k, p in n.named_parameters() if k.startswith(NONACT)]; r1 = fw()
    assert all(torch.equal(x_, y_) for x_, y_ in zip(list(r0[0]) + list(r0[1:]), list(r1[0]) + list(r1[1:]))), "acting reads a non-acting head"
    assert not any(k.startswith(NONACT) for k in actor._stack(nets)), "non-acting heads stacked"
    d = compare(nets, gidx, s, ent, grid, h, pv, actor); assert ok(d), ("with non-acting heads", d)
    lgt = torch.tensor([[0.0, 1.0, -1.0, 2.0]], device=dev).expand(200000, 4)   # sampler = Categorical.sample in distribution
    fr = torch.bincount(sample([lgt, lgt[:, :3], lgt, lgt])[0][:, 0], minlength=4).float() / 200000
    assert (fr - torch.softmax(lgt[0], -1)).abs().max() < 0.01, fr
    T = lambda x, dt=torch.float32: torch.as_tensor(x, device=dev).to(dt)
    grp = [(nets[g], np.flatnonzero(gidx == g)) for g in range(G) if (gidx == g).any()]
    def old():                                                    # train_ppo's per-poll acting code
        with torch.no_grad():
            D2 = [T(s), T(ent), T(grid, torch.uint8), T(h), T(pv)]
            lgS, vS, hS = act_stacked([g for g, _ in grp], [[d[torch.as_tensor(ix, device=dev)] for d in D2] for _, ix in grp])
            Bm = vS.shape[1]; sel = torch.as_tensor(np.concatenate([np.arange(len(ix)) + k * Bm for k, (_, ix) in enumerate(grp)]), device=dev)
            lp_, _, A_ = dist_logp_ent([l.flatten(0, 1)[sel] for l in lgS])
            return A_.cpu().numpy(), lp_.cpu().numpy(), vS.flatten(0, 1)[sel].cpu().numpy(), hS.flatten(0, 1)[sel].cpu().numpy()
    for name, fn in (("act_stacked path", old), ("StackedActor", lambda: actor(nets, gidx, s, ent, grid, h, pv))):
        for _ in range(5): fn()
        t = time.perf_counter()
        for _ in range(iters): fn()
        print("%-17s B %d G %d: %.2f ms per call" % (name, B, G, (time.perf_counter() - t) / iters * 1e3))
    for B2, G2 in ((20, 1), (70, 1), (140, 4), (280, 4)):
        s, ent, grid, h, pv = _rand_batch(B2, rng); gi = rng.choice(G2, B2)
        for _ in range(3): actor(nets, gi, s, ent, grid, h, pv)
        t = time.perf_counter()
        for _ in range(iters): actor(nets, gi, s, ent, grid, h, pv)
        print("StackedActor      B %d G %d: %.2f ms per call" % (B2, G2, (time.perf_counter() - t) / iters * 1e3))
    print("fast_act ok")


if __name__ == "__main__":
    _check()
