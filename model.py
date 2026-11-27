"""Policy for the ObsV5 observation: entity set + seg-class grid + self / conditioning vector -> GRU -> heads.

    net = Policy(); logits, v, h = net(s, ent, grid, h)      # one decision; s = cat[self (8), cond (30), intent (11)], h (B, HID)
    logits, v = net.seq(s, ent, grid, h0)                     # (N, L, ...) chunks from stored h0 -> flat (N * L) outputs
    logits = move 17 | fire 5 (obs_v5.FIRE: none / attack / super / gadget / hypercharge) | aim 360 (pointer over visible enemies / boxes
             + free) | distance 8

    python -m model      # self-check (CPU, no game)
The critic also gets `priv` (PRIV = 40: every player's true offset, hp, alive; train_ppo.priv) through a zero-initialised
branch, so the policy heads never see it and old checkpoints load with strict=False.
Stage 2 (BSRL v2 plan), both zero-initialised so s3 / s4 checkpoints act the same (load_state_dict pads):
* lead hint: 2 extra entity columns computed here from the obs (no obs / live change): sin of the angle from a foe to
  where a shot fired now meets it, and the flight time; own projectile speed = cond stats[3].
* per-brawler embedding `hemb` (a learned trunk bias per hero): the hero is found by matching cond's 13 stats against
  the `hero_stats` table (add_heroes; saved in the checkpoint, rows never reorder), unknown = the last row.
Obs v5.3 (obs_v5.OBS_VERSION): 4 area-effect columns at the end of the observation's entity row, before the lead columns;
load_state_dict zero-pads v5.2 checkpoints there (same outputs).
Obs v5.4: cond grew by 2 sliders (leash, gas_safe) at its end = the end of `s`; the generic pad zero-fills those
`vec.0` input columns of a v5.3 checkpoint (same outputs; slot 7 push -> aggressive keeps its column).
Obs v5.5: the intent block (obs_v5.N_INT, intent.py) at the end of `s`; its `vec.0` input columns start at zero (a fresh
Policy draws the same weights as before plus zero columns) and the generic pad zero-fills them for a v5.4 checkpoint,
which then acts the same whatever the block holds (free play = an all-zero block = the old input exactly).
Obs v5.6: identity (14) + line-of-sight (2) columns at the end of the observation's entity row (obs_v5.ID0 .. F_ENT):
their input weights in ent.0 / cand.0 / aux.fut.0 are inserted as zero columns before the lead columns (a fresh Policy
draws the v5.5 weights under a given seed, then the zero columns are put in), and pad_param inserts them the same way
into a v5.5 / v5.4 / v5.3 checkpoint's weights (load_state_dict) and Adam moments (train_ppo.load_opt): same outputs.
Obs v5.7: fire classes past none / attack / super (gadget) come from their own zero-initialised linear `fire_x` (one
output per extra class, appended to pi's three fire logits), so pi keeps its layout; fire_x is built on a forked RNG
stream (a fresh Policy draws the v5.6 weights, then zeroes vec.0's self-3 column) and registered after every other acting module (its parameters are the
tail of the main Adam's list: train_ppo.load_opt gives an older optimizer state fresh moments for them). An older
checkpoint loads with fire_x = zeros and its vec.0 column of self 3 (gadget ready; always 0 before, so still its random
init) zeroed. Each such class is masked while its obs_v5.FIRE_READY self column is off (mask_fire); with those columns
0 an older checkpoint acts exactly as before. The aim head counts for the classes in obs_v5.FIRE_AIM (gadget: its
direction), the distance head only for a super (dist_logp_ent, masked_kl).
Obs v5.8: + the class "hypercharge" (gated by self 4, no aim, no distance) = a second fire_x row; a v5.7 checkpoint's
one-row fire_x zero-pads (load_state_dict), so the new class starts at logit 0 and is masked while self 4 is off.
Obs v5.10: + 2 power-cube columns at the end of the entity row (obs_v5.CUB; zero input columns before the lead columns,
as v5.6's) and + 2 intent kinds, whose one-hot columns sit inside the intent block before dx, dy: pad_param inserts
them as zero columns into a v5.9 checkpoint's vec.0 at obs_v5.S_INT + 7, so its dx / dy / radius / time-left weights
stay on their inputs. Same outputs for the 7 old kinds; a new kind reaches it only through dx, dy, radius, time left.
Aim lead (trainer --aim-lead, buffer `aim_lead`, default 0; no obs change): 1 centres each target's aim bump on the
lead() intercept (lead_deg: asin of the lead column) instead of on its bearing; the learned +-25 deg offset stays on
top. 0 (older checkpoints load it as 0) = the bearing + offset only, as before. Saved in the checkpoint and exported in
the ONNX graph.
Heads the actor never runs (NONACT; fast_act / act_stacked skip them, old checkpoints load with strict=False and get
fresh ones; built on their own RNG stream, so Policy() under a given seed has the acting weights it had without them):
* live value `vl` (trainer --vlive): MLP on the detached cat[x, h], no priv, so it works live (priv does not exist
  there) and never changes the policy; zero-initialised. Target: the return without the intent reward.
* aux heads `aux` (trainer --aux-w; labels from the sim's true state at train time only, env_v5.AUX): fut = each
  enemy-block slot's position 1 s ahead (the slot's seen position + a zero-initialised offset: it starts at "stays
  where seen"), hit = P(enemy damage taken in the next 1 s), gas = gas margin, bush = P(an enemy hidden in a bush within
  5 tiles) per 45-degree sector. On cat[x, h] NOT detached: their gradients shape the encoders / trunk / GRU, never
  the policy or value heads (separate modules).

    lg, v, xc = net.seq(s, ent, grid, h0, priv, feats=True)  # + xc = cat[x, h] (N * L, d + HID) for the heads below
    vl = net.value_live(xc)                                   # (N * L,)
    xc = net.row_feats(s, ent, grid, h)                       # cat[x, h'] of single decisions from their stored h (no grad)
    aux = net.aux_out(xc, ent, s); loss, per_head = aux_losses(aux, labels)
"""
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import obs_v5 as O
from models4 import UnfoldConv2d                     # nirkt (MIOpen-safe conv)

N_FIRE = len(O.FIRE); N_FX = N_FIRE - 3               # fire classes; those past none / attack / super (fire_x outputs)
NVEC, HID, PRIV = [17, N_FIRE, 360, 8], 256, 40
_SUPER, _GADGET = O.FIRE.index("super"), O.FIRE_READY[O.FIRE.index("gadget")]   # super's class; gadget-ready self column
_GATE = [(c, k) for c, k in enumerate(O.FIRE_READY) if k is not None]   # fire class -> the self column that allows it
NONACT = ("vl.", "aux.")                              # parameter prefixes acting never uses (skipped by fast_act / act_stacked)
AUX_SLOTS = 9                                         # fut head: the enemy block (ent 0-8)
AUX_REL = {"fut": 1.0, "hit": 0.5, "gas": 0.5, "bush": 0.5}   # relative aux loss weights (behaviour design 5; x --aux-w)
_CAND = list(range(0, 9)) + list(range(25, 31))       # ent slots that can be aimed at: the enemy block + the power boxes
_FOE = [1 + O.ENT.index(c) for c in ("enemy", "enemy_summon", "power_box")]
N_LEAD, HMAX, N_STAT = 2, 160, 13                     # lead columns; hero table rows (+1 unknown); cond's brawler stats
F_IN = O.F_ENT + N_LEAD                               # entity row width the network sees
ENT_IN = ("ent.0.weight", "cand.0.weight", "aux.fut.0.weight")   # input = [x part] | obs row | lead (pad_param)
_OLD_ROW = {O.F_ENT_V52: (O.F_ENT_V52, 0), O.F_ENT_V52 + N_LEAD: (O.F_ENT_V52, N_LEAD),   # old input width after the x part
            O.F_ENT_V55 + N_LEAD: (O.F_ENT_V55, N_LEAD),                               # -> (obs row, lead) (v5.2 / v5.3-v5.5
            O.F_ENT_V59 + N_LEAD: (O.F_ENT_V59, N_LEAD)}                               #    / v5.6-v5.9)
