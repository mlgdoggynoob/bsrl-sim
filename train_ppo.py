"""Stage 1: BC from the native AI, then PPO, Piper on one Showdown map, ObsV5 observation (WSL, after `source env.sh`).

    python -m train_ppo --run s1 --hours 3            # outputs $SIM_WORK/runs/s1/
    python -m train_ppo --run t --smoke               # 2 instances, tiny rollouts, 3 updates: plumbing check
    python -m train_ppo --check                       # self-check of the update-time helpers (no game)

* Updates 1..--bc-updates: all 10 players are driven by the native AI and observed; loss = cross-entropy to its action
  (env_v5.Env labels) + value regression. Then PPO: k agents per battle (--kmix) vs the native AI, clip + entropy +
  beta * KL(BC snapshot || policy) with beta decaying to --kl-floor over --kl-updates updates (nirkt's recipe).
* GRU: every row stores its input hidden state; updates run chunks of --seq consecutive steps from the stored state.
* Eval inside the run every --eval-min minutes: seeds 1..--eval-episodes, player 0 = the policy vs 9 native (sampled
  actions, not trained on) -> evals.jsonl + ckpt_u<update>.pt. Stage 1 gate: mean rank <= 3.0 at 500 episodes.
* Dashboard: progress.jsonl (one row per update), evals.jsonl, replays/ (one battle of instance 0 per update: all
  players + what the focus agent's policy saw and did) and a copy of viz.html. See README "Dashboard".
* Self-play (PPO phase): --sp of the battles have all 10 players on policies; 0-7 of them (tag "opp") are played by a
  league snapshot (league/u*.pt: saved every --league-every updates), the rest by the learner. PFSP: --opp-slots
  snapshots are loaded at once (a battle is pinned to one slot; one slot is redrawn every --opp-hold updates) and a
  snapshot is drawn with weight ((10 - r) / 9) ** --pfsp-p, r = running mean rank of its players against the learner
  (league/pfsp.json; 5.5 = equal, lower = it beats the learner). When the pool is full the weakest one is evicted.
  The other battles are k agents vs the native AI as before. Only learner rows are trained on.
* Critic input `priv` (true state of all 10 players): see model.py.
* Eval = a frozen copy of the weights: "eval" vs 9 native (sanity gate) and "evalb" vs 9 copies of --base (default: the
  --resume checkpoint; from scratch: the BC snapshot) -> b_rank in evals.jsonl: 5.5 = equal to base, lower = stronger.
* Evals run on the last --eval-n instances only; the others keep training.
* Sliders (env_v5): --slider-scale x sum(weight x --slider-norm factor x term); weights per battle from --slider-sample.
  Evals use sampled weights unless --eval-sliders balanced; --eval-presets a,b adds "evalp" battles (same seeds vs 9
  native, player 0 on the preset's weights, + balanced) -> p_<preset> in evals.jsonl, scorecard.py per preset.
* Live value (--vlive 1, default 0 = off): model.Policy.vl (no priv, detached features: never changes the policy) is
  trained to its own lambda-return of the reward without the intent reward (rew - rew_int; rew_int = terms "i_rew", 0
  with intents off), its values from one no-grad pass over the rollout (model.Policy.row_feats: acting is unchanged).
  progress.jsonl: expl_var_live (next to expl_var, the critic with priv), vloss_live, extra_s (the pass). The heads that
  never act (model.NONACT) have their own Adam ("opt_x" in the checkpoint) and gradient clip, so the main optimizer and
  its clip see exactly the acting network's parameters.
* Aux heads (--aux-w W, default 0 = no loss, no gradient): W x model.aux_losses added to the BC / PPO loss, gradients
  into the encoders / trunk / GRU (not the policy / value heads). Labels from the sim's true state: env_v5.Env.aux_now
  at poll time (buffer columns tpos talive me gm be) + the transition term "te" (enemy damage taken), assembled at
  update time by aux_labels. progress.jsonl readouts on the pre-update predictions (row_pass): aux_fut_tiles (median
  error of the 1 s enemy position) next to aux_fut_cv_tiles (constant velocity from the seen velocity) and
  aux_fut_still_tiles (stays where seen), aux_fut_match (share of seen enemy slots matched to a true enemy),
  aux_hit_auc, aux_gas_mae_tiles, aux_bush_auc (+ base rates, aux_loss_*).
  Replays: the recorded row's predictions (frame "x") and truth (frame "xt"); viz draws them.
* Hard scenarios (--eval-scenarios 1, default 0 = off; every --scenario-every-th eval): scenarios.py's set (7 scenarios
  x 2 maps x 2 brawler picks x --scenario-seeds layouts) joins the eval queue as kind "evalscn", played by the frozen
  eval copy on the eval instances -> scenarios.jsonl (one row per eval: pass rate + mean scores per scenario),
  scenario_episodes.jsonl, every episode's replay in replays/scn/ (viz: failures first).
* Intents (--intent-scale S > 0 switches them on; default 0 = off: the intent block of s is all zeros, no intent reward):
  env_v5.Env.intents after the observation build gives the block (obs_v5 v5.5: s = cat[self, cond, intent]); per agent
  and battle --p-steer of the agents are steered, the rest free (always none); a steered agent's planner tick takes the
  rule planner's pick (planner.py, which may be none) with --p-plan (default 0 = no planner: the step-D behaviour;
  design 0.5), a random valid intent with --p-rand-intent, else none; a held planner intent may be preempted by the
  planner (gas / higher rule with a target change > 2 tiles), a random one never. Reward += S x intent.step_reward
  (terms "i_rew" = rew_int, which the live value excludes). BC battles (native AI) and evals (tag "intent": "none",
  scenario battles too) play free; --eval-plan 1 adds kind "evalp_plan" (the eval seeds vs 9 native, player 0 on the
  planner at every tick) -> pl_rank / pl_ci95 / pl_win / pl_top3 / pl_follow / pl_rules in evals.jsonl next to the
  free-play eval of the same seeds. progress.jsonl (only with S > 0): t_i_rew (mean per episode), intents {kind:
  [started, achieved, timeout, invalid]}, intent_follow (achieved / started) and with the planner plan_rules {rule:
  [picked, started, preempted]} over the recent episodes; replay frames carry "i" (the active intent: kind, target dx /
  dy, radius, time left, "y" its reason) or "iy" (the planner's reason for none).
* Gadgets (--gadgets 1, default 0 = off; obs v5.7, issue #3): every battle but the hard scenarios gives each player one
  of its brawler's gadget cards (env_v5.with_gadgets, drawn from MAEnv's rng: rng_b's draws stay the same) and the
  observation's self 3 = env_v5.Env.gadget (the host's gadget state: usable now); the fire head's gadget class
  (model.mask_fire) is allowed only then. Off: self 3 = 0, the class stays masked. fire_hist has one bin per
  obs_v5.FIRE class.
* Hypercharge (--hyper 1, default 0 = off; obs v5.8, issue #4): every battle but the hard scenarios equips each player's
  hypercharge card (env_v5.with_hyper, no draw) and self 4 = env_v5.Env.hyper (the host's state: can activate now); the
  fire head's hypercharge class is allowed only then. Off: self 4 = 0, the class stays masked.
* Star powers (--star-powers 1, default 0 = off; issue #20, no observation change): every battle but the hard scenarios
  gives each player one of its brawler's star power cards that this build really runs: the ones the star power probe found read
  plus the ones the host re-implements (issue #47) that star_check confirmed (env_v5.with_star_powers over star_audit.equipped(), drawn from MAEnv's rng after the gadgets). The policy does not see it.
* Gears (--gears 1, default 0 = off; issue #51, no observation change): every battle but the hard scenarios gives each
  player two gears its brawler may carry whose effect gear_check confirmed (env_v5.with_gears over gear_check.LIVE, drawn
  from MAEnv's rng after the star powers). The policy does not see them.
shortcut: no exploiters (a second learner trained only to beat this one); add them if b_rank flattens again with PFSP.
"""
import argparse, glob, json, os, shutil, signal, sys, time
import numpy as np
import torch
from nbpc import diversity as D
from nbpc.maenv import REWARD_W, TERMS
import env_v5 as E, obs_v5 as O, scenarios as SC
from model import Policy, HID, PRIV, NONACT, dist_logp_ent, masked_kl, act_stacked, aux_losses

NS = O.N_S                       # s = cat[self, cond, intent] (obs v5.5)
HERE = os.path.dirname(os.path.abspath(__file__))


class Buffer:
    """transition rows: observation + hidden state at action time, action, logp, value; reward / done on completion"""
    F = {"s": ((NS,), np.float16), "ent": ((O.N_ENT, O.F_ENT), np.float16), "grid": ((O.G, O.G), np.uint8), "h": ((HID,), np.float16), "priv": ((PRIV,), np.float16),
         "act": ((4,), np.int16), "logp": ((), np.float32), "val": ((), np.float32), "rew": ((), np.float32),
         "done": ((), bool), "complete": ((), bool), "bc": ((), bool), "dead": ((), bool),
         "rew_int": ((), np.float32)}   # the intent reward inside rew (terms "i_rew"; 0 with intents off): the live value's target excludes it

    def __init__(self, cap):
        self.cap, self.n = cap, 0
        for k, (shape, dt) in self.F.items(): setattr(self, k, np.zeros((cap,) + shape, dt))

    def add(self, **rows):
        B = len(rows["act"]); sl = slice(self.n, self.n + B)
        if self.n + B > self.cap: raise RuntimeError("buffer full")
        for k in self.F: getattr(self, k)[sl] = rows.get(k, 0)
        self.n += B
        return np.arange(sl.start, sl.stop)

    def compact(self, keep):
        k = np.asarray(keep, np.int64)
        for name in self.F: a = getattr(self, name); a[:len(k)] = a[k]
        self.n = len(k)


