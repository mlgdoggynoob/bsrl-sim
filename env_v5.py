"""Randomised Showdown battles on top of nirkt's MAEnv (run in WSL after `source rl/env.sh`).

    python3 -m env_v5 --n 12 --minutes 5 --agents 10      # benchmark: random actions, one summary line + bench.jsonl
    python3 -m env_v5 --n 3 --minutes 15 --native 1 --episodes nat.jsonl && python3 -m env_v5 --norm nat.jsonl
                                                          # slider_norm factors from native-AI battles (NORM_MEASURED)

battle_fn(): every battle a random Showdown map, a random playable brawler per player (heroes()), solo / duo (5 x 2) / trio (3 x 3 + 1
solo: the sim has 10 players, the real mode 12) teams, and `agents` policy-controlled slots (the rest = native AI).
The battle is still Solo Showdown underneath (teams only change who can hurt whom), so MAEnv's rank / place reward is
per player; `Env` holds a grouped agent's final transition until its team's rank is known and swaps in the team's
place / win (`team_ranks`). Solo players: unchanged.
Hard scenarios (scenarios.py, cfg "scenario"): Env runs the scripted set-up before MAEnv's trackers start
(_start_battle), sends the scenario's forced storm ring and events every step, ends the battle at its horizon, keeps a
trace and puts the scores / pass into the agent's episode row ("scn").
Aux-head labels (trainer --aux-w, model.Policy.aux), from the sim's true state: `Env.aux_now(ids)` at poll time (AUX
row: true positions, alive enemies, own index, gas margin, hidden enemies in bushes by sector), and the enemy damage
taken per step `te` in every transition's terms.
Intents (intent.py, behaviour design 4; on iff Env.intent_scale > 0 = trainer --intent-scale): `Env.intents(ids, o,
cond)` after the observation build gives the (B, N_INT) block of s (all zeros when off). Per agent and battle: free
(always none) or steered (p_steer); a steered agent's planner tick (every INTENT_EVERY decisions, staggered by player
index, and the decision right after an achieved end) with no active intent takes the rule planner's pick with p_plan
(Env.planner = planner.RulePlanner, trainer --p-plan; its "none" = free play), a random valid intent with p_rand_intent,
else none; at a tick with a held planner intent the planner may preempt it (planner.preempts; random intents never).
Battles tagged "intent": "plan" (evalp_plan) ask the planner at every tick; any other "intent" tag (evals, scenarios:
"none") and native-AI battles (BC) stay none. The world target is kept per agent; reward and ends are computed in
_finish_step on the true positions: reward += intent_scale x intent.step_reward, transition term "i_rew" (the scaled
part; the trainers' rew_int), episode rows "intents" {kind: [started, achieved, timeout, invalid]} (a preempted intent
has no end), "plan_rules" {rule: [picked, started, preempted]} (planner agents), "intent_mode" free | steered and terms
"i_rew". `Env.last_why` = per row of the last intents() call the reason of the active intent ("random" or the planner's)
or of the planner's none (replay frames).
Identity (obs v5.6): every poll sets `Env.last_who` = who(ids, vec), the owner player / brawler / side of each fair
observation row, read from the host's snap2 dump of that response (F_STATE; no host change) and matched to the rows by
position; obs_v5.ObsV5.build(..., who=env.last_who) turns it into the identity columns (with the identity noise).
Gadgets (obs v5.7, issue #3, off by default): make_battle_fn(gadgets=True) / with_gadgets (trainer --gadgets 1) give
every player one of its brawler's gadget cards; Env.gadget(ids) = whether the agent's gadget can be used now, from the
host's gadget state (NbeResp gad_*), for obs_v5's self 3 (ObsV5.build(..., gadget=)). The native AI's gadget use is not
in the BC labels (the controller records have no gadget calls).
Hypercharge (obs v5.8, issue #4, off by default): make_battle_fn(hyper=True) / with_hyper (trainer --hyper 1) equip every
player's hypercharge card (a brawler without one gets none); Env.hyper(ids) = whether the agent can activate it now, from
the host's hypercharge state (NbeResp hyp_*, native/loader/hyper.c), for obs_v5's self 4 (ObsV5.build(..., hyper=)).
Star powers (issue #20, off by default, no observation change): make_battle_fn(star_powers=True) / with_star_powers (trainer
--star-powers 1) give every player one of its brawler's star power cards (div "star", offline.c my_player_ctor), drawn
from the cards the star power probe found read by this build (star_audit.LIVE); a brawler with none gets none. The
policy does not see which card it carries.
"""
import argparse, functools, json, os, sys, time
import numpy as np
from nbpc import diversity as D, proto as P, fair as FAIR
from nbpc.maenv import MAEnv
import obs_v5 as O, intent as I

SKIP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skip.json")   # {"brawlers": [...], "locations": [...]}


def _skip():
    return json.load(open(SKIP_FILE)) if os.path.exists(SKIP_FILE) else {}


def SC():
    import scenarios                                     # lazy: only scenario battles (cfg "scenario") use it
    return scenarios


def _off(r):
    """a csv row's Disabled flag (cards.csv writes both true and TRUE)"""
    return (r.get("Disabled") or "").lower() == "true"


@functools.lru_cache(None)
def _unlocked():
    """brawlers (characters.csv Name) with an enabled unlock card (cards.csv MetaType 0, Type unlock, Target = the brawler)"""
    return frozenset(r["Target"] for r in D._rows("cards.csv")
                     if r[next(iter(r))] and r.get("MetaType") == "0" and r.get("Type") == "unlock" and r.get("Target") and not _off(r))


def heroes():
    """playable brawlers = obs_v5.hero_names rows with an enabled unlock card (106 in this build), table order, minus
    skip.json: the battle pool. The hero_names rows without one are forms()."""
    bad = set(_skip().get("brawlers", []))
    return [n for n in O.hero_names() if n in _unlocked() and n not in bad]


def forms():
    """hero_names rows without an unlock card (9 in this build): other forms a brawler turns into in battle (Meg's mech
    MechaDudeBig, Bonnie's CannonGirlSmall, Moe's DiggerDrill, Kaze's GeishaTransformed) and the SuperNova* event
    transforms. Never picked; they keep their identity rows (a transformed Meg is still a brawler to identify)."""
    return [n for n in O.hero_names() if n not in _unlocked()]


T_CARD = 23   # cards.csv data type (gadget cards are 23xxxxxx; ids count the named rows, as nbpc.diversity.table)


@functools.lru_cache(None)
def gadget_cards():
    """brawler (characters.csv Name) -> cards.csv data ids of its gadget cards (MetaType 5, Target = the brawler). The host
    checks each request (offline.c my_player_ctor) and flags a rejected one in div_err."""
    out, k = {}, 0
    for r in D._rows("cards.csv"):
        if not r[next(iter(r))]: continue
        if r.get("MetaType") == "5" and r.get("Target") and not _off(r):
            out.setdefault(r["Target"], []).append(T_CARD * 1000000 + k)
        k += 1
    return out


def with_gadgets(cfg, rng):
    """battle cfg -> the same cfg, every player (tag "chr") with a random gadget card of its brawler (none if it has none)"""
    gc = gadget_cards(); div = dict(cfg["div"])
    div["gadget"] = [int(rng.choice(gc[b])) if gc.get(b) else 0 for b in cfg["tag"]["chr"]]
    return {**cfg, "div": div}


@functools.lru_cache(None)
def star_cards(live_only=True):
    """brawler (characters.csv Name) -> cards.csv data ids of its star power cards (MetaType 4, Target = the brawler);
    live_only: only the ones star_audit.LIVE lists (the probe saw this build read them)"""
    import star_audit
    out, k = {}, 0
    for r in D._rows("cards.csv"):
        if not r[next(iter(r))]: continue
        if r.get("MetaType") == "4" and r.get("Target") and not _off(r) and (not live_only or r["Name"] in star_audit.LIVE):
            out.setdefault(r["Target"], []).append(T_CARD * 1000000 + k)
        k += 1
    return out


def with_star_powers(cfg, rng, live_only=True):
    """battle cfg -> the same cfg, every player (tag "chr") with a random star power card of its brawler (star_cards; none
    if it has none)"""
    sc = star_cards(live_only); div = dict(cfg["div"])
    div["star"] = [int(rng.choice(sc[b])) if sc.get(b) else 0 for b in cfg["tag"]["chr"]]
    return {**cfg, "div": div}


def with_hyper(cfg):
    """battle cfg -> the same cfg, every player (tag "chr") with its brawler's hypercharge card (the host looks the card up;
    a brawler without one gets none). No random draw."""
    return {**cfg, "div": {**cfg["div"], "hyper": list(range(len(cfg["tag"]["chr"])))}}


@functools.lru_cache(None)
def hyper_brawlers():
    """brawlers (characters.csv Name) with a hypercharge card (cards.csv MetaType 6, Target = the brawler)"""
    return frozenset(r["Target"] for r in D._rows("cards.csv")
                     if r[next(iter(r))] and r.get("MetaType") == "6" and r.get("Target") and not _off(r))


def locations():
    bad = set(_skip().get("locations", []))
    return [n for n, (_, r) in D.table("locations.csv").items()
            if r.get("GameModeVariation") == "Showdown" and r.get("Disabled") != "true" and n not in bad]


WORK = os.path.expanduser(os.environ.get("SIM_WORK", "~/nb68/rl"))   # run outputs + generated maps (env.sh sets it)
GEN_DIR = os.path.join(WORK, "genmaps")   # framegen/genmap.py OUT --seed N: OUT/game = game files with OUT's layout
GEN_BASE = "Survival612"                              # as this location's map (genmap's default base)


def use_genmaps(n_inst, dirs=None):
    """instances 0..n_inst-1 boot from a generated map's game dir (one layout per instance, round robin); call before
    Env(). Returns {instance: dir}. On those instances location GEN_BASE plays the generated layout."""
    from nbpc import instance as NI
    if dirs is None:   # a PayloadTrack tile ('b', from a Payload source map) crashes the boot (rc 139)
        dirs = sorted(os.path.join(GEN_DIR, d, "game") for d in os.listdir(GEN_DIR)) if os.path.isdir(GEN_DIR) else []
        dirs = [d for d in dirs if "b" not in open(os.path.join(os.path.dirname(d), "layout.txt")).read()]
    NI.APK_BY_IDX.clear(); NI.APK_BY_IDX.update({i: dirs[i % len(dirs)] for i in range(n_inst)} if dirs else {})
    return dict(NI.APK_BY_IDX)