_INT_AT = O.S_INT + O.N_INT_V59 - 4                   # vec.0 column after a v5.9 intent one-hot (pad_param inserts the new kinds)
_PSPEED = 4000 / 300 / 20                             # cond stats[3] (projectile Speed / 4000, units/s) -> tiles / tick
LAT = 3.0                                             # ticks between the frame and the shot: obs_v5 NOISE latency 1-2 decisions x 2


def lead(ent, s):
    """(..., N_ENT, 2) aim hint per present foe row: sin of the angle between the foe as seen and where a shot fired now
    meets it, and the flight time / 2 s. 0 for other rows, melee and targets faster than the shot. The frame is LAT ticks
    old when the shot leaves (obs latency 1-2 decisions, sim and live), so the foe is first moved on by its velocity
    relative to ours (s3 aimed behind movers: scorecard lead slope -0.41, HISTORY 82).
    ent (..., N_ENT, F_ENT): dx, dy in 10-tile units, vx, vy tiles / tick; s (..., N_S), self[6:8] own velocity."""
    p0 = ent[..., O.XY:O.XY + 2] * 10.0; v = ent[..., O.VEL:O.VEL + 2]
    p = p0 + (v - s[..., None, 6:8]) * LAT
    sp = (s[..., O.N_SELF + 3] * _PSPEED)[..., None]
    k = sp * sp - (v * v).sum(-1); bh = (p * v).sum(-1); c = (p * p).sum(-1)
    ok = ((k > 1e-4) & (ent[..., 0] > 0.5) & (ent[..., _FOE].sum(-1) > 0.5)).to(ent.dtype)
    t = ((bh + torch.sqrt((bh * bh + k * c).clamp_min(0.0))) / k.clamp_min(1e-4)).clamp(0.0, 40.0)
    q = p + v * t[..., None]
    sn = (p0[..., 0] * q[..., 1] - p0[..., 1] * q[..., 0]) / (torch.sqrt((p0 * p0).sum(-1) * (q * q).sum(-1)) + 1e-6)
    return torch.stack([sn, t / 40.0], -1) * ok[..., None]


def lead_deg(c, on):
    """(..., K) degrees from a candidate's bearing to where a shot fired now meets it (the lead() intercept; c = candidate
    rows with the lead columns at the end), times `on` (Policy.aim_lead: 0 = off, the aim bump sits on the bearing + the
    learned offset only). r51 left the intercept to the learned +-25 deg offset and aimed behind movers (scorecard lead
    slope -0.19, aim_err 11.7 deg)."""
    return torch.rad2deg(torch.asin(c[..., -N_LEAD].clamp(-1.0, 1.0))) * on


def _widen(lin, old_row):
    """insert zero input columns into Linear lin (input = [x part] | obs row (old_row wide) | lead) so its obs row is
    O.F_ENT wide; no RNG draw"""
    w = lin.weight; at = w.shape[1] - N_LEAD
    lin.weight = nn.Parameter(torch.cat([w[:, :at], w.new_zeros(w.shape[0], O.F_ENT - old_row), w[:, at:]], 1)); lin.in_features = lin.weight.shape[1]


def pad_param(name, v, o):
    """an old checkpoint's tensor v (a weight or its Adam moment) for this net's parameter o (same name) -> o's shape:
    the entity-input matrices (ENT_IN) get the newer obs-row columns as zeros between the old row and the lead columns,
    vec.0 of a v5.5-v5.9 net (a 7-kind intent block) gets the new kinds' one-hot columns as zeros at _INT_AT, before dx, dy;
    any other grown tensor zero-pads at the end of each dim (new inputs at the tail: s / cond / intent). v unchanged when
    it already fits or cannot be padded."""
    if v.shape == o.shape or v.dim() != o.dim() or not all(a <= b for a, b in zip(v.shape, o.shape)): return v
    if name == "vec.0.weight" and v.dim() == 2 and v.shape[1] == O.S_INT + O.N_INT_V59 and o.shape[1] == O.N_S:
        v = torch.cat([v[:, :_INT_AT], v.new_zeros(v.shape[0], O.N_INT - O.N_INT_V59), v[:, _INT_AT:]], 1)
        if v.shape == o.shape: return v
    if name in ENT_IN and v.dim() == 2 and v.shape[0] == o.shape[0]:
        pre = o.shape[1] - F_IN; row, n_lead = _OLD_ROW.get(v.shape[1] - pre, (None, None))
        assert row is not None, (name, tuple(v.shape))
        t = torch.zeros_like(o); t[:, :pre + row] = v[:, :pre + row]
        if n_lead: t[:, -N_LEAD:] = v[:, -N_LEAD:]
        return t
    t = torch.zeros_like(o); t[tuple(slice(0, n) for n in v.shape)] = v
    return t


def hero_index(s, table):
    """(...,) row of the hero whose stats match cond's (s[..., 8:21]); HMAX when none does. table (..., HMAX, 13)"""
    d2 = ((s[..., None, O.N_SELF:O.N_SELF + N_STAT] - table) ** 2).sum(-1)
    m, i = d2.min(-1)
    return torch.where(m < 1e-6, i, torch.full_like(i, HMAX))