def replay_head(s, upd):
    """a replay's header from instance state s (live map tiles as seg letters)"""
    tag = s.cfg["tag"]
    tiles = O._tile_lut()[np.clip(np.asarray(s.map_tiles).reshape(s.H, s.W) % 1000000 + 1, 0, 255)] if s.map_tiles is not None else np.zeros((s.H, s.W), np.uint8)
    return {"battle": s.battle, "update": upd, "kind": tag["kind"], "loc": tag["loc"], "chr": tag["chr"], "ctl": s.ctl, "W": s.W, "H": s.H,
            "groups": tag.get("groups"),   # scorecard.py: teammates are not targets
            "seg": list(O.SEG) + ["unknown"], "ent": list(O.ENT), "map": ["".join(chr(97 + c) for c in row) for row in tiles], "frames": []}


def replay_frame(s, ids, b, o, act):
    """one replay frame: row b of the poll (its agent = the focus), every player's true state, what the policy saw / did"""
    r = s.inst.resp; e = o["ent"][b]; e = e[e[:, 0] > 0.5]
    return {"t": int(r.tick), "f": int(ids[b]) & 15, "a": [int(x) for x in act[b]],
            "p": [[int(r.pl[p].x), int(r.pl[p].y), int(r.pl[p].hp), int(r.pl[p].max_hp), int(bool(r.pl[p].alive) and not r.pl[p].eliminated)] for p in range(10)],
            "e": [[int(x[1:1 + len(O.ENT)].argmax()), round(float(x[O.XY]), 3), round(float(x[O.XY + 1]), 3), round(float(x[O.HP]), 2)]
                  + id_name(x) for x in e],                # + the brawler the policy was given (v5.6), when known
            "s": [round(float(x), 2) for x in o["self"][b, :5]], "g": "".join(chr(97 + c) for c in o["grid"][b].ravel()),
            **intent_frame(o, b)}


def id_name(x):
    """[name] of the brawler whose obs_v5.brawler_stats an entity row's identity columns hold (known rows), else []"""
    if x[O.ID_KNOWN] < 0.5: return []
    names, lut = O.id_lut(); d = ((lut[:-1] - x[O.ID0:O.ID0 + 13].astype(np.float32)) ** 2).sum(1)
    return [names[int(d.argmin())]] if d.min() < 1e-6 else []


def intent_frame(o, b):
    """replay frame "i" of row b when it has an active intent (o["intent"] = env_v5.Env.intents' block): kind, target
    dx, dy (10-tile units, as the policy sees it), radius / 10 tiles, time left 1 -> 0, + "y" = its reason (o["i_why"] =
    env_v5.Env.last_why: the planner's text or "random"); without one, "iy" = the planner's reason for none, if any"""
    x = o.get("intent"); why = o.get("i_why"); why = why[b] if why is not None and b < len(why) else None
    if x is None or not x[b, :O.I_XY].any(): return {"iy": why} if why else {}
    out = {"k": O.INTENTS[1 + int(x[b, :O.I_XY].argmax())], "t": [round(float(x[b, O.I_XY]), 3), round(float(x[b, O.I_XY + 1]), 3)],
           "r": round(float(x[b, O.I_RAD]), 3), "l": round(float(x[b, O.I_LEFT]), 2)}
    return {"i": {**out, "y": why} if why else out}


def policy_s(env, ids, o):
    """the policy's vector input s = cat[self, cond, intent] of a poll (+ o["intent"] = the block, for the replay)"""
    c = env.cond(ids); o["intent"] = env.intents(ids, o, c); o["i_why"] = getattr(env, "last_why", None)   # reasons: replay frames
    return np.concatenate([o["self"], c, o["intent"]], 1)


class Recorder:
    """one battle of instance 0 per update -> replays/u<update>.json (+ index.json), the newest `keep` kept"""
    def __init__(self, out, keep=30):
        self.dir = os.path.join(out, "replays"); os.makedirs(self.dir, exist_ok=True)
        self.keep, self.want, self.cur, self.index = keep, True, None, []

    def row(self, env, ids):
        """index in ids of the agent frame() would record now (instance 0's battle), else None"""
        rows = np.nonzero((ids >> 4) == env.I[0].battle)[0]
        return int(rows[0]) if len(rows) and (self.cur is not None or self.want) else None

    def frame(self, env, ids, o, act, upd, x=None):
        """x = aux_readout of the recorded row (--aux-w): the frame gets "x" and the truth "xt" (env_v5.Env.aux_now: gas
        margin, hidden bush enemies by sector; "h" = enemy damage taken this step; the 1 s positions are the later frames' "p")"""
        s = env.I[0]; rows = np.nonzero((ids >> 4) == s.battle)[0]
        if self.cur is not None and (self.cur["battle"] != s.battle or len(self.cur["frames"]) >= 600):   # 600 steps = 1 min of game
            self.flush()
        if not len(rows) or (self.cur is None and not self.want): return
        r = s.inst.resp; b = int(rows[0])
        if self.cur is None:
            self.cur = replay_head(s, upd); self.want = False
        self.cur["frames"].append(replay_frame(s, ids, b, o, act))
        if x is not None:
            A = E.aux_split(env.aux_now(ids[b:b + 1])); pl = r.pl[int(ids[b]) & 15]
            self.cur["frames"][-1].update(x=x, xt={"g": round(float(A["gm"][0]), 1), "b": [int(v) for v in A["be"][0]], "h": int(pl.damage_taken > pl.gas_damage)})

    def flush(self):
        c, self.cur = self.cur, None
        if c is None or len(c["frames"]) < 20:
            self.want = True; return
        name = "u%04d.json" % c["update"]
        json.dump(c, open(os.path.join(self.dir, name), "w"), separators=(",", ":"))
        self.index = [x for x in self.index if x["file"] != name] + [{"file": name, "update": c["update"], "kind": c["kind"], "frames": len(c["frames"])}]
        for x in self.index[:-self.keep]: os.remove(os.path.join(self.dir, x["file"]))
        self.index = self.index[-self.keep:]
        json.dump(self.index, open(os.path.join(self.dir, "index.json"), "w"))


def priv(env, ids):
    """(B, PRIV) critic-only input: every player's true offset (/ 20 tiles), hp fraction, alive; zeros for the dead"""
    by = {s.battle: s for s in env.I}; cache = {}; out = np.zeros((len(ids), 10, 4), np.float32)
    for b, a in enumerate(ids):
        k = int(a) >> 4
        if k not in cache:
            pl = by[k].inst.resp.pl
            cache[k] = np.array([[pl[q].x, pl[q].y, pl[q].hp / max(1, pl[q].max_hp), bool(pl[q].alive) and not pl[q].eliminated] for q in range(10)], np.float32)
        c = cache[k].copy(); c[:, :2] = (c[:, :2] - c[int(a) & 15, :2]) / 6000.0; c[c[:, 3] < 0.5] = 0; out[b] = c
    return out.reshape(len(ids), PRIV)


def chunks(traj, L):
    """trajectories (lists of buffer rows in time order) -> (N, L) row indices, -1 = padding"""
    out = [r[i:i + L] + [-1] * (L - len(r[i:i + L])) for r in traj for i in range(0, len(r), L)]
    return np.array(out, np.int64).reshape(-1, L)


def eval_items(a):
    """the battles of one eval: (seed, kind, preset) for eval / evalb, then per --eval-presets name (balanced first, the
    paired reference) the same seeds as kind "evalp" vs 9 native, then with --eval-plan the eval seeds as kind
    "evalp_plan" (player 0 on the rule planner: eval_intent)"""
    pre = [p for p in a.eval_presets.split(",") if p]; pre = (["balanced"] + [p for p in pre if p != "balanced"]) if pre else []
    return ([(sd, "eval", None) for sd in range(1, a.eval_episodes + 1)] + [(sd, "evalb", None) for sd in range(1, a.evalb_episodes + 1)]
            + [(sd, "evalp", p) for p in pre for sd in range(1, a.eval_episodes + 1)]
            + [(sd, "evalp_plan", None) for sd in range(1, a.eval_episodes + 1) if getattr(a, "eval_plan", 0)])


def scenario_flags(ap):
    """step-S flags of the hard-scenario evals (scenarios.py), shared with train_fast (default off = the original evals)"""
    ap.add_argument("--eval-scenarios", type=int, default=0, help="1 = the hard-scenario set (scenarios.py, 7 x 16 battles) joins the evals")
    ap.add_argument("--scenario-every", type=int, default=1, help="with --eval-scenarios: on every k-th eval only")
    ap.add_argument("--scenario-seeds", type=int, default=4, help="layouts per (scenario, map, pick): 16 episodes per scenario at 4 (--smoke: 1)")


def scenario_items(a, n_eval, upd):
    """the scenario battles of eval number n_eval (0 = the first) as eval queue items (seed, "evalscn", item)"""
    if not a.eval_scenarios or n_eval % max(1, a.scenario_every): return []
    return [(it["seed"], "evalscn", it) for it in SC.items(seeds=a.scenario_seeds, update=upd)]


def scenario_eval(rows, ev, minutes, f_sum, f_ep):
    """an eval's scenario episodes (kind evalscn) -> one row in scenarios.jsonl (scenarios.summary per scenario) and
    their scenario_episodes.jsonl rows; None without any (scn_s = eval start to its last scenario episode)"""
    rs = [r for r in rows if r["tag"]["kind"] == "evalscn"]
    if not rs: return None
    good = [r for r in rs if r.get("scn")]
    sm = {"update": ev["update"], "minutes": minutes, "scn_s": round((ev.get("t_scn") or time.time()) - ev["t0"], 1),
          "episodes": len(rs), "invalid": len(rs) - len(good), **SC.summary(good)}
    f_sum.write(json.dumps(sm) + "\n"); f_sum.flush()
    for r in good: f_ep.write(json.dumps(SC.episode_row(r)) + "\n")
    f_ep.flush()
    print("[scenarios]", json.dumps({k: (v["pass"] if isinstance(v, dict) else v) for k, v in sm.items()}), flush=True)
    return sm


def eval_tag(a, preset):
    """slider weights of an eval battle (env_v5 tag "sliders", every player): a preset's; --eval-sliders balanced: all
    1.0; else none (sampled as in training)"""
    if preset is None and a.eval_sliders != "balanced": return {}
    p = preset or "balanced"
    return {"sliders": [float(v) for v in O.preset_vec(p)], "preset": p}


