"""Rule planner (behaviour design 4.5, intents_v2 2): one intent per agent and second from what the policy sees, with a
readable reason; "none" (free play) when no rule fits. Numpy only, deterministic (no RNG), no host.

    python -m planner        # self-check (synthetic observations, no game)

    pl = RulePlanner()
    pk = pl.decide(self8, ent, grid, cond, sub)   # one agent's observation rows -> pick {rule, kind, dx, dy, slot, obj, reason}
    c = pl.plan(env, s, p, b, w, o, cond)         # env_v5.Env hook: the pick with a world target (intent.new candidate +
                                                  # rule / reason); kind "none" = free play (also when a target is not matched)
    preempts(old_rule, old_xy, new_rule, new_xy)  # may a planner tick replace a held planner intent (hysteresis)?
    path(walk, a, b)                              # 8-neighbour A* tile path (overlay.path's rules); steps(pas, a): BFS steps

Input = exactly the policy's rows of one agent: self8 (obs_v5 "self"), ent (N_ENT, F_ENT), grid (25 x 25 seg classes, my
tile at [12, 12]), cond (N_COND: own stats, sliders, team size, HUD) + sub = my position inside my tile (0-1, x / y; the
camera tile offsets obs_v5._cam carry it live too). Offsets dx, dy in tiles (x right, y down). Grid classes count only
where a 4-neighbour has the same class (_solid: one wrong seg tile is not gas / a bush / the map edge).

Strength (intents_v2 2.1): S = hp fraction x (POWER x base hp + 400 c) x (1 + 0.1 c), c = cubes held (each cube: +400
max HP, +10 % damage). The HP fraction the observation carries is hp / max hp with the cubes' HP in max hp (host: the
character's +0x3c8, raised by 400 per cube; live: the HP bar), so fraction x (POWER base + 400 c) = hit points now.
Mine: base = cond 8 x 10000, c = cond 26 x 10. An enemy: base from its known stats (ent ID0 + 8), else mine; c =
View.ecubes = the row's cube column (obs_v5.CUB) when its count is known (CUB + 1), else my own count as the prior;
decide(ecubes=...) overrides both.
R = S_enemy / S_me. Engage test (rule engage, team focus, fight's third party): within 12 tiles and either a FINISH (it
is below 25 % and in my range: whatever its cubes, no other gate) or R < 0.7, or R < 1.0 in my range with aggressive >=
1.2; and ammo >= 2/3 (self 1); and not "healing": hp < 0.8 with no enemy in my range blocks a new engage.
Reach of an enemy = known: max(range, super range), cap 12 tiles; unknown: my range.
Rules, first match wins (PRI = order; thresholds from the slider weights in cond, so plans follow the play style):
  1  gas           poison within 2 tiles (or under me) -> move_to the nearest reachable walkable tile >= 3 tiles from the
                   poison, on the side away from the poison centroid   "gas 1 tile away: moving E out of it"
  2  rotate        poison within 5 tiles (not 2 teams left: endgame holds there) -> move_to a reachable walkable tile 5-7
                   tiles from the poison, away from its centroid, not within reach + 1 of a stronger enemy (R >= 1)
                                                                       "gas 4 tiles E: rotating W early"
  3  low_hp        hp < 0.35 + 0.1 x (retreat - 1) and an enemy within 1.2 x its reach -> hide in a bush 1-4 tiles away
                   that is farther from it, else away from it          "hp 30 %, enemy 4 tiles N: disengaging S"
  4  super         my super ready, an attack super (cond 9), an enemy in my super range (cond 12) below 50 % (the
                   observation has no super damage: a likely finish) -> super it, the lowest hp first
                                                                       "enemy 4 tiles S at 30 %: super"
  5  thrower_wall  a KNOWN thrower (ent col ID0+6) within its range + 1 with a wall between us (col LOS), me no thrower
                   -> engage it (around the wall) when hp >= 0.6 and (aggressive >= 1.2 or it is < 50 %), else away
                   from it (out of its range)                          "thrower TntDude 6 tiles NE behind a wall: leaving its range SW"
  6  keep_away     kite >= 0.5, a KNOWN short-range enemy (range <= 5.5 tiles, or melee and <= 8) within its range + 2,
                   my range >= 1.5 x its range -> away from it         "Undertaker (melee, range 3) 4 tiles E: keeping my distance W"
  7  outclassed    an enemy with R >= 1.5 within its reach + 2 (not a finish) -> away from it
                                                                       "ShotgunGirl 5 tiles E, 6 cubes vs my 1 (x2.5 my strength): staying away W"
  8  fight         two enemies within 4 tiles of each other, both >= 4 tiles from me, their centre <= 10 tiles, one
                   below 90 % (they are trading) -> third_party >= 1.2, the weaker of the two (lowest strength) < 40 %
                   and passing the ammo gate (or a finish): engage it, else away from their centre
                                                                       "two fighting 6 tiles N, one at 30 %: third-partying"
  9  endgame       teams left = 2 (cond HUD) and poison in view -> hold a reachable walkable tile 3-4 tiles from the
                   poison, the one farthest from the nearest enemy (- 0.5 x my steps to it)
                                                                       "endgame (2 left), enemy 5 tiles E: holding the gas edge 3 tiles W"
  10 regroup       team size > 1 and the nearest mate in view farther than 4 + 2 x (1 - leash) tiles (3-6)
                                                                       "mate 7 tiles E: regrouping"
  11 engage        team size > 1 and my nearest mate within 12 tiles: the enemy nearest to that mate if it passes the
                   engage test (focus fire, a 2v1); else the nearest enemy that passes it (finishes first)
                                                                       "enemy 5 tiles E at 40 %: engaging"
  12 pin           a weaker enemy (R < 0.8) within 2 tiles of the poison and 8 of me -> hold a reachable tile 2 tiles
                   from it on its safe side (away from the poison centroid): it must cross me or stay in the gas
                                                                       "enemy 6 tiles N by the gas at 50 %: cutting it off, holding 4 tiles N"
  13 check_bush    no enemy in view, ammo >= 2/3, bush_control >= 0.8, no bush check in the last CB_EVERY = 8 s ->
                   the nearest bush tile 1.5 tiles .. my range away (shoot into it)
                                                                       "no enemy seen, bush 3 tiles W in range: checking it"
  14 farm          the cube, else (collect >= 0.5, no enemy within 6 tiles of me) the box with the lowest score =
                   distance + 3 x (enemies within 6 tiles of it) - 2 x (it is nearer a seen map edge than I am, while
                   >= 6 teams are left: edges early); skipped: objects within 1.5 tiles of poison (invalid farm targets)
                   and objects whose nearest enemy is nearer to it than I am and stronger (R >= 1)
                                                                       "cube 3 tiles S: picking up"
  15 hide          bush_camp >= 1.2, no enemy in view, not in a bush, a reachable bush 1-5 tiles away -> hide there
                                                                       "no enemy seen, bush 3 tiles W: hiding"
  16 explore       no enemy, no box in view, the map edge (out_of_bounds) in view -> move_to a reachable walkable tile ~6
                   tiles away from it                                  "map edge 5 tiles W: exploring E"
  17 none          free play                                           "no plan fits: free play"
Rules 5 / 6 need the enemy's brawler (ID_KNOWN = 1) and skip unknown enemies; the rest fall back to the unknown readings.
Wall-aware targets: View.steps = BFS steps from my tile over the passable tiles of the grid (walkable, poison and
UNKNOWN pass; a wall / water / map-edge tile blocks only next to another one (4-neighbour, as _solid: seg noise); 8
neighbours without corner cutting, overlay.path's rule). Every move_to / hold / hide tile is picked among the tiles
reachable that way (gas / rotate / endgame by steps, not straight distance); with none reachable the rule falls back to
the straight-line pick. avoid keeps the threat as its target; its reason names the straight-away direction while that
way is open (a walkable tile ~3 tiles off within 5 steps), else that of the reachable tile <= 4 tiles off farthest from it.
Noisy obs (RulePlanner(noisy=True), trainer --noise 1, live): a row counts only when confirmed: velocity != 0 (tracked
for >= 2 decisions; a new detection, e.g. a false one, has velocity 0: obs_v5 noisy path, live alike) or, for players,
its identity known. Clean obs (noisy=False): every row counts (static boxes / cubes have velocity 0 there).
"Away from" = avoid(that point, R 8) when it is closer than R - 1 = 7 tiles (avoid is achieved at R: farther would pay its
bonus for nothing), else move_to a reachable walkable tile ~4 tiles straight away from it.
Hook (plan): the pick's offset + my true position -> the world target; anchored targets snap to the true object as live
re-anchors to the nearest detection (design 4.2): engage / super -> the nearest enemy I see within MATCH tiles, regroup -> the
nearest mate on my screen, farm -> the nearest box / cube of my fair state2 row within 1.5 tiles, hide / check_bush -> the nearest
true bush tile within 1.5 tiles, move_to / hold -> the nearest truly walkable tile within 1.5 tiles (else the tile as
seen). Not matched -> kind "none" with the reason + " (target not matched)".
Preemption (design 4.4, Env.intents at a planner tick while a planner intent is held; random intents are never
preempted): a higher-priority rule replaces it if it is the gas rule or its target is > HYST tiles from the held one;
the same rule re-targets when its target moved > HYST tiles; lower rules and none never replace it.

Fine-tuning a checkpoint on these intents (intents_v2 2.6 / 3.3 step 2; the 4-core settings of notes/cloud_runs.md,
CK = the checkpoint, e.g. the best r51 one; OMP_NUM_THREADS=2 as there; --bc-updates as in r51: the resumed count skips BC):
    python -m train_fast --run ft_plan --resume CK --hours 6 --n 4 --rollout 8192 --chunks 128 --bc-updates 20 \\
      --eval-min 120 --eval-episodes 8 --evalb-episodes 8 --league-every 10 --overlap-update 0 \\
      --gadgets 0 --hyper 1 --star-powers 1 --gears 1 \\
      --intent-scale 0.25 --p-plan 0.5 --p-rand-intent 0.3 --vlive 1 --eval-plan 1
    python scorecard.py ft_plan     # evalp_plan vs eval (same seeds): rank, follow rate per kind, rule census
"""
import heapq, sys
import numpy as np
import obs_v5 as O, intent as I