class Policy(nn.Module):
    def __init__(self, d=512):
        super().__init__()
        self.emb = nn.Embedding(O.UNKNOWN + 1, 8)
        self.grid = nn.Sequential(UnfoldConv2d(8, 32, 3, 2, 1), nn.ReLU(), UnfoldConv2d(32, 64, 3, 2, 1), nn.ReLU(),
                                  nn.Flatten(), nn.Linear(64 * 7 * 7, 256), nn.ReLU())
        F55 = O.F_ENT_V55 + N_LEAD                       # v5.5 width: the same draws as before, v5.6 columns put in after
        self.ent = nn.Sequential(nn.Linear(F55, 128), nn.ReLU(), nn.Linear(128, 128), nn.ReLU())
        self.vec = nn.Sequential(nn.Linear(O.N_SELF + O.N_COND, 128), nn.ReLU())
        with torch.no_grad():                            # + the intent columns (v5.5), zero: same draws as before, same start
            v0 = self.vec[0]; v0.weight = nn.Parameter(torch.cat([v0.weight, v0.weight.new_zeros(128, O.N_INT)], 1)); v0.in_features = O.N_S
        self.trunk = nn.Sequential(nn.Linear(512, d), nn.ReLU())
        self.hemb = nn.Embedding(HMAX + 1, d); nn.init.zeros_(self.hemb.weight)
        self.register_buffer("hero_stats", torch.full((HMAX, N_STAT), 1e4))   # empty rows match nothing
        self.gru = nn.GRUCell(d, HID)
        self.pi = nn.Linear(d + HID, 17 + 3 + 8); self.v = nn.Linear(d + HID, 1)
        self.cand = nn.Sequential(nn.Linear(d + HID + F55, 128), nn.ReLU(), nn.Linear(128, 3))
        self.vp = nn.Sequential(nn.Linear(d + HID + PRIV, 256), nn.ReLU(), nn.Linear(256, 1))
        nn.init.zeros_(self.vp[2].weight); nn.init.zeros_(self.vp[2].bias)
        self.free = nn.Linear(d + HID, 360); self.free_score = nn.Linear(d + HID, 1)
        nn.init.orthogonal_(self.pi.weight, 0.01); nn.init.zeros_(self.pi.bias); nn.init.zeros_(self.free.weight)
        with torch.no_grad():   # the identity / line-of-sight columns (v5.6) start at zero, the lead columns unused
            _widen(self.ent[0], O.F_ENT_V55); _widen(self.cand[0], O.F_ENT_V55)
            self.ent[0].weight[:, O.F_ENT:] = 0; self.cand[0].weight[:, -N_LEAD:] = 0
        self.register_buffer("bins", torch.arange(360).float())
        self.register_buffer("aim_lead", torch.zeros(()))   # 1 = aim bumps centred on the lead() intercept (trainer --aim-lead)
        with torch.random.fork_rng(devices=[]):          # own CPU stream: the acting weights' draws stay as before
            torch.default_generator.manual_seed((torch.initial_seed() + 1) % 2 ** 63)
            self.vl = nn.Sequential(nn.Linear(d + HID, 256), nn.ReLU(), nn.Linear(256, 1))   # live value (no priv)
            nn.init.zeros_(self.vl[2].weight); nn.init.zeros_(self.vl[2].bias)

        with torch.random.fork_rng(devices=[]):          # aux heads, own stream too (128 wide: small next to the grid conv)
            torch.default_generator.manual_seed((torch.initial_seed() + 2) % 2 ** 63)
            mlp = lambda i, o: nn.Sequential(nn.Linear(i, 128), nn.ReLU(), nn.Linear(128, o))
            self.aux = nn.ModuleDict({"fut": mlp(d + HID + F55, 2), "hit": mlp(d + HID, 1), "gas": mlp(d + HID, 1), "bush": mlp(d + HID, 8)})
            nn.init.zeros_(self.aux["fut"][2].weight); nn.init.zeros_(self.aux["fut"][2].bias)
            with torch.no_grad(): _widen(self.aux["fut"][0], O.F_ENT_V55)
        with torch.random.fork_rng(devices=[]):          # v5.7 extra fire classes: zero-init, no draw from the acting stream;
            self.fire_x = nn.Linear(d + HID, N_FX)       # registered last = the tail of the main Adam's parameter list
        nn.init.zeros_(self.fire_x.weight); nn.init.zeros_(self.fire_x.bias)
        with torch.no_grad(): self.vec[0].weight[:, _GADGET] = 0   # the gadget-ready input (self 3, always 0 before v5.7) starts unused

    def add_heroes(self, stats):
        """put each (13,) stats row not in the table yet into the next free row (order-stable across resumes) -> count"""
        t = self.hero_stats
        with torch.no_grad():
            for r in torch.as_tensor(np.asarray(stats, np.float32), device=t.device):
                if hero_index(torch.cat([r.new_zeros(O.N_SELF), r]), t) < HMAX:
                    continue
                free = (t[:, 0] >= 1e3).nonzero()
                assert len(free), "hero table full (HMAX %d)" % HMAX
                t[free[0, 0]] = r
        return int((t[:, 0] < 1e3).sum())

    def load_state_dict(self, sd, strict=True, **kw):
        """old checkpoints: grown inputs zero-padded in place (pad_param: the entity input weights by the lead columns,
        the area-effect columns (v5.3) and the identity / line-of-sight columns (v5.6), between the observation's row and
        the lead columns; s / cond / intent at the tail) = same outputs; no hemb -> zeros (a reused league slot must not
        keep the previous snapshot's rows; the hero table may stay); no fire_x (before v5.7) -> zeros (the new classes
        start at logit 0, masked until ready), fewer fire_x rows -> zero-padded, and its vec.0 column of the gadget-ready
        input zeroed: self 3 was always 0, so those weights are still their random init; no aim_lead -> 0 (aims as before)"""
        own = self.state_dict(); sd = dict(sd)
        if "fire_x.weight" not in sd and "vec.0.weight" in sd:
            sd["vec.0.weight"] = sd["vec.0.weight"].clone(); sd["vec.0.weight"][:, _GADGET] = 0
        for k in ("hemb.weight", "fire_x.weight", "fire_x.bias", "aim_lead"):
            if k not in sd: sd[k] = torch.zeros_like(own[k])
        for k, v in sd.items():
            if k in own: sd[k] = pad_param(k, v, own[k])
        return super().load_state_dict(sd, strict=strict, **kw)

    def encode(self, s, ent, grid):
        ent = torch.cat([ent, lead(ent, s)], -1)
        e = self.ent(ent).masked_fill(ent[..., :1] < 0.5, 0.0).amax(1)             # set pooling over the present slots
        g = self.grid(self.emb(grid.long()).permute(0, 3, 1, 2))
        x = self.trunk[0](torch.cat([self.vec(s), e, g], -1)) + self.hemb(hero_index(s, self.hero_stats))
        return F.relu(x)

    def heads(self, x, ent, s, priv=None):
        """x = cat[trunk, gru]. The aim head is nirkt's PointerAim: a bump at every target's angle (+ the lead() intercept
        when aim_lead is 1, + a learned lead of up to 25 degrees, learned width) mixed with a free 360-bin component;
        log-probabilities."""
        mv, fi, di = torch.split(self.pi(x), [17, 3, 8], -1); fi = torch.cat([fi, self.fire_x(x)], -1)
        c = ent[:, _CAND]; c = torch.cat([c, lead(c, s)], -1); B, K, _ = c.shape
        here = (c[..., 0] > 0.5) & (c[..., _FOE].sum(-1) > 0.5)
        o = self.cand(torch.cat([x[:, None].expand(B, K, x.shape[-1]), c], -1))
        mu = torch.rad2deg(torch.atan2(c[..., O.XY + 1], c[..., O.XY])) % 360.0 + lead_deg(c, self.aim_lead) + 25.0 * torch.tanh(o[..., 1])
        dd = (self.bins - mu[..., None]).abs() % 360.0; dd = torch.minimum(dd, 360.0 - dd)
        bump = torch.log_softmax(-0.5 * (dd / (F.softplus(o[..., 2]) + 0.7)[..., None]) ** 2, -1)
        mix = torch.log_softmax(torch.cat([o[..., 0].masked_fill(~here, -1e9), self.free_score(x)], -1), -1)
        comp = torch.cat([bump, torch.log_softmax(self.free(x), -1)[:, None]], 1)
        v = self.v(x).squeeze(-1)
        if priv is not None: v = v + self.vp(torch.cat([x, priv], -1)).squeeze(-1)
        return (mv, fi, torch.logsumexp(mix[..., None] + comp, 1), di), v

    def forward(self, s, ent, grid, h, priv=None):
        x = self.encode(s, ent, grid); h = self.gru(x, h)
        (mv, fi, ai, di), v = self.heads(torch.cat([x, h], -1), ent, s, priv)
        return (mv, mask_fire(fi, s), ai, di), v, h

    def seq(self, s, ent, grid, h, priv=None, feats=False):
        """feats: also return xc = cat[x, h] (N * L, d + HID), the input of value_live / the aux heads"""
        N, L = s.shape[:2]; f = lambda t: t.flatten(0, 1)
        x = self.encode(f(s), f(ent), f(grid)).view(N, L, -1); hs = []
        for t in range(L):
            h = self.gru(x[:, t], h); hs.append(h)
        xc = f(torch.cat([x, torch.stack(hs, 1)], -1))
        (mv, fi, ai, di), v = self.heads(xc, f(ent), f(s), None if priv is None else f(priv))
        return ((mv, mask_fire(fi, f(s)), ai, di), v, xc) if feats else ((mv, mask_fire(fi, f(s)), ai, di), v)

    def value_live(self, xc):
        """(N,) live value from cat[x, h]: no priv, detached input (a probe: its loss reaches only `vl`)"""
        return self.vl(xc.detach()).squeeze(-1)

    def aux_out(self, xc, ent, s):
        """aux predictions from cat[x, h] (not detached) and the entity rows (N, N_ENT, F_ENT): fut (N, 9, 2) each
        enemy-block slot's position in 1 s relative to my position now (10-tile units), hit (N,) logit of P(enemy damage
        taken in the next 1 s), gas (N,) gas margin / 10 tiles, bush (N, 8) logits per sector (env_v5.AUX "be")"""
        e = ent[:, :AUX_SLOTS]; e = torch.cat([e, lead(e, s)], -1); N, K, _ = e.shape
        fut = e[..., O.XY:O.XY + 2] + self.aux["fut"](torch.cat([xc[:, None].expand(N, K, xc.shape[-1]), e], -1))
        return {"fut": fut, "hit": self.aux["hit"](xc)[:, 0], "gas": self.aux["gas"](xc)[:, 0], "bush": self.aux["bush"](xc)}

    @torch.no_grad()
    def row_feats(self, s, ent, grid, h):
        """cat[x, h'] of single decisions from their stored GRU input state h (the acting math; the trainers' pass over a
        rollout and the replay readout)"""
        x = self.encode(s, ent, grid)
        return torch.cat([x, self.gru(x, h)], -1)