def eval_intent(kind):
    """the eval battles' tag "intent": evalp_plan -> "plan" (env_v5: the planner at every tick), every other -> "none"
    (free play)"""
    return "plan" if kind == "evalp_plan" else "none"


def eval_plan(rows):
    """{"pl_<k>": ...} of an eval's evalp_plan rows (player 0, one per seed): eval_summary's episodes / rank / ci95 / win /
    top3 (compare with the same seeds' free-play "eval" numbers) + pl_follow = achieved / started intents; {} without"""
    rs = list({r["seed"]: r for r in rows if r["tag"]["kind"] == "evalp_plan" and r["player"] == 0}.values())
    if not rs: return {}
    st = intent_stats(rs)
    return {**{"pl_" + k: v for k, v in eval_summary(rs).items() if k in ("episodes", "rank", "ci95", "win", "top3")},
            "pl_follow": st["intent_follow"], "pl_rules": st.get("plan_rules", {})}


def eval_presets(rows):
    """{"p_<preset>": eval_summary} of an eval's evalp rows (player 0, one per seed)"""
    out = {}
    for p in sorted({r["tag"].get("preset") for r in rows if r["tag"]["kind"] == "evalp"} - {None}):
        out["p_" + p] = eval_summary(list({r["seed"]: r for r in rows if r["tag"]["kind"] == "evalp" and r["tag"].get("preset") == p and r["player"] == 0}.values()))
    return out


def slider_flags(ap):
    """step-A slider flags, shared with train_fast (defaults = the original behaviour)"""
    ap.add_argument("--slider-norm", default="", help="'' = terms unscaled, 'measured' = env_v5.NORM_MEASURED, or a JSON file {slider: factor}")
    ap.add_argument("--slider-sample", default="uniform", choices=("uniform", "mix"), help="per-battle slider weights: U(0, 2) or the preset mix (env_v5.sample_sliders)")
    ap.add_argument("--eval-sliders", default="random", choices=("random", "balanced"), help="eval / evalb weights: sampled as in training, or all 1.0")
    ap.add_argument("--eval-presets", default="", help="comma list of obs_v5.PRESETS: each also plays the eval seeds vs native (kind evalp, + balanced)")


def intent_flags(ap):
    """step-D intent flags, shared with train_fast (default --intent-scale 0 = off: zero block, no intent reward)"""
    ap.add_argument("--intent-scale", type=float, default=0.0, help="weight of the intent reward; > 0 switches intents on (start 0.25)")
    ap.add_argument("--p-steer", type=float, default=0.7, help="with intents on: share of agents per battle that get intents (the rest play free)")
    ap.add_argument("--p-rand-intent", type=float, default=0.3, help="with intents on: chance per planner tick of a random valid intent (else none)")
    ap.add_argument("--p-plan", type=float, default=0.0, help="with intents on: chance per planner tick of the rule planner's pick (planner.py; design 0.5; 0 = off)")
    ap.add_argument("--eval-plan", type=int, default=0, help="1 = evals also play the eval seeds with player 0 on the rule planner (kind evalp_plan; needs --intent-scale > 0)")


def set_intents(a):
    """the intent flags -> env_v5.Env (class attributes: train_fast's workers inherit them); the rule planner exists only
    with --p-plan > 0 or --eval-plan (else Env.planner None: the step-D behaviour)"""
    if (a.p_plan > 0 or a.eval_plan) and not a.intent_scale: raise SystemExit("--p-plan / --eval-plan need --intent-scale > 0")
    E.Env.intent_scale, E.Env.p_steer, E.Env.p_rand_intent, E.Env.p_plan = a.intent_scale, a.p_steer, a.p_rand_intent, a.p_plan
    E.Env.intent_jitter = O.NOISE["jitter"] if a.noise else (0.0, 0.0)
    if a.p_plan > 0 or a.eval_plan:
        import planner as PL
        E.Env.planner = PL.RulePlanner(noisy=bool(a.noise))   # clean obs: no false detections to confirm


def intent_stats(rows):
    """progress.jsonl intent fields of episode rows (env_v5 "intents" / terms "i_rew"): mean i_rew, summed counts per
    kind, achieved / started; + plan_rules {rule: [picked, started, preempted]} summed when rows have them (--p-plan)"""
    rows = [r for r in rows if "intents" in r]
    cnt = {k: [0, 0, 0, 0] for k in O.INTENTS[1:]}
    for r in rows:
        for k, v in r["intents"].items(): cnt[k] = [x + y for x, y in zip(cnt[k], v)]
    st = sum(v[0] for v in cnt.values())
    return {"t_i_rew": round(float(np.mean([r["terms"].get("i_rew", 0.0) for r in rows])), 4) if rows else None,
            "intents": {k: v for k, v in cnt.items() if v[0]}, "intent_follow": round(sum(v[1] for v in cnt.values()) / st, 3) if st else None,
            "steered": round(float(np.mean([r.get("intent_mode") == "steered" for r in rows])), 3) if rows else None,
            **({"plan_rules": pr} if (pr := _plan_rules(rows)) else {})}


def _plan_rules(rows):
    """episode rows' "plan_rules" summed: {rule: [picked, started, preempted]} in planner.RULES order"""
    tot = {}
    for r in rows:
        for k, v in (r.get("plan_rules") or {}).items(): tot[k] = [x + y for x, y in zip(tot.get(k, [0, 0, 0]), v)]
    import planner as PL
    return {k: tot[k] for k in PL.RULES if k in tot}


TR_X = ("i_rew",)   # transition terms the buffer keeps besides rew / done (train_fast's workers send these)


def head_flags(ap):
    """step-C flags of the heads that never act, shared with train_fast (defaults = off, the original behaviour)"""
    ap.add_argument("--vlive", type=int, default=0, help="1 = train the live value head (model.Policy.vl: no priv, return without the intent reward)")
    ap.add_argument("--aux-w", type=float, default=0.0, help="weight of the aux head losses (model.Policy.aux; 0 = off: no loss, no gradient; start 0.1)")


def _opt_tail(opt, sd):
    """an optimizer state saved before parameters were appended to its groups (obs v5.7: model.Policy.fire_x is the tail
    of the acting parameters) -> the state with fresh ids for the new tail parameters (no moments: Adam starts them
    fresh); None if the groups do not match that way (fewer groups, fewer parameters now, or a moment that does not fit
    its parameter's shape)"""
    gs, cur = sd["param_groups"], opt.param_groups
    if len(gs) != len(cur) or any(len(g["params"]) > len(c["params"]) for g, c in zip(gs, cur)): return None
    for g, c in zip(gs, cur):
        for i, p in zip(g["params"], c["params"]):
            for v in sd["state"].get(i, {}).values():
                if torch.is_tensor(v) and v.dim() == p.dim() and not all(a <= b for a, b in zip(v.shape, p.shape)): return None
    nxt = 1 + max([i for g in gs for i in g["params"]], default=-1); groups = []
    for g, c in zip(gs, cur):
        n = len(c["params"]) - len(g["params"]); groups.append({**g, "params": list(g["params"]) + list(range(nxt, nxt + n))}); nxt += n
    return {"state": sd["state"], "param_groups": groups}


def load_opt(opt, sd, what="optimizer state", net=None):
    """an optimizer state from a checkpoint; moments of a parameter that grew since (new input columns, zero-padded by
    model.load_state_dict) are padded the same way (model.pad_param by the parameter's name in net: the entity inputs
    get their new columns before the lead columns; without net, or a tail input: zeros at the end; torch loads them
    unchecked and the first step would fail); parameters appended since (model.Policy.fire_x, v5.7) start with fresh
    moments (_opt_tail); any other change of the parameter set -> the fresh Adam is kept (printed)"""
    if not sd: return
    try: opt.load_state_dict(sd)
    except ValueError:
        t = _opt_tail(opt, sd)
        if t is None: print("%s not loaded (parameters changed): fresh Adam" % what, flush=True); return
        opt.load_state_dict(t); print("%s loaded; %d parameters added since start fresh" % (what, sum(
            len(c["params"]) - len(g["params"]) for g, c in zip(sd["param_groups"], opt.param_groups))), flush=True)
    from model import pad_param
    name = {id(p): k for k, p in net.named_parameters()} if net is not None else {}
    for g in opt.param_groups:
        for p in g["params"]:
            st = opt.state.get(p, {})
            for k, v in st.items():
                if torch.is_tensor(v) and v.dim() == p.dim() and v.shape != p.shape:
                    st[k] = pad_param(name.get(id(p), ""), v, p.detach())


def split_params(net):
    """(acting parameters = the main optimizer's, in the original order; the NONACT heads' parameters)"""
    named = list(net.named_parameters())
    return [p for k, p in named if not k.startswith(NONACT)], [p for k, p in named if k.startswith(NONACT)]


def gae(traj, pending, final, rew, val, gamma, lam, done):
    """GAE per buffer row of the rollout's trajectories -> (advantage, lambda-return); bootstrap = the value of the
    pending (next) row, 0 after the end"""
    adv = np.zeros(len(rew), np.float32); ret = np.zeros(len(rew), np.float32)
    for aid, rows in traj.items():
        nxt = 0.0 if aid in final else float(val[pending[aid]]) if aid in pending else float(val[rows[-1]]); last = 0.0
        for j in rows[::-1]:
            nt = 0.0 if done[j] else 1.0
            last = rew[j] + gamma * nxt * nt - val[j] + gamma * lam * nt * last
            adv[j] = last; ret[j] = last + val[j]; nxt = val[j]
    return adv, ret


def expl_var(ret, val):
    return 1 - float(((ret - val) ** 2).mean() / (ret.var() + 1e-8)) if len(ret) else 0.0


@torch.no_grad()
def row_pass(net, g, n, fns, bs=4096):
    """one no-grad pass over buffer rows 0..n-1 from their stored GRU state (model.Policy.row_feats, the acting math):
    {name: fn(net, xc, s, ent) for every row} (fn -> a tensor), concatenated over batches of bs rows"""
    out = {k: [] for k in fns}
    for a in range(0, n, bs):
        s, ent = g["s"][a:a + bs], g["ent"][a:a + bs]; xc = net.row_feats(s, ent, g["grid"][a:a + bs], g["h"][a:a + bs])
        for k, fn in fns.items(): out[k].append(fn(net, xc, s, ent))
    return {k: torch.cat(v) for k, v in out.items()}