RULES = ("gas", "rotate", "low_hp", "super", "thrower_wall", "keep_away", "outclassed", "fight", "endgame", "regroup", "engage",
         "pin", "check_bush", "farm", "hide", "explore", "none")
PRI = {r: k for k, r in enumerate(RULES)}
TILE = 300.0
HYST = 2.0                # tiles: preemption / re-target only for a target change larger than this (design 4.4)
MATCH = 2.0               # tiles: a seen player matches the true one this close (1 tile of detector jitter + 2 decisions
                          # of latency at ~0.5 tile each)
SNAP = 1.5                # tiles: boxes / cubes / bushes / walkable tiles re-anchor this close (design 4.2: 1.5 tiles)
AVOID_MAX = I.SPEC["avoid"]["r"] - 1   # 7 tiles: avoid only what is closer (intent.candidates' rule too)
POWER = 2.0               # sim players are power 11: max HP = 2 x characters.csv Hitpoints (+ the cubes; live_check 10)
CUBE_HP, CUBE_DMG = 400.0, 0.1   # per cube held: +400 max HP, +10 % damage (items.csv BattleRoyaleBuff Value2 / Value)
WEAK, AGG_R, OUT_R, PIN_R = 0.7, 1.0, 1.5, 0.8   # strength ratios (intents_v2 2.1 / 2.4): engage below WEAK (AGG_R when
                          # aggressive and in range), outclassed from OUT_R, pin below PIN_R
FINISH = 0.25             # an enemy below 25 % in my range is engaged whatever its cubes (it drops c / 3 + 1 of them and
                          # dies before its damage bonus matters)
AMMO_MIN = 2.0 / 3 - 1e-3  # engage with >= 2 of 3 ammo bars (self 1); float32 slack
HEAL_HP = 0.8             # below this, with no enemy in my range, no new engage (reset and heal first)
SUPER_HP = 0.5            # super on an enemy in my super range below this (no super damage in the obs: a likely finish)
CB_EVERY = 8.0            # s: at most one bush check this often (a check_bush intent lasts <= 2 s; the rest of the time
                          # farm / hide / explore run)