def aux_losses(out, lab):
    """masked aux losses (Policy.aux_out vs train_ppo.aux_labels) -> (sum of AUX_REL x loss, {head: loss}). lab: fut
    (N, 9, 2) + fut_m (N, 9), hit (N,) + hit_m (N,), gas (N,), bush (N, 8), m (N,) = rows with labels (alive). Huber
    delta 0.1 = 1 tile (fut, gas), BCE (hit, bush multi-label)"""
    mm = lambda x, m: (x * m).sum() / m.sum().clamp(min=1)
    m = lab["m"]
    L = {"fut": mm(F.huber_loss(out["fut"], lab["fut"], reduction="none", delta=0.1).sum(-1), lab["fut_m"] * m[:, None]),
         "hit": mm(F.binary_cross_entropy_with_logits(out["hit"], lab["hit"], reduction="none"), lab["hit_m"] * m),
         "gas": mm(F.huber_loss(out["gas"], lab["gas"], reduction="none", delta=0.1), m),
         "bush": mm(F.binary_cross_entropy_with_logits(out["bush"], lab["bush"], reduction="none").mean(-1), m)}
    return sum(AUX_REL[k] * v for k, v in L.items()), L


def mask_fire(fi, s):
    """fire head (obs_v5.FIRE): a class with a FIRE_READY column only while that self column is set (super: self 2, super
    ready; gadget: self 3, gadget ready); s = the self (+ cond + intent) rows. HISTORY 77: 12 % of decisions pressed an
    uncharged super (live that blocks the fire finger 150 ms). Works on a 3-class head too (classes past its width are
    skipped)."""
    cls = torch.arange(fi.shape[-1], device=fi.device)
    for c, k in _GATE:
        if c < fi.shape[-1]: fi = fi.masked_fill((s[..., k] < 0.5)[..., None] & (cls == c), -1e9)
    return fi


def aim_mask(fire):
    """(...,) fire class -> 1.0 where the aim head counts (obs_v5.FIRE_AIM)"""
    return torch.as_tensor(O.FIRE_AIM, dtype=torch.float32, device=fire.device)[fire]


def dist_logp_ent(logits, actions=None, masks=None):
    """categorical heads (move, fire, aim, distance) -> (log-prob of actions, entropy, sampled actions): nirkt's
    models4.dist_logp_ent for the obs_v5.FIRE classes (models4 masks only a 3-class fire head): the aim head counts when
    the fire class aims (FIRE_AIM) and the distance head only for a super (their values do nothing otherwise). Same draws
    and, for fire < 3, the same values as models4's. masks: unused (as in models4)."""
    lps, ents, samples = [], [], []
    for i, lg in enumerate(logits):
        d = torch.distributions.Categorical(logits=lg)
        a = d.sample() if actions is None else actions[:, i]
        samples.append(a); lps.append(d.log_prob(a)); ents.append(d.entropy())
    lp, en = torch.stack(lps, -1), torch.stack(ents, -1)
    if len(logits) == 4:
        fire = samples[1]; one = torch.ones_like(fire, dtype=lp.dtype)
        m = torch.stack([one, one, aim_mask(fire).to(lp.dtype), (fire == _SUPER).to(lp.dtype)], -1)
        lp, en = lp * m, en * m
    return lp.sum(-1), en.sum(-1), torch.stack(samples, -1)


class _Act(nn.Module):
    """acting forward of one Policy with the GRU step written out (torch.func.vmap has no gru_cell rule; same math as
    nn.GRUCell): used by act_stacked"""
    def __init__(self, p): super().__init__(); self.p = p

    def forward(self, s, ent, grid, h, priv):
        p = self.p; x = p.encode(s, ent, grid); g = p.gru
        ir, iz, i_n = F.linear(x, g.weight_ih, g.bias_ih).chunk(3, -1); hr, hz, h_n = F.linear(h, g.weight_hh, g.bias_hh).chunk(3, -1)
        r, z = torch.sigmoid(ir + hr), torch.sigmoid(iz + hz); h = (1 - z) * torch.tanh(i_n + r * h_n) + z * h
        (mv, fi, ai, di), v = p.heads(torch.cat([x, h], -1), ent, s, priv)
        return (mv, mask_fire(fi, s), ai, di), v, h


_ACT_META = None


def acting_params(net):
    """name -> parameter of a Policy, without the heads acting never runs (NONACT)"""
    return {k: v for k, v in net.named_parameters() if not k.startswith(NONACT)}


def act_stacked(nets, xs):
    """one vmapped forward for several Policies (different weights) on their own row sets (speed round, HISTORY 68: the
    per-net loop paid ~8 ms of fixed GPU cost per net). nets: list of Policy; xs: list of (s, ent, grid, h, priv) device
    tensors, one tuple per net (any batch sizes, padded to the largest). -> logits tuple, v, h with a leading net axis
    (G, Bmax, ...); rows past each net's own B are padding."""
    global _ACT_META
    from torch.func import functional_call, vmap
    acts = [_Act(n) for n in nets]
    if _ACT_META is None: _ACT_META = _Act(Policy()).to("meta")
    st = lambda ds: {k: torch.stack([d[k].detach() for d in ds]) for k in ds[0]}   # detached: the learner has grads, frozen nets not
    P, Bf = st([{"p." + k: v for k, v in acting_params(n).items()} for n in nets]), st([dict(a.named_buffers()) for a in acts])
    Bm = max(x[0].shape[0] for x in xs)
    pad = lambda t: torch.cat([t, t.new_zeros((Bm - t.shape[0],) + t.shape[1:])]) if t.shape[0] < Bm else t
    X = [torch.stack([pad(x[i]) for x in xs]) for i in range(5)]
    r = vmap(lambda p, b, *x: functional_call(_ACT_META, (p, b), x))(P, Bf, *X)
    return r[0], r[1], r[2]


def masked_kl(ref, new):
    """KL(ref || new) of the factored policy: move + fire + P_ref(an aiming fire class) aim + P_ref(super) distance
    (nirkt F1.4; aiming classes = obs_v5.FIRE_AIM)"""
    kl = []
    for a, b in zip(ref, new):
        pa, pb = torch.log_softmax(a.float(), -1), torch.log_softmax(b.float(), -1)
        kl.append((pa.exp() * (pa - pb)).sum(-1))
    pf = torch.softmax(ref[1].float(), -1); aim = torch.as_tensor(O.FIRE_AIM[:pf.shape[-1]], dtype=pf.dtype, device=pf.device)
    return kl[0] + kl[1] + (pf * aim).sum(-1) * kl[2] + pf[:, _SUPER] * kl[3]