def live_targets(a, net, g, buf, traj, pending, final, n, use_rows):
    """--vlive: the live value of every row (row_pass) and its lambda-return of rew - rew_int -> (values, returns,
    expl_var_live over the trained rows)"""
    vl = row_pass(net, g, n, {"vl": lambda net_, xc, s, ent: net_.value_live(xc)})["vl"].float().cpu().numpy()
    _, ret = gae(traj, pending, final, buf.rew[:n] - buf.rew_int[:n], vl, a.gamma, a.lam, buf.done[:n])
    return vl, ret, expl_var(ret[use_rows], vl[use_rows])


Buffer.F.update({"tpos": ((10, 2), np.float32), "talive": ((10,), bool), "me": ((), np.int8), "gm": ((), np.float32),
                 "be": ((8,), bool), "te": ((), np.float32)})   # aux labels: env_v5.AUX columns + the transition's te
TR_X = TR_X + ("te",)
FUT_GATE, FUT_K = 1.5, 10   # tiles: a slot is that enemy within 1.5 tiles of where it is seen (noise ~0.4, latency <= 0.2 s); 10 rows = 1 s


def aux_labels(buf, traj, final, n):
    """update-time aux labels of buffer rows 0..n-1 (numpy, the model.aux_losses keys) from the trajectories' row lists
    (time order), the env_v5.AUX columns and the transitions' te:
      fut (n, 9, 2) / fut_m: enemy-block slot k of row j greedily matched to the nearest alive true enemy within FUT_GATE
        of where the slot is seen (relative to me at j); label = that enemy's true position FUT_K rows later (same
        trajectory, still alive) minus mine at j, / 10 tiles, clip +-2.5
      hit / hit_m: enemy damage taken in the transitions of rows j .. j+9; known once 10 transitions follow, the
        trajectory ended, or a hit came already
      gas: gas margin at j / 10 tiles, 0 in the gas; bush: "be"; m: rows of an alive (not respawning) agent
      cv, still (n, 9, 2): the fut baselines (metrics only): constant velocity from the seen velocity (moved on by the
        frame's latency model.LAT, relative to me), and stays where seen; fut_p (n, 9): present enemy slots of rows with
        a row 1 s later (metrics only: the share matched to a true enemy)"""
    from model import AUX_SLOTS, LAT
    pos = np.full(n, -1, np.int64); hit = np.zeros(n, np.float32); hit_m = np.zeros(n, np.float32)
    for aid, r in traj.items():
        r = np.asarray(r, np.int64); L = len(r); i = np.arange(L)
        if L > FUT_K: pos[r[:-FUT_K]] = r[FUT_K:]
        cs = np.concatenate([[0], np.cumsum(buf.te[r] > 0)]); hh = cs[np.minimum(i + 10, L)] > cs[i]
        hit[r] = hh; hit_m[r] = hh | (i + 10 <= L) | (aid in final)
    E_ = buf.ent[:n, :AUX_SLOTS].astype(np.float32); seen = E_[..., O.XY:O.XY + 2]; v = E_[..., O.VEL:O.VEL + 2]
    lab = {"fut": np.zeros((n, AUX_SLOTS, 2), np.float32), "fut_m": np.zeros((n, AUX_SLOTS), np.float32), "hit": hit, "hit_m": hit_m,
           "gas": np.maximum(buf.gm[:n], 0) / 10.0, "bush": buf.be[:n].astype(np.float32), "m": (~buf.dead[:n]).astype(np.float32),
           "still": seen, "cv": seen + ((v - buf.s[:n, None, 6:8].astype(np.float32)) * LAT + v * 2 * FUT_K) / 10.0,   # 2 ticks per row
           "fut_p": np.zeros((n, AUX_SLOTS), np.float32)}
    j = np.flatnonzero(pos >= 0); J = len(j); k10 = pos[j]; ar = np.arange(J)
    if J:
        me = buf.me[j].astype(np.int64); tp = buf.tpos[j]; mine = tp[ar, me]
        en = (E_[j, :, 0] > 0.5) & (E_[j, :, 1 + O.ENT.index("enemy")] > 0.5); lab["fut_p"][j] = en
        d = np.linalg.norm(seen[j][:, :, None] * 10.0 - (tp - mine[:, None])[:, None], axis=-1)      # (J, 9, 10) tiles
        d[~(en[:, :, None] & buf.talive[j][:, None])] = np.inf
        q = np.full((J, AUX_SLOTS), -1, np.int64)
        for _ in range(AUX_SLOTS):                       # greedy: the closest (slot, player) pair first
            f = d.reshape(J, -1); a_ = f.argmin(1); ok = f[ar, a_] < FUT_GATE
            if not ok.any(): break
            jj = np.flatnonzero(ok); kk, qq = np.divmod(a_[jj], 10)
            q[jj, kk] = qq; d[jj, kk, :] = np.inf; d[jj, :, qq] = np.inf
        qc = np.maximum(q, 0)
        lab["fut"][j] = np.clip((buf.tpos[k10][ar[:, None], qc] - mine[:, None]) / 10.0, -2.5, 2.5)
        lab["fut_m"][j] = (q >= 0) & buf.talive[k10][ar[:, None], qc]
    return lab


def auc(score, y):
    """ROC AUC (Mann-Whitney U, ties averaged); None without both classes"""
    y = np.asarray(y) > 0.5; npos = int(y.sum()); nneg = len(y) - npos
    if not npos or not nneg: return None
    _, inv, cnt = np.unique(score, return_inverse=True, return_counts=True); rk = (np.cumsum(cnt) - (cnt - 1) / 2.0)[inv]
    return float((rk[y].sum() - npos * (npos + 1) / 2.0) / (npos * nneg))


def aux_targets(a, net, g, buf, traj, final, n, use_rows, xrow, T):
    """--aux-w: labels (aux_labels, as tensors -> X["AUX"]) and the readouts of the pre-update predictions on the rows
    trained on (row_pass) into xrow"""
    from model import AUX_SLOTS
    lab = aux_labels(buf, traj, final, n); K2 = AUX_SLOTS * 2
    cat = lambda net_, xc, s, ent: (lambda o: torch.cat([o["fut"].flatten(1), o["hit"][:, None], o["gas"][:, None], o["bush"]], 1))(net_.aux_out(xc, ent, s))
    P = row_pass(net, g, n, {"aux": cat})["aux"].float().cpu().numpy()[use_rows]; L = {k: v[use_rows] for k, v in lab.items()}
    fut, hit, gas, bush = P[:, :K2].reshape(-1, AUX_SLOTS, 2), P[:, K2], P[:, K2 + 1], P[:, K2 + 2:]
    m = L["m"] > 0; fm = (L["fut_m"] > 0) & m[:, None]; hm = (L["hit_m"] > 0) & m
    err = lambda p: round(float(np.median(np.linalg.norm(p[fm] - L["fut"][fm], axis=-1))) * 10, 3) if fm.any() else None
    r3 = lambda v: None if v is None else round(v, 4)
    fp = (L["fut_p"] > 0) & m[:, None]
    xrow.update(aux_fut_tiles=err(fut), aux_fut_cv_tiles=err(L["cv"]), aux_fut_still_tiles=err(L["still"]), aux_fut_n=int(fm.sum()),
                aux_fut_match=round(float(fm.sum() / fp.sum()), 3) if fp.any() else None,
                aux_hit_auc=r3(auc(hit[hm], L["hit"][hm])), aux_hit_rate=r3(float(L["hit"][hm].mean())) if hm.any() else None,
                aux_gas_mae_tiles=round(float(np.abs(gas[m] - L["gas"][m]).mean()) * 10, 3) if m.any() else None,
                aux_bush_auc=r3(auc(bush[m].ravel(), L["bush"][m].ravel())), aux_bush_rate=r3(float(L["bush"][m].mean())) if m.any() else None)
    return {"AUX": {k: T(v) for k, v in lab.items() if k not in ("cv", "still", "fut_p")}, "s": g["s"], "ent": g["ent"]}


@torch.no_grad()
def aux_readout(net, s, ent, grid, h):
    """the aux heads on one decision (replay frame "x"; device tensors with a batch of 1): per present enemy slot of the
    enemy block [seen dx, dy, predicted dx, dy in 1 s] (10-tile units), p_hit, gas margin (tiles), P(hidden enemy in a
    bush) per sector"""
    from model import AUX_SLOTS
    o = net.aux_out(net.row_feats(s, ent, grid, h), ent, s); e = ent[0, :AUX_SLOTS].float().cpu().numpy(); f = o["fut"][0].float().cpu().numpy()
    on = (e[:, 0] > 0.5) & (e[:, 1 + O.ENT.index("enemy")] > 0.5)
    return {"f": [[round(float(v), 3) for v in (*e[k, O.XY:O.XY + 2], *f[k])] for k in np.flatnonzero(on)],
            "h": round(float(torch.sigmoid(o["hit"][0])), 3), "g": round(float(o["gas"][0]) * 10, 2),
            "b": [round(float(v), 3) for v in torch.sigmoid(o["bush"][0])]}


def head_loss(net, xc, rf, X, a):
    """loss of the heads that never act on a minibatch (xc = cat[x, h] of its rows, rf = their buffer rows) -> (loss,
    {stat: value}); 0 with the flags off. --vlive: 0.5 x 0.5 MSE to the live lambda-return (as the critic's)"""
    loss, st = 0.0, {}
    if a.vlive:
        lv = 0.5 * ((net.value_live(xc) - X["RETL"][rf]) ** 2).mean(); loss = loss + 0.5 * lv; st["vloss_live"] = lv.item()
    if a.aux_w:                                          # --aux-w: x model.aux_losses (no detach: shapes the shared layers)
        la, per = aux_losses(net.aux_out(xc, X["ent"][rf], X["s"][rf]), {k: v[rf] for k, v in X["AUX"].items()})
        loss = loss + a.aux_w * la; st.update({"aux_loss_" + k: v.item() for k, v in per.items()})
    return loss, st