def make_battle_fn(agents=10, seed0=10_000_000, roster=None, locs=None, p_team=0.5, gen=None, p_gen=0.5, gadgets=False, hyper=False,
                   star_powers=False):
    """gen = use_genmaps()'s {instance: dir}: there a battle plays the generated layout with probability p_gen;
    gadgets: every player gets a random gadget card of its brawler (none if it has none); hyper: every player gets its
    brawler's hypercharge card (with_hyper); star_powers: every player gets a random live star power card of its brawler
    (with_star_powers)"""
    roster = roster or heroes(); locs = locs or locations(); gen = gen or {}
    seeds = iter(range(seed0, seed0 + 10 ** 9))

    def battle_fn(rng, i):
        br = [roster[int(rng.integers(len(roster)))] for _ in range(10)]
        g = gen.get(i) if i in gen and rng.random() < p_gen else None
        loc = GEN_BASE if g else locs[int(rng.integers(len(locs)))]
        if not g and i in gen and loc == GEN_BASE: loc = locs[(locs.index(loc) + 1) % len(locs)]   # shipped map not on this instance
        div = D.make_div(location=loc, chr=br)
        size = int(rng.integers(2, 4)) if rng.random() < p_team else 1
        groups = [0] * 10                                    # group id per player, 0 = alone (host: nbhost_rl)
        if size > 1:
            for k, p in enumerate(rng.permutation(10)[:10 // size * size]): groups[int(p)] = k // size + 1
            div["team_groups"] = groups
        ctl = sorted(int(p) for p in rng.choice(10, size=agents, replace=False))
        cfg = {"seed": next(seeds), "ctl": ctl, "end": "agents", "div": div,
               "tag": {"loc": os.path.basename(os.path.dirname(g)) if g else loc, "chr": br, "team_size": size, "groups": groups}}
        cfg = with_gadgets(cfg, rng) if gadgets else cfg   # drawn last: the rest of the battle is the same without gadgets
        cfg = with_star_powers(cfg, rng) if star_powers else cfg   # after the gadgets: their draws stay the same
        return with_hyper(cfg) if hyper else cfg            # no draw
    return battle_fn


SL = O.SLIDERS
_COVER = [O.SEG.index(c) for c in ("indestructible", "destructible_wall", "fragile_wall", "bouncer", "gravity", "destructible")]
_WALK = [O.SEG.index(c) for c in ("floor", "bush", "slow_tile", "fast_tile", "ice")]   # where a random move_to / hold point may be
_PL = ("x", "y", "hp", "max_hp", "damage_dealt", "bomb_damage", "damage_taken", "gas_damage", "box_damage", "cubes",
       "cubes_total", "in_gas", "kills")
# behaviour counters per player and battle (row["beh"]; scorecard's per-preset / slider-slope metrics), steps unless noted:
# alive, on a bush tile, hidden by a bush from an enemy whose screen it is on, enemy in range with >= 40 % hp, in gas,
# a living mate, mate 1.5-4 tiles, mate < 1 tile, mate distance (tiles, summed), visible enemy <= 12 tiles, its distance /
# own range (summed), damage dealt / 1000, box damage / 1000, then cubes held: max, at the end; then near the gas (gas_safe)
BEH = ("alive", "bush", "hidden", "engaged", "gas", "mate", "mate_band", "clump", "mate_tiles", "near", "range_ratio",
       "dealt", "box", "cubes_max", "cubes_end", "gas_near")
# per-slider factors on the terms so each is worth ~0.5 per battle at weight 1 (0.5 / mean per-battle sum of |term| per
# player, norm_from; against the 8 of place + win). Measured 2026-11-24 on the native AI (the BC target), on main after
# #34-#38 plus Trio's no respawn shield in the gas: `env_v5 --n 3 --minutes 15 --native 1` = 822 battles / 8199 player
# rows, random maps / brawlers, half in teams, then `--norm`. Re-measure when the terms or the host's rules change, or the
# policy is far from the native AI.
NORM_MEASURED = {"bush_camp": 0.2449, "collect": 0.0747, "protect": 0.3754, "retreat": 0.1932, "kite": 0.1491, "peek": 0.0537,
                 "focus": 0.0455, "aggressive": 0.0346, "third_party": 2.6454, "bush_control": 0.5798, "leash": 2.0781,
                 "gas_safe": 5.3048}


def slider_norm(spec):
    """--slider-norm: '' = all 1.0 (terms as computed), 'measured' = NORM_MEASURED, else a JSON file {slider: factor}"""
    d = {} if not spec else NORM_MEASURED if spec == "measured" else json.load(open(spec))
    return np.array([float(d.get(k, 1.0)) for k in SL])


def sample_sliders(rng, n, mode="uniform"):
    """(n, len(SL)) per-battle slider weights 0-2. uniform: U(0, 2) each (the original sampler, same draws). mix (train
    --slider-sample mix): per player 40 % uniform, 40 % a preset + N(0, 0.3) (density where people steer), 10 % an exact
    preset, 10 % sparse (all 0.5, one or two sliders at 2: single-style coverage)"""
    if mode == "uniform": return rng.uniform(0, 2, (n, len(SL)))
    names = list(O.PRESETS); w = np.zeros((n, len(SL)))
    for p in range(n):
        u = rng.random(); pre = O.preset_vec(names[int(rng.integers(len(names)))])
        if u < 0.4: w[p] = rng.uniform(0, 2, len(SL))
        elif u < 0.8: w[p] = np.clip(pre + rng.normal(0, 0.3, len(SL)), 0, 2)
        elif u < 0.9: w[p] = pre
        else: w[p] = 0.5; w[p, rng.choice(len(SL), int(rng.integers(1, 3)), replace=False)] = 2.0
    return w


def slider_map(sl, tiles, W, H):
    """sl["bush"] / sl["nearcover"] (cover within 2 tiles) / sl["walk"] (intent points) from the host's tile ids (H*W,),
    in place; Env calls it again whenever the live tiles change (a bush or wall destroyed)"""
    t = O._tile_lut()[np.clip(np.asarray(tiles).reshape(H, W) % 1000000 + 1, 0, 255)] if tiles is not None else np.zeros((H, W), np.uint8)
    cover = np.pad(np.isin(t, _COVER), 2)
    near = np.zeros((H, W), bool)
    for dy in range(5):
        for dx in range(5): near |= cover[dy:dy + H, dx:dx + W]
    sl["bush"], sl["nearcover"], sl["walk"] = t == O.SEG.index("bush"), near, np.isin(t, _WALK)
    return sl


def slider_state(tiles, W, H, brawlers, rng, n=10, w=None, mode="uniform"):
    """per-battle state of the slider rewards: weights 0-2 per player and slider (w: (len(SL),) for every player or
    (n, len(SL)); None = sample_sliders(rng, n, mode)), map masks, trackers, behaviour counters"""
    # own attack range (units); floor 600 = 2 tiles, the shortest real melee reach (Rock has no CastingRange)
    rg = [max(float(O.brawler_stats(b)[0]) * 3000, 600.0) if b else 2400.0 for b in (list(brawlers) + [None] * n)[:n]]
    w = sample_sliders(rng, n, mode) if w is None else np.broadcast_to(np.asarray(w, np.float64), (n, len(SL))).copy()
    return slider_map({"w": w, "range": np.array(rg),
                       "hid": np.zeros(n, bool), "low": np.zeros(n, bool), "hp": np.full(n, np.nan),
                       "held": np.zeros(n), "was": np.zeros(n, bool), "mhit": np.zeros(n),
                       "checked": np.zeros((n, H, W), bool), "sum": np.zeros((n, len(SL))), "sumw": np.zeros((n, len(SL))),
                       "asum": np.zeros((n, len(SL))),
                       "ret": np.zeros(n), "beh": np.zeros((n, len(BEH)))}, tiles, W, H)


def gas_margin(x, y, ring, W, H):
    """tiles from the gas edge per position (< 0 = in the gas) and the safe zone's half-size: the host's storm rule
    (env.c in_gas_tile: a tile is gas iff min(tx, ty, W-1-tx, H-1-ty) < ring), ring = the latched storm step
    (NbeResp.reserved[0], 1 tile per step)"""
    tx, ty = np.clip(np.asarray(x) // 300, 0, W - 1), np.clip(np.asarray(y) // 300, 0, H - 1)
    return np.minimum(np.minimum(tx, ty), np.minimum(W - 1 - tx, H - 1 - ty)) - ring, (np.minimum(W, H) - 1) / 2.0 - ring


def fair_vis(x, y, inb, W):
    """the fair visibility of nbpc.fair on true positions (10,): screen[q, p] = p is on q's screen (camera x clamped to
    [3000, W x 300 - 3000], |dx| < 4500, -3500 < dy < 2900), sees[q, p] = and not hidden in a bush (on a bush tile,
    > 900 away); d = distances (units)"""
    d = np.hypot(x[None, :] - x[:, None], y[None, :] - y[:, None])
    camx = np.clip(x, 3000.0, W * 300 - 3000.0); ry = y[None, :] - y[:, None]
    screen = (np.abs(x[None, :] - camx[:, None]) < 4500) & (ry > -3500) & (ry < 2900)
    return screen, screen & ~(inb[None, :] & (d > 900)), d


def slider_terms(sl, pl, n=10, ring=0):
    """(n, len(SLIDERS)) slider reward terms of one env step, order SLIDERS; pl = the response's players. Units as MAEnv's terms
    (1000 damage = 1), before the weights and slider_norm. A respawning player (reserved[3] > 0) counts as out. Enemy
    damage taken `te` = damage_taken - gas_damage (the host's damage_taken includes the gas). The host reports damage per
    player, not per target, so `focus`, `protect`, `third_party` and `bush_control` use "that enemy took damage this step"
    instead of "I hit it". Bushes / cover = sl's map masks, the live tiles (Env refreshes them every MAP_EVERY steps).
      bush_camp     0.002 per step hidden by a bush from an enemy that has me on its screen, + damage dealt the step after
      collect       out of the gas: 0.2 x box damage + cubes picked up; - cubes lost (knock-out / elimination drops them)
      protect       damage dealt while a mate within 6 tiles took enemy damage in the last 10 steps (peel)
      retreat       hp regained while low (latched < 40 % until 80 %); not the respawn refill, not a cube's +hp
      kite          damage dealt taking no enemy damage, the nearest enemy >= 0.7 x own range away
      peek          damage dealt within 2 tiles of cover
      focus         damage dealt while the lowest-hp enemy in range is taking enemy damage
      aggressive    damage dealt + 0.5 per kill + 0.002 per step with an enemy in range while >= 40 % hp
      third_party   damage dealt taking none, an enemy in range taking more than I dealt
      bush_control  0.005 per bush tile first within 3 tiles this battle + damage dealt while an enemy hidden in a bush in
                    my range takes damage (checking bushes from range)
      leash         0.002 per step with the nearest living mate 1.5-4 tiles away, -0.002 under 1 tile (clumping into AoE)
      gas_safe      -0.01 per step in the gas, -0.002 per step within 2 tiles of it while the safe zone is >= 4 tiles
                    across from the centre (the endgame zone is all near the gas); ring = the latched storm step
    Also accumulates sl["beh"] (BEH)."""
    A = np.array([[getattr(pl[p], k) for k in _PL] + [pl[p].reserved[2], pl[p].alive and not pl[p].eliminated and pl[p].reserved[3] <= 0]
                  for p in range(n)], np.float64)
    x, y, hp, mhp, dealt, bomb, taken, gasd, box, cubes, held, ingas, kills, team, alive = A.T
    alive = alive > 0; was = sl["was"]; H, W = sl["bush"].shape; dk = (dealt + bomb) / 1000.0; idx = np.arange(n)
    te = np.maximum(taken - gasd, 0.0); ingas = ingas > 0
    d = np.hypot(x[None, :] - x[:, None], y[None, :] - y[:, None])
    both = alive[:, None] & alive[None, :]
    en = both & (team[:, None] != team[None, :]); mate = both & (team[:, None] == team[None, :]) & (idx[:, None] != idx[None, :])
    tx, ty = np.clip(x // 300, 0, W - 1).astype(int), np.clip(y // 300, 0, H - 1).astype(int)
    inb = sl["bush"][ty, tx]
    # screen[q, p]: p is on q's screen (the camera rule of nbpc.fair); sees[q, p]: and not hidden in a bush (> 900 away)
    camx = np.clip(x, 3000.0, W * 300 - 3000.0); ry = y[None, :] - y[:, None]
    screen = (np.abs(x[None, :] - camx[:, None]) < 4500) & (ry > -3500) & (ry < 2900)
    sees = screen & ~(inb[None, :] & (d > 900))
    hid = inb & alive & ~(en & sees).any(0) & (en & screen).any(0)   # the bush is what hides me from someone
    d_en = np.where(en, d, np.inf); near = d_en.min(1); has = np.isfinite(near)
    inr = en & (d <= sl["range"][:, None])
    low_hp = np.where(inr, (hp / np.maximum(mhp, 1))[None, :], np.inf).argmin(1)
    sl["mhit"] = np.where(alive & (te > 0), 10, np.maximum(sl["mhit"] - 1, 0))   # 10 steps = 1 s of "under fire"
    peel = (mate & (d < 1800) & (sl["mhit"] > 0)[None, :]).any(1)               # 6 tiles: near enough to help
    gain = np.nan_to_num(np.maximum(hp - sl["hp"], 0)) / 1000.0 * (cubes == 0)  # sl["hp"] nan while out / respawning
    low = sl["low"] | (hp < 0.4 * mhp)
    engaged = inr.any(1) & (hp >= 0.4 * mhp)                                    # not while low: no suicide rushes
    dm = np.where(mate, d, np.inf).min(1); hm = np.isfinite(dm) & alive
    gm, zone = gas_margin(x, y, ring, W, H); gnear = alive & (gm >= 0) & (gm < 2) & (zone >= 4)
    others = te[None, :] > (dealt + bomb)[:, None]       # others[p, q]: q took more than p dealt = someone else hit it too
    bushhit = (inr & inb[None, :] & ~sees & (te > 0)[None, :]).any(1)          # sees[p, q]: p sees q
    new = np.zeros(n)
    for p in np.nonzero(alive)[0]:                       # bush tiles within 3 tiles, first time this battle
        ys, xs = slice(max(ty[p] - 3, 0), ty[p] + 4), slice(max(tx[p] - 3, 0), tx[p] + 4)
        fresh = sl["bush"][ys, xs] & ~sl["checked"][p, ys, xs]
        new[p] = fresh.sum(); sl["checked"][p, ys, xs] |= fresh
    held = np.where(alive, held, 0.0); lost = np.minimum(held - sl["held"] - cubes, 0) * was   # an elimination: held -> 0
    T = np.stack([
        0.002 * hid + dk * sl["hid"],                                             # bush_camp
        ~ingas * (0.2 * box / 1000.0 + cubes),                                    # collect (+ lost below)
        dk * peel,                                                                # protect
        gain * low,                                                               # retreat
        dk * (te == 0) * (has & (near >= 0.7 * sl["range"])),                     # kite
        dk * sl["nearcover"][ty, tx],                                             # peek
        dk * inr.any(1) * (te[low_hp] > 0),                                       # focus
        dk + 0.5 * kills + 0.002 * engaged,                                       # aggressive
        dk * (te == 0) * (inr & others).any(1),                                   # third_party
        0.005 * new + dk * bushhit,                                               # bush_control
        0.002 * (hm & (dm >= 450) & (dm <= 1200)) - 0.002 * (hm & (dm < 300)),    # leash: 1.5-4 tiles (Pyla), clump < 1 tile
        -0.01 * ingas - 0.002 * gnear], 1) * alive[:, None]                       # gas_safe
    T[:, 1] += lost
    dv = np.where(en & sees, d, np.inf).min(1); nv = alive & (dv < 3600)      # a visible enemy within 12 tiles
    b = sl["beh"]
    b[:, :13] += np.stack([alive, inb & alive, hid, engaged, ingas & alive, hm, hm & (dm >= 450) & (dm <= 1200),
                           hm & (dm < 300), np.where(hm, dm, 0) / 300.0, nv, np.where(nv, dv, 0) / sl["range"], dk * alive, box / 1000.0], 1)
    b[:, 13] = np.maximum(b[:, 13], held); b[:, 14] = held; b[:, 15] += gnear
    sl["hid"], sl["hp"], sl["low"] = hid, np.where(alive, hp, np.nan), low & (hp < 0.8 * mhp)
    sl["held"], sl["was"] = held, alive
    return T


# Env.aux_now row layout (float32): name -> (offset, shape). tpos = the 10 players' true positions (tiles), talive = an
# alive, not respawning enemy of mine, me = own player index, gm = gas margin (tiles, < 0 in the gas), be = per 45-degree
# sector (0 = right, clockwise as the y-down screen; centred on k x 45 degrees) an enemy hidden from me (fair rule) in a
# bush within 5 tiles (1500 units: the design's "hidden enemy near me", beyond the 900-unit bush reveal)
AUX = {"tpos": (0, (10, 2)), "talive": (20, (10,)), "me": (30, ()), "gm": (31, ()), "be": (32, (8,))}
AUX_W = 40
BUSH_NEAR = 1500.0


def aux_split(A):
    """(B, AUX_W) aux_now rows -> {name: (B, ...) array} (AUX layout)"""
    return {k: A[:, o:o + int(np.prod(sh, dtype=int))].reshape((len(A),) + sh) for k, (o, sh) in AUX.items()}


def gadget_ready(r, p):
    """host response r, player p -> the gadget can be used now (Env.gadget's rule)"""
    pl = r.pl[p]
    return bool(getattr(r, "gad_valid", 0) and r.gad_kind[p] != P.GAD_NONE and r.gad_charges[p] > 0 and r.gad_cd[p] <= 0
                and pl.alive and not pl.eliminated and pl.reserved[3] <= 0)


def hyper_ready(r, p):
    """host response r, player p -> the hypercharge can be activated now (Env.hyper's rule): the host runs hypercharge
    (hyp_valid, native/loader/hyper.c), the player has its card, the charge (reserved[0]) is full (>= reserved[1]), it is
    not active, the brawler is in play"""
    pl = r.pl[p]
    return bool(getattr(r, "hyp_valid", 0) and r.hyp_card[p] and r.hyp_left[p] <= 0 and pl.reserved[1] > 0
                and pl.reserved[0] >= pl.reserved[1] and pl.alive and not pl.eliminated and pl.reserved[3] <= 0)


def player_ranks(r):
    """(10,) rank each player has / would get if its episode ended now (MAEnv._finish_step's rule), (10,) eliminated"""
    done, alive = bool(r.done), int(r.alive or 0); pr = np.zeros(10); dead = np.zeros(10, bool)
    for p in range(10):
        pl = r.pl[p]
        if pl.eliminated or not pl.alive: pr[p] = pl.elim_rank if pl.elim_rank > 0 else 10; dead[p] = True
        elif done: pr[p] = 1 if (r.winner == p or alive <= 1) else max(1, alive)
        else: pr[p] = (1 + alive) / 2.0
    return pr, dead


def team_ranks(groups, pr, dead, over):
    """(10,) placement per player: group 0 = own rank; a group = the best rank among its members (alive members outrank
    eliminated ones), nan while a member lives and the battle goes on.
    shortcut: a battle cut short (end "agents" once every agent is out, max_ticks) ranks a living native mate by MAEnv's
    truncation estimate (1 + alive) / 2; exact only with end "done"."""
    g, out = np.asarray(groups), np.asarray(pr, np.float64).copy()
    for k in set(g[g > 0].tolist()):
        m = g == k; out[m] = out[m].min() if over or dead[m].all() else np.nan
    return out


class Env(MAEnv):
    """MAEnv + a log of every instance restart with the battle that caused it + the slider rewards: every player gets
    weights 0-2 per battle (tag "sliders": fixed, one vector for every player or one per player; else sample_sliders
    with slider_sample); reward += slider_scale x sum(weight x slider_norm x term). The transitions' terms carry the raw
    terms ("s_<slider>"); the episode rows carry the raw sums ("s_<slider>"), the reward they gave ("sn_<slider>"), the
    weights ("sliders"), the sums of |term| ("sa_<slider>", slider_norm's measure) and the behaviour counters ("beh", BEH).
    Intents (module doc): intents(ids, o, cond) -> the block; reward += intent_scale x intent reward (term "i_rew")."""
    crashes = []
    slider_scale = 1.0
    slider_sample = "uniform"     # train --slider-sample
    slider_norm = np.ones(len(SL))   # train --slider-norm (env_v5.slider_norm)
    dead_aids = set()   # agents respawning right now (host: duo / trio knock-out with a living mate, 17 s): dead(ids)
    resp = {"out": 0, "back": 0, "wiped": 0}   # knock-outs into respawn, respawns, waits ended by the team's wipe
    record = False    # True: battles with cfg "native_ctl" put the native AI's action into the transition terms ("_act": BC labels)
    # sim_plan B3 (train_fast --cube-shaping K): the flat per-cube reward becomes potential shaping on the cubes held,
    # K x (gamma x held_after - held_before), held = NbePlayer.cubes_total (the host zeroes it at a team knock-out, as Duo
    # Showdown does) and 0 once eliminated, so losing the cubes gives their reward back.
    cube_k, cube_gamma = 0.0, 0.999
    # the slider rewards' bush / cover masks follow the live tiles: F_MAP every MAP_EVERY steps per instance, masks rebuilt
    # when map_hash changed. 10 steps = 1 s at ticks 2: a destroyed bush keeps paying for <= 1 s. Cost (measured): F_MAP ~45 us
    # of host time per request (us_state 575 vs 530 us), ~4.5 us per step at k = 10; the rebuild (~120 us) only when a tile
    # changed (live_check: ~1.7 refreshes per battle)
    MAP_EVERY = 10
    # intents (module doc; intent.py): off at intent_scale 0 (block all zeros, no reward, no random draws)
    intent_scale = 0.0             # train --intent-scale (start 0.25)
    p_steer, p_rand_intent = 0.7, 0.3   # train --p-steer, --p-rand-intent (design 4.4)
    p_plan, planner = 0.0, None    # train --p-plan: the rule planner's share at a tick; planner.RulePlanner (None = off)
    intent_jitter = O.NOISE["jitter"]   # per-episode sigma range of the target offset noise (10-tile units; trainer --noise 0: none)
    INTENT_EVERY = 10              # decisions between planner ticks (1 s at ticks 2)

    def __init__(self, *a, **kw):
        self._irng = np.random.default_rng([int(kw.get("seed", 0)), 44])   # intents' own stream: the battle draws stay as without
        super().__init__(*a, **kw)

    def _ir(self):
        r = getattr(self, "_irng", None)
        if r is None: r = self._irng = np.random.default_rng([0, 44])
        return r

    def _gather(self):
        out = super()._gather(); self.last_vec = out[0]["vec"]   # the fair state2 rows of this poll (intents: boxes / cubes in view)
        self.last_who = self.who(out[1], out[0]["vec"])           # the rows' owners (obs_v5 identity columns)
        return out

    def _flags(self):
        # F_STATE: the host keeps state_ints of the snap2 dump it encodes the observations from anyway (env.c: no other
        # effect), so who() can read the owners of the rows
        return super()._flags() | P.F_STATE | (P.F_REC if self.record else 0) | (P.F_MAP if getattr(self, "_map_now", False) else 0)

    def who(self, ids, vec):
        """(B, N_ENT, 3) int16 per observation row (obs_v5 `who`): owner player index, its brawler's obs_v5.id_lut row,
        side (obs_v5.WHO_FOE / WHO_MATE / WHO_ME); -1 = none. From the host's snap2 dump of this response (the state the
        encoder wrote the rows from; characters [0] id, [1] data id, [2] owner player, [3, 4] x, y, [6] hp, [18] not a
        brawler class; projectiles [2] owner, [3, 4] x, y; players [0] index, [1] team, [2] character, [3] controlled),
        matched to the fair rows by position: a row's dx, dy are float32((x - my x) / 3000) of exactly one dump row (an
        exact tie of two objects takes the first in dump order). Enemy-block rows that are brawlers (feature 14 = 0) match
        the players' brawlers, projectile rows the projectiles; summons, boxes, items: -1. The brawler = the character's
        data id (the tag's pick if its character is gone, e.g. a projectile of an eliminated player)."""
        B = len(ids); out = np.full((B, O.N_ENT, 3), -1, np.int16)
        if not B: return out
        ids = np.asarray(ids, np.int64); by = {s.battle: s for s in self.I}
        for bat in np.unique(ids >> 4):
            s = by.get(int(bat)); rows = np.flatnonzero((ids >> 4) == bat)
            a = np.asarray(s.inst.state_i32) if s is not None else None
            if a is None or a[0] != 0x4e423253 or not 0 < a[3] <= 16: continue   # no dump (e.g. an older host)
            npl, nch, npj = int(a[3]), int(a[4]), int(a[5]); k0 = 8 + npl * 8
            pl = a[8:k0].reshape(npl, 8); ch = a[k0:k0 + nch * 23].reshape(nch, 23); pj = a[k0 + nch * 23:k0 + nch * 23 + npj * 18].reshape(npj, 18)
            team = np.full(16, -999, np.int64); bid = np.full(16, -1, np.int64); ok = (pl[:, 0] >= 0) & (pl[:, 0] < 16)
            team[pl[ok, 0]] = pl[ok, 1]
            bid[pl[ok, 0]] = np.where((pl[ok, 3] != 0) & (pl[ok, 3] != -2 ** 31), pl[ok, 3], pl[ok, 2])
            own = ch[:, 2]; br = (ch[:, 18] == 0) & (own >= 0) & (own < 16) & (ch[:, 0] == bid[np.clip(own, 0, 15)])
            hero = np.array([O.id_row(c) for c in ((s.cfg.get("tag") or {}).get("chr") or [""] * 10)] + [-1] * 16, np.int64)[:16]
            for c in np.flatnonzero(br):                 # the character on the map names the brawler
                r_ = O.id_row_of_data(ch[c, 1])
                if r_ >= 0: hero[own[c]] = r_
            p = ids[rows] & 15; mi = np.full(len(p), -1, np.int64)
            for j, q in enumerate(p):                    # my brawler's dump row (the encoder's origin)
                f = np.flatnonzero(br & (own == q))
                if len(f): mi[j] = f[0]
            has = mi >= 0; mi = np.maximum(mi, 0)
            mx, my = ch[mi, 3].astype(np.float64), ch[mi, 4].astype(np.float64)
            f32 = lambda c, m: ((c[None].astype(np.float64) - m[:, None]) / FAIR.R).astype(np.float32)   # encode.c's dx, dy
            v = vec[rows]
            for blk, K, Fn, cand, cx, cy, co in ((0, FAIR.EN_K, FAIR.EN_F, br & (ch[:, 6] > 0) & (ch[:, 1] != 16000120), ch[:, 3], ch[:, 4], own),
                                                 (FAIR.EN_K, FAIR.PJ_K, FAIR.PJ_F, (pj[:, 2] >= 0) & (pj[:, 2] < 16), pj[:, 3], pj[:, 4], pj[:, 2])):
                off = FAIR.EN0 if blk == 0 else FAIR.PJ0; e = v[:, off:off + K * Fn].reshape(len(rows), K, Fn)
                if not cand.any(): continue
                dx, dy = f32(cx[cand], mx), f32(cy[cand], my); oc = co[cand].astype(np.int64)
                hit = (e[:, :, 1, None] == dx[:, None]) & (e[:, :, 2, None] == dy[:, None]) & (oc[None, None] != p[:, None, None]) if blk == 0 else \
                      (e[:, :, 1, None] == dx[:, None]) & (e[:, :, 2, None] == dy[:, None])
                hit &= (e[:, :, :1] > 0.5) & has[:, None, None]
                if blk == 0: hit &= e[:, :, 14:15] < 0.5         # summons stay unknown
                got = hit.any(2); q = oc[hit.argmax(2)]
                side = np.where(q == p[:, None], O.WHO_ME, np.where(team[q] == team[p][:, None], O.WHO_MATE, O.WHO_FOE))
                w = np.stack([q, hero[q], side], -1); w[~got] = -1
                out[rows, blk:blk + K] = w
        return out

    def _send_step(self, i, acts):
        s = self.I[i]; s.nstep = getattr(s, "nstep", 0) + 1; self._map_now = s.nstep % self.MAP_EVERY == 0
        try:
            if getattr(s, "scn", None) is not None: SC().send_step(self, i, acts)   # scenario: its events + forced storm ring
            else: super()._send_step(i, acts)
        finally: self._map_now = False

    def _battle_over(self, i, r):
        s = self.I[i]; sc = getattr(s, "scn", None)
        if sc is not None and r.tick - s.start_tick >= sc["horizon"]: return True   # a scenario ends at its horizon
        return super()._battle_over(i, r)

    def _labels(self, s, r):
        """player -> [move, fire, aim, dist] the native AI did this step: the rules of nirkt's collect_demos4 (move = the
        displacement's 16-direction bucket, fire = first unblocked controller record, super wins)"""
        rec = np.frombuffer(s.inst.mm, np.int32, r.rec_n * 8, P.OFF_REC).reshape(-1, 8) if r.rec_n else np.zeros((0, 8), np.int32)
        jump = {int(r.jumps[k][0]) for k in range(r.njumps)}; out = {}
        for p in s.ep:
            pl = r.pl[p]; cid = int(pl.char_id); x0, y0 = s.pos[p]; dx, dy = float(pl.x - x0), float(pl.y - y0); act = [0, 0, 0, 0]
            if cid not in jump and cid not in s.pjump and dx * dx + dy * dy >= (10.0 * self.ticks) ** 2 and pl.alive:
                act[0] = 1 + int(np.round(np.arctan2(dy, dx) / (np.pi / 8))) % 16
            for c in rec[(rec[:, 1] == cid) & (rec[:, 2] == 1)]:
                if c[6] == 1: continue
                f = min(1.0, max(0.0, (float(c[0]) - s.ptick) / max(1.0, float(r.tick - s.ptick))))
                tx, ty = float(c[3] - (x0 + f * dx)), float(c[4] - (y0 + f * dy)); ang = int(round(np.degrees(np.arctan2(ty, tx)))) % 360
                if c[5] == 1 and act[1] != 2: act[1:] = [2, ang, min(7, max(0, int(np.ceil(np.hypot(tx, ty) / 2600.0 * 8)) - 1))]
                elif c[5] == 0 and act[1] == 0: act[1], act[2] = 1, ang
            out[p] = act
        return out

    def _restart(self, i, why):
        self.crashes.append({"why": str(why)[:200], **(self.I[i].cfg or {}).get("tag", {})})
        self._trans += getattr(self.I[i], "hold", {}).values(); self.I[i].hold = {}   # crashed: own placement only
        return super()._restart(i, why)

    def _start_battle(self, i, r):
        s = self.I[i]; scn = (s.cfg or {}).get("scenario")
        if scn:                                          # hard scenario: scripted set-up first, r (= s.inst.resp) is its end state
            from nbpc.instance import InstanceDead
            try: SC().preroll(self, i)
            except InstanceDead as e: s.scn = None; return self._restart(i, "scenario pre-roll: %s" % e)   # the item is lost
        super()._start_battle(i, r)
        s.scn = SC().start(self, s) if scn else None     # its trace (scores at the episode's end)
        if scn and 0 not in s.agents:                    # the agent did not survive the set-up: an invalid row, no battle
            self.episodes.append({"seed": int(s.cfg["seed"]), "player": 0, "rank": None, "win": None, "ticks": 0, "steps": 0, "ret": 0.0,
                                  "terms": {}, "storm_death": 0, "truncated": True, "restart": False, "tag": s.cfg.get("tag"), "ctl": s.ctl,
                                  "invalid": "agent out after the scenario set-up", "scn": None})
        s.hold = {}                                      # player -> its final transition, held until the team's rank is known
        s.it = {}                                        # player -> intent state (Env.intents)
        tag = s.cfg.get("tag") or {}
        s.sl = slider_state(s.map_tiles, s.W, s.H, tag.get("chr", []), self.rng, w=tag.get("sliders"), mode=self.slider_sample)
        s.map_hash = int(r.map_hash)
        s.pos = {p: (r.pl[p].x, r.pl[p].y) for p in range(10)}; s.ptick = r.tick; s.pjump = set(); s.wprev = set()
        s.cprev = {p: int(r.pl[p].cubes_total) for p in range(10)}
        s.hud = self._hud(s, r)

    def _hud(self, s, r):
        """the two Showdown HUD numbers per player: own cubes held (cubes_total: 0 after a team knock-out, as B3), teams
        left (a group with a member not eliminated, or a solo player still in)"""
        g = (s.cfg.get("tag") or {}).get("groups") or [0] * 10; inn = [not r.pl[p].eliminated for p in range(10)]
        left = len({g[p] for p in range(10) if inn[p] and g[p]}) + sum(1 for p in range(10) if inn[p] and not g[p])
        return [int(r.pl[p].cubes_total) for p in range(10)], left

    def dead(self, ids):
        """(B,) bool: the agent is respawning (its observation is all zeros, its actions are ignored by the host)"""
        return np.array([int(x) in self.dead_aids for x in ids], bool)

    def _finish_step(self, i, r):
        s = self.I[i]; sl = s.sl
        if getattr(r, "map_written", 0) and int(r.map_hash) != s.map_hash:   # a tile changed (bush / wall destroyed): live masks
            s.map_tiles = s.inst.map_tiles(); s.map_hash = int(r.map_hash); slider_map(sl, s.map_tiles, s.W, s.H)
        T = slider_terms(sl, r.pl, ring=int(r.reserved[0])) if self.slider_scale else np.zeros(np.shape(sl["w"]))   # speed round: off = no reward, skip it (s_* logs 0)
        Tw = T * sl["w"] * self.slider_norm * self.slider_scale; extra = Tw.sum(1); sl["sum"] += T; sl["sumw"] += Tw; sl["ret"] += extra
        sl["asum"] += np.abs(T)
        n0, e0 = len(self._trans), len(self.episodes)
        lab = self._labels(s, r) if self.record and s.cfg.get("native_ctl") else {}
        if getattr(s, "scn", None) is not None: SC().trace(s.scn, r, lab.get(0) if s.cfg.get("native_ctl") else s.acts.get(0))
        s.pos = {p: (r.pl[p].x, r.pl[p].y) for p in range(10)}; s.ptick = r.tick; s.pjump = {int(r.jumps[k][0]) for k in range(r.njumps)}
        g = np.array((s.cfg.get("tag") or {}).get("groups") or [0] * 10)
        if g.any(): pr, dead = player_ranks(r); b0 = s.battle   # read r before a reset reuses it
        wait = {p for p in range(10) if r.pl[p].reserved[3] > 0}; agents = dict(s.agents); elim = {p for p in range(10) if r.pl[p].eliminated}
        back = s.wprev - wait                            # respawned this step (or wiped out with the team)
        self.resp["out"] += len(wait - s.wprev); self.resp["wiped"] += len(back & elim); self.resp["back"] += len(back - elim)
        for p, aid in agents.items(): (self.dead_aids.add if p in wait else self.dead_aids.discard)(aid)
        s.wprev = wait
        shaped = {}; s.hud = self._hud(s, r)             # cond's HUD numbers for the next poll (a reset sets them anew)
        te = [max(r.pl[p].damage_taken - r.pl[p].gas_damage, 0) / 1000.0 for p in range(10)]   # enemy damage taken (aux hit label)
        irew = self._intent_step(s, r) if self.intent_scale and getattr(s, "it", None) else {}   # from r before a reset
        if self.cube_k:                                  # B3, from r before super() may reset the instance
            for p in list(s.ep):
                pl = r.pl[p]; after = 0 if (pl.eliminated or not pl.alive) and p not in wait else int(pl.cubes_total)
                shaped[p] = self.cube_k * (self.cube_gamma * after - s.cprev.get(p, 0)); s.cprev[p] = after
        super()._finish_step(i, r)                       # may reset the instance: sl stays this battle's
        for k in range(n0, len(self._trans)):
            aid, rew, fin, t, rank = self._trans[k]; p = aid & 15
            if p in back - elim: rew -= self.w.get("hp", 0) * t["hp"]; t = {**t, "hp": 0.0}   # respawn refill is no hp gain
            if p in shaped: rew += shaped[p] - self.w.get("cubes", 0) * t["cubes"]; t = {**t, "cube_shaped": shaped[p]}
            if fin: self.dead_aids.discard(aid)
            ix = {}
            if self.intent_scale:                        # the intent reward (scaled) in rew and as term i_rew
                ix = {"i_rew": self.intent_scale * irew.get(p, 0.0)}; st = s.it.get(p)
                if st is not None: st["sum"] += ix["i_rew"]
            self._trans[k] = (aid, rew + float(extra[p]) + ix.get("i_rew", 0.0), fin, {**t, **{"s_" + m: float(v) for m, v in zip(SL, T[p])},
                              "_act": lab.get(p), "dead": float(p in wait), "te": te[p], **ix}, rank)
        if g.any():                                      # duo / trio: placement = the team's (Solo Showdown underneath)
            for k in range(len(self._trans) - 1, n0 - 1, -1):
                p = self._trans[k][0] & 15
                if self._trans[k][2] and g[p]: s.hold[p] = self._trans.pop(k)
            tr = team_ranks(g, pr, dead, s.battle != b0)
            for p in [p for p in s.hold if not np.isnan(tr[p])]:
                aid, rew, fin, t, rank = s.hold.pop(p); place = (10 - tr[p]) / 9.0; win = float(tr[p] == 1)
                rew += self.w.get("place", 0) * (place - t["place"]) + self.w.get("win", 0) * (win - t["win"])
                self._trans.append((aid, rew, fin, {**t, "team_place": place}, rank))
        for row in self.episodes[e0:]:
            p = row["player"]; row["ret"] += float(sl["ret"][p]); row["sliders"] = [round(float(v), 3) for v in sl["w"][p]]
            row["terms"].update({"s_" + m: round(float(v), 4) for m, v in zip(SL, sl["sum"][p])})
            row["terms"].update({"sn_" + m: round(float(v), 4) for m, v in zip(SL, sl["sumw"][p])})
            row["terms"].update({"sa_" + m: round(float(v), 4) for m, v in zip(SL, sl["asum"][p])})
            row["beh"] = {k: round(float(v), 3) for k, v in zip(BEH, sl["beh"][p])}
            st = getattr(s, "it", {}).get(p) if self.intent_scale else None
            if st is not None:
                row["ret"] += st["sum"]; row["terms"]["i_rew"] = round(st["sum"], 4); row["intent_mode"] = "steered" if st["steer"] else "free"
                row["intents"] = {k: list(v) for k, v in st["cnt"].items() if v[0]}
                if st.get("rules"): row["plan_rules"] = {k: list(v) for k, v in st["rules"].items()}
            if getattr(s, "scn", None) is not None and p == 0 and (row["tag"] or {}).get("scn"):   # the scenario's agent
                row["scn"] = {"name": s.scn["name"], "item": s.scn["item"], "battle": s.scn["battle"], "pre": s.scn["pre"], **SC().score(s.scn)}

    # ------------------------------------------------------------------ intents (intent.py, design 4)
    def intents(self, ids, o=None, cond=None):
        """(B, N_INT) intent blocks of the agents of the last poll() (intent.encode; all zeros when intents are off).
        Runs the planner ticks: a steered agent with no active intent picks one at its tick (decision n with
        (n + player) % INTENT_EVERY == 0, or the decision after an achieved end; not while respawning); at a tick with a
        held planner intent the planner may preempt it (planner.preempts: gas rule / higher rule or same rule with the
        target > 2 tiles away; random intents never). The offset is the target's true world point (an anchored player:
        where it is now) minus the true own position, plus the episode's detector jitter. o / cond = this poll's
        observation / conditioning rows (what the planner reads). Sets last_why: per row the active intent's reason, or
        the planner's reason for none at its last tick (None: no reason; replay frames)."""
        ids = np.asarray(ids, np.int64); B = len(ids)
        if not self.intent_scale or not B: self.last_why = None; return np.zeros((B, O.N_INT), np.float32)
        by = {s.battle: s for s in self.I}; rg = self._ir(); ws = {}; why = [None] * B
        kind, dx, dy, rad, lf = np.zeros(B, np.int64), np.zeros(B), np.zeros(B), np.zeros(B), np.zeros(B)
        for b, a in enumerate(ids):
            s, p = by[int(a) >> 4], int(a) & 15
            if getattr(s, "it", None) is None: s.it = {}
            st = s.it.get(p) or self._intent_agent(s, p)
            tick = (st["n"] + p) % self.INTENT_EVERY == 0 or st["replan"]; st["n"] += 1
            w = ws.get(s.battle)
            if st["act"] is None and tick:
                st["replan"] = False
                if st["steer"] and int(a) not in self.dead_aids:
                    w = ws[s.battle] = w or self._world(s)
                    c = self._choose(s, p, b, w, o, cond)
                    if c is not None: self._intent_start(s, p, st, c, w)
            elif tick and self.planner is not None and st["act"].get("rule") and int(a) not in self.dead_aids:
                w = ws[s.battle] = w or self._world(s); self._preempt(s, p, st, b, w, o, cond)
            it = st["act"]
            if it is None: why[b] = st.get("why"); continue
            why[b] = it["reason"]
            w = ws[s.battle] = w or self._world(s)
            tx, ty = (w["x"][it["q"]], w["y"][it["q"]]) if it["q"] >= 0 else it["pt"]
            nz = rg.normal(0.0, st["jit"], 2) * 10.0 if st["jit"] > 0 else np.zeros(2)   # 10-tile units -> tiles
            kind[b] = I.K[it["kind"]]; dx[b] = (tx - w["x"][p]) / 300.0 + nz[0]; dy[b] = (ty - w["y"][p]) / 300.0 + nz[1]
            rad[b] = it["r"]; lf[b] = I.left(it)
        self.last_why = why
        return I.encode(kind, dx, dy, rad, lf)

    def _intent_agent(self, s, p):
        """per agent and battle: free (always none) or steered (p_steer); tag "intent" "plan" (evalp_plan battles): steered
        with every tick the planner's (needs Env.planner); any other tag "intent" (evals / scenarios: "none") or a
        native-AI battle (BC): free"""
        rg = self._ir(); mode = (s.cfg.get("tag") or {}).get("intent"); fixed = mode is not None or bool(s.cfg.get("native_ctl"))
        plan = mode == "plan" and self.planner is not None and not s.cfg.get("native_ctl")
        st = s.it[p] = {"steer": plan or ((not fixed) and rg.random() < self.p_steer), "n": 0, "act": None, "replan": False,
                        "jit": float(rg.uniform(*self.intent_jitter)), "cnt": {k: [0, 0, 0, 0] for k in I.SPEC}, "sum": 0.0}
        if plan: st["plan_only"] = True
        return st

    def _world(self, s, r=None):
        """true state of a battle for the intents: positions, up (alive, not respawning), team, own tile, bush, fair_vis"""
        r = r if r is not None else s.inst.resp; pl = r.pl; H, W = s.sl["bush"].shape
        x = np.array([pl[q].x for q in range(10)], np.float64); y = np.array([pl[q].y for q in range(10)], np.float64)
        up = np.array([bool(pl[q].alive) and not pl[q].eliminated and pl[q].reserved[3] <= 0 for q in range(10)])
        tx, ty = np.clip(x // 300, 0, W - 1).astype(int), np.clip(y // 300, 0, H - 1).astype(int); inb = s.sl["bush"][ty, tx]
        screen, sees, _ = fair_vis(x, y, inb, W)
        return {"x": x, "y": y, "up": up, "team": np.array([pl[q].reserved[2] for q in range(10)]), "tx": tx, "ty": ty, "inb": inb,
                "screen": screen, "sees": sees, "W": W, "H": H, "ring": int(r.reserved[0])}

    def _scene(self, s, p, b, w):
        """intent.candidates' scene of agent p (row b of the last poll): the enemies it sees and the mates on its screen
        (true positions), the boxes / cubes in its fair state2 row (exact positions), the live walk / bush masks"""
        x, y, team = w["x"], w["y"], w["team"]; oth = w["up"].copy(); oth[p] = False
        foes = [[q, x[q], y[q]] for q in np.flatnonzero(oth & (team != team[p]) & w["sees"][p])]
        mates = [[q, x[q], y[q]] for q in np.flatnonzero(oth & (team == team[p]) & w["screen"][p])]
        boxes = cubes = np.zeros((0, 2))
        v = getattr(self, "last_vec", None)
        if v is not None and b < len(v):
            bx = v[b, FAIR.BX0:FAIR.BX0 + FAIR.BX_K * FAIR.BX_F].reshape(FAIR.BX_K, FAIR.BX_F)
            it = v[b, FAIR.IT0:FAIR.IT0 + FAIR.IT_K * FAIR.IT_F].reshape(FAIR.IT_K, FAIR.IT_F)
            at = lambda blk: np.stack([x[p] + blk[:, 1] * FAIR.R, y[p] + blk[:, 2] * FAIR.R], 1)
            boxes = at(bx[bx[:, 0] > 0.5]); cubes = at(it[(it[:, 0] > 0.5) & (it[:, 3] > 0.5)])
        return {"me": (x[p], y[p]), "range": float(s.sl["range"][p]), "W": w["W"], "H": w["H"], "ring": w["ring"],
                "walk": s.sl["walk"], "bush": s.sl["bush"], "foes": foes, "mates": mates, "boxes": boxes, "cubes": cubes}

    def _choose(self, s, p, b, w, o, cond):
        """a steered agent's planner tick with no active intent -> an intent.new candidate or None (none for this second).
        One draw u: u < p_plan -> the rule planner (self.planner.plan(env, s, p, b, w, o, cond); its none = None); u < p_plan
        + p_rand_intent -> a random valid intent (intent.sample); else none. An evalp_plan agent (plan_only) always asks the
        planner (no draw)."""
        st = s.it[p]
        if st.get("plan_only"): return self._plan(s, p, b, w, o, cond)
        u = self._ir().random(); st["why"] = None
        if self.planner is not None and u < self.p_plan: return self._plan(s, p, b, w, o, cond)
        if u < self.p_plan + self.p_rand_intent: return I.sample(self._scene(s, p, b, w), self._ir())
        return None

    def _plan(self, s, p, b, w, o, cond):
        """the planner's pick at a tick -> the candidate (None for its none); counts st["rules"][rule] = [picked, started,
        preempted] (an anchor not matched: picked, not started); st["why"] = the reason of a none pick (replay frames)"""
        c = self.planner.plan(self, s, p, b, w, o, cond); st = s.it[p]
        n = st.setdefault("rules", {}).setdefault(c["rule"], [0, 0, 0]); n[0] += 1
        if c["kind"] == "none": st["why"] = c["reason"]; return None
        n[1] += 1; st["why"] = None
        return c

    def _preempt(self, s, p, st, b, w, o, cond):
        """a tick while a planner intent is held: the planner's pick replaces it when planner.preempts says so (the old one
        is dropped: no end counted, its reward so far stays)"""
        import planner as PL
        c = self.planner.plan(self, s, p, b, w, o, cond); it = st["act"]
        if c["kind"] == "none": return
        xy = lambda q, pt: (w["x"][q] / 300.0, w["y"][q] / 300.0) if q >= 0 else (pt[0] / 300.0, pt[1] / 300.0)
        if not PL.preempts(it.get("rule"), xy(it["q"], it["pt"]), c["rule"], xy(c.get("q", -1), c.get("pt"))): return
        n = st.setdefault("rules", {}).setdefault(c["rule"], [0, 0, 0]); n[0] += 1; n[1] += 1; n[2] += 1
        self._intent_start(s, p, st, c, w)

    def _intent_start(self, s, p, st, c, w):
        tx, ty = (w["x"][c["q"]], w["y"][c["q"]]) if c.get("q", -1) >= 0 else c["pt"]
        d0 = np.hypot(tx - w["x"][p], ty - w["y"][p]) / 300.0
        st["act"] = I.new(c, d0, s.sl["range"][p] / 300.0, steps_per_s=max(1, 20 // self.ticks)); st["cnt"][c["kind"]][0] += 1
        st["act"]["rule"] = c.get("rule")                # the planner rule (None: a random intent, never preempted)

    def _raw_has(self, s, r, p, pt, obj):
        """is a box / cube still at pt (within 1 tile)? From agent p's raw state2 row of this response (the nearest 6 boxes /
        8 items, any distance); True when the list is full and ends before pt (cannot tell)"""
        if not (int(getattr(r, "obs_written", 0)) >> p) & 1: return True
        NV = P.OBS_VEC; v = np.asarray(s.inst.obs_f32[p * (NV + P.OBS_GRID):p * (NV + P.OBS_GRID) + NV])
        if obj == "box": blk = v[FAIR.BX0:FAIR.BX0 + FAIR.BX_K * FAIR.BX_F].reshape(FAIR.BX_K, FAIR.BX_F); listed = blk[:, 0] > 0.5; mine = listed
        else: blk = v[FAIR.IT0:FAIR.IT0 + FAIR.IT_K * FAIR.IT_F].reshape(FAIR.IT_K, FAIR.IT_F); listed = blk[:, 0] > 0.5; mine = listed & (blk[:, 3] > 0.5)
        mx, my = float(r.pl[p].x), float(r.pl[p].y); ex, ey = mx + blk[:, 1] * FAIR.R, my + blk[:, 2] * FAIR.R
        if (np.hypot(ex - pt[0], ey - pt[1])[mine] <= 300).any(): return True
        far = np.hypot(ex - mx, ey - my)[listed].max() if listed.any() else 0.0
        return bool(listed.all() and far < np.hypot(pt[0] - mx, pt[1] - my) + 300)

    def _intent_step(self, s, r):
        """the active intents of battle s over the step that produced r (true state) -> {player: intent reward before
        intent_scale}; ends counted per kind, an achieved end asks for a re-plan at the next decision"""
        act = {p: st for p, st in s.it.items() if st["act"] is not None}
        if not act: return {}
        w = self._world(s, r); pl = r.pl; x, y, up, team = w["x"], w["y"], w["up"], w["team"]; out = {}
        dk = np.array([(pl[q].damage_dealt + pl[q].bomb_damage) / 1000.0 for q in range(10)])
        te = np.array([max(pl[q].damage_taken - pl[q].gas_damage, 0) for q in range(10)])
        for p, st in act.items():
            it = st["act"]; k, q, t, sps = it["kind"], it["q"], it["t"] + 1, it["sps"]   # t: the step being scored
            px, py = (x[q], y[q]) if q >= 0 else it["pt"]; d = float(np.hypot(px - x[p], py - y[p]) / 300.0)
            ev = {"d": d, "out": not up[p], "dk": dk[p], "box": pl[p].box_damage / 1000.0}; lost = got = False
            if q >= 0:
                seen = w["sees"][p, q] if team[q] != team[p] else w["screen"][p, q]
                if k == "engage":
                    ev["in_range"] = d <= it["range"]
                    if dk[p] > 0 and ev["in_range"] and te[q] > 0: it["hit_t"] = t
                    if not up[q]: got = pl[p].kills > 0 or t - it["hit_t"] <= I.HIT_S * sps; lost = not got
                elif not up[q]: lost = True
            else:
                seen = k != "farm" or bool(I.on_screen(x[p], y[p], px, py, w["W"]))   # unseen rule: anchored targets (players, farm objects)
                gx, gy = min(max(int(px // 300), 0), w["W"] - 1), min(max(int(py // 300), 0), w["H"] - 1)
                if k == "farm":
                    if I.gas_margin_t(gx, gy, w["ring"], w["W"], w["H"]) < 0: lost = True
                    elif it["obj"] == "box":
                        if pl[p].box_damage > 0: it["box_t"] = t
                        if not self._raw_has(s, r, p, (px, py), "box"): got = t - it["box_t"] <= I.HIT_S * sps; lost = not got
                    elif pl[p].cubes > 0 and d <= I.PICK: got = True
                    elif not self._raw_has(s, r, p, (px, py), "cube"): lost = True
                elif k == "hide":
                    if not s.sl["bush"][gy, gx]: lost = True
                    en = up & (team != team[p])
                    hid = w["inb"][p] and not (en & w["sees"][:, p]).any() and (en & w["screen"][:, p]).any()   # env slider_terms hid_vs
                    ev["on"] = (w["tx"][p], w["ty"][p]) == (gx, gy); ev["hid"] = hid or not (en & w["sees"][p]).any()
            it["unseen"] = 0 if seen else it["unseen"] + 1
            ev["lost"] = lost or (not got and it["unseen"] >= I.SEEN_S * sps); ev["got"] = got
            out[p], end = I.step_reward(it, ev)
            if end: st["cnt"][k][1 + I.END.index(end)] += 1; st["act"] = None; st["replan"] = end == "achieved"
        return out

    def aux_now(self, ids):
        """(B, AUX_W) aux-head labels of the agents of the last poll() from the true state of their battle's current
        response (as train_ppo.priv): AUX layout. The fair visibility rule as nbpc.fair / slider_terms: camera x clamped
        to [3000, W x 300 - 3000], in view iff |dx| < 4500 and -3500 < dy < 2900, a brawler on a bush tile hidden beyond
        900 units; bushes = the live slider mask sl["bush"]."""
        ids = np.asarray(ids, np.int64); B = len(ids); out = np.zeros((B, AUX_W), np.float32)
        if not B: return out
        by = {s.battle: s for s in self.I}; ub, inv = np.unique(ids >> 4, return_inverse=True)
        tab = np.zeros((len(ub), 5, 10)); geo = np.zeros((len(ub), 3))
        for u, k in enumerate(ub):
            s = by[int(k)]; r = s.inst.resp; pl = r.pl; H, W = s.sl["bush"].shape
            x = np.array([pl[q].x for q in range(10)], np.float64); y = np.array([pl[q].y for q in range(10)], np.float64)
            tx, ty = np.clip(x // 300, 0, W - 1).astype(int), np.clip(y // 300, 0, H - 1).astype(int)
            tab[u] = [x, y, [bool(pl[q].alive) and not pl[q].eliminated and pl[q].reserved[3] <= 0 for q in range(10)],
                      [pl[q].reserved[2] for q in range(10)], s.sl["bush"][ty, tx]]
            geo[u] = int(r.reserved[0]), W, H
        x, y, al, team, inb = tab[inv].transpose(1, 0, 2); ring, W, H = geo[inv].T; me = ids & 15; ar = np.arange(B)
        mx, my = x[ar, me], y[ar, me]; dx, dy = x - mx[:, None], y - my[:, None]; d = np.hypot(dx, dy)
        en = (al > 0.5) & (team != team[ar, me][:, None])
        camx = np.clip(mx, 3000.0, W * 300 - 3000.0)
        sees = (np.abs(x - camx[:, None]) < 4500) & (dy > -3500) & (dy < 2900) & ~((inb > 0.5) & (d > 900))
        hb = en & (inb > 0.5) & ~sees & (d <= BUSH_NEAR)
        sec = (np.floor((np.degrees(np.arctan2(dy, dx)) + 22.5) % 360.0 / 45.0)).astype(int) % 8
        col = lambda k: AUX[k][0]
        out[:, :20] = (np.stack([x, y], -1) / 300.0).reshape(B, 20); out[:, col("talive"):col("talive") + 10] = en
        out[:, col("me")] = me; out[:, col("gm")] = gas_margin(mx, my, ring, W, H)[0]
        for k in range(8): out[:, col("be") + k] = (hb & (sec == k)).any(1)
        return out

    def cmd_vel(self, ids):
        """(B, 2) tiles / tick: the agents' last commanded move x their brawler speed (sim_plan A2; what the agent uses live
        as its own velocity: BSRL brain.player / play_live). 0 when stopped or before the first action of a battle."""
        by = {s.battle: s for s in self.I}; out = np.zeros((len(ids), 2), np.float32)
        for k, a in enumerate(ids):
            s, p = by[int(a) >> 4], int(a) & 15; act = s.acts.get(p)
            if act is not None and int(act[0]) > 0:
                sp = O.brawler_stats(s.cfg["tag"]["chr"][p])[1] / 6.0   # stats[1] = Speed / 1000; units/s / 300 / 20 ticks
                t = np.deg2rad((int(act[0]) - 1) * 22.5); out[k] = sp * np.cos(t), sp * np.sin(t)
        return out

    def gadget(self, ids):
        """(B,) float32: 1 = the agent's gadget can be used now (obs_v5 self 3): the host publishes gadget state (gad_valid),
        activates this gadget's kind (gad_kind != NONE), a use is left and no cooldown runs, and the brawler is in play.
        All 0 with a host without gadget activation."""
        by = {s.battle: s for s in self.I}; out = np.zeros(len(ids), np.float32)
        for k, a in enumerate(ids):
            s = by.get(int(a) >> 4)
            if s is not None: out[k] = gadget_ready(s.inst.resp, int(a) & 15)
        return out

    def hyper(self, ids):
        """(B,) float32: 1 = the agent can activate its hypercharge now (obs_v5 self 4; hyper_ready): the host runs
        hypercharge (hyp_valid), the card is equipped, the charge is full, it is not active and the brawler is in play.
        All 0 with a host without hyper.c."""
        by = {s.battle: s for s in self.I}; out = np.zeros(len(ids), np.float32)
        for k, a in enumerate(ids):
            s = by.get(int(a) >> 4)
            if s is not None: out[k] = hyper_ready(s.inst.resp, int(a) & 15)
        return out

    def cond(self, ids):
        """(B, N_COND) conditioning vectors (obs_v5.cond) of the agents of the last poll()"""
        by = {s.battle: s for s in self.I}
        out = []
        for a in ids:
            s, p = by[int(a) >> 4], int(a) & 15; tag = s.cfg["tag"]; ts = tag["team_size"] if tag["groups"][p] else 1
            cubes, left = getattr(s, "hud", (None, None))
            out.append(O.cond(tag["chr"][p], s.sl["w"][p], ts, cubes[p] if cubes else 0, left))
        return np.stack(out) if out else np.zeros((0, O.N_COND), np.float32)


def _check():
    from types import SimpleNamespace as NS
    def players(**over):
        pl = [NS(x=1650 + 3000 * (p % 5), y=1650 + 6000 * (p // 5), hp=3000, max_hp=4000, damage_dealt=0, bomb_damage=0, damage_taken=0,
                 box_damage=0, cubes=0, cubes_total=0, gas_damage=0, in_gas=0, kills=0, reserved=[0, 0, p, 0], alive=1, eliminated=0) for p in range(10)]
        for k, v in over.items(): setattr(pl[int(k[1])], k[3:], v)
        return pl
    cub, left = Env._hud(None, NS(cfg={"tag": {"groups": [1, 1, 1, 2, 2, 2, 3, 3, 3, 0]}}),   # cond's HUD numbers
                         NS(pl=players(p0_eliminated=1, p3_eliminated=1, p4_eliminated=1, p5_eliminated=1, p9_cubes_total=4)))
    assert left == 3 and cub[9] == 4 and cub[0] == 0, (left, cub)
    tiles = np.full((40, 60), 27000000); bush = D.table("tiles.csv")["Forest"][0]; wall = D.table("tiles.csv")["Indestructible"][0]
    tiles[5, 5] = bush; tiles[20:23, 30] = bush; tiles[25, 10] = wall
    sl = slider_state(tiles.ravel(), 60, 40, ["Sniper"] * 10, np.random.default_rng(0))
    assert sl["w"].shape == (10, len(SL)) and 0 <= sl["w"].min() and sl["w"].max() <= 2 and sl["range"][0] == 3000
    assert sl["bush"].sum() == 4 and sl["nearcover"][23, 8] and sl["nearcover"][27, 12] and not sl["nearcover"][28, 10]
    t2 = tiles.copy(); t2[25, 10] = 27000000; t2[5, 5] = 27000000; s2 = slider_map(dict(sl), t2.ravel(), 60, 40)   # destroyed
    assert s2["bush"].sum() == 3 and not s2["bush"][5, 5] and not s2["nearcover"][23, 8] and sl["bush"][5, 5]
    col = lambda T, name: T[:, SL.index(name)]
    fresh = lambda: slider_state(tiles.ravel(), 60, 40, ["Sniper"] * 10, np.random.default_rng(0))
    T = slider_terms(sl, players())                      # p0 on the bush tile (5, 5), on p1's screen 10 tiles away: hidden
    assert col(T, "bush_camp")[0] == 0.002 and col(T, "bush_camp")[1:].sum() == 0 and col(T, "bush_control")[0] == 0.005
    assert sl["beh"][0, BEH.index("hidden")] == 1 and sl["beh"][0, BEH.index("bush")] == 1 and sl["beh"][1, BEH.index("bush")] == 0
    T = slider_terms(sl, players(p0_damage_dealt=500, p0_box_damage=1000, p0_cubes=1, p0_cubes_total=1, p1_damage_taken=800))
    assert np.isclose(col(T, "bush_camp")[0], 0.502) and np.isclose(col(T, "collect")[0], 1.2) and col(T, "bush_control")[0] == 0
    assert col(T, "kite")[0] == 0.5 and col(T, "focus")[0] == 0.5 and col(T, "third_party")[0] == 0.5 and col(T, "peek")[0] == 0
    assert col(T, "kite")[1] == 0 and col(T, "protect").sum() == 0 and np.isclose(col(T, "aggressive")[0], 0.502)   # + p1 in range
    g = fresh(); slider_terms(g, players(p0_eliminated=1, p2_eliminated=1, p3_eliminated=1, p4_eliminated=1, p5_eliminated=1,
                                          p6_eliminated=1, p7_eliminated=1, p8_eliminated=1, p9_eliminated=1, p1_x=15000))
    assert g["beh"][0, BEH.index("hidden")] == 0 and g["beh"][1, BEH.index("alive")] == 1   # A4: a bush with nobody around is no hiding
    gas = players(p0_damage_dealt=500, p1_damage_taken=800, p1_gas_damage=800, p0_box_damage=1000, p0_in_gas=1)
    T = slider_terms(fresh(), gas)                       # A2: gas damage is no enemy hit; A5: no farming in the gas
    assert col(T, "third_party")[0] == 0 and col(T, "focus")[0] == 0 and col(T, "collect")[0] == 0 and col(T, "kite")[1] == 0.0
    T = slider_terms(sl, players(p0_hp=1000)); assert col(T, "retreat")[0] == 0 and sl["low"][0]
    T = slider_terms(sl, players(p0_hp=1600)); assert np.isclose(col(T, "retreat")[0], 0.6)
    T = slider_terms(sl, players(p0_hp=3500)); assert np.isclose(col(T, "retreat")[0], 1.9) and not sl["low"][0]
    T = slider_terms(sl, players(p0_hp=3600, p0_x=1800)); assert col(T, "retreat")[0] == 0
    T = slider_terms(fresh(), players(p0_damage_dealt=1000, p0_kills=1)); assert np.isclose(col(T, "aggressive")[0], 1.502)
    T = slider_terms(fresh(), players(p0_hp=1000)); assert col(T, "aggressive")[0] == 0   # in range but low: no engagement pay
    assert slider_terms(fresh(), players(p1_x=9000))[0, SL.index("aggressive")] == 0      # nobody in range
    assert gas_margin(1650, 1650, 4, 60, 40) == (1, 15.5) and gas_margin(-5, 99999, 0, 60, 40)[0] == 0
    T = slider_terms(fresh(), players(), ring=4); assert col(T, "gas_safe")[0] == -0.002 and col(T, "gas_safe")[6] == 0   # p0 1 tile in, p6 10 in
    T = slider_terms(fresh(), players(p0_in_gas=1), ring=6); assert col(T, "gas_safe")[0] == -0.01
    T = slider_terms(fresh(), players(p0_x=9150, p0_y=6150), ring=18); assert col(T, "gas_safe")[0] == 0   # endgame zone (1.5): no near-gas cost
    g = fresh(); slider_terms(g, players(p0_hp=1000))   # A1 / A7: knocked out low, respawned full: no retreat for the refill
    ko = players(p0_hp=0); ko[0].reserved = [0, 0, 0, 100]; assert not slider_terms(g, ko)[0].any()
    assert col(slider_terms(g, players(p0_hp=4000)), "retreat")[0] == 0 and g["beh"][0, BEH.index("alive")] == 2
    g = fresh(); slider_terms(g, players(p0_hp=1000)); assert col(slider_terms(g, players(p0_hp=1400, p0_cubes=1, p0_cubes_total=1)), "retreat")[0] == 0
    g = fresh(); slider_terms(g, players(p0_cubes=3, p0_cubes_total=3))           # cubes lost at a knock-out / an elimination
    ko = players(); ko[0].reserved = [0, 0, 0, 100]; assert col(slider_terms(g, ko), "collect")[0] == -3
    g = fresh(); slider_terms(g, players(p0_cubes=2, p0_cubes_total=2))
    assert col(slider_terms(g, players(p0_eliminated=1, p0_cubes_total=2)), "collect")[0] == -2 and g["beh"][0, BEH.index("cubes_max")] == 2
    mates = lambda **o: [setattr(q, "reserved", [0, 0, 0 if k < 3 else k, 0]) or q for k, q in enumerate(players(**o))]
    g = fresh(); T = slider_terms(g, mates(p2_damage_taken=1000, p2_x=2500, p0_damage_dealt=400))   # A3: peel, no proximity pay
    assert np.isclose(col(T, "protect")[0], 0.4) and col(T, "protect")[1] == 0
    for k in range(8): slider_terms(g, mates())          # steps k+1 .. k+8
    assert np.isclose(col(slider_terms(g, mates(p0_damage_dealt=400, p2_x=2500)), "protect")[0], 0.4)   # step k+9: still (10 steps)
    assert col(slider_terms(g, mates(p0_damage_dealt=400, p2_x=2500)), "protect")[0] == 0
    T = slider_terms(fresh(), mates(p2_damage_taken=1000, p0_damage_dealt=400)); assert col(T, "protect")[0] == 0   # p2 15+ tiles away
    assert slider_terms(fresh(), mates())[:, SL.index("protect")].sum() == 0   # being near a mate pays nothing by itself
    T = slider_terms(fresh(), mates(p1_x=2500)); assert np.allclose(col(T, "leash")[:3], [0.002, 0.002, 0])   # 850 apart: band
    T = slider_terms(fresh(), mates(p1_x=1800)); assert np.allclose(col(T, "leash")[:3], [-0.002, -0.002, 0])   # 150 apart: clump
    assert not slider_terms(fresh(), mates())[:, SL.index("leash")].any() and not slider_terms(fresh(), players())[:, SL.index("leash")].any()
    hb = players(p1_x=4500, p1_y=6300, p1_damage_taken=500, p0_damage_dealt=300, p0_x=4500, p0_y=4200)   # p1 in the bush (15, 21)
    tiles2 = tiles.copy(); tiles2[21, 15] = bush; g = slider_state(tiles2.ravel(), 60, 40, ["Sniper"] * 10, np.random.default_rng(0))
    assert np.isclose(col(slider_terms(g, hb), "bush_control")[0], 0.3)   # hidden in a bush 7 tiles off, in range, hit
    w = slider_state(tiles.ravel(), 60, 40, [], np.random.default_rng(0), w=O.preset_vec("bush_camper"))["w"]
    assert w.shape == (10, len(SL)) and (w == O.preset_vec("bush_camper")).all()
    r0, r1 = np.random.default_rng(5), np.random.default_rng(5)
    assert np.array_equal(sample_sliders(r0, 10), r1.uniform(0, 2, (10, len(SL))))   # uniform = the original draws
    m = sample_sliders(np.random.default_rng(1), 4000, "mix"); pre = np.stack([O.preset_vec(k) for k in O.PRESETS])
    exact = (m[:, None] == pre[None]).all(2).any(1).mean(); sparse = ((m == 0.5) | (m == 2.0)).all(1).mean()
    assert m.min() >= 0 and m.max() <= 2 and 0.08 < exact < 0.13 and 0.08 < sparse < 0.15, (exact, sparse)
    assert (slider_norm("") == 1).all() and slider_norm("measured").shape == (len(SL),)
    dead = players(p0_alive=0, p0_damage_dealt=900); assert not slider_terms(sl, dead)[0].any()
    pl = players(p0_alive=0, p1_eliminated=1, p2_eliminated=1, p3_eliminated=1)          # team placement
    for p, k in ((0, 9), (1, 8), (2, 10), (3, 7)): pl[p].elim_rank = k
    pr, dd = player_ranks(NS(done=0, alive=6, winner=-1, pl=pl))
    assert list(pr[:5]) == [9, 8, 10, 7, 3.5] and list(dd[:5]) == [1, 1, 1, 1, 0]
    g = [1, 1, 2, 2, 2, 0, 0, 0, 0, 0]                   # team 1 out (best 8), team 2 alive through p4, rest alone
    tr = team_ranks(g, pr, dd, False); assert list(tr[:2]) == [8, 8] and np.isnan(tr[2:5]).all() and tr[5] == 3.5
    assert list(team_ranks(g, pr, dd, True)[:5]) == [8, 8, 3.5, 3.5, 3.5]                     # cut short: p4's estimate
    assert np.array_equal(team_ranks([0] * 10, pr, dd, False), pr)                            # solo: own rank
    def fake(self, i, r):                                # MAEnv._finish_step stand-in: the final transitions of r.fin
        for p in r.fin: rk = r.pl[p].elim_rank; self._trans.append((16 + p, 1.0, True, {"place": (10 - rk) / 9, "win": 0.0}, rk))
        self.I[i].battle += r.over
    env = Env.__new__(Env); env._trans, env.episodes, env.w, env.slider_scale = [], [], {"place": 5.0, "win": 3.0}, 0.0
    for groups, want in (([0] * 10, [1.0, 1.0]), ([1, 1] + [0] * 8, [1.0, 1.0 + 5 * (10 - 3) / 9 - 5 * (10 - 8) / 9])):
        env.I = [NS(sl=sl, cfg={"tag": {"groups": groups}}, hold={}, battle=1, pos={}, ptick=0, pjump=set(), agents={}, wprev=set())]
        mk = lambda fin, over, **o: NS(pl=players(**o), fin=fin, over=over, tick=1, njumps=0, jumps=[], done=0, alive=8, winner=-1, reserved=[0] * 8)
        r1 = mk([1], 0, p1_eliminated=1); r1.pl[1].elim_rank = 8
        r2 = mk([0], 0, p0_eliminated=1, p1_eliminated=1); r2.pl[0].elim_rank = 3; r2.pl[1].elim_rank = 8
        sup, MAEnv._finish_step = MAEnv._finish_step, fake
        try:
            env._finish_step(0, r1); n1 = len(env._trans); env._finish_step(0, r2)
        finally: MAEnv._finish_step = sup
        got = {a & 15: rw for a, rw, *_ in env._trans}; env._trans = []
        assert n1 == (0 if groups[0] else 1) and np.allclose([got[0], got[1]], want), (groups, n1, got)   # p1 held until p0 out
    def fake2(self, i, r):                               # p0 steps on: its hp term is the host's hp change
        self._trans.append((16, 2.0 * r.pl[0].hp / 1000, False, {"hp": r.pl[0].hp / 1000, "place": 0.0, "win": 0.0}, None))
    env.w = {"hp": 2.0}; env.I = [NS(sl=sl, cfg={"tag": {"groups": [1, 1] + [0] * 8}}, hold={}, battle=1, pos={}, ptick=0, pjump=set(), agents={0: 16}, wprev=set())]
    sup, MAEnv._finish_step = MAEnv._finish_step, fake2
    try:
        rw = mk([], 0, p0_hp=0); rw.pl[0].reserved[3] = 120; env._finish_step(0, rw)       # respawning: hp 0, dead
        assert env.dead([16, 17]).tolist() == [True, False] and env._trans[-1][3]["dead"] == 1.0
        env._finish_step(0, mk([], 0, p0_hp=4000))                                         # back with full hp
        assert env._trans[-1][1] == 0.0 and env._trans[-1][3]["hp"] == 0.0 and not env.dead([16]).any()
        assert env.resp == {"out": 1, "back": 1, "wiped": 0}
    finally: MAEnv._finish_step = sup
    def fake3(self, i, r):                               # p0 steps on with base reward 0 and finishes: an episode row
        self._trans.append((16, 0.0, False, {"hp": 0.0, "place": 0.0, "win": 0.0}, None)); self.episodes.append({"player": 0, "ret": 0.0, "terms": {}})
    sl3 = fresh(); sl3["w"][:] = 2.0; env.slider_scale = 0.5; env.slider_norm = np.full(len(SL), 3.0); env.w = {}
    env.I = [NS(sl=sl3, cfg={"tag": {"groups": [0] * 10}}, hold={}, battle=1, pos={}, ptick=0, pjump=set(), agents={0: 16}, wprev=set())]
    sup, MAEnv._finish_step = MAEnv._finish_step, fake3
    try: env._finish_step(0, mk([], 0)); env._finish_step(0, mk([], 0, p0_damage_dealt=1000))   # hidden, then an ambush hit
    finally: MAEnv._finish_step = sup
    want = 2.0 * 3.0 * 0.5 * np.array([0.002 + 0.005 + 0.002, 0.002 + 1.0 + 1.0 + 1.002])   # weight x norm x scale x (bush_camp + bush_control's
    # new tile + aggressive's engagement; bush_camp + ambush + kite + aggressive)
    assert np.allclose([t[1] for t in env._trans[-2:]], want), [t[1] for t in env._trans[-2:]]
    row = env.episodes[-1]; assert np.isclose(row["terms"]["sn_bush_camp"], 3 * 1.004) and np.isclose(row["terms"]["s_bush_camp"], 1.004)
    assert row["beh"]["alive"] == 2 and row["sliders"] == [2.0] * len(SL) and np.isclose(row["terms"]["sa_bush_camp"], 1.004)
    nr = lambda ts, leash, sa: {"sliders": [1.0] * len(SL), "tag": {"team_size": ts},
                                "terms": {**{"s_" + k: 1.0 for k in SL}, "s_leash": leash, **({"sa_leash": sa} if sa is not None else {})}}
    f, m = norm_from([nr(3, 0.01, 0.4), nr(3, -0.01, 0.6), nr(1, 0.0, 0.0)])   # band / clump cancel in the sum, not in |term|
    assert np.isclose(m["leash"], 0.5) and np.isclose(f["leash"], 1.0) and np.isclose(f["kite"], 0.5)   # leash: team rows only
    assert np.isclose(norm_from([nr(3, 0.2, None)])[1]["leash"], 0.2)   # rows without sa_: |s_|
    def fake4(self, i, r):                               # p0 takes 800 damage, 300 of it from the gas
        self._trans.append((16, 0.0, False, {"hp": 0.0, "place": 0.0, "win": 0.0}, None))
    env.I = [NS(sl=fresh(), cfg={"tag": {"groups": [0] * 10}}, hold={}, battle=1, pos={}, ptick=0, pjump=set(), agents={0: 16}, wprev=set())]
    sup, MAEnv._finish_step = MAEnv._finish_step, fake4
    try: env._finish_step(0, mk([], 0, p0_damage_taken=800, p0_gas_damage=300))
    finally: MAEnv._finish_step = sup
    assert np.isclose(env._trans[-1][3]["te"], 0.5), env._trans[-1][3]          # aux hit label: enemy damage only
    _check_aux(players, tiles, bush, NS)
    _check_intents(players, tiles, NS)
    _check_planner(players, tiles, NS)
    _check_who(NS)
    _check_gadgets(NS)
    _check_star_powers()
    _check_hyper(NS)
    _check_roster()
    print("env_v5 sliders, aux labels, intents, planner hook, identity rows, gadget / hypercharge readiness, star powers, roster ok")


def _check_roster():
    """the battle pool (issue #23): the playable brawlers, not the other forms or event transforms (the game's tables)"""
    hs, fs = heroes(), forms()
    assert len(hs) == 106 and len(fs) == 9 and not set(hs) & set(fs) and set(hs) | set(fs) == set(O.hero_names()), (len(hs), fs)
    assert {"MechaDudeBig", "CannonGirlSmall", "DiggerDrill", "GeishaTransformed", "SuperNovaCactus"} <= set(fs)
    assert {"MechaDude", "CannonGirl", "Digger", "Geisha", "ShotgunGirl", "KatanaKid", "FutureGirl"} <= set(hs)
    assert all(O.id_row(f) >= 0 for f in fs)                                    # forms keep their identity rows
    cfg = make_battle_fn(10, seed0=7)(np.random.default_rng(1), 0)
    assert set(cfg["tag"]["chr"]) <= set(hs), cfg["tag"]["chr"]
    gc = gadget_cards()                                                         # Disabled TRUE (Driller_Proto, Baseball_Proto): out
    assert len(gc["Driller"]) == 2 and len(gc["Baseball"]) == 2, (gc.get("Driller"), gc.get("Baseball"))


def _check_star_powers():
    """the star power loadout request: the game's cards.csv, LIVE-only by default, drawn after the gadgets"""
    import star_audit
    sa, sl, hs = star_cards(False), star_cards(), heroes()
    assert sum(map(len, sa.values())) >= 200 and all(c // 1000000 == T_CARD for v in sa.values() for c in v)
    assert all(set(v) <= set(sa[b]) for b, v in sl.items()) and sum(map(len, sl.values())) <= len(star_audit.LIVE)
    for live in (False, True):
        sc = star_cards(live); cfg = with_star_powers({"div": {"chr": [0] * 16}, "tag": {"chr": hs[:10]}}, np.random.default_rng(0), live)
        assert all((c in sc.get(b, [])) or (c == 0 and not sc.get(b)) for c, b in zip(cfg["div"]["star"], hs[:10]))
    r1, r2 = np.random.default_rng(4), np.random.default_rng(4)
    c1, c2 = make_battle_fn(3, seed0=7, gadgets=True)(r1, 0), make_battle_fn(3, seed0=7, gadgets=True, star_powers=True)(r2, 0)
    assert c1["tag"] == c2["tag"] and c1["div"]["gadget"] == c2["div"]["gadget"] and "star" not in c1["div"] and len(c2["div"]["star"]) == 10


def _check_gadgets(NS):
    """gadget readiness from the host's gad_* fields (fake responses) and the loadout request (the game's cards.csv)"""
    pl = lambda **o: NS(**{"alive": 1, "eliminated": 0, "reserved": [0, 0, 0, 0], **o})
    def resp(valid=1, kind=P.GAD_DASH, charges=3, cd=0, **o):
        return NS(gad_valid=valid, gad_kind=[kind] * 16, gad_charges=[charges] * 16, gad_cd=[cd] * 16, pl=[pl(**o)] * 16)
    assert gadget_ready(resp(), 0) and not gadget_ready(NS(pl=[pl()] * 16), 0)          # a host without gad_*: never
    for bad in (dict(valid=0), dict(kind=P.GAD_NONE), dict(charges=0), dict(cd=5), dict(alive=0), dict(eliminated=1), dict(reserved=[0, 0, 0, 40])):
        assert not gadget_ready(resp(**bad), 0), bad
    env = Env.__new__(Env); env.I = [NS(battle=3, inst=NS(resp=resp())), NS(battle=4, inst=NS(resp=resp(cd=2)))]
    assert env.gadget(np.array([3 << 4 | 2, 4 << 4 | 2, 9 << 4])).tolist() == [1, 0, 0]       # unknown battle: 0
    gc = gadget_cards(); hs = heroes()
    assert gc and all(k // 1000000 == T_CARD for v in gc.values() for k in v) and sum(b in gc for b in hs) > len(hs) // 2, len(gc)
    cfg = with_gadgets({"div": {"chr": [0] * 16}, "tag": {"chr": hs[:10]}}, np.random.default_rng(0))
    assert all((g in gc.get(b, [])) or (g == 0 and not gc.get(b)) for g, b in zip(cfg["div"]["gadget"], hs[:10]))
    r1, r2 = np.random.default_rng(4), np.random.default_rng(4)                              # gadgets drawn last: the battle
    c1, c2 = make_battle_fn(3, seed0=7)(r1, 0), make_battle_fn(3, seed0=7, gadgets=True)(r2, 0)   # is the same without them
    assert c1["tag"] == c2["tag"] and c1["ctl"] == c2["ctl"] and "gadget" not in c1["div"] and len(c2["div"]["gadget"]) == 10


def _check_hyper(NS):
    """hypercharge readiness from the host's hyp_* fields (fake responses) and the loadout request"""
    pl = lambda **o: NS(**{"alive": 1, "eliminated": 0, "reserved": [4000, 4000, 0, 0], **o})
    def resp(valid=1, card=23000777, left=0, **o):
        return NS(hyp_valid=valid, hyp_card=[card] * 16, hyp_left=[left] * 16, pl=[pl(**o)] * 16)
    assert hyper_ready(resp(), 0) and not hyper_ready(NS(pl=[pl()] * 16), 0)                 # a host without hyp_*: never
    for bad in (dict(valid=0), dict(card=0), dict(left=30), dict(reserved=[3999, 4000, 0, 0]), dict(reserved=[0, 0, 0, 0]),
                dict(alive=0), dict(eliminated=1), dict(reserved=[4000, 4000, 0, 40])):
        assert not hyper_ready(resp(**bad), 0), bad
    env = Env.__new__(Env); env.I = [NS(battle=3, inst=NS(resp=resp())), NS(battle=4, inst=NS(resp=resp(left=2)))]
    assert env.hyper(np.array([3 << 4 | 2, 4 << 4 | 2, 9 << 4])).tolist() == [1, 0, 0]        # unknown battle: 0
    hb = hyper_brawlers(); assert "ShotgunGirl" in hb and len(hb) > 50, len(hb)
    r1, r2 = np.random.default_rng(4), np.random.default_rng(4)                              # no draw: the same battle
    c1, c2 = make_battle_fn(3, seed0=7, gadgets=True)(r1, 0), make_battle_fn(3, seed0=7, gadgets=True, hyper=True)(r2, 0)
    assert c1["tag"] == c2["tag"] and c1["div"]["gadget"] == c2["div"]["gadget"] and "hyper" not in c1["div"]
    assert c2["div"]["hyper"] == list(range(10))


def _check_aux(players, tiles, bush, NS):
    """Env.aux_now on a synthetic battle: positions, alive enemies (no mate, no respawning player), gas margin, hidden
    enemies in bushes by sector (900 < d <= 1500 units, a mate / a respawning enemy / one too far do not count)"""
    tl = tiles.copy()
    for ty, tx in ((18, 15), (14, 19), (14, 21), (14, 12), (12, 13)): tl[ty, tx] = bush
    pl = players(p0_x=4650, p0_y=4350, p1_x=4650, p1_y=5400, p2_x=5700, p2_y=4350, p3_x=6450, p3_y=4350, p4_x=3600, p4_y=4350,
                 p6_x=3900, p6_y=3600)
    pl[2].reserved = [0, 0, 0, 0]; pl[4].reserved = [0, 0, 4, 50]   # p2: p0's mate; p4: respawning
    env = Env.__new__(Env)
    env.I = [NS(battle=1, inst=NS(resp=NS(pl=pl, reserved=[3, 0, 0, 0])), sl=slider_state(tl.ravel(), 60, 40, [], np.random.default_rng(0)))]
    A = aux_split(env.aux_now([16, 17, 18]))
    assert np.allclose(A["tpos"][0, 0], [15.5, 14.5]) and np.allclose(A["tpos"][1], A["tpos"][0]) and list(A["me"]) == [0, 1, 2]
    assert A["talive"][0].tolist() == [0, 1, 0, 1, 0, 1, 1, 1, 1, 1] and A["talive"][1, 0] == 1 and A["talive"][2, 0] == 0
    assert A["gm"][0] == 14 - 3, A["gm"]                    # tile (15, 14) on a 60 x 40 map, storm ring 3
    assert np.flatnonzero(A["be"][0]).tolist() == [2, 5], A["be"][0]   # p1 below (90 deg), p6 up-left (225 deg)
    assert np.flatnonzero(A["be"][2]).tolist() == [3] and env.aux_now([]).shape == (0, AUX_W)   # p2: p1 down-left 1485 away; p3 750 away = seen


def _check_who(NS):
    """Env.who on a synthetic snap2 dump + the fair rows the encoder would write from it (dx, dy = float32 of the offset
    / 3000): brawlers -> owner / tag brawler (or the character's data id) / side; summons, boxes, items none; projectiles
    their owner (mine = WHO_ME); my own brawler is never a row; a vacant slot none"""
    chr_ = ["Sniper", "BullDude", "ShotgunGirl", "Gunslinger", "RocketGirl", "Sniper", "BullDude", "Sniper", "Sniper", "Sniper"]
    team = [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]; NIL = -2 ** 31; cd = lambda n: D.table("characters.csv")[n][0]
    pl = [[i, team[i], 100 + i, NIL if i != 4 else 400, 0, 1, 0, 0] for i in range(10)]   # player 4 controls character 400
    xy = {i: (3000 + 450 * i, 6000 - 300 * i) for i in range(10)}
    ch = [[100 + i, cd(chr_[i]), i, *xy[i], 0, 3000, 3000] + [0] * 15 for i in range(10) if i != 4]
    ch.append([400, cd("Gunslinger"), 4, *xy[4], 0, 3000, 3000] + [0] * 15)         # 4's brawler on the map: Gunslinger, not its tag pick
    ch.append([200, cd("Sniper"), 3, 3300, 6300, 0, 900, 900] + [0] * 15)            # a summon of player 3 (not its brawler)
    ch.append([300, 16000120, -1, 3600, 6300, 0, 4000, 4000] + [0] * 15)             # a power box
    pj = [[500 + k, 0, q, 3000 + 100 * k, 5000, 0] + [0] * 12 for k, q in enumerate([0, 2, 1, 7])]
    a = np.zeros(8192, np.int32); a[[0, 3, 4, 5, 6]] = [0x4e423253, 10, len(ch), len(pj), 0]
    flat = np.array(sum(pl, []) + sum(ch, []) + sum(pj, []), np.int32); a[8:8 + len(flat)] = flat
    env = Env.__new__(Env); env.I = [NS(battle=1, inst=NS(state_i32=a), cfg={"tag": {"chr": chr_}})]
    vec = np.zeros((1, 436), np.float32); mx, my = xy[0]; f = lambda v, m: np.float32((v - m) / FAIR.R)
    rows = [(xy[2], 0, 0), (xy[1], 0, 1), (xy[4], 0, 0), ((3300, 6300), 1, 0)]        # (position, summon, on my team): players 2, 1, 4, the summon
    for k, ((x, y), summ, mate) in enumerate(rows):
        o = FAIR.EN0 + k * FAIR.EN_F; vec[0, o:o + 3] = [1, f(x, mx), f(y, my)]; vec[0, o + 14] = summ; vec[0, o + 15] = mate
    for k, r in enumerate(pj): o = FAIR.PJ0 + k * FAIR.PJ_F; vec[0, o:o + 3] = [1, f(r[3], mx), f(r[4], my)]; vec[0, o + 5] = r[2] == 0
    o = FAIR.BX0; vec[0, o:o + 3] = [1, f(3600, mx), f(6300, my)]
    w = env.who(np.array([16]), vec)[0]
    assert w.shape == (O.N_ENT, 3) and w.dtype == np.int16
    assert w[0].tolist() == [2, O.id_row("ShotgunGirl"), O.WHO_FOE] and w[1].tolist() == [1, O.id_row("BullDude"), O.WHO_MATE], w[:3]
    assert w[2].tolist() == [4, O.id_row("Gunslinger"), O.WHO_FOE] and (w[3] == -1).all() and (w[4:9] == -1).all()
    side = [O.WHO_ME, O.WHO_FOE, O.WHO_MATE, O.WHO_FOE]
    assert [w[FAIR.EN_K + k].tolist() for k in range(4)] == [[q, O.id_row(chr_[q]), sd] for q, sd in zip([0, 2, 1, 7], side)], w[9:13]
    assert (w[FAIR.EN_K + 4:] == -1).all()                                            # vacant projectile slots, boxes, items
    vec[0, FAIR.EN0 + 1:FAIR.EN0 + 3] = [0, 0]                                       # a row at my own spot: never my brawler
    assert (env.who(np.array([16]), vec)[0, 0] == -1).all() and env.who(np.zeros(0, np.int64), vec[:0]).shape == (0, O.N_ENT, 3)


def _check_intents(players, tiles, NS):
    """Env.intents and the intent reward in _finish_step on a synthetic solo battle (agents p0, p3): off = zeros and no
    state; tag "intent" none / native-AI battles = free; the staggered ticks; the block's encoding; signed progress into
    rew and term i_rew (x intent_scale); achieved -> counts + a re-plan at the next decision; engage invalid when the
    target goes down without my damage, achieved after it; a box broken by me (raw state2 row); the episode row"""
    NW = P.OBS_VEC + P.OBS_GRID
    mk = lambda **o: NS(pl=players(**o), fin=[0] if o.get("p0_eliminated") else [], over=0, tick=1, njumps=0, jumps=[], done=0,
                        alive=10, winner=-1, reserved=[0] * 8, obs_written=1)
    def battle(tag=None, **cfg):
        sl = slider_state(tiles.ravel(), 60, 40, ["Sniper"] * 10, np.random.default_rng(0))
        return NS(sl=sl, cfg={"tag": {"groups": [0] * 10, **(tag or {})}, **cfg}, hold={}, battle=1, pos={}, ptick=0, pjump=set(),
                  agents={0: 16, 3: 19}, wprev=set(), it={}, inst=NS(resp=mk(), obs_f32=np.zeros(10 * NW, np.float32)))
    def fake(self, i, r):                                # MAEnv._finish_step stand-in: base reward 0, p0's row when it is out
        for p, aid in self.I[i].agents.items(): self._trans.append((aid, 0.0, p in r.fin, {"hp": 0.0, "place": 0.0, "win": 0.0}, None))
        for p in r.fin: self.episodes.append({"player": p, "ret": 0.0, "terms": {}})
    def step(r):
        env.I[0].inst.resp = r; n0 = len(env._trans); sup, MAEnv._finish_step = MAEnv._finish_step, fake
        try: env._finish_step(0, r)
        finally: MAEnv._finish_step = sup
        return {a & 15: (rw, t) for a, rw, _, t, _ in env._trans[n0:]}
    env = Env.__new__(Env); env._trans, env.episodes, env.w, env.slider_scale, env.ticks, env.dead_aids = [], [], {}, 0.0, 2, set()
    env.I = [battle()]; ids = np.array([16, 19])
    assert not env.intents(ids).any() and env.I[0].it == {} and "i_rew" not in step(mk())[0][1]   # off: zeros, no state, no term
    env.intent_scale, env.p_steer, env.p_rand_intent, env.intent_jitter = 0.25, 1.0, 1.0, (0.0, 0.0)
    for tag, cfg in (({"intent": "none"}, {}), ({}, {"native_ctl": True})):       # eval / scenario tag, BC: always none
        env.I = [battle(tag, **cfg)]
        assert not any(env.intents(ids).any() for _ in range(12)) and not env.I[0].it[0]["steer"]
    env.I = [battle()]; first = {}
    for n in range(10):                                  # ticks staggered by player: p0 at its decision 0, p3 at 7
        blk = env.intents(ids); first.update({int(a): n for b, a in enumerate(ids) if blk[b].any() and int(a) not in first})
    assert first == {16: 0, 19: 7}, first
    s = env.I[0]; st = s.it[0]; mv = lambda: I.new(dict(kind="move_to", q=-1, pt=(1650.0 + 1500, 1650.0)), 5.0)
    st["act"] = mv(); st["cnt"]["move_to"][0] += 1; blk = env.intents(ids[:1])[0]
    assert blk[I.K["move_to"] - 1] == 1 and blk[:7].sum() == 1 and np.allclose(blk[O.I_XY:], [0.5, 0, 0.1, 1.0]), blk
    tr = step(mk(p0_x=2250)); assert np.isclose(tr[0][0], 0.25 * 0.01 * 2) and np.isclose(tr[0][1]["i_rew"], tr[0][0])   # 2 tiles closer
    assert np.isclose(env.intents(ids[:1])[0, O.I_LEFT], 1 - 1 / 40)
    tr = step(mk(p0_x=3150)); assert np.isclose(tr[0][0], 0.25 * (0.01 * 3 + 0.03)) and st["act"] is None and st["replan"]   # arrived
    assert st["cnt"]["move_to"][1] == 1 and env.intents(ids[:1]).any() and not st["replan"]   # re-planned at once (off its tick)
    st["act"] = mv(); st["cnt"]["move_to"][0] += 1
    tr = step(mk(p0_x=1050)); assert tr[0][0] < 0                               # away from it: negative (signed progress)
    e = lambda: I.new(dict(kind="engage", q=1, pt=None), 10.0, 10.0)
    st["act"] = e(); n_inv = st["cnt"]["engage"][3]
    tr = step(mk(p1_eliminated=1)); assert tr[0][0] == 0 and st["act"] is None and st["cnt"]["engage"][3] == n_inv + 1   # someone else's kill
    st["act"] = e(); step(mk(p0_damage_dealt=600, p1_damage_taken=600)); tr = step(mk(p1_eliminated=1))
    assert st["cnt"]["engage"][1] == 1 and tr[0][0] >= 0.25 * 0.05 and st["replan"]
    raw = s.inst.obs_f32.reshape(10, NW); o = FAIR.BX0; raw[0, o:o + 5] = [1, 900 / FAIR.R, 0, 1, 0.43]   # a box 3 tiles right of p0
    st["act"] = I.new(dict(kind="farm", q=-1, pt=(1650.0 + 900, 1650.0), obj="box"), 3.0)
    tr = step(mk(p0_box_damage=1000)); assert np.isclose(tr[0][0], 0.25 * 0.03) and st["act"] is not None   # box part (capped)
    raw[0, o:o + 5] = 0; tr = step(mk()); assert np.isclose(tr[0][0], 0.25 * 0.03) and st["cnt"]["farm"][1] == 1   # broken by me
    st["act"] = mv(); st["cnt"]["move_to"][0] += 1
    tr = step(mk(p0_eliminated=1)); assert tr[0][0] == 0 and st["cnt"]["move_to"][3] >= 1                  # knocked out: invalid
    row = env.episodes[-1]; got = sum(t.get("i_rew", 0.0) for a, _, _, t, _ in env._trans if a == 16)
    assert np.isclose(row["terms"]["i_rew"], round(got, 4)) and np.isclose(row["ret"], got) and row["intent_mode"] == "steered"
    assert row["intents"] == {k: v for k, v in st["cnt"].items() if v[0]} and row["intents"]["move_to"][3] == 1, row


def _check_planner(players, tiles, NS):
    """the planner hook (step E) on a synthetic solo battle (agent p0, enemy p1 10 tiles right): p_plan 1 -> the
    planner's pick starts, anchored to the true player, with its rule / reason (last_why, plan_rules); the same pick at
    the next tick keeps it; a gas pick preempts it; a random intent is never preempted; the planner's none and an
    unmatched anchor = no intent (reason kept); tag "intent": "plan" asks the planner even at p_plan 0; the episode row"""
    import planner as PL
    NW = P.OBS_VEC + P.OBS_GRID
    mk = lambda **o: NS(pl=players(**o), fin=[0] if o.get("p0_eliminated") else [], over=0, tick=1, njumps=0, jumps=[], done=0,
                        alive=10, winner=-1, reserved=[0] * 8, obs_written=1)
    def battle(tag=None):
        sl = slider_state(tiles.ravel(), 60, 40, ["Sniper"] * 10, np.random.default_rng(0))
        return NS(sl=sl, cfg={"tag": {"groups": [0] * 10, **(tag or {})}}, hold={}, battle=1, pos={}, ptick=0, pjump=set(),
                  agents={0: 16}, wprev=set(), it={}, inst=NS(resp=mk(), obs_f32=np.zeros(10 * NW, np.float32)))
    def fake(self, i, r):
        for p, aid in self.I[i].agents.items(): self._trans.append((aid, 0.0, p in r.fin, {"hp": 0.0, "place": 0.0, "win": 0.0}, None))
        for p in r.fin: self.episodes.append({"player": p, "ret": 0.0, "terms": {}})
    def obs(**kw):
        s8, e, g, c = PL.synth(**kw); return {"self": s8[None], "ent": e[None], "grid": g[None]}, c[None]
    env = Env.__new__(Env); env._trans, env.episodes, env.w, env.slider_scale, env.ticks, env.dead_aids = [], [], {}, 0.0, 2, set()
    env.intent_scale, env.p_steer, env.p_rand_intent, env.p_plan, env.intent_jitter = 0.25, 1.0, 0.0, 1.0, (0.0, 0.0)
    env.planner = PL.RulePlanner(); env.last_meta = np.array([[1650, 1650, 0, 60, 40]]); ids = np.array([16])
    env.I = [battle()]; st = None
    weak = obs(foes=[((10, 0), 0.4, None, False)])                    # p1 is 10 tiles right of p0, at 40 % as seen
    blk = env.intents(ids, *weak); st = env.I[0].it[0]
    assert blk[0, I.K["engage"] - 1] == 1 and st["act"]["q"] == 1 and st["act"]["rule"] == "engage" and st["rules"] == {"engage": [1, 1, 0]}
    assert env.last_why == [st["act"]["reason"]] and st["act"]["reason"] == "enemy 10 tiles E at 40 %: engaging", env.last_why
    for _ in range(10): env.intents(ids, *weak)                       # its next tick: the same pick keeps it
    assert st["rules"] == {"engage": [1, 1, 0]} and st["cnt"]["engage"][0] == 1
    gas = np.full((O.G, O.G), O.SEG.index("floor"), np.uint8); gas[:, 11:] = O.SEG.index("poison")
    g_o = obs(foes=[((10, 0), 0.4, None, False)], grid=gas)
    for _ in range(9): env.intents(ids, *g_o)                         # between ticks: no planner call
    assert st["act"]["rule"] == "engage"
    env.intents(ids, *g_o); assert st["act"]["rule"] == "gas" and st["act"]["kind"] == "move_to" and st["rules"]["gas"] == [1, 1, 1]
    assert st["act"]["pt"][0] < 1650 and env.last_why[0].startswith("in the gas")
    st["act"] = I.new(dict(kind="hold", q=-1, pt=(2250.0, 1650.0)), 2.0); n = dict(st["rules"])   # a random intent: never preempted
    for _ in range(10): env.intents(ids, *g_o)
    assert st["act"]["kind"] == "hold" and st["act"].get("rule") is None and st["rules"] == n and env.last_why == ["random"]
    env.I = [battle()]; blk = env.intents(ids, *obs()); st = env.I[0].it[0]   # nothing in view: the planner's none
    assert not blk.any() and st["act"] is None and env.last_why == ["no plan fits: free play"] and st["rules"] == {"none": [1, 0, 0]}
    env.I = [battle()]; env.intents(ids, *obs(foes=[((0, 5), 0.4, None, False)])); st = env.I[0].it[0]   # nobody there
    assert st["act"] is None and env.last_why[0].endswith("(target not matched)") and st["rules"] == {"engage": [1, 0, 0]}
    env.p_plan, env.p_rand_intent = 0.0, 1.0; env.I = [battle({"intent": "plan"})]   # evalp_plan: the planner on every tick
    env.intents(ids, *weak); st = env.I[0].it[0]
    assert st["plan_only"] and st["steer"] and st["act"]["rule"] == "engage"
    env.I[0].inst.resp = mk(p0_eliminated=1); sup, MAEnv._finish_step = MAEnv._finish_step, fake
    try: env._finish_step(0, env.I[0].inst.resp)
    finally: MAEnv._finish_step = sup
    row = env.episodes[-1]; assert row["plan_rules"] == {"engage": [1, 1, 0]} and row["intents"]["engage"] == [1, 0, 0, 1], row


TEAM_SLIDERS = ("protect", "leash")   # fire only with a mate: normalised over team battles


def norm_from(rows, budget=0.5):
    """{slider: factor} so that each term's mean per-battle sum of |term| (row "sa_<slider>"; older rows: |"s_<slider>"|)
    becomes `budget` (0.5: a slider at weight 1 is worth ~0.5 per battle, against the 8 of place + win). |term| per step,
    not |sum|: a signed term (leash: band +, clump -) would cancel and get a huge factor. Team sliders over team battles
    only (in solo they are 0 by definition). A term that never fired: 1.0"""
    rows = [r for r in rows if "sliders" in r and not r.get("restart")]
    a = lambda r, k: r["terms"]["sa_" + k] if "sa_" + k in r["terms"] else abs(r["terms"].get("s_" + k, 0.0))
    use = lambda k: [r for r in rows if k not in TEAM_SLIDERS or r["tag"].get("team_size", 1) > 1]
    m = {k: float(np.mean([a(r, k) for r in use(k)])) if use(k) else 0.0 for k in SL}
    return {k: round(budget / v, 4) if v > 1e-6 else 1.0 for k, v in m.items()}, m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12); ap.add_argument("--minutes", type=float, default=5)
    ap.add_argument("--agents", type=int, default=10); ap.add_argument("--ticks", type=int, default=2)
    ap.add_argument("--out", default="bench.jsonl"); ap.add_argument("--gen", type=int, default=0, help="instances on generated maps")
    ap.add_argument("--native", type=int, default=0, help="1 = the native AI plays the agents (observed; the slider-norm reference)")
    ap.add_argument("--episodes", default="", help="also write every episode row to this jsonl")
    ap.add_argument("--norm", default="", help="RUN dir or episodes jsonl -> slider_norm factors (no game)")
    ap.add_argument("--check", action="store_true", help="slider reward self-check (no game)")
    a = ap.parse_args()
    if a.check: return _check()
    if a.norm:
        fn = os.path.join(a.norm, "episodes.jsonl") if os.path.isdir(a.norm) else a.norm
        f, m = norm_from([json.loads(l) for l in open(fn)])
        print("mean |term| per player and battle:", {k: round(v, 4) for k, v in m.items()}); print(json.dumps(f)); return
    bf = make_battle_fn(a.agents, gen=use_genmaps(a.gen) if a.gen else None)
    battle_fn = (lambda rng, i: {**bf(rng, i), "native_ctl": True}) if a.native else bf
    env = Env(a.n, battle_fn, ticks=a.ticks, fair=True, max_ticks=4000)
    rng = np.random.default_rng(0); t0 = None; steps = 0
    try:
        while t0 is None or time.time() - t0 < a.minutes * 60:
            obs, ids, _ = env.poll(min_ready=1, max_wait=0.003)
            if not len(ids): continue
            if t0 is None: t0 = time.time()     # clock starts at the first observation (after boot)
            B = len(ids); steps += B
            if steps == B: assert env.cond(ids).shape == (B, O.N_COND)
            act = np.stack([rng.integers(0, 17, B), rng.integers(0, 3, B), rng.integers(0, 360, B), rng.integers(0, 8, B)], 1)
            env.send(ids, act)
    finally:
        dt = time.time() - (t0 or time.time()); env.close()
    with open(a.out, "w") as f:
        for c in env.crashes: f.write(json.dumps(c) + "\n")
    if a.episodes:
        with open(a.episodes, "w") as f:
            for r in env.episodes: f.write(json.dumps(r) + "\n")
    print("n %d agents %d ticks %d: %.0f decisions/s, %d battles, %d episodes, %d restarts (%s), %d brawlers, %d maps" % (
        a.n, a.agents, a.ticks, steps / max(dt, 1e-9), env.stats["battles"], len(env.episodes), env.stats["restarts"],
        a.out, len(heroes()), len(locations())))
    rows = [e["terms"] for e in env.episodes if "sliders" in e]
    print("slider terms per episode (mean over %d): %s" % (len(rows), {m: round(float(np.mean([t["s_" + m] for t in rows])), 3) for m in SL} if rows else {}))


if __name__ == "__main__":
    sys.exit(main())