def _check():
    torch.manual_seed(0); net = Policy(); N, L = 3, 4
    s = torch.randn(N, L, O.N_S); ent = torch.zeros(N, L, O.N_ENT, O.F_ENT)
    grid = torch.randint(0, O.UNKNOWN + 1, (N, L, O.G, O.G), dtype=torch.uint8)
    ent[:, :, 0, 0] = 1; ent[:, :, 0, 1 + O.ENT.index("enemy")] = 1; ent[:, :, 0, O.XY] = 0.3      # an enemy straight right
    ent[:, :, 1, 0] = 1; ent[:, :, 1, 1 + O.ENT.index("teammate")] = 1; ent[:, :, 1, O.XY + 1] = 0.3   # a teammate below
    pv = torch.randn(N, L, PRIV); h = torch.zeros(N, HID); outs = []
    assert torch.equal(net.seq(s, ent, grid, h, pv)[1], net.seq(s, ent, grid, h)[1])     # zero-init branch: an old checkpoint's value
    nn.init.normal_(net.vp[2].weight, std=0.1)
    for t in range(L):                                    # step by step == seq from the same h0
        lg, v, h = net(s[:, t], ent[:, t], grid[:, t], h, pv[:, t]); outs.append((lg, v))
    lg2, v2 = net.seq(s, ent, grid, torch.zeros(N, HID), pv)
    assert [x.shape[-1] for x in lg2] == NVEC and v2.shape == (N * L,)
    assert torch.allclose(torch.stack([o[1] for o in outs], 1).flatten(), v2, atol=1e-5)
    assert torch.allclose(torch.stack([o[0][2] for o in outs], 1).flatten(0, 1), lg2[2], atol=1e-4)
    p = lg2[2].exp(); assert torch.allclose(p.sum(-1), torch.ones(N * L), atol=1e-4)
    near = lambda a: p[:, [(a + k) % 360 for k in range(-30, 31)]].sum(-1).mean().item()
    assert near(0) > 3 * near(90), (near(0), near(90))    # mass at the enemy (0 deg), none pulled to the teammate (90 deg)
    lp, en, a = dist_logp_ent(lg2); assert a.shape == (N * L, 4) and torch.isfinite(lp).all()
    assert masked_kl(lg2, lg2).abs().max() < 1e-5
    (lp.mean() + v2.mean()).backward()
    _check_aux(net, s, ent, grid)
    _check_live(net, s, ent, grid, pv)
    _check_stage2()
    _check_aim_lead()
    print("model ok: %d parameters" % sum(x.numel() for x in net.parameters()))


def _check_live(net, s, ent, grid, pv):
    """vl: zero at init, its loss reaches only vl.*, feats / row_feats are the acting features, acting ignores NONACT"""
    N = s.shape[0]; h0 = torch.zeros(N, HID); net.zero_grad(set_to_none=True)
    lg, v, xc = net.seq(s, ent, grid, h0, pv, feats=True); lg0, v0 = net.seq(s, ent, grid, h0, pv)
    assert all(torch.equal(a, b) for a, b in zip(lg, lg0)) and torch.equal(v, v0) and xc.shape == (s.shape[0] * s.shape[1], 512 + HID)
    assert torch.allclose(net.row_feats(s[:, 0], ent[:, 0], grid[:, 0], h0), xc.view(N, -1, xc.shape[-1])[:, 0], atol=1e-6)
    vl = net.value_live(xc); assert not vl.any()
    ((vl - 1.0) ** 2).mean().backward()
    assert all(p.grad is None for k, p in net.named_parameters() if not k.startswith("vl.")) and net.vl[2].weight.grad.abs().sum() > 0
    xs = [(s[:, 0], ent[:, 0], grid[:, 0], h0, pv[:, 0])]
    with torch.no_grad():
        r0 = act_stacked([net], xs)
        for k, p in net.named_parameters():
            if k.startswith(NONACT): p.normal_(0, 0.5)
        r1 = act_stacked([net], xs)
    assert all(torch.equal(a, b) for a, b in zip(list(r0[0]) + [r0[1], r0[2]], list(r1[0]) + [r1[1], r1[2]])), "acting reads a non-acting head"
    assert not any(k.startswith(NONACT) for k in acting_params(net)) and len(acting_params(net)) < len(dict(net.named_parameters()))


def _check_aux(net, s, ent, grid):
    """aux heads: shapes, fut starts at the seen position, masked labels do not count, the loss reaches the encoders /
    GRU and the aux heads but no policy / value head"""
    N, L = s.shape[:2]; f = lambda t: t.flatten(0, 1); net.zero_grad(set_to_none=True)
    xc = net.seq(s, ent, grid, torch.zeros(N, HID), feats=True)[2]; out = net.aux_out(xc, f(ent), f(s)); M = N * L
    assert out["fut"].shape == (M, AUX_SLOTS, 2) and out["hit"].shape == out["gas"].shape == (M,) and out["bush"].shape == (M, 8)
    assert torch.equal(out["fut"], f(ent)[:, :AUX_SLOTS, O.XY:O.XY + 2])          # zero-init offset: "stays where seen"
    g = torch.Generator().manual_seed(3); r = lambda *sh: torch.rand(*sh, generator=g)
    lab = {"fut": r(M, AUX_SLOTS, 2), "fut_m": (r(M, AUX_SLOTS) < 0.5).float(), "hit": (r(M) < 0.3).float(), "hit_m": (r(M) < 0.8).float(),
           "gas": r(M), "bush": (r(M, 8) < 0.1).float(), "m": torch.ones(M)}
    lab["m"][0] = 0; tot, per = aux_losses(out, lab)
    lab2 = dict(lab); lab2["fut"] = torch.where(lab["fut_m"][..., None] > 0, lab["fut"], lab["fut"] + 5)   # masked: anything
    lab2["hit"] = torch.where(lab["hit_m"] > 0, lab["hit"], 1 - lab["hit"]); lab2["gas"] = lab["gas"].clone(); lab2["gas"][0] = 9.0
    tot2, per2 = aux_losses(out, lab2)
    assert torch.allclose(tot, tot2) and all(torch.isfinite(v) and v > 0 for v in per.values()), (per, per2)
    tot.backward()
    grads = {k: p.grad is not None and p.grad.abs().sum() > 0 for k, p in net.named_parameters()}
    for k in ("ent.0.weight", "grid.0.weight", "vec.0.weight", "trunk.0.weight", "gru.weight_ih", "aux.fut.2.weight", "aux.bush.0.weight"):
        assert grads[k], k
    assert not any(v for k, v in grads.items() if k.split(".")[0] in ("pi", "v", "vp", "cand", "free", "free_score", "vl")), [k for k, v in grads.items() if v]