def eval_summary(rows):
    ok = [r for r in rows if r["rank"] is not None and not r["truncated"]]
    rk = np.array([r["rank"] for r in ok], float); m = lambda k: round(float(np.mean([r["terms"][k] for r in ok])), 3) if ok else None
    return {"episodes": len(ok), "rank": round(float(rk.mean()), 3) if ok else None,
            "ci95": round(float(1.96 * rk.std(ddof=1) / np.sqrt(len(rk))), 3) if len(ok) > 1 else None,
            "win": round(float(np.mean([r["win"] for r in ok])), 3) if ok else None, "top3": round(float((rk <= 3).mean()), 3) if ok else None,
            "dealt": m("dealt"), "taken": m("taken"), "kills": m("kills"), "cubes": m("cubes"),
            "ticks": round(float(np.mean([r["ticks"] for r in ok])), 1) if ok else None,
            "hit_rate": round(sum(r["terms"]["hits"] for r in ok) / max(1.0, sum(r["terms"]["shots"] for r in ok)), 3) if ok else None}


def _check():
    """gae == the original inline loop; aux_labels on a synthetic trajectory (slot matching, 1 s label, masks, hit
    window, baselines); auc; the replay frame "i" and the progress intent fields"""
    rng = np.random.default_rng(0); n = 60; buf = Buffer(n)
    buf.rew[:n] = rng.normal(size=n); buf.val[:n] = rng.normal(size=n); buf.done[29] = True; buf.n = n
    traj, pending, final = {1: list(range(30)), 2: list(range(30, 55))}, {2: 57}, {1}
    adv, ret = gae(traj, pending, final, buf.rew[:n], buf.val[:n], 0.99, 0.9, buf.done[:n]); last = 0.0; nxt = float(buf.val[57])
    for j in range(54, 29, -1):
        last = buf.rew[j] + 0.99 * nxt - buf.val[j] + 0.99 * 0.9 * last; nxt = buf.val[j]; assert adv[j] == last and ret[j] == last + buf.val[j]
    assert np.isclose(ret[29], buf.rew[29]) and adv[29] == buf.rew[29] - buf.val[29]     # done: no bootstrap
    # trajectory 1 (rows 0-29): me (player 3) still at (10, 10) tiles; enemy 5 walks right 0.1 tiles / row (0.05 / tick),
    # seen in slot 2 (slot 0: a teammate on the same spot, slot 1: a false enemy far from any player); enemy 7 dies at row 15
    buf.me[:n] = 3; buf.tpos[:n] = 20.0; buf.tpos[:n, 3] = 10.0; buf.talive[:n, [5, 7]] = True; buf.talive[15:30, 7] = False
    k = np.arange(30); buf.tpos[k, 5] = np.stack([12.0 + 0.1 * k, np.full(30, 10.0)], 1); buf.tpos[k, 7] = [10.0, 13.0]
    en, mate = 1 + O.ENT.index("enemy"), 1 + O.ENT.index("teammate")
    buf.ent[k, 2, 0] = 1; buf.ent[k, 2, en] = 1; buf.ent[k, 2, O.XY] = (2.0 + 0.1 * k + 0.05) / 10; buf.ent[k, 2, O.VEL] = 0.05   # seen 0.05 tiles off
    buf.ent[k, 0, 0] = 1; buf.ent[k, 0, mate] = 1; buf.ent[k, 0, O.XY] = 0.2
    buf.ent[k, 1, 0] = 1; buf.ent[k, 1, en] = 1; buf.ent[k, 1, O.XY + 1] = -0.6
    buf.ent[k, 3, 0] = 1; buf.ent[k, 3, en] = 1; buf.ent[k, 3, O.XY + 1] = 0.3                                  # enemy 7, 3 tiles below
    buf.te[[4, 12]] = 0.3; buf.dead[20] = True
    lab = aux_labels(buf, traj, final, n)
    assert lab["fut_m"][:20, 2].all() and not lab["fut_m"][20:, 2].any() and not lab["fut_m"][:, :2].any()   # 10 rows ahead in the trajectory
    assert lab["fut_p"][:20, 1:4].all() and not lab["fut_p"][:, 0].any() and not lab["fut_p"][20:].any()   # slot 1: present, unmatched
    assert np.allclose(lab["fut"][:20, 2], np.stack([(2.0 + 0.1 * (k[:20] + 10)) / 10, np.zeros(20)], 1), atol=1e-6)
    assert lab["fut_m"][:5, 3].all() and not lab["fut_m"][5:, 3].any()   # enemy 7 dead at row 15 = 10 rows after row 5
    from model import LAT
    assert np.allclose(lab["cv"][:20, 2, 0], buf.ent[:20, 2, O.XY].astype(np.float32) + (0.05 * LAT + 0.05 * 20) / 10, atol=1e-3)
    assert np.allclose(lab["still"][:, 2], buf.ent[:, 2, O.XY:O.XY + 2].astype(np.float32))
    assert lab["hit"][:13].all() and not lab["hit"][13:30].any() and lab["hit_m"][:30].all()            # rows j .. j+9, ended trajectory
    assert lab["hit"][30:].sum() == 0 and lab["hit_m"][30:46].all() and not lab["hit_m"][46:55].any()    # not ended: last 9 unknown
    assert lab["m"][20] == 0 and lab["m"][19] == 1 and np.allclose(lab["gas"], 0)
    assert auc([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1]) == 1.0 and auc([0.5] * 4, [0, 1, 0, 1]) == 0.5 and auc([1, 2], [1, 1]) is None
    assert abs(auc([0.9, 0.2, 0.8, 0.1], [0, 0, 1, 1]) - 0.25) < 1e-9                      # 1 of 4 pairs ordered
    a_ = torch.nn.Linear(38, 4); o_ = torch.optim.Adam(a_.parameters()); a_(torch.randn(2, 38)).sum().backward(); o_.step()
    b_ = torch.nn.Linear(49, 4); o2 = torch.optim.Adam(b_.parameters()); load_opt(o2, o_.state_dict())   # an input that grew
    m_ = o2.state[b_.weight]["exp_avg"]; assert m_.shape == (4, 49) and not m_[:, 38:].any() and torch.equal(m_[:, :38], o_.state[a_.weight]["exp_avg"])
    b_(torch.randn(2, 49)).sum().backward(); o2.step()
    import model as M                                    # obs v5.6: an entity input's moments get the new columns before the lead
    from model import Policy as P_, F_IN
    n_ = P_(); c_ = n_.cand[0].weight; pre = c_.shape[1] - F_IN; F55 = O.F_ENT_V55 + 2
    a_ = torch.nn.Linear(pre + F55, 128); o_ = torch.optim.Adam(a_.parameters()); a_(torch.randn(2, pre + F55)).sum().backward(); o_.step()
    o3 = torch.optim.Adam([c_, n_.cand[0].bias]); load_opt(o3, o_.state_dict(), net=n_); m3, m0 = o3.state[c_]["exp_avg"], o_.state[a_.weight]["exp_avg"]
    assert m3.shape == c_.shape and torch.equal(m3[:, :pre + O.F_ENT_V55], m0[:, :pre + O.F_ENT_V55]) and torch.equal(m3[:, -2:], m0[:, -2:])
    assert not m3[:, pre + O.F_ENT_V55:pre + O.F_ENT].any() and M.ENT_IN[1] == "cand.0.weight"
    torch.manual_seed(3); n6 = P_(); p6, _ = split_params(n6); old6 = [p for k, p in n6.named_parameters() if p in set(p6) and not k.startswith("fire_x")]
    o6 = torch.optim.Adam(old6); sum(x.float().sum() for x in old6).backward(); o6.step()           # a v5.6 run's Adam (no fire_x)
    sd6 = o6.state_dict(); sd6["state"][0]["exp_avg"] = sd6["state"][0]["exp_avg"][:, :5]            # + an input that grew since
    n7 = P_(); p7, _ = split_params(n7); o7 = torch.optim.Adam(p7); load_opt(o7, sd6, net=n7)        # v5.7: fire_x at the tail
    assert len(p7) == len(old6) + 2 and [k for k, p in n7.named_parameters() if p is p7[-1]] == ["fire_x.bias"]
    assert all(torch.equal(o7.state[a]["exp_avg_sq"], o6.state[b]["exp_avg_sq"]) for a, b in zip(p7[1:-2], old6[1:]))
    assert o7.state[p7[0]]["exp_avg"].shape == p7[0].shape and not o7.state[p7[-1]] and not o7.state[p7[-2]]
    sum(x.float().sum() for x in p7).backward(); o7.step(); assert o7.state[p7[-1]]["step"] == 1 and o7.state[p7[0]]["step"] == 2
    o8 = torch.optim.Adam(p7[:-3]); load_opt(o8, sd6)                                                  # fewer parameters: fresh
    assert not o8.state
    sd7 = o7.state_dict(); L = len(p7)                                                               # a v5.7 run's Adam: one fire_x row
    sd7["state"][L - 2] = {**sd7["state"][L - 2], **{k: v[:1] for k, v in sd7["state"][L - 2].items() if torch.is_tensor(v) and v.dim()}}
    sd7["state"][L - 1] = {**sd7["state"][L - 1], **{k: v[:1] for k, v in sd7["state"][L - 1].items() if torch.is_tensor(v) and v.dim()}}
    o9 = torch.optim.Adam(p7); load_opt(o9, sd7, net=n7); m9 = o9.state[p7[-2]]["exp_avg"]            # v5.8: the hypercharge row padded
    assert M.N_FX == 2 and m9.shape == p7[-2].shape and torch.equal(m9[:1], o7.state[p7[-2]]["exp_avg"][:1]) and not m9[1].any()
    import intent as I                                   # replay frame "i", progress intent fields
    o = {"intent": I.encode([0, 5], [0, 3.0], [0, -1.0], [0, 1.0], [0, 0.5])}
    x = np.zeros(O.F_ENT, np.float32); assert id_name(x) == []
    x[O.ID0:O.ID0 + 13] = O.brawler_stats("Sniper"); x[O.ID_KNOWN] = 1; assert id_name(x) == ["Sniper"]
    assert intent_frame(o, 0) == {} and intent_frame({}, 0) == {} and intent_frame(o, 1)["i"] == {"k": "farm", "t": [0.3, -0.1], "r": 0.1, "l": 0.5}
    st = intent_stats([{"intents": {"farm": [2, 1, 1, 0]}, "terms": {"i_rew": 0.02}, "intent_mode": "steered"},
                       {"intents": {}, "terms": {"i_rew": 0.0}, "intent_mode": "free"}, {"terms": {}}])
    assert st == {"t_i_rew": 0.01, "intents": {"farm": [2, 1, 1, 0]}, "intent_follow": 0.5, "steered": 0.5}, st
    o["i_why"] = ["no plan fits: free play", "cube 3 tiles S: picking up"]   # step E: reasons (env_v5.Env.last_why)
    assert intent_frame(o, 0) == {"iy": "no plan fits: free play"} and intent_frame(o, 1)["i"]["y"] == "cube 3 tiles S: picking up"
    o["i_why"] = None; assert intent_frame(o, 0) == {} and "y" not in intent_frame(o, 1)["i"]
    pr = [{"intents": {"farm": [1, 1, 0, 0]}, "terms": {"i_rew": 0.01}, "plan_rules": {"farm": [2, 1, 0], "none": [3, 0, 0]}},
          {"intents": {"move_to": [1, 0, 0, 0]}, "terms": {"i_rew": 0.0}, "plan_rules": {"gas": [1, 1, 1], "farm": [1, 0, 0]}}]
    assert intent_stats(pr)["plan_rules"] == {"gas": [1, 1, 1], "farm": [3, 1, 0], "none": [3, 0, 0]}   # planner.RULES order
    tm = {"dealt": 1.0, "taken": 1.0, "kills": 0, "cubes": 0, "hits": 1, "shots": 2}
    ev = [dict(r, seed=k + 1, player=0, rank=3 + k, win=0, ticks=100, truncated=False, terms={**tm, **r["terms"]}, tag={"kind": "evalp_plan"})
          for k, r in enumerate(pr)]
    ep = eval_plan(ev + [dict(ev[0], tag={"kind": "eval"})])
    assert ep["pl_episodes"] == 2 and ep["pl_rank"] == 3.5 and ep["pl_follow"] == 0.5 and ep["pl_rules"]["farm"] == [3, 1, 0], ep
    assert eval_plan(ev[:0]) == {} and eval_intent("evalp_plan") == "plan" and eval_intent("eval") == "none"
    A = argparse.Namespace(eval_presets="", eval_episodes=2, evalb_episodes=1, eval_plan=1)
    assert [k for _, k, _ in eval_items(A)] == ["eval", "eval", "evalb", "evalp_plan", "evalp_plan"]
    assert "evalp_plan" not in [k for _, k, _ in eval_items(argparse.Namespace(**{**vars(A), "eval_plan": 0}))]
    print("train_ppo helpers ok")