_C = 12                   # my grid cell (row and column)
_S = O.SEG.index
_WALK = np.isin(np.arange(len(O.SEG) + 1), [_S(c) for c in ("floor", "bush", "slow_tile", "fast_tile", "ice")])   # = env_v5._WALK
_PASS = _WALK | np.isin(np.arange(len(O.SEG) + 1), [_S("poison"), O.UNKNOWN])   # walk through gas / unseen tiles, not wall / water
_T0 = int(O.COND_SLIDERS[9]) + 1          # cond: team size one-hot (3) after the first 10 sliders, then cubes, left
_CUBES, _LEFT = _T0 + 3, _T0 + 4
_SL = {k: int(i) for k, i in zip(O.SLIDERS, O.COND_SLIDERS)}
_E = {k: 1 + O.ENT.index(k) for k in ("enemy", "teammate", "power_box", "power_cube")}   # class one-hot columns
_D8 = [(dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dx or dy]


def dir8(dx, dy):
    """compass word of an offset (x right, y down: N = up on the screen)"""
    a = np.degrees(np.arctan2(-dy, dx)) % 360.0
    return ("E", "NE", "N", "NW", "W", "SW", "S", "SE")[int((a + 22.5) // 45) % 8]


def tiles(d):
    d = max(int(round(float(d))), 1)
    return "%d tile%s" % (d, "" if d == 1 else "s")


def _solid(m):
    """m and at least one 4-neighbour also m (a single wrong seg tile does not count)"""
    p = np.pad(m, 1)
    return m & (p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:])


def strength(hpf, base, cubes):
    """effective HP x damage factor (module doc): hp fraction x (POWER base + 400 c) x (1 + 0.1 c)"""
    return hpf * (POWER * base + CUBE_HP * cubes) * (1.0 + CUBE_DMG * cubes)


def steps(pas, a):
    """(H, W) BFS steps from tile a = (x, y) over pas (H, W) bool, 8 neighbours, a diagonal only when both side tiles
    pass (no corner cutting; overlay.path's moves at cost 1 each); inf where unreachable. a itself always counts"""
    H, W = pas.shape; pas = pas.copy(); pas[a[1], a[0]] = True
    pp = np.pad(pas, 1); sh = lambda m, dx, dy: m[1 - dy:1 - dy + H, 1 - dx:1 - dx + W]   # out[y, x] = m[y - dy, x - dx]
    mv = [(dx, dy, pas & sh(pp, 0, dy) & sh(pp, dx, 0) if dx and dy else pas) for dx, dy in _D8]
    d = np.full((H, W), np.inf); seen = np.zeros((H, W), bool); seen[a[1], a[0]] = True; d[a[1], a[0]] = 0
    front, k = seen.copy(), 0
    fp = np.zeros((H + 2, W + 2), bool)
    while front.any():
        k += 1; fp[1:-1, 1:-1] = front; nxt = np.zeros((H, W), bool)
        for dx, dy, m in mv: nxt |= sh(fp, dx, dy) & m
        nxt &= ~seen; seen |= nxt; d[nxt] = k; front = nxt
    return d


def path(walk, a, b):
    """8-neighbour A* on walk (H, W) bool from tile a = (tx, ty) to b; diagonals only when both side tiles are walkable;
    [] when b cannot be reached (the same search as overlay.path, so a drawn path and a planner target agree)"""
    Hh, Ww = walk.shape; a = (int(a[0]), int(a[1])); b = (int(b[0]), int(b[1]))
    ok = lambda t: 0 <= t[0] < Ww and 0 <= t[1] < Hh and bool(walk[t[1], t[0]])
    if not ok(b): return []
    hfn = lambda t: max(abs(t[0] - b[0]), abs(t[1] - b[1])) + 0.414 * min(abs(t[0] - b[0]), abs(t[1] - b[1]))
    g = {a: 0.0}; prev = {}; q = [(hfn(a), a)]          # the start tile may be unwalkable (a bush edge, the gas): searched from
    while q:
        _, t = heapq.heappop(q)
        if t == b:
            out = [t]
            while t in prev: t = prev[t]; out.append(t)
            return out[::-1]
        for ddx, ddy in _D8:
            n = (t[0] + ddx, t[1] + ddy)
            if not ok(n): continue
            if ddx and ddy and not (ok((t[0] + ddx, t[1])) and ok((t[0], t[1] + ddy))): continue
            c = g[t] + (1.414 if ddx and ddy else 1.0)
            if c < g.get(n, np.inf):
                g[n] = c; prev[n] = t; heapq.heappush(q, (c + hfn(n), n))
    return []


def _name(row):
    """the brawler whose stats a known row carries (obs_v5.id_lut name; live: the countdown name)"""
    names, lut = O.id_lut(); d = ((lut[:-1] - row[O.ID0:O.ID0 + 13].astype(np.float32)) ** 2).sum(1)
    return names[int(d.argmin())]


class View:
    """one agent's observation rows, read for the rules. ecubes (N_ENT,) = cubes held per row (None = the prior)"""

    def __init__(self, self8, ent, grid, cond, sub=(0.5, 0.5), noisy=True, ecubes=None, since_cb=None):
        self.hp, self.ammo, self.inbush = float(self8[0]), float(self8[1]), bool(self8[5] > 0.5)
        self.sup = bool(self8[2] > 0.5)
        c = np.asarray(cond, np.float64); self.c = c
        self.srng, self.satk = c[12] * 10.0, bool(c[9] > 0.5)   # own super range (tiles), the super is an attack
        self.w = {k: float(c[i]) for k, i in _SL.items()}
        self.rng = max(c[0] * 10.0, 2.0)          # own range in tiles (floor 2 = env_v5's 600 units)
        self.thrower, self.maxhp = bool(c[6] > 0.5), c[8] * 10000.0
        self.team = int(np.argmax(c[_T0:_T0 + 3])) + 1; self.left = c[_LEFT] * 10.0; self.cubes = c[_CUBES] * 10.0
        e = np.asarray(ent, np.float64); on = e[:, 0] > 0.5; cls = 1 + np.argmax(e[:, 1:1 + len(O.ENT)], 1)
        rows = lambda k: np.flatnonzero(on & (cls == _E[k]))
        self.e = e
        # noisy obs: a row counts once confirmed: tracked (velocity != 0: matched to the last decision's detection; a new
        # one, e.g. a false detection, has velocity 0) or, players, identity known. Clean obs (noisy False): every row
        trk = (e[:, O.VEL] != 0) | (e[:, O.VEL + 1] != 0)
        ok = np.ones(len(e), bool) if not noisy else trk | (e[:, O.ID_KNOWN] > 0.5)
        okb = np.ones(len(e), bool) if not noisy else trk
        sel = lambda k, m: rows(k)[m[rows(k)]]
        self.foes, self.mates, self.boxes, self.cubes_at = sel("enemy", ok), sel("teammate", ok), sel("power_box", okb), sel("power_cube", okb)
        self.xy = e[:, O.XY:O.XY + 2] * 10.0; self.d = np.hypot(self.xy[:, 0], self.xy[:, 1])
        self.ehp, self.known = e[:, O.HP], e[:, O.ID_KNOWN] > 0.5
        self.erng, self.esup = e[:, O.ID0] * 10.0, e[:, O.ID0 + 12] * 10.0
        self.thrown, self.melee, self.emax = e[:, O.ID0 + 6] > 0.5, e[:, O.ID0 + 7] > 0.5, e[:, O.ID0 + 8] * 10000.0
        self.wall = e[:, O.LOS] > 0.5
        self.reach = np.where(self.known, np.minimum(np.maximum(self.erng, self.esup), 12.0), self.rng)   # known: range / super
        # strength (module doc); enemy cubes: the row's count when read (OBS v5.10), else the prior = my own count
        self.ecubes = (np.where(e[:, O.CUB + 1] > 0.5, e[:, O.CUB] * 10.0, self.cubes) if ecubes is None
                       else np.asarray(ecubes, np.float64))
        self.smine = strength(self.hp, self.maxhp, self.cubes)
        self.S = strength(self.ehp, np.where(self.known, self.emax, self.maxhp), self.ecubes)
        self.R = self.S / max(self.smine, 1.0)
        g = np.asarray(grid); self.g = g
        jj, ii = np.mgrid[0:O.G, 0:O.G]
        self.ox, self.oy = ii - _C + 0.5 - float(sub[0]), jj - _C + 0.5 - float(sub[1])   # tile centre - me, tiles
        self.td = np.hypot(self.ox, self.oy)
        self.walk = _WALK[g] & (g != _S("poison"))
        self.poison, self.bush, self.edge = _solid(g == _S("poison")), _solid(g == _S("bush")), _solid(g == _S("out_of_bounds"))
        self._steps = None
        self.since_cb = np.inf if since_cb is None else float(since_cb)   # s since my last bush check

    @property
    def steps(self):
        """(G, G) BFS steps from my tile (module doc: wall-aware targets), computed on first use"""
        if self._steps is None: self._steps = steps(~_solid(~_PASS[self.g]), (_C, _C))
        return self._steps

    def name(self, k):
        """an enemy row as text: its brawler when known"""
        return _name(self.e[k]) if self.known[k] else "enemy"

    def dist_to(self, mask):
        """(G, G) tiles from every tile centre to the nearest tile of mask (inf without one)"""
        if not mask.any(): return np.full(self.g.shape, np.inf)
        p = np.pad(mask, 1, constant_values=True)        # the nearest tile of mask from outside it is on its rim
        rim = mask & ~(p[:-2, :-2] & p[:-2, 1:-1] & p[:-2, 2:] & p[1:-1, :-2] & p[1:-1, 2:] & p[2:, :-2] & p[2:, 1:-1] & p[2:, 2:])
        px, py = self.ox[rim], self.oy[rim]
        return np.where(mask, 0.0, np.hypot(self.ox[..., None] - px, self.oy[..., None] - py).min(-1))

    def tile_pick(self, ok, key):
        """(dx, dy) of the tile with the smallest key among ok, or None"""
        if not ok.any(): return None
        k = np.where(ok, key, np.inf); j = np.unravel_index(int(np.argmin(k)), k.shape)
        return float(self.ox[j]), float(self.oy[j])

    def reach_pick(self, ok, key=None):
        """tile_pick among the reachable tiles of ok by key (None: steps, ties to the nearer tile); with none of ok
        reachable, among all of ok (None: straight distance), the straight-line pick"""
        st = self.steps; r = ok & np.isfinite(st)
        if r.any(): return self.tile_pick(r, st + 0.01 * self.td if key is None else key)   # 0.01 x td < 1 step
        return self.tile_pick(ok, self.td if key is None else key)

    def finish(self, k):
        return self.ehp[k] < FINISH and self.d[k] <= self.rng

    def engage_ok(self, k, aggressive):
        """the engage test (module doc) of enemy row k -> None | "finish" | "weak" | "aggressive" """
        if self.d[k] > 12.0: return None                 # intent.candidates' engage reach
        if self.finish(k): return "finish"
        if self.ammo < AMMO_MIN: return None
        if self.hp < HEAL_HP and not any(self.d[j] <= self.rng for j in self.foes): return None   # healing: no new fight
        if self.R[k] < WEAK: return "weak"
        if self.R[k] < AGG_R and self.d[k] <= self.rng and aggressive: return "aggressive"
        return None


def pick(rule, kind, dx=0.0, dy=0.0, slot=-1, obj=None, reason=""):
    return {"rule": rule, "kind": kind, "dx": float(dx), "dy": float(dy), "slot": int(slot), "obj": obj, "reason": reason}


class RulePlanner:
    """decide(): the rules on one agent's observation rows; plan(): the env_v5.Env hook (world target, anchors).
    noisy = the observation has detector noise (trainer --noise 1, live): rows count once confirmed (module doc)"""

    def __init__(self, noisy=True):
        self.noisy = bool(noisy)

    def decide(self, self8, ent, grid, cond, sub=(0.5, 0.5), ecubes=None, since_cb=None):
        """since_cb = seconds since this agent's last check_bush intent started (None = never; Env: s.it[p]["cb_n"])"""
        v = View(self8, ent, grid, cond, sub, self.noisy, ecubes, since_cb)
        for r in RULES[:-1]:
            out = getattr(self, "_" + r)(v)
            if out is not None: return out
        return pick("none", "none", reason="no plan fits: free play")

    # ---------------------------------------------------------------- helpers
    def _away(self, v, rule, x, y, why):
        """leave the point (x, y): avoid it (R 8) when closer than AVOID_MAX (the reason names the best reachable escape
        tile's direction), else move_to a reachable walkable tile ~4 tiles away"""
        d = float(np.hypot(x, y)); ux, uy = (-x / d, -y / d) if d > 1e-6 else (1.0, 0.0)
        if d < AVOID_MAX:                                # escape direction: straight away while that way is open
            st = v.steps; open_ = v.walk & (np.hypot(v.ox - 3 * ux, v.oy - 3 * uy) <= 1.0) & (st <= 5)
            ex, ey = ux, uy
            if not open_.any():                          # walled: the reachable tile <= 4 tiles off, farthest from it
                de = np.hypot(v.ox - x, v.oy - y)
                esc = v.tile_pick(v.walk & (st <= 6) & (v.td >= 1.0) & (v.td <= 4.0) & (de > d), -de + 0.01 * st)
                if esc is not None: ex, ey = esc
            return pick(rule, "avoid", x, y, reason="%s %s" % (why, dir8(ex, ey)))
        tx, ty = 4 * ux, 4 * uy; near = np.hypot(v.ox - tx, v.oy - ty)
        t = v.reach_pick(v.walk & (near <= 2.0), near)
        tx, ty = t if t is not None else (tx, ty)
        return pick(rule, "move_to", tx, ty, reason="%s %s" % (why, dir8(tx, ty)))

    def _who(self, v, k):
        ex, ey = v.xy[k]; return "%s %s %s" % (v.name(k), tiles(v.d[k]), dir8(ex, ey))

    def _cubes_vs(self, v, k):
        """", 6 cubes vs my 1" when either side holds cubes (with the prior both are mine), else "" """
        ec, mc = int(round(v.ecubes[k])), int(round(v.cubes))
        return ", %d cubes vs my %d" % (ec, mc) if ec or mc else ""

    def _from_gas(self, v, lo, hi, avoid=()):
        """a reachable walkable tile lo..hi tiles from the poison on the side away from its centroid (steps key);
        avoid = [(x, y, r)] discs left out unless nothing else is left"""
        pd = v.dist_to(v.poison); cx, cy = v.ox[v.poison].mean(), v.oy[v.poison].mean()
        ok = v.walk & (pd >= lo) & (pd <= hi); away = ok & (v.ox * cx + v.oy * cy < 0)
        safe = np.ones_like(ok)
        for x, y, r in avoid: safe &= np.hypot(v.ox - x, v.oy - y) > r
        for m in (away & safe, ok & safe, away, ok):
            if m.any(): return v.reach_pick(m), (cx, cy)
        return None, (cx, cy)

    # ---------------------------------------------------------------- the rules (RULES order)
    def _gas(self, v):
        if not v.poison.any(): return None
        dme = float(v.td[v.poison].min())
        if dme > 2.0: return None
        t, (cx, cy) = self._from_gas(v, 3.0, np.inf)
        if t is None:                                    # nothing safe in view: straight away from the poison
            n = np.hypot(cx, cy)
            if n < 0.5: return None
            t = (-5 * cx / n, -5 * cy / n)
        where = "in the gas" if v.g[_C, _C] == _S("poison") else "gas %s away" % tiles(max(dme, 1.0))
        return pick("gas", "move_to", *t, reason="%s: moving %s out of it" % (where, dir8(*t)))

    def _rotate(self, v):
        if not v.poison.any() or 1.5 < v.left < 2.5: return None   # 2 teams left: endgame holds the gas edge instead
        dme = float(v.td[v.poison].min())
        if dme > 5.0: return None                        # gas (<= 2) has already fired when it is closer
        strong = [(v.xy[k, 0], v.xy[k, 1], v.reach[k] + 1.0) for k in v.foes if v.R[k] >= 1.0]
        t, (cx, cy) = self._from_gas(v, 5.0, 7.0, strong)   # 5-7 tiles: past rotate's own trigger, a short walk
        if t is None or np.hypot(*t) < 0.75: return None
        return pick("rotate", "move_to", *t, reason="gas %s %s: rotating %s early" % (tiles(dme), dir8(cx, cy), dir8(*t)))

    def _low_hp(self, v):
        thr = float(np.clip(0.35 + 0.1 * (v.w["retreat"] - 1.0), 0.25, 0.45))   # retreat style: earlier / later
        if v.hp >= thr or not len(v.foes): return None
        th = [k for k in v.foes if v.d[k] <= 1.2 * v.reach[k]]
        if not th: return None
        k = min(th, key=lambda j: v.d[j]); ex, ey = v.xy[k]
        who = self._who(v, k) + (" (reach %s)" % tiles(v.reach[k]) if v.known[k] else "")
        why = "hp %d %%, %s" % (round(100 * v.hp), who)
        de = np.hypot(v.ox - ex, v.oy - ey)
        t = v.reach_pick(v.bush & (v.td >= 1.0) & (v.td <= 4.0) & (de >= v.d[k] + 1.0), v.td)
        if t is not None:
            return pick("low_hp", "hide", *t, reason="%s: hiding in a bush %s %s" % (why, tiles(np.hypot(*t)), dir8(*t)))
        return self._away(v, "low_hp", ex, ey, why + ": disengaging")

    def _super(self, v):
        if not (v.sup and v.satk and v.srng > 0): return None
        ks = [k for k in v.foes if v.d[k] <= v.srng and v.ehp[k] < SUPER_HP]
        if not ks: return None
        k = min(ks, key=lambda j: (v.ehp[j], v.d[j]))
        return pick("super", "super", *v.xy[k], slot=k, reason="%s %s %s at %d %%: super" % (
            v.name(k), tiles(v.d[k]), dir8(*v.xy[k]), round(100 * v.ehp[k])))

    def _check_bush(self, v):
        if v.since_cb < CB_EVERY or len(v.foes) or v.ammo < AMMO_MIN or v.w["bush_control"] < 0.8: return None
        t = v.tile_pick(v.bush & (v.td >= 1.5) & (v.td <= v.rng), v.td)
        if t is None: return None
        return pick("check_bush", "check_bush", *t, reason="no enemy seen, bush %s %s in range: checking it" % (tiles(np.hypot(*t)), dir8(*t)))

    def _thrower_wall(self, v):
        if v.thrower: return None                        # a thrower answers over the wall itself
        th = [k for k in v.foes if v.known[k] and v.thrown[k] and v.wall[k] and v.d[k] <= v.erng[k] + 1.0]
        if not th: return None
        k = min(th, key=lambda j: v.d[j]); ex, ey = v.xy[k]
        why = "thrower %s behind a wall" % self._who(v, k)
        if v.hp >= 0.6 and (v.w["aggressive"] >= 1.2 or v.ehp[k] < 0.5):
            return pick("thrower_wall", "engage", ex, ey, slot=k, reason=why + ": going around it to engage")
        return self._away(v, "thrower_wall", ex, ey, why + ": leaving its range")

    def _keep_away(self, v):
        if v.w["kite"] < 0.5: return None
        close = lambda k: v.erng[k] <= 5.5 or (v.melee[k] and v.erng[k] <= 8.0)   # Bull 5.3, Mortis 2.7 tiles
        th = [k for k in v.foes if v.known[k] and close(k) and v.d[k] <= v.erng[k] + 2.0 and v.rng >= 1.5 * v.erng[k]]
        if not th: return None
        k = min(th, key=lambda j: v.d[j]); ex, ey = v.xy[k]
        why = "%s (%srange %s) %s %s" % (v.name(k), "melee, " if v.melee[k] else "", int(round(v.erng[k])), tiles(v.d[k]), dir8(ex, ey))
        return self._away(v, "keep_away", ex, ey, why + ": keeping my distance")

    def _outclassed(self, v):
        th = [k for k in v.foes if v.R[k] >= OUT_R and v.d[k] <= v.reach[k] + 2.0 and not v.finish(k)]
        if not th: return None
        k = min(th, key=lambda j: v.d[j]); ex, ey = v.xy[k]
        why = self._who(v, k) + (self._cubes_vs(v, k) or ", %d %% vs my %d %%" % (round(100 * v.ehp[k]), round(100 * v.hp)))
        return self._away(v, "outclassed", ex, ey, why + " (x%.1f my strength): staying away" % v.R[k])

    def _fight(self, v):
        f = [k for k in v.foes if v.d[k] >= 4.0]
        best = None
        for a in range(len(f)):
            for b in range(a + 1, len(f)):
                i, j = f[a], f[b]
                if np.hypot(*(v.xy[i] - v.xy[j])) <= 4.0 and min(v.ehp[i], v.ehp[j]) < 0.9:
                    c = (v.xy[i] + v.xy[j]) / 2; dc = float(np.hypot(*c))
                    if dc <= 10.0 and (best is None or dc < best[0]): best = (dc, i, j, c)   # farther: not my business
        if best is None: return None
        dc, i, j, c = best; lo = i if v.S[i] <= v.S[j] else j   # the weaker fighter by strength (cubes count)
        gate = v.finish(lo) or (v.ammo >= AMMO_MIN and v.R[lo] < OUT_R)
        if v.w["third_party"] >= 1.2 and v.ehp[lo] < 0.4 and gate:
            return pick("fight", "engage", *v.xy[lo], slot=lo, reason="two fighting %s %s, one at %d %%: third-partying" % (
                tiles(dc), dir8(*c), round(100 * v.ehp[lo])))
        return self._away(v, "fight", c[0], c[1], "2 players fighting %s %s: going" % (tiles(dc), dir8(*c)))

    def _endgame(self, v):
        if not 1.5 < v.left < 2.5 or not v.poison.any(): return None   # 2 teams left (1: nobody to hold against)
        pd = v.dist_to(v.poison)
        ok = v.walk & (pd >= 3.0) & (pd <= 4.0)          # >= 3 tiles inside the poison edge (intents_v2 2.3)
        st = v.steps; near = ok & (st <= 6)              # a spot I reach in the hold's 5 s
        if not near.any(): near, st = ok & (v.td <= 6.0), v.td   # nothing reachable: the straight-line choice
        if not near.any(): return None
        if len(v.foes):
            k = min(v.foes, key=lambda j: v.d[j]); ex, ey = v.xy[k]
            t = v.tile_pick(near, -(np.hypot(v.ox - ex, v.oy - ey) - 0.5 * st))
            why = "endgame (%d left), %s" % (round(v.left), self._who(v, k))
        else:
            t = v.tile_pick(near, st); why = "endgame (%d left)" % round(v.left)
        at = "here" if np.hypot(*t) < 0.75 else "%s %s" % (tiles(np.hypot(*t)), dir8(*t))
        return pick("endgame", "hold", *t, reason="%s: holding the gas edge %s" % (why, at))

    def _regroup(self, v):
        if v.team < 2 or not len(v.mates): return None
        thr = float(np.clip(4.0 + 2.0 * (1.0 - v.w["leash"]), 3.0, 6.0))   # leash style: tighter / looser
        k = min(v.mates, key=lambda j: v.d[j])
        if v.d[k] <= thr: return None
        return pick("regroup", "regroup", *v.xy[k], slot=k, reason="mate %s %s: regrouping" % (tiles(v.d[k]), dir8(*v.xy[k])))

    def _engage(self, v):
        agg = v.w["aggressive"] >= 1.2; how = {k: v.engage_ok(k, agg) for k in v.foes}
        ok = [k for k in v.foes if how[k]]
        if not ok: return None
        k, focus = min(ok, key=lambda j: (how[j] != "finish", v.d[j])), False   # solo: finishes first, then the nearest
        if v.team > 1 and len(v.mates):                  # team focus (intents_v2 2.5): my nearest mate's nearest enemy
            m = min(v.mates, key=lambda j: v.d[j]); dm = lambda j: np.hypot(*(v.xy[j] - v.xy[m]))
            f = min(v.foes, key=dm)
            if v.d[m] <= 12.0 and how[f]: k, focus = f, True
        ex, ey = v.xy[k]
        why = "%s at %d %%" % (self._who(v, k), round(100 * v.ehp[k]))
        if how[k] == "finish": why += self._cubes_vs(v, k) + ", in my range: finishing"
        else:
            if how[k] == "weak" and v.known[k]:
                hpk = v.ehp[k] * (POWER * v.emax[k] + CUBE_HP * v.ecubes[k]); hpm = v.hp * (POWER * v.maxhp + CUBE_HP * v.cubes)
                why += " (%d vs my %d hp%s)" % (round(hpk, -2), round(hpm, -2), self._cubes_vs(v, k))
            elif how[k] == "aggressive": why += ", in my range, aggressive"
            why += " next to my mate: focusing" if focus else ": engaging"
        return pick("engage", "engage", ex, ey, slot=k, reason=why)

    def _pin(self, v):
        if not v.poison.any(): return None
        pd = lambda k: np.hypot(v.ox[v.poison] - v.xy[k, 0], v.oy[v.poison] - v.xy[k, 1]).min()
        th = [k for k in v.foes if v.R[k] < PIN_R and v.d[k] <= 8.0 and pd(k) <= 2.0]
        if not th: return None
        k = min(th, key=lambda j: v.d[j]); ex, ey = v.xy[k]
        cx, cy = v.ox[v.poison].mean(), v.oy[v.poison].mean(); n = float(np.hypot(ex - cx, ey - cy))
        if n < 1e-6: return None
        px, py = ex + 2.0 * (ex - cx) / n, ey + 2.0 * (ey - cy) / n   # its safe side: 2 tiles from it, away from the gas
        near = np.hypot(v.ox - px, v.oy - py)
        t = v.reach_pick(v.walk & (near <= 1.5), near)
        if t is None: return None
        return pick("pin", "hold", *t, reason="%s by the gas at %d %%: cutting it off, holding %s %s" % (
            self._who(v, k), round(100 * v.ehp[k]), tiles(np.hypot(*t)), dir8(*t)))

    def _farm(self, v):
        def fine(k):                                     # not in the gas (an invalid farm target), not a stronger enemy's
            if v.poison.any() and np.hypot(v.ox[v.poison] - v.xy[k, 0], v.oy[v.poison] - v.xy[k, 1]).min() <= 1.5: return False
            de = [np.hypot(*(v.xy[j] - v.xy[k])) for j in v.foes]
            return not de or not (min(de) < v.d[k] and v.R[v.foes[int(np.argmin(de))]] >= 1.0)
        edme = float(v.td[v.edge].min()) if v.edge.any() else None
        def score(k):                                    # distance + 3 per enemy near it - 2 toward the edge (early game)
            s = v.d[k] + 3.0 * sum(np.hypot(*(v.xy[j] - v.xy[k])) <= 6.0 for j in v.foes)
            if edme is not None and v.left >= 5.5 and np.hypot(v.ox[v.edge] - v.xy[k, 0], v.oy[v.edge] - v.xy[k, 1]).min() < edme: s -= 2.0
            return s
        def best(ks):
            k = min(ks, key=lambda j: (score(j), v.d[j])); n = min(ks, key=lambda j: v.d[j])
            return k, "" if k == n or v.d[k] <= v.d[n] else " (safer than the nearest)"
        cubes = [k for k in v.cubes_at if fine(k)]
        if cubes:
            k, tag = best(cubes)
            return pick("farm", "farm", *v.xy[k], slot=k, obj="cube", reason="cube %s %s%s: picking up" % (tiles(v.d[k]), dir8(*v.xy[k]), tag))
        boxes = [k for k in v.boxes if fine(k)]
        if not boxes or v.w["collect"] < 0.5 or any(v.d[k] <= 6.0 for k in v.foes): return None
        k, tag = best(boxes)
        return pick("farm", "farm", *v.xy[k], slot=k, obj="box", reason="box %s %s%s, no enemy near: farming" % (tiles(v.d[k]), dir8(*v.xy[k]), tag))

    def _hide(self, v):
        if v.w["bush_camp"] < 1.2 or len(v.foes) or v.inbush: return None
        t = v.reach_pick(v.bush & (v.td >= 1.0) & (v.td <= 5.0), v.td)
        if t is None: return None
        return pick("hide", "hide", *t, reason="no enemy seen, bush %s %s: hiding" % (tiles(np.hypot(*t)), dir8(*t)))

    def _explore(self, v):
        if len(v.foes) or len(v.boxes) or v.edge.sum() < 3: return None
        cx, cy = v.ox[v.edge].mean(), v.oy[v.edge].mean(); n = float(np.hypot(cx, cy))
        if n < 1e-6: return None
        tx, ty = -6 * cx / n, -6 * cy / n; near = np.hypot(v.ox - tx, v.oy - ty)
        t = v.reach_pick(v.walk & (near <= 2.0), near)
        t = t if t is not None else (tx, ty)
        return pick("explore", "move_to", *t, reason="map edge %s %s: exploring %s" % (tiles(v.td[v.edge].min()), dir8(cx, cy), dir8(*t)))

    # ---------------------------------------------------------------- env_v5.Env hook
    def plan(self, env, s, p, b, w, o, cond):
        """Env._choose / the preemption check: the pick of agent p (row b of this poll's observation o / cond rows) as an
        intent.new candidate {kind, q, pt, obj, rule, reason} on true world positions (w = Env._world); kind "none" = free
        play. o is the frame the policy acts on (noise + latency included)."""
        if o is None or cond is None:
            return dict(kind="none", rule="none", reason="no observation: free play")
        meta = getattr(env, "last_meta", None)
        sub = ((float(meta[b, 0]) % TILE) / TILE, (float(meta[b, 1]) % TILE) / TILE) if meta is not None and b < len(meta) else (0.5, 0.5)
        st = (getattr(s, "it", None) or {}).get(p) or {}
        since = (st["n"] - st["cb_n"]) / max(1, 20 // getattr(env, "ticks", 2)) if "cb_n" in st else None   # decisions -> s
        pk = self.decide(o["self"][b], o["ent"][b], o["grid"][b], cond[b], sub, since_cb=since)
        return self.resolve(env, s, p, b, w, pk)

    def resolve(self, env, s, p, b, w, pk):
        """a pick -> a world-target candidate (module doc: anchors snap to the true object)"""
        c = dict(kind=pk["kind"], q=-1, pt=None, obj=pk["obj"], rule=pk["rule"], reason=pk["reason"])
        if pk["kind"] == "none": return c
        mx, my = float(w["x"][p]), float(w["y"][p]); x, y = mx + pk["dx"] * TILE, my + pk["dy"] * TILE
        miss = lambda: dict(c, kind="none", reason=pk["reason"] + " (target not matched)")
        if pk["kind"] in ("engage", "regroup", "super"):
            oth = w["up"].copy(); oth[p] = False; mate = w["team"] == w["team"][p]
            ok = oth & (mate & w["screen"][p] if pk["kind"] == "regroup" else ~mate & w["sees"][p])
            d = np.where(ok, np.hypot(w["x"] - x, w["y"] - y) / TILE, np.inf)
            if d.min() > MATCH: return miss()
            c["q"] = int(np.argmin(d)); return c
        if pk["kind"] == "farm":
            sc = env._scene(s, p, b, w); xy = np.asarray(sc["boxes" if pk["obj"] == "box" else "cubes"], np.float64).reshape(-1, 2)
            d = np.hypot(xy[:, 0] - x, xy[:, 1] - y) / TILE if len(xy) else np.zeros(0)
            if not len(d) or d.min() > SNAP: return miss()
            c["pt"] = (float(xy[int(np.argmin(d)), 0]), float(xy[int(np.argmin(d)), 1])); return c
        if pk["kind"] == "avoid":
            c["pt"] = (x, y); return c
        bushy = pk["kind"] in ("hide", "check_bush")
        mask = s.sl["bush"] if bushy else s.sl["walk"]   # hide / check_bush: a true bush; move_to / hold: walkable
        H, W = mask.shape; tx, ty = int(np.clip(x // TILE, 0, W - 1)), int(np.clip(y // TILE, 0, H - 1))
        if not mask[ty, tx]:
            n = int(np.ceil(SNAP)); y0, x0 = max(ty - n, 0), max(tx - n, 0)
            jj, ii = np.nonzero(mask[y0:ty + n + 1, x0:tx + n + 1]); jj, ii = jj + y0, ii + x0
            dd = np.hypot(ii - tx, jj - ty)
            if len(dd) and dd.min() <= SNAP: k = int(np.argmin(dd)); tx, ty = int(ii[k]), int(jj[k])
            elif bushy: return miss()
        c["pt"] = ((tx + 0.5) * TILE, (ty + 0.5) * TILE)
        return c


def preempts(old_rule, old_xy, new_rule, new_xy):
    """may a planner pick (new_rule, target new_xy in tiles) replace the held planner intent (old_rule, old_xy)? Random
    intents (old_rule None) and a none pick never; a higher-priority rule if it is gas or moves the target > HYST; the
    same rule if its target moved > HYST (re-target); lower rules never"""
    if old_rule is None or new_rule in (None, "none"): return False
    far = float(np.hypot(new_xy[0] - old_xy[0], new_xy[1] - old_xy[1])) > HYST
    if new_rule == old_rule: return far
    return PRI[new_rule] < PRI[old_rule] and (new_rule == "gas" or far)


# ------------------------------------------------------------------ self-check
def synth(foes=(), mates=(), boxes=(), cubes=(), hp=1.0, inbush=False, me="Sniper", sliders=None, team=1, left=None,
          grid=None, sub=(0.5, 0.5), ammo=1.0, mycubes=0, sup=False):
    """synthetic rows of one agent: foes / mates = [(dx, dy) tiles, hp, brawler name or None (unknown), wall, (new)];
    player rows are tracked (velocity 0.01) unless new = True (velocity 0, a first / false detection); boxes / cubes =
    [(dx, dy)]; grid = (25, 25) seg classes (default all floor); ammo = self 1; mycubes = my cubes held (cond); sup = my
    super is ready (self 2)"""
    self8 = np.zeros(O.N_SELF, np.float32); self8[0], self8[1], self8[2], self8[5] = hp, ammo, float(sup), float(inbush)
    ent = np.zeros((O.N_ENT, O.F_ENT), np.float32); k = 0
    def row(cls, xy, h=1.0, name=None, wall=False, new=False):
        nonlocal k
        ent[k, 0] = 1; ent[k, 1 + O.ENT.index(cls)] = 1; ent[k, O.XY:O.XY + 2] = np.asarray(xy) / 10.0; ent[k, O.HP] = h
        if not new: ent[k, O.VEL] = 0.01                 # tracked (a noisy-obs row seen at the last decision too)
        if name: ent[k, O.ID0:O.ID0 + 13] = O.brawler_stats(name); ent[k, O.ID_KNOWN] = 1
        ent[k, O.LOS] = float(wall); k += 1
    for f in foes: row("enemy", *f)
    for m in mates: row("teammate", *m)
    k = O.N_ENT - 14                                    # boxes / cubes in the later blocks
    for x in boxes: row("power_box", x)
    for x in cubes: row("power_cube", x)
    g = np.full((O.G, O.G), _S("floor"), np.uint8) if grid is None else grid
    w = np.ones(len(O.SLIDERS), np.float32)
    for n, val in (sliders or {}).items(): w[O.SLIDERS.index(n)] = val
    cond = O.cond(me, w, team, mycubes, left)
    return self8, ent, g, cond


def _check():
    P = RulePlanner(); Fl = _S("floor")
    def run(**kw):
        sub, ec, cb = kw.pop("sub", (0.5, 0.5)), kw.pop("ecubes", None), kw.pop("since_cb", 0.0)   # default: a bush just checked
        if ec is not None: ec = np.r_[ec, np.zeros(O.N_ENT - len(ec))]   # cubes of the first rows (the foes), the rest 0
        return P.decide(*synth(**kw), sub=sub, ecubes=ec, since_cb=cb)
    def grid(**cls):                                     # grid(poison=[(r0, r1, c0, c1)], bush=...): class blocks (rows, cols)
        g = np.full((O.G, O.G), Fl, np.uint8)
        for n, blocks in cls.items():
            for r0, r1, c0, c1 in blocks: g[r0:r1, c0:c1] = _S(n)
        return g
    seen = {}
    def want(pk, rule, kind, sub=None, sx=0, sy=0):
        assert pk["rule"] == rule and pk["kind"] == kind, (rule, kind, pk)
        assert sub is None or sub in pk["reason"], (sub, pk["reason"])
        if sx: assert np.sign(pk["dx"]) == sx, (rule, pk)
        if sy: assert np.sign(pk["dy"]) == sy, (rule, pk)
        seen[rule] = pk["reason"]; return pk
    # strength: same brawler, 4 cubes vs 0, both full: (5600 + 1600) x 1.4 / 5600 = 1.8; the cube HP is in max hp
    assert np.isclose(strength(1.0, 2800, 4) / strength(1.0, 2800, 0), 7200 * 1.4 / 5600)
    # path / steps: around a wall, no corner cutting; unreachable = [] / inf; both agree on what is reachable
    walk = np.ones((6, 6), bool); walk[1:5, 2] = False
    p = path(walk, (0, 2), (4, 2))
    assert p[0] == (0, 2) and p[-1] == (4, 2) and all(walk[y, x] for x, y in p), p
    for (x0, y0), (x1, y1) in zip(p, p[1:]):
        assert max(abs(x1 - x0), abs(y1 - y0)) == 1 and (x0 == x1 or y0 == y1 or (walk[y0, x1] and walk[y1, x0])), p
    walk2 = walk.copy(); walk2[:, 2] = False
    assert path(walk2, (0, 2), (4, 2)) == [] and path(walk, (0, 0), (2, 2)) == []
    st, st2 = steps(walk, (0, 2)), steps(walk2, (0, 2))
    assert st[2, 4] == len(p) - 1 and np.isinf(st2[2, 4]) and np.isinf(st[2, 2])
    assert all(np.isfinite(st[y, x]) == bool(path(walk, (0, 2), (x, y))) for y in range(6) for x in range(6))
    diag = np.ones((3, 3), bool); diag[0, 1] = diag[1, 0] = False; assert np.isinf(steps(diag, (0, 0))[1, 1])   # no corner cut
    # 1 gas: a poison band 2 tiles right (cols 14-24) -> west, >= 3 tiles from it; under me: "in the gas"
    gg = grid(poison=[(0, 25, 14, 25)])
    pk = want(run(grid=gg), "gas", "move_to", "gas 2 tiles away: moving W", sx=-1)
    assert min(np.hypot(pk["dx"] - (c - _C), pk["dy"] - (r - _C)) for r in range(25) for c in range(14, 25)) >= 3
    want(run(grid=grid(poison=[(0, 25, 11, 25)])), "gas", "move_to", "in the gas: moving W", sx=-1)
    assert run(grid=grid(poison=[(0, 25, 16, 25)]))["rule"] != "gas"                     # 4 tiles away: no
    g1 = grid(); g1[_C, _C + 1] = _S("poison"); assert run(grid=g1)["rule"] == "none"       # one wrong seg tile is no gas
    # wall-aware: a wall 2 tiles thick right behind me (cols 10-11, rows 6-18): the gas exit goes around it, not through
    gw = grid(poison=[(0, 25, 14, 25)], indestructible=[(6, 19, 10, 12)])
    pk = want(run(grid=gw), "gas", "move_to", "moving")
    tx, ty = _C + int(np.floor(pk["dx"])), _C + int(np.floor(pk["dy"]))
    wk = _WALK[gw] & (gw != _S("poison")); pw = path(_PASS[gw], (_C, _C), (tx, ty))
    assert wk[ty, tx] and pw and len(pw) - 1 <= 8 and abs(pk["dy"]) >= 6, (pk, pw)        # around the wall end, ~7 steps
    assert not (tx <= 9 and 6 <= ty <= 18)                                                 # not the straight pick behind it
    # 2 rotate: poison 4 tiles E -> 5-7 tiles from it, W; not at 2 teams left (endgame); away from a stronger enemy
    gr = grid(poison=[(0, 25, 16, 25)])
    pk = want(run(grid=gr), "rotate", "move_to", "gas 4 tiles E: rotating W early", sx=-1)
    assert 5 <= 16 - (_C + pk["dx"]) <= 7, pk                                           # poison from col 16
    assert run(grid=gr, left=2)["rule"] != "rotate" and run(grid=grid(poison=[(0, 25, 19, 25)]))["rule"] != "rotate"   # 7 tiles: no
    pk = want(run(grid=gr, me="Undertaker", hp=0.6, foes=[((-3, 0), 1.0, None, False)]), "rotate", "move_to")   # R 1.7, reach 2.7
    assert np.hypot(pk["dx"] + 3, pk["dy"]) > 3.7 - 1e-9 and pk["dx"] < 0, pk
    # 3 low hp: unknown enemy 4 tiles N (my range 10): a bush south -> hide; none -> avoid it (S); known reach
    want(run(hp=0.3, foes=[((0, -4), 1.0, None, False)], grid=grid(bush=[(14, 16, 11, 13)])), "low_hp", "hide", "hp 30 %, enemy 4 tiles N: hiding in a bush", sy=1)
    pk = want(run(hp=0.3, foes=[((0, -4), 1.0, None, False)]), "low_hp", "avoid", "disengaging S", sy=-1)   # avoid: target = the enemy
    assert run(hp=0.3, foes=[((0, -11), 1.0, None, False)], me="Undertaker")["rule"] != "low_hp"   # unknown: 1.2 x my range (2.7)
    want(run(hp=0.3, foes=[((0, -9), 1.0, "Gunslinger", False)], me="Undertaker"), "low_hp", "move_to", "Gunslinger 9 tiles N (reach 11 tiles): disengaging S", sy=1)   # known reach, far: walk away
    assert run(hp=0.3, sliders={"retreat": 0}, foes=[((0, -4), 1.0, None, False)])["rule"] != "low_hp"   # retreat 0: threshold 0.25
    gs = grid(indestructible=[(13, 15, 9, 16)])          # a wall right below me: the escape from an enemy N bends E / W
    assert run(hp=0.3, foes=[((0, -4), 1.0, None, False)], grid=gs)["reason"][-1] in "EW", run(hp=0.3, foes=[((0, -4), 1.0, None, False)], grid=gs)
    # 4 thrower behind a wall (known): leave its range / engage at high hp and aggressive; unknown or no wall: skip
    T = ((5, -3), 1.0, "TntDude", True)
    want(run(hp=0.5, foes=[T]), "thrower_wall", "avoid", "thrower TntDude 6 tiles NE behind a wall: leaving its range SW", sx=1)
    want(run(foes=[T], sliders={"aggressive": 1.5}), "thrower_wall", "engage", "going around it to engage")
    assert run(hp=0.5, foes=[((5, -3), 1.0, None, True)])["rule"] != "thrower_wall"        # ID_KNOWN 0: skipped
    assert run(hp=0.5, foes=[((5, -3), 1.0, "TntDude", False)])["rule"] != "thrower_wall"   # no wall
    assert run(hp=0.5, foes=[T], me="Barkeep")["rule"] != "thrower_wall"                   # I am a thrower too
    # 5 keep away from a known close-range enemy (me Piper, range 10)
    want(run(foes=[((4, 0), 1.0, "Undertaker", False)]), "keep_away", "avoid", "Undertaker (melee, range 3) 4 tiles E: keeping my distance W")
    assert run(foes=[((4, 0), 1.0, None, False)])["rule"] != "keep_away"                    # unknown: skipped
    assert run(foes=[((4, 0), 1.0, "Undertaker", False)], sliders={"kite": 0.2})["rule"] != "keep_away"
    assert run(foes=[((4, 0), 1.0, "Undertaker", False)], me="Luchador")["rule"] != "keep_away"   # not outranging it
    # 6 outclassed: Shelly with 6 cubes vs my 1, both full: (7800 + 2400) x 1.6 / ((5600 + 400) x 1.1) = 2.5 -> away
    pk = want(run(foes=[((5, 0), 1.0, "ShotgunGirl", False)], mycubes=1, ecubes=[6]), "outclassed", "avoid",
              "ShotgunGirl 5 tiles E, 6 cubes vs my 1 (x2.5 my strength): staying away W")
    assert run(foes=[((5, 0), 1.0, "ShotgunGirl", False)], mycubes=1)["rule"] != "outclassed"   # the prior: same cubes, x1.4
    sv, en, g0, cd = synth(foes=[((5, 0), 1.0, "ShotgunGirl", False)], mycubes=1); en[0, O.CUB:O.CUB + 2] = [0.6, 1]
    assert P.decide(sv, en, g0, cd) == pk                                                    # v5.10: the row's read count
    en[0, O.CUB + 1] = 0; assert P.decide(sv, en, g0, cd)["rule"] != "outclassed"             # not read: the prior
    assert run(foes=[((5, 0), 1.0, None, False)], mycubes=3)["rule"] == "none"             # prior: equal cubes cancel (x1.0)
    want(run(hp=0.6, foes=[((8, 0), 1.0, None, False)]), "outclassed", "move_to", "enemy 8 tiles E, 100 % vs my 60 % (x1.7 my strength): staying away W")
    assert run(hp=0.6, foes=[((13, 0), 1.0, None, False)])["rule"] != "outclassed"         # beyond its reach (my 10) + 2
    # 7 fight: two enemies 3 tiles apart, 6 tiles N, one at 30 %: third party at >= 1.2, else go the other way
    F2 = [((-1.5, -6), 0.3, None, False), ((1.5, -6), 0.8, None, False)]
    want(run(foes=F2, sliders={"third_party": 1.5}), "fight", "engage", "two fighting 6 tiles N, one at 30 %: third-partying")
    assert run(foes=F2, sliders={"third_party": 1.5})["dx"] < 0                             # the low one
    want(run(foes=F2), "fight", "avoid", "2 players fighting 6 tiles N: going S")
    assert run(foes=[((-1.5, -6), 1.0, None, False), ((1.5, -6), 1.0, None, False)])["rule"] != "fight"   # nobody hurt: not a fight
    FS = [((-1.5, -6), 0.35, "BullDude", False), ((1.5, -6), 0.38, "Sniper", False)]       # lowest strength, not lowest %
    assert run(foes=FS, sliders={"third_party": 1.5, "kite": 0})["dx"] > 0                 # kite 0: no keep_away from Bull
    assert run(foes=F2, sliders={"third_party": 1.5}, ammo=1 / 3)["kind"] == "avoid"       # ammo gate on the third party
    # 8 endgame: 2 left, poison 4+ tiles W, an enemy E -> hold 3-4 tiles from the poison
    ge = grid(poison=[(0, 25, 0, 8)])
    pk = want(run(left=2, grid=ge, foes=[((5, 0), 1.0, None, False)], sliders={"aggressive": 0}), "endgame", "hold", "endgame (2 left), enemy 5 tiles E: holding the gas edge")
    assert 3.0 <= _C + pk["dx"] - 7 <= 4.0 + 1e-9, pk
    assert run(left=3, grid=ge)["rule"] != "endgame" and run(left=1, grid=ge)["rule"] != "endgame"
    # 9 regroup: trio, mate 7 tiles E (leash 1: > 4 tiles)
    want(run(team=3, mates=[((7, 0), 1.0, None, False)]), "regroup", "regroup", "mate 7 tiles E: regrouping", sx=1)
    assert run(team=3, mates=[((3, 0), 1.0, None, False)])["rule"] != "regroup" and run(mates=[((7, 0), 1.0, None, False)])["rule"] != "regroup"
    assert run(team=3, mates=[((5, 0), 1.0, None, False)], sliders={"leash": 0})["rule"] != "regroup"   # leash 0: > 6 tiles
    # 10 engage: weaker by strength (unknown: the fraction; known: hit points from the stats) / aggressive in range
    want(run(foes=[((5, 0), 0.4, None, False)]), "engage", "engage", "enemy 5 tiles E at 40 %: engaging", sx=1)
    assert run(foes=[((5, 0), 0.9, None, False)])["rule"] == "none"
    assert run(foes=[((5, 0), 0.4, None, False, True)])["rule"] == "none"                  # a new unknown detection: not yet
    assert run(foes=[((5, 0), 0.4, "Gunslinger", False, True)])["rule"] == "engage"        # known: counts at once
    want(run(foes=[((5, 0), 0.9, "Sniper", False)], hp=1.0, me="BullDude"), "engage", "engage", "(5000 vs my 10000 hp)")   # 90 % of a weaker brawler
    assert run(foes=[((5, 0), 0.5, "BullDude", False)], hp=0.8, me="Sniper")["rule"] != "engage"   # 50 % of a tank: no
    want(run(foes=[((5, 0), 0.9, None, False)], sliders={"aggressive": 1.5}), "engage", "engage", "in my range, aggressive")
    assert run(foes=[((5, 0), 1.0, None, False)], sliders={"aggressive": 1.5})["rule"] == "none"   # an even fight: no
    # finish: Shelly with 10 cubes at 20 % in my range (x0.8, not weak) and me at 1 of 3 ammo: engaged anyway; 30 %: no
    want(run(foes=[((5, 0), 0.2, "ShotgunGirl", False)], ecubes=[10], ammo=1 / 3), "engage", "engage",
         "ShotgunGirl 5 tiles E at 20 %, 10 cubes vs my 0, in my range: finishing")
    assert run(foes=[((5, 0), 0.3, "ShotgunGirl", False)], ecubes=[10])["rule"] != "engage"
    assert run(foes=[((11, 0), 0.2, "ShotgunGirl", False)], ecubes=[10])["rule"] != "engage"   # out of my range: no finish
    # ammo gate: 2 of 3 bars needed
    assert run(foes=[((5, 0), 0.4, None, False)], ammo=0.5)["rule"] == "none" and run(foes=[((5, 0), 0.4, None, False)], ammo=2 / 3)["rule"] == "engage"
    # heal reset: hp 70 %, a weak enemy out of my range: no new engage; in my range: engage; a finish in range: yes
    assert run(hp=0.7, foes=[((11, 0), 0.25, None, False)])["rule"] == "none"
    assert run(hp=0.7, foes=[((8, 0), 0.3, None, False)])["rule"] == "engage"
    assert run(hp=0.7, foes=[((8, 0), 0.2, None, False), ((0, 11), 0.25, None, False)])["reason"].endswith("finishing")
    # team focus: trio, mate 3 tiles E; enemy A 4 tiles W (nearest me), B next to the mate: B (2v1); B too strong: A
    TF = dict(team=3, mates=[((3, 0), 1.0, None, False)])
    want(run(foes=[((-4, 0), 0.4, None, False), ((6, 1), 0.5, None, False)], **TF), "engage", "engage", "next to my mate: focusing", sx=1)
    assert run(foes=[((-4, 0), 0.4, None, False), ((6, 1), 0.9, None, False)], **TF)["dx"] < 0
    # 11 pin: an enemy at 50 % 6 tiles N, 1 tile from the poison (rows 0-5); me at 1 of 3 ammo (no engage): hold 2 tiles S of it
    gp = grid(poison=[(0, 6, 0, 25)])
    pk = want(run(grid=gp, foes=[((0, -6), 0.5, None, False)], ammo=1 / 3), "pin", "hold", "enemy 6 tiles N by the gas at 50 %: cutting it off, holding 4 tiles N")
    assert abs(pk["dx"]) < 1 and -4.5 <= pk["dy"] <= -3.5, pk
    assert run(grid=gp, foes=[((0, -6), 0.5, None, False)])["rule"] == "engage"           # it can be engaged: engage first
    assert run(grid=gp, foes=[((0, -6), 0.75, None, False)])["rule"] == "pin"              # x0.75: not weak enough to engage
    assert run(grid=gp, foes=[((0, -6), 0.85, None, False)])["rule"] != "pin"
    # 12 farm: a cube; a box with no enemy near; collect < 0.5: no box
    want(run(cubes=[(0, 3)], boxes=[(2, 0)]), "farm", "farm", "cube 3 tiles S: picking up", sy=1)
    pk = want(run(boxes=[(-4, 0)]), "farm", "farm", "box 4 tiles W, no enemy near: farming", sx=-1); assert pk["obj"] == "box"
    assert run(boxes=[(-4, 0)], sliders={"collect": 0.3})["rule"] != "farm"
    assert run(cubes=[(0, -5)], grid=grid(poison=[(0, 7, 0, 25)]))["rule"] != "farm"       # a cube 1 tile from poison: skipped
    # weighting: an even enemy (x1.0) 9 tiles E: the cube 4 tiles E next to it scores 7, the one 5 W 5 -> W; a cube it is
    # nearer to and it is not weaker: skipped; the box toward the seen map edge early (10 left): W
    E9 = [((9, 0), 1.0, None, False)]
    pk = want(run(foes=E9, cubes=[(4, 0), (-5, 0)]), "farm", "farm", "cube 5 tiles W (safer than the nearest): picking up", sx=-1)
    assert run(foes=E9, cubes=[(6, 0)])["rule"] == "none" and run(foes=[((9, 0), 0.9, None, False)], cubes=[(6, 0)])["rule"] == "farm"
    gx2 = grid(out_of_bounds=[(0, 25, 0, 4)])
    assert run(grid=gx2, boxes=[(4, 0), (-5, 0)])["dx"] < 0 and run(grid=gx2, boxes=[(4, 0), (-5, 0)], left=5)["dx"] > 0
    assert run(foes=[((-1.5, -11), 0.3, None, False), ((1.5, -11), 0.8, None, False)])["rule"] != "fight"   # 11 tiles: not mine
    s8, e, g, c = synth(cubes=[(0, 3)]); e[:, O.VEL] = 0                                  # new detections (e.g. false ones)
    assert P.decide(s8, e, g, c)["rule"] == "none" and RulePlanner(noisy=False).decide(s8, e, g, c)["rule"] == "farm"   # clean: all count
    # 13 hide: bush camper, no enemy, bush 3 tiles W; not while in a bush; not below 1.2; not a bush walled off
    gb = grid(bush=[(11, 14, 8, 10)])
    want(run(grid=gb, sliders={"bush_camp": 1.5}), "hide", "hide", "no enemy seen, bush 3 tiles W: hiding", sx=-1)
    assert run(grid=gb, sliders={"bush_camp": 1.5}, inbush=True)["rule"] == "none" and run(grid=gb)["rule"] == "none"
    gbw = grid(bush=[(11, 14, 8, 10), (11, 14, 15, 17)], indestructible=[(0, 25, 10, 12)])   # W bush behind a wall: the E one
    assert run(grid=gbw, sliders={"bush_camp": 1.5})["dx"] > 0
    # super: ready, an attack super (Shelly, super range 7.7), an enemy in it below 50 % -> super it (lowest hp first)
    want(run(me="ShotgunGirl", sup=True, foes=[((5, 0), 0.4, None, False), ((0, 4), 0.3, None, False)]), "super", "super",
         "enemy 4 tiles S at 30 %: super", sy=1)
    assert run(me="ShotgunGirl", foes=[((5, 0), 0.4, None, False)])["rule"] != "super"                  # not ready
    assert run(me="ShotgunGirl", sup=True, foes=[((5, 0), 0.6, None, False)])["rule"] != "super"        # not low
    assert run(me="ShotgunGirl", sup=True, foes=[((9, 0), 0.3, None, False)])["rule"] != "super"        # out of super range
    assert run(sup=True, foes=[((5, 0), 0.3, None, False)])["rule"] != "super"                          # Piper: no attack super
    # check_bush: no enemy, a bush in my range, not checked in the last CB_EVERY s -> shoot into it (the nearest tile)
    want(run(grid=gb, since_cb=None), "check_bush", "check_bush", "no enemy seen, bush 3 tiles W in range: checking it", sx=-1)
    assert run(grid=gb, since_cb=CB_EVERY - 1)["rule"] == "none" and run(grid=gb, since_cb=None, ammo=1 / 3)["rule"] == "none"
    assert run(grid=gb, since_cb=None, sliders={"bush_control": 0.5})["rule"] == "none"
    assert run(grid=gb, since_cb=None, foes=[((-9, 0), 1.0, None, False)])["rule"] != "check_bush"
    # 14 explore: the map edge 6 tiles W in view, nothing else -> east
    gx = grid(out_of_bounds=[(0, 25, 0, 7)])
    want(run(grid=gx), "explore", "move_to", "map edge 6 tiles W: exploring E", sx=1)
    assert run(grid=gx, boxes=[(3, 3)])["rule"] == "farm" and run(grid=gx, foes=[((6, 0), 1.0, None, False)])["rule"] == "none"
    # 15 fallback
    want(run(), "none", "none", "no plan fits: free play")
    assert set(seen) == set(RULES), set(RULES) - set(seen)
    # priority order: each state built for rule k also matching a later rule picks k
    rich = dict(team=3, mates=[((7, 0), 1.0, None, False)], cubes=[(0, 3)], sliders={"bush_camp": 1.5})
    order = [("gas", dict(grid=gg, hp=0.3, foes=[((0, -4), 1.0, None, False)])),
             ("rotate", dict(grid=gr, hp=0.3, foes=[((0, -4), 1.0, None, False)])),
             ("low_hp", dict(hp=0.3, me="ShotgunGirl", sup=True, foes=[T, ((0, -4), 0.3, None, False)])),
             ("super", dict(me="ShotgunGirl", sup=True, hp=0.5, foes=[((4, 0), 0.4, "Undertaker", False), ((0, 4), 0.4, None, False)])),
             ("thrower_wall", dict(hp=0.5, foes=[T, ((4, 0), 1.0, "Undertaker", False)])),
             ("keep_away", dict(foes=[((4, 0), 1.0, "Undertaker", False), ((8, 0), 1.0, None, False)] + F2, hp=0.6)),
             ("outclassed", dict(hp=0.6, foes=[((8, 0), 1.0, None, False)] + F2)),
             ("fight", dict(foes=F2, left=2, grid=ge)), ("endgame", dict(left=2, grid=ge, **rich)),
             ("regroup", dict(foes=[((5, 0), 0.4, None, False)], **rich)), ("engage", dict(foes=[((5, 0), 0.4, None, False)], cubes=[(0, 3)], grid=gp)),
             ("pin", dict(grid=gp, foes=[((0, -6), 0.75, None, False)], cubes=[(3, 0)])),
             ("check_bush", dict(cubes=[(0, 3)], grid=gb, sliders={"bush_camp": 1.5}, since_cb=None)),
             ("farm", dict(cubes=[(0, 3)], grid=gb, sliders={"bush_camp": 1.5})), ("hide", dict(grid=np.where(gx == Fl, gb, gx), sliders={"bush_camp": 1.5})),
             ("explore", dict(grid=gx))]
    for rule, kw in order:
        pk = run(**kw); assert pk["rule"] == rule, (rule, pk)
    # the sub-tile position shifts tile offsets (my tile centre = 0.5 - sub)
    pk = run(boxes=[(-4, 0)], sub=(0.9, 0.5)); assert np.isclose(pk["dx"], -4.0)
    pk = run(grid=gb, sliders={"bush_camp": 1.5}, sub=(0.9, 0.5)); assert np.isclose(pk["dx"], -3.4), pk   # entity rows: exact offsets
    # preemption / hysteresis
    assert preempts("farm", (0, 0), "gas", (1, 0)) and not preempts(None, (0, 0), "gas", (5, 0))   # random intents: never
    assert preempts("farm", (0, 0), "low_hp", (5, 0)) and not preempts("farm", (0, 0), "low_hp", (1, 1))   # higher: target > 2 tiles
    assert not preempts("low_hp", (0, 0), "farm", (9, 9)) and not preempts("farm", (0, 0), "none", (9, 9))  # lower / none: never
    assert preempts("engage", (0, 0), "engage", (3, 0)) and not preempts("engage", (0, 0), "engage", (1.5, 1))   # re-target
    assert preempts("farm", (0, 0), "rotate", (5, 0)) and not preempts("rotate", (0, 0), "pin", (5, 0))
    print("planner ok: %d rules fire on their states in priority order, identity rules skip unknown enemies, strength / "
          "ammo / heal gates, wall-aware targets, fallback none, preemption hysteresis %.0f tiles" % (len(RULES), HYST))
    for r in RULES: print("  %-12s %s" % (r, seen[r]))


if __name__ == "__main__":
    sys.exit(_check())