def _check_stage2():
    """lead hint math; an old-format checkpoint (no lead columns / hero table) acts the same after loading; hero rows"""
    s = torch.zeros(1, O.N_S); s[0, O.N_SELF + 3] = 1.0                    # shot 0.667 tiles / tick
    ent = torch.zeros(1, O.N_ENT, O.F_ENT); ent[0, :2, 0] = 1; ent[0, :2, 1 + O.ENT.index("enemy")] = 1
    ent[0, :2, O.XY] = 0.3; ent[0, 0, O.VEL + 1] = 0.12                                  # 3 tiles right, slot 0 walks down
    ld = lead(ent, s)[0]; sp = 4000 / 6000                                               # slot 0: brute-force intercept
    ts = np.linspace(0, 40, 400001); y0 = 0.12 * LAT                                     # seen at y 0, now at 0.12 x LAT
    t = ts[np.argmin(np.abs(np.hypot(3.0, y0 + 0.12 * ts) - sp * ts))]; qy = y0 + 0.12 * t
    assert abs(ld[0, 1] - t / 40) < 1e-3 and abs(ld[0, 0] - qy / np.hypot(3.0, qy)) < 1e-3, (ld[0], t, qy)
    assert abs(ld[1, 0]) < 1e-6 and abs(ld[1, 1] - 3.0 / sp / 40) < 1e-3 and ld[2:].abs().max() == 0, ld[:3]
    s2 = s.clone(); s2[0, 6:8] = torch.tensor([0.0, 0.12])     # we walk along with it: no latency shift, still a lead
    t0 = 3.0 / (sp ** 2 - 0.12 ** 2) ** 0.5
    assert abs(lead(ent, s2)[0, 0, 0] - 0.12 * t0 / np.hypot(3.0, 0.12 * t0)) < 1e-3
    torch.manual_seed(1); N, L = 2, 3
    s = torch.randn(N, L, O.N_S); s[..., O.N_SELF:O.N_SELF + N_STAT] = s[:, :1, O.N_SELF:O.N_SELF + N_STAT]
    s[..., O.N_SELF + 3] = 1.0                                                            # one hero per sequence
    ent = torch.zeros(N, L, O.N_ENT, O.F_ENT); ent[..., :3, 0] = 1; ent[..., :3, 1 + O.ENT.index("enemy")] = 1
    ent[..., :3, O.XY:O.HP] = torch.randn(N, L, 3, 4) * 0.2
    grid = torch.randint(0, O.UNKNOWN + 1, (N, L, O.G, O.G), dtype=torch.uint8); h0 = torch.zeros(N, HID)
    ent[..., :3, O.RAD:] = torch.rand(N, L, 3, O.F_ENT - O.RAD)                          # new inputs present: an old net ignores them
    a = Policy(); nn.init.normal_(a.pi.weight, std=0.1); na = O.F_ENT - O.F_ENT_V52; pre = a.cand[0].weight.shape[1] - F_IN
    with torch.no_grad():                                                                 # a v5.2 net: lead used, no area columns
        nn.init.normal_(a.ent[0].weight[:, O.F_ENT:], std=0.3); nn.init.normal_(a.cand[0].weight[:, -N_LEAD:], std=0.3)
        a.ent[0].weight[:, O.F_ENT_V52:O.F_ENT] = 0; a.cand[0].weight[:, pre + O.F_ENT_V52:pre + O.F_ENT] = 0
        a.vec[0].weight[:, O.N_SELF + O.N_COND_V53:] = 0                                 # and v5.3's cond (28: no leash / gas_safe)
    ref = a.seq(s, ent, grid, h0)[0]
    old = {k: v for k, v in a.state_dict().items() if k not in ("hemb.weight", "hero_stats")}
    v52 = lambda w, p: torch.cat([w[:, :p + O.F_ENT_V52], w[:, p + O.F_ENT:]], 1)        # the v5.2 layout: row 16 | lead 2
    old["ent.0.weight"] = v52(old["ent.0.weight"], 0); old["cand.0.weight"] = v52(old["cand.0.weight"], pre)
    old["vec.0.weight"] = old["vec.0.weight"][:, :O.N_SELF + O.N_COND_V53]; assert O.N_COND - O.N_COND_V53 == 2
    assert old["ent.0.weight"].shape[1] == O.F_ENT_V52 + N_LEAD and O.F_ENT_V55 - O.F_ENT_V52 == 4 and na == 22
    c = Policy(); c.load_state_dict({**old, "ent.0.weight": old["ent.0.weight"][:, :O.F_ENT_V52]}, strict=False)   # pre-lead format
    assert torch.equal(c.ent[0].weight[:, :O.F_ENT_V52], a.ent[0].weight[:, :O.F_ENT_V52]) and not c.ent[0].weight[:, O.F_ENT_V52:].any()
    b = Policy(); b.load_state_dict(old, strict=False)
    assert b.add_heroes(s[:, 0, O.N_SELF:O.N_SELF + N_STAT]) == N and b.add_heroes(s[:1, 0, O.N_SELF:O.N_SELF + N_STAT]) == N
    got = b.seq(s, ent, grid, h0)[0]
    assert max((x - y).abs().max().item() for x, y in zip(ref, got)) < 1e-6, "old checkpoint acts differently"
    assert (hero_index(s, b.hero_stats) < N).all() and (hero_index(torch.randn(4, s.shape[-1]), b.hero_stats) == HMAX).all()
    nn.init.normal_(b.hemb.weight, std=0.5)
    assert max((x - y).abs().max().item() for x, y in zip(ref, b.seq(s, ent, grid, h0)[0])) > 1e-3   # the embedding is used
    _check_v55(ent, grid, h0)
    _check_v56(ent, grid, h0)
    _check_v510(ent, grid, h0)
    _check_fire()


def _check_v55(ent, grid, h0):
    """obs v5.5: a v5.4 checkpoint (vec.0 without the intent columns) acts the same with a zero and with any intent block;
    a fresh Policy's intent columns start at zero and get a gradient"""
    torch.manual_seed(2); N, L = ent.shape[:2]
    assert not Policy().vec[0].weight[:, O.S_INT:].any() and Policy().vec[0].weight.shape == (128, O.N_S)
    s = torch.randn(N, L, O.N_S); s[..., O.N_SELF + 3] = 1.0; s0 = s.clone(); s0[..., O.S_INT:] = 0   # free play: block zero
    a = Policy(); nn.init.normal_(a.pi.weight, std=0.1)
    old = dict(a.state_dict()); old["vec.0.weight"] = old["vec.0.weight"][:, :O.S_INT]          # the v5.4 layout: 38 columns
    with torch.no_grad(): nn.init.normal_(a.vec[0].weight[:, O.S_INT:], std=0.3)               # a v5.5 net that reads the block
    b = Policy(); b.load_state_dict(old, strict=False); assert not b.vec[0].weight[:, O.S_INT:].any()
    ref, got0, got = a.seq(s0, ent, grid, h0)[0], b.seq(s0, ent, grid, h0)[0], b.seq(s, ent, grid, h0)[0]
    d = lambda x, y: max((u - v).abs().max().item() for u, v in zip(x, y))
    assert d(ref, got0) < 1e-6 and d(got0, got) < 1e-6, "v5.4 checkpoint acts differently"
    assert d(ref, a.seq(s, ent, grid, h0)[0]) > 1e-3                                           # the block is an input
    b.zero_grad(); b.seq(s, ent, grid, h0)[0][0].sum().backward(); assert b.vec[0].weight.grad[:, O.S_INT:].abs().sum() > 0