def main():
    if "--check" in sys.argv: return _check()
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True); ap.add_argument("--hours", type=float, default=3.0); ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--rollout", type=int, default=32768); ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--seq", type=int, default=8); ap.add_argument("--chunks", type=int, default=512, help="chunks per minibatch")
    ap.add_argument("--lr", type=float, default=1e-4); ap.add_argument("--bc-lr", type=float, default=5e-4)
    ap.add_argument("--bc-updates", type=int, default=40); ap.add_argument("--gamma", type=float, default=0.995)
    ap.add_argument("--lam", type=float, default=0.95); ap.add_argument("--clip", type=float, default=0.15)
    ap.add_argument("--ent", type=float, default=0.001); ap.add_argument("--kl-beta", type=float, default=0.5)
    ap.add_argument("--kl-updates", type=int, default=60); ap.add_argument("--kl-floor", type=float, default=0.02)
    ap.add_argument("--kmix", default="1,2,3,4,5"); ap.add_argument("--brawler", default="Sniper", help="Sniper = Piper")
    ap.add_argument("--loc", default=None, help="Showdown location (default: the first of env_v5.locations())")
    ap.add_argument("--slider-scale", type=float, default=0.0, help="weight of the slider rewards (stage 1: off)")
    slider_flags(ap); head_flags(ap); scenario_flags(ap); intent_flags(ap)
    ap.add_argument("--noise", type=int, default=1, help="ObsV5 vision noise + latency")
    ap.add_argument("--eval-min", type=float, default=30.0); ap.add_argument("--eval-episodes", type=int, default=200)
    ap.add_argument("--max-ticks", type=int, default=4000); ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--min-ready", type=int, default=0, help="instances per poll (0 = all; s1-s3 used n // 3)")
    ap.add_argument("--max-wait", type=float, default=0.004, help="poll waits this long after the first ready instance (s1-s3: 0.002)")
    ap.add_argument("--resume", default=None); ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--sp", type=float, default=0.8, help="share of PPO battles that are self-play (rest: vs native AI)")
    ap.add_argument("--league-every", type=int, default=20); ap.add_argument("--league-size", type=int, default=16)
    ap.add_argument("--base", default=None, help="checkpoint of the evalb opponent (default: --resume)")
    ap.add_argument("--evalb-episodes", type=int, default=200)
    ap.add_argument("--eval-n", type=int, default=99, help="instances that play the evals (the rest keep training; fewer than --n was slower overall, see README)")
    ap.add_argument("--opp-slots", type=int, default=3); ap.add_argument("--opp-hold", type=int, default=2)
    ap.add_argument("--pfsp-p", type=float, default=2.0)
    ap.add_argument("--gadgets", type=int, default=0, help="1 = players carry a gadget, the policy sees it ready (self 3) and may use it (obs v5.7, issue #3; needs a host that activates its kind)")
    ap.add_argument("--star-powers", type=int, default=0, help="1 = players carry a star power card this build runs (libg reads it: star_audit.LIVE, or the host re-implements it: star_check.LIVE; issues #20, #47; not in the observation)")
    ap.add_argument("--gears", type=int, default=0, help="1 = players carry two gears of their brawler whose effect gear_check confirmed (gear_check.LIVE; issue #51; not in the observation)")
    ap.add_argument("--hyper", type=int, default=0, help="1 = players carry their hypercharge card, the policy sees it ready (self 4) and may activate it (obs v5.8, issue #4; needs a host with hyper.c)")
    a = ap.parse_args()
    if a.smoke: a.n, a.rollout, a.chunks, a.bc_updates, a.eval_episodes, a.evalb_episodes, a.hours, a.scenario_seeds = 2, 2048, 64, 1, 4, 4, 0.2, 1
    torch.manual_seed(a.seed); np.random.seed(a.seed)
    out = os.path.join(E.WORK, "runs", a.run); os.makedirs(out, exist_ok=True)
    loc = a.loc or E.locations()[0]
    json.dump({**vars(a), "loc": loc, "reward_w": REWARD_W}, open(os.path.join(out, "config.json"), "w"), indent=1)
    shutil.copy(os.path.join(HERE, "viz.html"), os.path.join(out, "index.html"))
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")   # CPU: plumbing checks (--smoke) only
    def frozen(sd):
        m = Policy().to(dev).eval(); m.load_state_dict(sd, strict=False); [p.requires_grad_(False) for p in m.parameters()]
        return m
    net = Policy().to(dev); ref = bnet = enet = None; main_p, x_p = split_params(net)
    opt = torch.optim.Adam(main_p, lr=a.bc_lr, eps=1e-5); opt_x = torch.optim.Adam(x_p, lr=a.bc_lr, eps=1e-5)
    upd = 0; agent_steps = 0
    if a.resume:
        ck = torch.load(a.resume, map_location="cpu", weights_only=False)
        net.load_state_dict(ck["model"], strict=False); upd, agent_steps = ck["update"], ck["agent_steps"]
        if ck.get("obs_version") != O.OBS_VERSION:   # older inputs: the new columns load zero-padded (model.load_state_dict), same actions
            print("checkpoint obs %s, this code %s: new input columns zero-padded" % (ck.get("obs_version", "< v5.4"), O.OBS_VERSION), flush=True)
        load_opt(opt, ck["opt"], net=net); load_opt(opt_x, ck.get("opt_x"), "optimizer state of the non-acting heads", net=net)
        if ck.get("ref"): ref = frozen(ck["ref"])
        bnet = frozen(torch.load(a.base, map_location="cpu", weights_only=False)["model"] if a.base else ck["model"])
    kmix = [int(x) for x in a.kmix.split(",")]; rng_b = np.random.default_rng(a.seed + 7)
    eval_queue = []; ev = {"active": False, "t_last": 0.0 if a.resume else time.time()}      # resumed: eval first
    os.makedirs(os.path.join(out, "league"), exist_ok=True); M = a.opp_slots
    lnets = [frozen(net.state_dict()) for _ in range(M)]; lname = [None] * M     # loaded league opponents / their file names
    pool = sorted(glob.glob(os.path.join(out, "league", "u*.pt"))); pf_path = os.path.join(out, "league", "pfsp.json")
    pf = json.load(open(pf_path)) if os.path.exists(pf_path) else {}             # file name -> [mean rank of its players, rows]
    pfr = lambda p: pf.get(os.path.basename(p), [5.5, 0])[0]
    def load_slot(k):
        w = np.array([((10 - pfr(p)) / 9) ** a.pfsp_p for p in pool]); p = pool[int(rng_b.choice(len(pool), p=w / w.sum()))]
        lnets[k].load_state_dict(torch.load(p, map_location=dev), strict=False); lname[k] = os.path.basename(p)
    if pool: [load_slot(k) for k in range(M)]
    bc = lambda: upd < a.bc_updates

    def battle_fn(rng, i):
        cfg = battle_cfg(rng, i)                         # --gadgets: MAEnv's rng, so rng_b's draws stay the same
        cfg = E.with_gadgets(cfg, rng) if a.gadgets and "scenario" not in cfg else cfg   # scenarios: as set up
        cfg = E.with_star_powers(cfg, rng) if a.star_powers and "scenario" not in cfg else cfg   # after the gadgets' draws
        cfg = E.with_gears(cfg, rng) if a.gears and "scenario" not in cfg else cfg             # after the star powers' draws
        return E.with_hyper(cfg) if a.hyper and "scenario" not in cfg else cfg         # --hyper: no draw

    def battle_cfg(rng, i):
        tag = {"loc": loc, "chr": [a.brawler] * 10, "team_size": 1, "groups": [0] * 10}
        cfg = {"div": D.make_div(location=loc, chr=tag["chr"]), "tag": tag, "end": "agents"}
        if eval_queue and not bc() and i >= a.n - a.eval_n:
            sd, kd, pre = eval_queue.pop(0); b = kd == "evalb"
            if kd == "evalscn": return SC.battle_cfg(pre)
            return {**cfg, "seed": sd, "ctl": list(range(10)) if b else [0], "end": "player0",
                    "tag": {**tag, "kind": kd, "opp": list(range(1, 10)) if b else [], "intent": eval_intent(kd), **eval_tag(a, pre)}}   # free play (evalp_plan: planner)
        sd = int(rng_b.integers(10_000_000, 2 ** 31 - 1))
        if bc():
            return {**cfg, "seed": sd, "ctl": list(range(10)), "native_ctl": True, "tag": {**tag, "kind": "bc"}}
        if rng_b.random() < a.sp:
            opp = sorted(rng_b.choice(10, int(rng_b.integers(0, 8)), replace=False).tolist())
            k = int(rng_b.integers(M))
            return {**cfg, "seed": sd, "ctl": list(range(10)), "tag": {**tag, "kind": "sp", "opp": opp, "slot": k, "snap": lname[k]}}
        k = int(rng_b.choice(kmix))
        return {**cfg, "seed": sd, "ctl": sorted(rng_b.choice(10, k, replace=False).tolist()), "tag": {**tag, "kind": "k%d" % k}}

    E.Env.slider_scale = a.slider_scale; E.Env.record = a.bc_updates > 0
    E.Env.slider_sample, E.Env.slider_norm = a.slider_sample, E.slider_norm(a.slider_norm); set_intents(a)
    env = E.Env(a.n, battle_fn, ticks=2, fair=True, max_ticks=a.max_ticks, verbose=True, seed=a.seed, tag="ppo%d" % os.getpid())
    ob = O.ObsV5(noise=O.NOISE if a.noise else None, seed=a.seed); rec = Recorder(out)
    srec, sidx = (SC.Recorder(out), SC.ScnIndex(out)) if a.eval_scenarios else (None, None)   # every scenario episode's replay
    buf = Buffer(a.rollout + 8192)
    pending, traj, final, hid = {}, {}, set(), {}      # aid -> row waiting for its transition / rows this rollout / ended / GRU state
    epf = open(os.path.join(out, "episodes.jsonl"), "a"); evf = open(os.path.join(out, "evals.jsonl"), "a")
    evepf = open(os.path.join(out, "eval_episodes.jsonl"), "a")   # the policy's (player 0) eval rows: scorecard.py eval / per-preset groups
    prf = open(os.path.join(out, "progress.jsonl"), "a")
    scf = open(os.path.join(out, "scenarios.jsonl"), "a") if a.eval_scenarios else None   # --eval-scenarios: one row per scenario eval
    scef = open(os.path.join(out, "scenario_episodes.jsonl"), "a") if a.eval_scenarios else None
    t0 = time.time(); n_ep = 0; ep_rows = []; stop = {"now": False}; z = np.zeros(HID, np.float32)
    signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__("now", True))
    T = lambda x, dt=torch.float32: torch.as_tensor(x, device=dev).to(dt)

    def save(path):
        torch.save({"model": net.state_dict(), "opt": opt.state_dict(), "opt_x": opt_x.state_dict(), "ref": ref.state_dict() if ref else None, "update": upd,
                    "agent_steps": agent_steps, "args": vars(a), "loc": loc, "obs_version": O.OBS_VERSION}, path)

    def start_eval():
        nonlocal enet
        enet = frozen(net.state_dict())
        eval_queue.extend(eval_items(a) + scenario_items(a, ev.get("n", 0), upd))
        ev.update(n=ev.get("n", 0) + 1, t_scn=None)
        ev.update(active=True, update=upd, steps=agent_steps, t0=time.time(), n0=len(env.episodes))
        save(os.path.join(out, "ckpt_u%04d.pt" % upd))

    def finish_eval():
        if eval_queue or any(s.state != "idle" and (s.cfg or {}).get("tag", {}).get("kind", "").startswith("eval") for s in env.I): return
        by = lambda kd: list({r["seed"]: r for r in env.episodes[ev["n0"]:] if r["tag"]["kind"] == kd and r["player"] == 0}.values())
        sm = {"update": ev["update"], "agent_steps": ev["steps"], "minutes": round((time.time() - t0) / 60, 1),
              "eval_s": round(time.time() - ev["t0"], 1), **eval_summary(by("eval")),
              **{"b_" + k: v for k, v in eval_summary(by("evalb")).items() if k in ("episodes", "rank", "ci95", "win", "top3")},
              **eval_presets(env.episodes[ev["n0"]:]), **eval_plan(env.episodes[ev["n0"]:])}
        evf.write(json.dumps(sm) + "\n"); evf.flush(); print("[eval]", json.dumps(sm), flush=True); evepf.flush()
        if scf: scenario_eval(env.episodes[ev["n0"]:], ev, sm["minutes"], scf, scef)
        ev.update(active=False, t_last=time.time())

    t_end = t0 + a.hours * 3600; smoke_end = upd + 3
    try:
        while time.time() < t_end and not stop["now"] and not (a.smoke and upd >= smoke_end):
            # ---------------- collect
            dec_t, dec_n = time.time(), 0; tm = np.zeros(4)   # poll / obs build / act forward / rest (s, timers)
            while buf.n < a.rollout and not stop["now"]:
                tq = time.perf_counter(); obs, ids, tr = env.poll(min_ready=a.min_ready or a.n, max_wait=a.max_wait); tm[0] += time.perf_counter() - tq
                for (aid, rew, done, terms, rank) in tr:
                    j = pending.pop(aid, None)
                    if done: hid.pop(aid, None)
                    if j is None: continue
                    buf.rew[j] = rew; buf.done[j] = done; buf.complete[j] = True
                    buf.rew_int[j] = terms.get("i_rew", 0.0)
                    if buf.bc[j] and terms.get("_act") is not None: buf.act[j] = terms["_act"]
                    elif buf.bc[j]: continue                 # a BC row without a label (recording went off): not trained on
                    traj.setdefault(aid, []).append(j)
                    buf.te[j] = terms.get("te", 0.0)
                    if done: final.add(aid)
                for aid in env.dropped: pending.pop(aid, None); hid.pop(aid, None)
                env.dropped = []
                if not len(ids): continue
                tq = time.perf_counter(); o = ob.build(obs["vec"], obs["grid"], env.last_meta, ids, who=env.last_who, gadget=env.gadget(ids) if a.gadgets else None, hyper=env.hyper(ids) if a.hyper else None); tm[1] += time.perf_counter() - tq
                s = policy_s(env, ids, o); h = np.stack([hid.get(int(x), z) for x in ids])
                pv = priv(env, ids); B = len(ids); kind = np.array([t["kind"] for t in env.last_tags])
                isev = np.char.startswith(kind, "eval"); opp = np.array([int(x) & 15 in t.get("opp", ()) for x, t in zip(ids, env.last_tags)], bool)
                A = np.zeros((B, 4), np.int64); h2 = np.zeros((B, HID), np.float32); lp = np.zeros(B, np.float32); v = np.zeros(B, np.float32)
                sl = np.array([t.get("slot", 0) for t in env.last_tags])
                tq = time.perf_counter()
                with torch.no_grad():                        # learner / frozen eval copy / evalb base / league slots
                    grp = [(net_, np.flatnonzero(mk)) for net_, mk in [(net, ~isev & ~opp), (enet, isev & ~opp), (bnet, isev & opp)]
                           + [(lnets[k], ~isev & opp & (sl == k)) for k in range(M)] if mk.any()]
                    # speed round (HISTORY 68): one upload, ONE vmapped forward over all weight sets, one sample, one download
                    D_ = [T(s), T(o["ent"]), T(o["grid"], torch.uint8), T(h), T(pv)]
                    lgS, vS, hS = act_stacked([g for g, _ in grp], [[d[torch.as_tensor(ix, device=dev)] for d in D_] for _, ix in grp])
                    Bm = vS.shape[1]; sel = torch.as_tensor(np.concatenate([ix_k + k * Bm for k, ix_k in enumerate(np.arange(len(ix)) for _, ix in grp)]), device=dev)
                    lp_, _, A_ = dist_logp_ent([l.flatten(0, 1)[sel] for l in lgS])
                    order = np.concatenate([ix for _, ix in grp])
                    A[order], lp[order], v[order], h2[order] = A_.cpu().numpy(), lp_.cpu().numpy(), vS.flatten(0, 1)[sel].cpu().numpy(), hS.flatten(0, 1)[sel].cpu().numpy()
                tm[2] += time.perf_counter() - tq
                for x, hh in zip(ids, h2): hid[int(x)] = hh
                m = ~isev & ~opp & ((kind == "bc") == bc())   # BC battles still running after the switch are not collected
                if m.any():
                    rows = buf.add(s=s[m], ent=o["ent"][m], grid=o["grid"][m], h=h[m], priv=pv[m], act=A[m], logp=lp[m],
                                   val=v[m], bc=kind[m] == "bc", dead=env.dead(ids[m]), **(E.aux_split(env.aux_now(ids[m])) if a.aux_w else {}))
                    for aid, j in zip(ids[m], rows): pending[int(aid)] = int(j)
                    agent_steps += int(m.sum()); dec_n += int(m.sum())
                b = rec.row(env, ids) if a.aux_w else None   # the aux heads' readout for the replay
                xr = aux_readout(net, T(s[b:b + 1]), T(o["ent"][b:b + 1]), T(o["grid"][b:b + 1], torch.uint8), T(h[b:b + 1])) if b is not None else None
                rec.frame(env, ids, o, A, upd, x=xr)
                if srec: srec.frame(env, ids, o, A)
                env.send(ids, A)
                for r in env.episodes[n_ep:]:
                    tg = r["tag"]                            # PFSP score: only battles whose snapshot stayed loaded to the end
                    if (tg["kind"] == "sp" and r["player"] in tg["opp"] and tg.get("snap") and tg["snap"] == lname[tg["slot"]]
                            and r["rank"] is not None and not r["truncated"]):
                        e = pf.setdefault(tg["snap"], [5.5, 0]); e[0] += 0.02 * (r["rank"] - e[0]); e[1] += 1
                    if not r["tag"]["kind"].startswith("eval") and r["player"] not in r["tag"].get("opp", ()):
                        ep_rows.append(r); epf.write(json.dumps(r) + "\n")
                    elif r["tag"]["kind"] == "evalscn":      # scenarios.jsonl at the eval's end; the replay now
                        if srec: sidx.add([srec.finish(r)]); ev["t_scn"] = time.time()
                    elif r["tag"]["kind"].startswith("eval") and r["player"] == 0: evepf.write(json.dumps(r) + "\n")
                n_ep = len(env.episodes)
                if ev["active"]: finish_eval()
                elif not bc() and time.time() - ev["t_last"] > a.eval_min * 60: start_eval()
            if stop["now"]: break
            collect_s = time.time() - dec_t; dps = dec_n / max(1e-9, collect_s)
            # ---------------- update
            tu = time.time(); epf.flush(); is_bc = bc(); n = buf.n
            adv, ret = gae(traj, pending, final, buf.rew[:n], buf.val[:n], a.gamma, a.lam, buf.done[:n])   # bootstrap: the pending row
            use = [r for r in traj.values() if bool(buf.bc[r[0]]) == is_bc]
            C = torch.as_tensor(chunks(use, a.seq), device=dev); nrow = int((C >= 0).sum())
            g = {k: T(getattr(buf, k)[:n], dt) for k, dt in (("s", torch.float32), ("ent", torch.float32), ("grid", torch.uint8),
                 ("h", torch.float32), ("priv", torch.float32), ("act", torch.long), ("logp", torch.float32), ("val", torch.float32))}
            ADV, RET = T(adv), T(ret); LIVE = T(~buf.dead[:n], torch.float32)   # respawning rows: value only (actions ignored)
            rows = C[C >= 0].cpu().numpy(); X = {}; xrow = {}; tx = time.time()
            if a.vlive:
                _, retl, xrow["expl_var_live"] = live_targets(a, net, g, buf, traj, pending, final, n, rows); X["RETL"] = T(retl)
            if a.aux_w: X.update(aux_targets(a, net, g, buf, traj, final, n, rows, xrow, T))
            if X: xrow["extra_s"] = round(time.time() - tx, 2)
            pu = upd - a.bc_updates
            beta = 0.0 if ref is None else max(a.kl_floor, a.kl_beta * (1 - pu / max(1, a.kl_updates)))
            for pg_ in opt.param_groups + opt_x.param_groups: pg_["lr"] = a.bc_lr if is_bc else a.lr
            stats = []; xst = []; mb = min(a.chunks, len(C))
            for _ in range(a.epochs if mb else 0):
                perm = torch.randperm(len(C), device=dev)
                for s0 in range(0, len(C) - mb + 1, mb):
                    c = C[perm[s0:s0 + mb]]; mk = (c >= 0).flatten(); r = c.clamp(min=0); rf = r.flatten()[mk]
                    lg, v, *xc = net.seq(g["s"][r], g["ent"][r], g["grid"][r], g["h"][r[:, 0]], g["priv"][r], feats=bool(X))
                    lg = [x[mk] for x in lg]; v = v[mk]
                    lp, ent, _ = dist_logp_ent(lg, g["act"][rf]); vl = 0.5 * ((v - RET[rf]) ** 2).mean()
                    lv = LIVE[rf]; lm = lambda x: (x * lv).sum() / lv.sum().clamp(min=1)
                    if is_bc:
                        loss = -lm(lp) + 0.5 * vl; st = [-lm(lp).item(), vl.item(), ent.mean().item(), 0.0, 0.0]
                    else:
                        ratio = (lp - g["logp"][rf]).exp(); ad = ADV[rf]; ad = (ad - ad.mean()) / (ad.std() + 1e-8)
                        pg = lm(torch.max(-ad * ratio, -ad * ratio.clamp(1 - a.clip, 1 + a.clip)))
                        kl = torch.zeros((), device=dev)
                        if beta > 0:
                            with torch.no_grad(): lr_, _ = ref.seq(g["s"][r], g["ent"][r], g["grid"][r], g["h"][r[:, 0]])
                            kl = masked_kl([x[mk] for x in lr_], lg).mean()
                        loss = pg - a.ent * lm(ent) + beta * kl + 0.5 * vl
                        st = [pg.item(), vl.item(), ent.mean().item(), kl.item(), ((ratio - 1).abs() > a.clip).float().mean().item()]
                    if X: hl, hs = head_loss(net, xc[0][mk], rf, X, a); loss = loss + hl; xst.append(hs)
                    opt.zero_grad(set_to_none=True); opt_x.zero_grad(set_to_none=True); loss.backward()
                    torch.nn.utils.clip_grad_norm_(main_p, 0.5); opt.step()
                    if X: torch.nn.utils.clip_grad_norm_(x_p, 0.5); opt_x.step()
                    stats.append(st)
            expl = expl_var(ret[rows], buf.val[rows])
            for k in sorted({k for d in xst for k in d}): xrow[k] = round(float(np.mean([d[k] for d in xst if k in d])), 5)
            acts = buf.act[rows]; fired = acts[acts[:, 1] > 0]
            upd += 1
            if is_bc and not bc():                           # BC done: freeze the anchor, PPO starts with an eval
                ref = frozen(net.state_dict()); bnet = ref if bnet is None else bnet
                env.record = False; save(os.path.join(out, "bc.pt")); start_eval()
            if not bc():                                     # league: a snapshot now and then, one opponent per update
                if not pool or upd % a.league_every == 0:
                    if len(pool) >= max(2, a.league_size):   # evict the snapshot the learner beats most easily
                        old = pool.pop(int(np.argmax([pfr(p) for p in pool]))); os.remove(old); pf.pop(os.path.basename(old), None)
                    pool.append(os.path.join(out, "league", "u%05d.pt" % upd)); torch.save(net.state_dict(), pool[-1])
                for k in [k for k in range(M) if lname[k] is None] or ([upd // a.opp_hold % M] if upd % a.opp_hold == 0 else []):
                    load_slot(k)
                json.dump(pf, open(pf_path, "w"))
            keep = sorted(set(pending.values())); buf.compact(keep); remap = {j: i for i, j in enumerate(keep)}
            pending = {aid: remap[j] for aid, j in pending.items()}; traj = {}; final = set(); rec.want = True
            # ---------------- log
            s = np.mean(stats, 0) if stats else np.zeros(5); recent = ep_rows[-400:]; ep_rows = recent
            ok = [r for r in recent if r["rank"] is not None and not r["truncated"]]
            mean = lambda xs: round(float(np.mean(xs)), 4) if len(xs) else None
            row = {"update": upd, "phase": "bc" if is_bc else "ppo", "agent_steps": agent_steps, "minutes": round((time.time() - t0) / 60, 2),
                   "decisions_per_s": round(dps, 1), "update_s": round(time.time() - tu, 2), "rows": nrow,
                   "t_poll_build_act_rest": [round(float(x), 1) for x in np.r_[tm[:3], max(0.0, collect_s - tm[:3].sum())]],
                   "loss_pi": round(float(s[0]), 5), "vloss": round(float(s[1]), 4), "entropy": round(float(s[2]), 4),
                   "kl_bc": round(float(s[3]), 5), "clipfrac": round(float(s[4]), 4), "beta": round(beta, 4), "expl_var": round(expl, 4),
                   "episodes": len(env.episodes), "restarts": env.stats["restarts"],
                   "rank": mean([r["rank"] for r in ok]), "win": mean([r["win"] for r in ok]), "ret": mean([r["ret"] for r in recent]),
                   "ticks": mean([r["ticks"] for r in ok]), "storm_death": mean([r["storm_death"] for r in ok]),
                   "hit_rate": round(sum(r["terms"]["hits"] for r in recent) / max(1.0, sum(r["terms"]["shots"] for r in recent)), 4),
                   "attack_frac": mean([r["attack_steps"] / max(1, r["steps"]) for r in recent]),
                   "move_hist": np.bincount(acts[:, 0], minlength=17)[:17].tolist(), "fire_hist": np.bincount(acts[:, 1], minlength=len(O.FIRE))[:len(O.FIRE)].tolist(),
                   "aim_hist": np.bincount(fired[:, 2] // 15, minlength=24)[:24].tolist()}
            for k in sorted({r["tag"]["kind"] for r in ok}): row["rank_" + k] = mean([r["rank"] for r in ok if r["tag"]["kind"] == k])
            row["pfsp"] = {os.path.basename(p)[:-3]: [round(pfr(p), 2), pf.get(os.path.basename(p), [0, 0])[1]] for p in pool}
            for k in TERMS: row["t_" + k] = mean([r["terms"][k] for r in recent])
            if a.intent_scale: row.update(intent_stats(recent))
            row.update({k: (round(v, 4) if isinstance(v, float) else v) for k, v in xrow.items()})
            prf.write(json.dumps(row) + "\n"); prf.flush()
            print(json.dumps({k: v for k, v in row.items() if not k.endswith("_hist") and k != "pfsp"}), flush=True)
            if upd % 5 == 0: save(os.path.join(out, "ckpt_last.pt"))
    finally:
        save(os.path.join(out, "ckpt_last.pt")); env.close()
        if a.smoke and sys.exc_info()[0] is None:
            assert upd >= smoke_end and os.path.getsize(os.path.join(out, "progress.jsonl")) > 0
            print("smoke ok: %d updates, %d steps, replays %s" % (upd, agent_steps, [x["file"] for x in rec.index]))


if __name__ == "__main__":
    sys.exit(main())