def _check_v56(ent, grid, h0):
    """obs v5.6: a v5.5 checkpoint (entity rows 20 wide + lead, aux fut included) acts the same whatever the identity /
    line-of-sight columns hold, its lead / aux weights land on the lead columns; a fresh Policy's new columns are zero and
    get a gradient; pad_param on an Adam moment = the weight's layout"""
    torch.manual_seed(5); N, L = ent.shape[:2]; d = 512 + HID
    fresh = Policy(); n_new = O.F_ENT - O.F_ENT_V55
    for k in ENT_IN:
        w = fresh.state_dict()[k]; pre = w.shape[1] - F_IN
        assert not w[:, pre + O.F_ENT_V55:pre + O.F_ENT].any() and w.shape[1] == pre + F_IN, k
    s = torch.randn(N, L, O.N_S); s[..., O.N_SELF + 3] = 1.0
    e0 = ent.clone(); e0[..., O.ID0:] = 0; e1 = ent.clone(); e1[..., :5, O.ID0:] = torch.rand(N, L, 5, n_new) * 2
    e1[..., :5, O.ID_KNOWN] = 1
    a = Policy(); nn.init.normal_(a.pi.weight, std=0.1)
    with torch.no_grad():
        for k in ENT_IN:                                  # a v5.5 net: lead used, no identity columns
            w = dict(a.named_parameters())[k]; pre = w.shape[1] - F_IN
            nn.init.normal_(w[:, -N_LEAD:], std=0.3); w[:, pre + O.F_ENT_V55:pre + O.F_ENT] = 0
        nn.init.normal_(a.aux["fut"][2].weight, std=0.3)
    cut = lambda w: torch.cat([w[:, :w.shape[1] - F_IN + O.F_ENT_V55], w[:, w.shape[1] - N_LEAD:]], 1)   # the v5.5 layout
    old = {k: (cut(v) if k in ENT_IN else v) for k, v in a.state_dict().items()}
    assert old["ent.0.weight"].shape[1] == O.F_ENT_V55 + N_LEAD and old["aux.fut.0.weight"].shape[1] == d + O.F_ENT_V55 + N_LEAD
    b = Policy(); b.load_state_dict(old, strict=False)
    assert all(torch.equal(a.state_dict()[k], b.state_dict()[k]) for k in ENT_IN)             # lead weights back on the lead columns
    ref = a.seq(s, e0, grid, h0, feats=True); got = b.seq(s, e1, grid, h0, feats=True)
    dd = lambda x, y: max((u - v).abs().max().item() for u, v in zip(x, y))
    assert dd(ref[0], got[0]) < 1e-6 and (ref[2] - got[2]).abs().max() < 1e-6, "v5.5 checkpoint acts differently"
    fa = lambda n, e, xc: n.aux_out(xc, e.flatten(0, 1), s.flatten(0, 1))["fut"]
    assert (fa(a, e0, ref[2]) - fa(b, e1, got[2])).abs().max() < 1e-6                         # aux fut reads the same columns
    with torch.no_grad(): nn.init.normal_(a.ent[0].weight[:, O.ID0:O.F_ENT], std=0.3)
    assert dd(ref[0], a.seq(s, e1, grid, h0)[0]) > 1e-3                                       # the new columns are inputs
    b.zero_grad(); b.seq(s, e1, grid, h0)[0][0].sum().backward(); assert b.ent[0].weight.grad[:, O.ID0:O.F_ENT].abs().sum() > 0
    m = torch.randn_like(old["cand.0.weight"])               # an Adam moment of the v5.5 layout
    pm = pad_param("cand.0.weight", m, b.cand[0].weight); pre = pm.shape[1] - F_IN
    assert torch.equal(pm[:, :pre + O.F_ENT_V55], m[:, :pre + O.F_ENT_V55]) and torch.equal(pm[:, -N_LEAD:], m[:, -N_LEAD:]) and not pm[:, pre + O.F_ENT_V55:pre + O.F_ENT].any()
    v = torch.randn(128, O.S_INT); pv = pad_param("vec.0.weight", v, b.vec[0].weight)       # tail inputs: the generic pad
    assert torch.equal(pv[:, :O.S_INT], v) and not pv[:, O.S_INT:].any()



def _check_v510(ent, grid, h0):
    """obs v5.10: a v5.9 checkpoint (entity rows 36 wide + lead, a 7-kind intent block in vec.0) loads with its weights on
    the same inputs: zero columns for the cubes and the two new kinds, so it acts the same whatever they hold; an Adam
    moment of vec.0 pads the same way"""
    torch.manual_seed(7); N, L = ent.shape[:2]; k0, k1 = _INT_AT, _INT_AT + O.N_INT - O.N_INT_V59
    a = Policy(); nn.init.normal_(a.pi.weight, std=0.1)
    with torch.no_grad():
        nn.init.normal_(a.vec[0].weight[:, O.S_INT:], std=0.3); a.vec[0].weight[:, k0:k1] = 0   # a v5.9 net reads its block
        for k in ENT_IN:
            w = dict(a.named_parameters())[k]; pre = w.shape[1] - F_IN
            nn.init.normal_(w[:, pre + O.ID0:], std=0.3); w[:, pre + O.CUB:pre + O.F_ENT] = 0
    cut = lambda w: torch.cat([w[:, :w.shape[1] - F_IN + O.F_ENT_V59], w[:, w.shape[1] - N_LEAD:]], 1)   # the v5.9 layout
    vcut = lambda w: torch.cat([w[:, :k0], w[:, k1:]], 1)
    old = {k: (cut(v) if k in ENT_IN else vcut(v) if k == "vec.0.weight" else v) for k, v in a.state_dict().items()}
    assert old["vec.0.weight"].shape[1] == 49 and old["ent.0.weight"].shape[1] == O.F_ENT_V59 + N_LEAD
    b = Policy(); b.load_state_dict(old, strict=False)
    assert all(torch.equal(a.state_dict()[k], b.state_dict()[k]) for k in ENT_IN + ("vec.0.weight",))
    s = torch.randn(N, L, O.N_S); s[..., O.N_SELF + 3] = 1.0; e1 = ent.clone(); e1[..., :5, O.CUB:] = torch.rand(N, L, 5, 2) * 2
    s0 = s.clone(); s0[..., k0:k1] = 0; e0 = ent.clone(); e0[..., O.CUB:] = 0
    dd = lambda x, y: max((u - v).abs().max().item() for u, v in zip(x, y))
    assert dd(b.seq(s, e1, grid, h0)[0], a.seq(s0, e0, grid, h0)[0]) < 1e-6, "v5.9 checkpoint acts differently"
    m = torch.randn(128, 49); pm = pad_param("vec.0.weight", m, b.vec[0].weight)
    assert torch.equal(pm[:, :k0], m[:, :k0]) and torch.equal(pm[:, k1:], m[:, k0:]) and not pm[:, k0:k1].any()
    assert (O.I_XY + O.S_INT, k0, k1) == (k1, 45, 47)    # dx sits right after the widened one-hot


def _check_fire():
    """v5.7 / v5.8 fire head: the gadget class is masked while self 3 is off, the hypercharge class while self 4 is off; a
    v5.6 checkpoint (no fire_x) acts exactly as before with self 3 / 4 off and can learn the gadget once it is ready; a v5.7
    checkpoint (one fire_x row) loads with the hypercharge row zero-padded; log-prob masking (aim for the gadget, not for
    the hypercharge, distance only for a super) and the masked KL; fire_x is the tail of the acting parameters"""
    torch.manual_seed(2); N, L, G_, H_ = 3, 4, O.FIRE.index("gadget"), O.FIRE.index("hypercharge")
    s = torch.randn(N, L, O.N_S); s[..., 2] = 1.0; s[..., 3] = 0.0; s[..., 4] = 0.0          # super ready, gadget / hypercharge not
    ent = torch.zeros(N, L, O.N_ENT, O.F_ENT); ent[..., 0, 0] = 1; ent[..., 0, 1 + O.ENT.index("enemy")] = 1; ent[..., 0, O.XY] = 0.3
    grid = torch.randint(0, O.UNKNOWN + 1, (N, L, O.G, O.G), dtype=torch.uint8); h0 = torch.zeros(N, HID)
    assert list(acting_params(Policy()))[-2:] == ["fire_x.weight", "fire_x.bias"] and not Policy().vec[0].weight[:, _GADGET].any()
    a = Policy(); nn.init.normal_(a.pi.weight, std=0.1)
    with torch.no_grad(): a.vec[0].weight[:, _GADGET].normal_(0, 1.0)                     # as an old run left it (never trained)
    lg = a.seq(s, ent, grid, h0)[0]
    assert lg[1].shape[-1] == N_FIRE == 5 and (lg[1][:, G_] < -1e8).all() and (lg[1][:, H_] < -1e8).all(), lg[1][:2]
    old = {k: v for k, v in a.state_dict().items() if not k.startswith("fire_x")}          # a v5.6 checkpoint
    b = Policy(); nn.init.normal_(b.fire_x.weight, std=1.0); b.load_state_dict(old)       # strict: fire_x filled with zeros
    assert b.fire_x.weight.abs().max() == 0 and b.fire_x.bias.abs().max() == 0 and not b.vec[0].weight[:, _GADGET].any()
    got = b.seq(s, ent, grid, h0)[0]
    assert all(torch.equal(x, y) for x, y in zip(lg, got))
    p3 = torch.softmax(lg[1][:, :3], -1)                                                  # = the 3-class head's distribution
    assert torch.allclose(torch.softmax(got[1], -1)[:, :3], p3, atol=1e-6) and torch.softmax(got[1], -1)[:, 3:].max() < 1e-30
    v57 = {k: (v[:1] if k.startswith("fire_x") else v) for k, v in b.state_dict().items()}   # a v5.7 checkpoint: one fire_x row
    with torch.no_grad(): v57["fire_x.bias"] = v57["fire_x.bias"] + 0.25
    c = Policy(); c.load_state_dict(v57)                                                 # the hypercharge row zero-padded
    assert c.fire_x.weight.shape[0] == 2 and c.fire_x.bias[0] == 0.25 and c.fire_x.bias[1] == 0 and not c.fire_x.weight[1].any()
    sh = s.clone(); sh[..., 4] = 1.0; fh = c.seq(sh, ent, grid, h0)[0][1]                # hypercharge ready: allowed, at logit 0
    assert (fh[:, H_] == 0).all() and (fh[:, G_] < -1e8).all()
    s2 = s.clone(); s2[..., 3] = 1.0                                                     # gadget ready: the old heads unchanged,
    g2 = b.seq(s2, ent, grid, h0)[0]; fg = g2[1]                                          # the gadget at logit 0
    assert torch.equal(fg[:, :3], got[1][:, :3]) and (fg[:, G_] == 0).all() and all(torch.equal(x, y) for x, y in zip(g2[::2], got[::2]))
    s3 = s2.clone(); s3[..., 2] = 0.0                                                    # super not ready: only super masked
    f3 = b.seq(s3, ent, grid, h0)[0][1]; assert (f3[:, _SUPER] < -1e8).all() and (f3[:, G_] == 0).all()
    acts = torch.tensor([[1, 0, 10, 5], [1, 1, 10, 5], [1, 2, 10, 5], [1, G_, 10, 5], [1, H_, 10, 5], [1, 1, 10, 5]]).repeat(N * L // 6, 1)
    s2h = s2.clone(); s2h[..., 4] = 1.0
    lgs = [x[:len(acts)] for x in b.seq(s2h, ent, grid, h0)[0]]
    lp, en, _ = dist_logp_ent(lgs, acts)
    ls = [torch.log_softmax(x, -1).gather(-1, acts[:, i:i + 1])[:, 0] for i, x in enumerate(lgs)]
    aims = (acts[:, 1] > 0) & (acts[:, 1] != H_)
    want = ls[0] + ls[1] + aims * ls[2] + (acts[:, 1] == _SUPER) * ls[3]   # gadget: aim yes, distance no; hypercharge: neither
    assert torch.allclose(lp, want, atol=1e-5), (lp, want)
    import models4                                                                       # nirkt's, on the 3-class head
    l3 = [lgs[0], lgs[1][:, :3], lgs[2], lgs[3]]; a3 = acts.clone(); a3[a3[:, 1] >= G_, 1] = 1
    assert all(torch.allclose(x, y) for x, y in zip(dist_logp_ent(l3, a3)[:2], models4.dist_logp_ent(l3, a3)[:2]))
    torch.manual_seed(7); x1 = dist_logp_ent(l3); torch.manual_seed(7); x2 = models4.dist_logp_ent(l3)   # same draws
    assert all(torch.equal(x, y) for x, y in zip(x1, x2))
    assert masked_kl(lgs, lgs).abs().max() < 1e-5 and torch.isfinite(masked_kl(lgs, [x.flip(0) for x in lgs])).all()
    l4 = [lgs[0], torch.cat([lgs[1][:, :3], torch.full_like(lgs[1][:, :2], -1e9)], -1), lgs[2], lgs[3]]   # gadget / hypercharge masked:
    l3n = [x.flip(0) for x in l3]; l4n = [l3n[0], torch.cat([l3n[1], l4[1][:, 3:]], -1), l3n[2], l3n[3]]  # = the 3-class KL
    pf = torch.softmax(l3[1].float(), -1); kl = [(torch.softmax(a_, -1) * (torch.log_softmax(a_, -1) - torch.log_softmax(b_, -1))).sum(-1) for a_, b_ in zip(l3, l3n)]
    assert torch.allclose(masked_kl(l4, l4n), kl[0] + kl[1] + (1 - pf[:, 0]) * kl[2] + pf[:, 2] * kl[3], atol=1e-5)



def _check_aim_lead():
    """aim_lead: off by default and for a checkpoint saved without it (same aim as before); on, the bump of a crossing
    enemy moves to the lead() intercept, ahead of it; the trainer flag sets it on the learner and its anchor only"""
    torch.manual_seed(3); net = Policy().eval(); N = 2
    s = torch.zeros(N, O.N_S); s[:, O.N_SELF + 3] = 0.6                 # own projectile speed (cond stats[3])
    ent = torch.zeros(N, O.N_ENT, O.F_ENT); ent[:, 0, 0] = 1; ent[:, 0, 1 + O.ENT.index("enemy")] = 1
    ent[:, 0, O.XY] = 0.6; ent[:, 0, O.VEL + 1] = 0.15                  # 6 tiles right, crossing up at 0.15 tiles / tick
    grid = torch.zeros(N, O.G, O.G, dtype=torch.uint8); h = torch.zeros(N, HID)
    assert float(net.aim_lead) == 0
    sd = {k: v for k, v in net.state_dict().items() if k != "aim_lead"}  # a checkpoint from before the buffer
    old = Policy().eval(); old.aim_lead.fill_(1.0); old.load_state_dict(sd); assert float(old.aim_lead) == 0
    with torch.no_grad():
        a0 = net(s, ent, grid, h)[0][2]; assert torch.equal(a0, old(s, ent, grid, h)[0][2])
        c = torch.cat([ent[:, _CAND], lead(ent[:, _CAND], s)], -1); want = float(lead_deg(c, 1.0)[0, 0])
        assert 10 < want < 60, want                                     # ahead of it = towards +y = positive degrees
        net.aim_lead.fill_(1.0); a1 = net(s, ent, grid, h)[0][2]
    win = lambda a: (a[0, :90].argmax() + 0).item()                     # the bump near the enemy (0 .. 89 deg)
    shift = win(a1) - win(a0) if win(a0) < 45 else None
    assert shift is not None and abs(shift - want) <= 2, (win(a0), win(a1), want)
    import argparse, train_ppo
    a = argparse.Namespace(aim_lead=-1); n2 = Policy(); n2.aim_lead.fill_(1.0); train_ppo.set_aim_lead(a, n2); assert float(n2.aim_lead) == 1
    a.aim_lead = 0; train_ppo.set_aim_lead(a, n2, None); assert float(n2.aim_lead) == 0


if __name__ == "__main__":
    _check()
