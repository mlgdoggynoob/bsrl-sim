"""train_ppo.py with the collection split over processes: same PPO + BC, KL anchor, PFSP league, evals and output
files; checkpoints load both ways (--resume a train_ppo checkpoint here and the other way round).

    python -m train_fast --run fast_t --smoke [train_ppo flags]     # outputs $SIM_WORK/runs/fast_t/

What changes (HISTORY 69):
* --workers processes (forked before CUDA starts, no torch use) each own a slice of the instances: MAEnv poll / send,
  the observation (fast_obs.FastObsV5: ObsV5.build with its per-agent loops vectorised, same observations for the
  same RNG state), priv, cond, the battle setup (battle_fn) and, on the worker with instance 0, the replay recorder.
  Rows go to the main process through shared memory (one block per worker), actions come back through a pipe.
* The main process only acts and trains: whatever workers are ready is batched into ONE forward
  (fast_act.StackedActor: stacked weights cached between polls, hand-written batched forward, one upload / download).
  While it acts on one batch the other workers' instances keep stepping.
* --overlap-update (default OFF, a behaviour change): the PPO update runs in a thread while the next rollout is
  collected with the weights from before that update (one-update-stale data; logp / value come from the acting
  weights, so the PPO ratio covers it). Evals and checkpoints are only started between updates in this mode.
Statistically the same algorithm, not bit-identical: every worker has its own battle / noise RNG streams, the rows
of one forward come from whichever instances were ready, and actions are sampled by Gumbel-max (fast_act.sample).
Non-acting heads (--vlive, --aux-w): as train_ppo (its helpers: targets / readouts in prepare(), losses in train()); the
aux labels (env_v5.Env.aux_now) are computed in the workers next to priv and reach the main process in a second shared
memory block; the replay readout (train_ppo.aux_readout of the recorded row) goes back with the actions.
Intents (--intent-scale > 0, --p-plan, --eval-plan: train_ppo's flags): env_v5.Env.intents (and the rule planner) runs in
the workers (train_ppo.policy_s, after the observation build), so the block reaches the main process inside s and both
trainers share one implementation; the planner's reasons go into the worker's replay frames.
Gadgets (--gadgets 1, train_ppo's flag): the workers' battle_fn adds the loadouts (env_v5.with_gadgets) and their
observation build gets env_v5.Env.gadget (self 3).
Star powers (--star-powers 1, train_ppo's flag): the workers' battle_fn adds env_v5.with_star_powers (not observed).
Gears (--gears 1, train_ppo's flag): the workers' battle_fn adds env_v5.with_gears (not observed).
Imitation rows (--imit-data / --imit-updates / --imit-w / --imit-chunks / --imit-burn, train_ppo's flags and helpers, all off):
the pretraining runs in the main process after the BC phase (resumed runs: before the first rollout); --imit-w adds the term
to every minibatch (in the update thread with --overlap-update, which is then the only user of the imitation rng).
Hypercharge (--hyper 1, train_ppo's flag): the same with env_v5.with_hyper and env_v5.Env.hyper (self 4).
Hard scenarios (--eval-scenarios): every worker records its scenario episodes (scenarios.Recorder) and sends their
index entries; the main process writes replays/scn/index.json and, at the eval's end, scenarios.jsonl.
progress.jsonl: all train_ppo fields; t_poll_build_act_rest = [main waiting for workers, build per worker (mean),
act, rest] (workers run in parallel, so they no longer add up to the collect time) + "t_fast" (more timers) and
"wall_dps" (learner decisions per wall second incl. the update).
"""
import argparse, glob, json, mmap, os, shutil, signal, subprocess, sys, threading, time, traceback
import multiprocessing as mp
from multiprocessing.connection import wait as mp_wait
import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))


def parse(argv=None):
    """train_ppo's flags (same names / defaults) + the new ones at the end"""
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
    from train_ppo import slider_flags, head_flags, scenario_flags, intent_flags, imit_flags
    slider_flags(ap); head_flags(ap); scenario_flags(ap); intent_flags(ap)   # sliders; --vlive / --aux-w; --eval-scenarios; --intent-scale
    imit_flags(ap)                                   # --imit-data / --imit-updates / --imit-w / --imit-chunks / --imit-burn
    ap.add_argument("--reward-w", default="", help='JSON overrides of maenv.REWARD_W, e.g. {"taken": -0.25, "dealt": 0.3, "shots": -0.03} (HISTORY 77)')
    ap.add_argument("--noise", type=int, default=1, help="ObsV5 vision noise + latency")
    ap.add_argument("--eval-min", type=float, default=30.0); ap.add_argument("--eval-episodes", type=int, default=200)
    ap.add_argument("--max-ticks", type=int, default=4000); ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--min-ready", type=int, default=0, help="instances per worker poll (0 = all of the worker's)")
    ap.add_argument("--max-wait", type=float, default=0.004, help="a worker poll waits this long after its first ready instance")
    ap.add_argument("--resume", default=None); ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--sp", type=float, default=0.8, help="share of PPO battles that are self-play (rest: vs native AI)")
    ap.add_argument("--league-every", type=int, default=20); ap.add_argument("--league-size", type=int, default=16)
    ap.add_argument("--base", default=None, help="checkpoint of the evalb opponent (default: --resume)")
    ap.add_argument("--evalb-episodes", type=int, default=200)
    ap.add_argument("--eval-n", type=int, default=99, help="instances that play the evals (the rest keep training)")
    ap.add_argument("--opp-slots", type=int, default=3); ap.add_argument("--opp-hold", type=int, default=2)
    ap.add_argument("--pfsp-p", type=float, default=2.0)
    # new
    ap.add_argument("--workers", type=int, default=0, help="collection processes (0 = one per 2 instances)")
    ap.add_argument("--overlap-update", type=int, default=0, help="1 = train while collecting the next rollout (one-update-stale data)")
    ap.add_argument("--smoke-n", type=int, default=2, help="instances for --smoke")
    # BSRL P6 (sim_plan; all off by default = s4 unchanged)
    ap.add_argument("--cmd-vel", type=int, default=0, help="1 = own velocity in the obs = commanded move x speed, as live (A2)")
    ap.add_argument("--cube-shaping", type=float, default=0.0, help="K: cube reward = K x (gamma x held_after - held_before) (B3)")
    ap.add_argument("--roster", default="", help="training battles' brawlers: '' = --brawler only, 'all' = env_v5.heroes(), or codes a,b,c (A3)")
    # BSRL v2 Stage 2 (trio generalist; HISTORY 82)
    ap.add_argument("--p-team", type=float, default=0.0, help="share of training battles played in teams (rest solo)")
    ap.add_argument("--team-size", type=int, default=3, help="team size of team battles: 2, 3, or 0 = random 2-3")
    ap.add_argument("--eval-team", type=int, default=1, help="team size of the eval battles (1 = solo, as before)")
    ap.add_argument("--gen", type=int, default=0, help="1 = instances boot generated layouts (env_v5.use_genmaps), played with --p-gen")
    ap.add_argument("--p-gen", type=float, default=0.5)
    ap.add_argument("--star-powers", type=int, default=0, help="1 = players carry a star power card this build runs (libg reads it: star_audit.LIVE, or the host re-implements it: star_check.LIVE; issues #20, #47; not in the observation)")
    ap.add_argument("--gears", type=int, default=0, help="1 = players carry two gears of their brawler whose effect gear_check confirmed (gear_check.LIVE; issue #51; not in the observation)")
    ap.add_argument("--gadgets", type=int, default=0, help="1 = players carry a gadget, the policy sees it ready (self 3) and may use it (obs v5.7, issue #3; needs a host that activates its kind)")
    ap.add_argument("--hyper", type=int, default=0, help="1 = players carry their hypercharge card, the policy sees it ready (self 4) and may activate it (obs v5.8, issue #4; needs a host with hyper.c)")
    a = ap.parse_args(argv)
    if a.smoke: a.n, a.rollout, a.chunks, a.bc_updates, a.eval_episodes, a.evalb_episodes, a.hours, a.scenario_seeds = a.smoke_n, 2048, 64, 1, 4, 4, 0.2, 1
    a.workers = max(1, min(a.n, a.workers or (a.n + 1) // 2))
    return a


# ------------------------------------------------------------------------------------------------ worker process
def worker(w, lo, hi, a, loc, out, conn, shm, init, ashm=None):
    """instances lo..hi-1 of the run (local index i = global lo + i). Loop: poll -> build -> rows into shm -> message ->
    wait for actions (+ control state) -> send. Never touches torch / CUDA."""
    signal.signal(signal.SIGTERM, signal.SIG_IGN); signal.signal(signal.SIGINT, signal.SIG_IGN)   # the main process stops us
    try:
        from nbpc import diversity as D
        import env_v5 as E, obs_v5 as O, fast_obs as FO, scenarios as SC
        from train_ppo import Recorder, eval_tag, eval_intent, TR_X, policy_s, set_intents
        from fast_act import OBS_W, _OFF
        st = dict(init); evq = []; rng_b = np.random.default_rng(a.seed + 7 + 1000 * w)
        kmix = [int(x) for x in a.kmix.split(",")]; M = a.opp_slots; NW = a.workers
        roster = E.heroes() if a.roster == "all" else [x for x in a.roster.split(",") if x]
        locs = E.locations() if loc == "all" else [loc]
        gen = E.use_genmaps(hi - lo) if a.gen else {}   # before WEnv: these instances boot generated layouts

        def teams(cfg, tag, size):
            """team battle: random groups of `size` (+ the rest alone: trio = 3 x 3 + 1), as env_v5.make_battle_fn"""
            g = [0] * 10
            for k, p in enumerate(rng_b.permutation(10)[:10 // size * size]): g[int(p)] = k // size + 1
            div = dict(cfg["div"]); div["team_groups"] = g
            return {**cfg, "div": div, "tag": {**tag, "team_size": size, "groups": g}}

        def units(g):
            """players grouped by team (a solo player = its own unit), shuffled"""
            u = {}
            for p in range(10): u.setdefault(g[p] or 100 + p, []).append(p)
            return [u[k] for k in rng_b.permutation(sorted(u))]

        def battle_fn(rng, i):                          # --gadgets: MAEnv's rng, so rng_b's draws stay the same
            cfg = battle_cfg(rng, i)
            cfg = E.with_gadgets(cfg, rng) if a.gadgets and "scenario" not in cfg else cfg   # scenarios: as set up
            cfg = E.with_star_powers(cfg, rng) if a.star_powers and "scenario" not in cfg else cfg   # after the gadgets' draws
            cfg = E.with_gears(cfg, rng) if a.gears and "scenario" not in cfg else cfg             # after the star powers' draws
            return E.with_hyper(cfg) if a.hyper and "scenario" not in cfg else cfg         # --hyper: no draw

        def battle_cfg(rng, i):                         # train_ppo.battle_fn; state from the main process
            li, i = i, lo + i; bc = st["bc"]
            tag = {"loc": locs[0], "chr": [a.brawler] * 10, "team_size": 1, "groups": [0] * 10}
            cfg = {"div": D.make_div(location=tag["loc"], chr=tag["chr"]), "tag": tag, "end": "agents"}
            if evq and not bc and i >= a.n - a.eval_n:   # evals stay on --brawler / the first location (comparable numbers)
                sd, kd, pre = evq.pop(0); b = kd == "evalb"
                if kd == "evalscn": return SC.battle_cfg(pre)   # hard scenario (its own map / brawlers / teams)
                if a.eval_team > 1: cfg = teams(cfg, tag, a.eval_team); tag = cfg["tag"]
                return {**cfg, "seed": sd, "ctl": list(range(10)) if b else [0], "end": "player0",
                        "tag": {**tag, "kind": kd, "opp": list(range(1, 10)) if b else [], "intent": eval_intent(kd), **eval_tag(a, pre)}}   # free play (evalp_plan: planner)
            if roster or len(locs) > 1 or gen:           # A3: random brawlers / map per training battle
                g = gen.get(li) if li in gen and rng_b.random() < a.p_gen else None
                lc = E.GEN_BASE if g else locs[int(rng_b.integers(len(locs)))]
                if not g and li in gen and lc == E.GEN_BASE: lc = locs[(locs.index(lc) + 1) % len(locs)]   # shipped map not on this instance
                tag = {**tag, "loc": os.path.basename(os.path.dirname(g)) if g else lc,
                       "chr": [str(x) for x in rng_b.choice(roster, 10)] if roster else tag["chr"]}
                cfg = {**cfg, "div": D.make_div(location=lc, chr=tag["chr"]), "tag": tag}
            if a.p_team and rng_b.random() < a.p_team:
                cfg = teams(cfg, tag, a.team_size or int(rng_b.integers(2, 4))); tag = cfg["tag"]
            sd = int(rng_b.integers(10_000_000, 2 ** 31 - 1))
            if bc:
                return {**cfg, "seed": sd, "ctl": list(range(10)), "native_ctl": True, "tag": {**tag, "kind": "bc"}}
            if rng_b.random() < a.sp:
                k = int(rng_b.integers(M))
                if any(tag["groups"]):                   # teams: a league snapshot plays whole units, the learner at least one
                    us = units(tag["groups"]); opp = sorted(p for u in us[:int(rng_b.integers(0, len(us)))] for p in u)
                else:
                    opp = sorted(rng_b.choice(10, int(rng_b.integers(0, 8)), replace=False).tolist())
                return {**cfg, "seed": sd, "ctl": list(range(10)), "tag": {**tag, "kind": "sp", "opp": opp, "slot": k, "snap": st["lname"][k]}}
            k = int(rng_b.choice(kmix))
            if any(tag["groups"]):                       # vs native: the learner plays k whole units (teamwork with itself)
                us = units(tag["groups"]); ctl = sorted(p for u in us[:max(1, min(k, len(us) - 1))] for p in u)
            else:
                ctl = sorted(rng_b.choice(10, k, replace=False).tolist())
            return {**cfg, "seed": sd, "ctl": ctl, "tag": {**tag, "kind": "k%d" % k}}

        class WEnv(E.Env):
            def _reset(self, i):                        # battle ids unique over the workers (agent id = battle << 4 | player)
                super()._reset(i)
                if self.I[i].state == "resetting": self.I[i].battle = self.battles * NW + w

        E.Env.slider_scale = a.slider_scale; E.Env.record = st["record"]
        E.Env.cube_k, E.Env.cube_gamma = a.cube_shaping, a.gamma
        E.Env.slider_sample, E.Env.slider_norm = a.slider_sample, E.slider_norm(a.slider_norm); set_intents(a)
        env = WEnv(hi - lo, battle_fn, ticks=2, fair=True, max_ticks=a.max_ticks, verbose=True, seed=a.seed + 1000 * w, tag="pf%d_%d" % (os.getpid(), w),
                   reward_w=json.loads(a.reward_w) if a.reward_w else None)
        ob = FO.FastObsV5(noise=O.NOISE if a.noise else None, seed=a.seed + 1000 * w)
        rec = Recorder(out) if lo == 0 else None
        srec = SC.Recorder(out) if a.eval_scenarios else None   # every scenario episode of this worker's instances
        X = np.frombuffer(shm, np.float32).reshape(-1, OBS_W); n_ep = 0; tw = np.zeros(4)   # poll / build / wait for main / messages
        XA = np.frombuffer(ashm, np.float32).reshape(-1, E.AUX_W) if a.aux_w else None     # --aux-w: aux label rows
        while True:
            t0 = time.perf_counter()
            obs, ids, tr = env.poll(min_ready=min(a.min_ready or (hi - lo), hi - lo), max_wait=a.max_wait)
            t1 = time.perf_counter(); B = len(ids); msg = {"B": B}
            if B:
                o = ob.build(obs["vec"], obs["grid"], env.last_meta, ids, cmd=env.cmd_vel(ids) if a.cmd_vel else None, who=env.last_who,
                             gadget=env.gadget(ids) if a.gadgets else None, hyper=env.hyper(ids) if a.hyper else None)
                X[:B, :_OFF[1]] = policy_s(env, ids, o); X[:B, _OFF[1]:_OFF[2]] = o["ent"].reshape(B, -1)   # s = self | cond | intent
                X[:B, _OFF[2]:_OFF[3]] = o["grid"].reshape(B, -1); X[:B, _OFF[3]:_OFF[4]] = FO.priv_fast(env, ids)
                kind = [t["kind"] for t in env.last_tags]; isev = np.char.startswith(np.array(kind), "eval")
                opp = np.array([int(x) & 15 in t.get("opp", ()) for x, t in zip(ids, env.last_tags)], bool)
                sl = np.array([t.get("slot", 0) for t in env.last_tags])
                grp = np.where(~isev & ~opp, 0, np.where(isev & ~opp, 1, np.where(isev & opp, 2, 3 + sl)))   # learner / eval copy / base / league slot
                msg.update(ids=ids, grp=grp.astype(np.int8), isbc=np.array([k == "bc" for k in kind]), dead=env.dead(ids))
                if XA is not None: XA[:B] = env.aux_now(ids); msg["rec"] = rec.row(env, ids) if rec is not None else None
            tw[0] += t1 - t0; tw[1] += time.perf_counter() - t1
            msg["tr"] = [(aid, rew, done, t.get("_act"), {k: t[k] for k in TR_X if k in t}) for (aid, rew, done, t, rank) in tr]
            msg["dropped"] = env.dropped; env.dropped = []
            msg["eps"] = env.episodes[n_ep:]; n_ep = len(env.episodes)
            if srec is not None: msg["scn_rep"] = [srec.finish(r) for r in msg["eps"] if r.get("scn")]   # the main writes the index
            msg["busy"] = len(evq) + sum(s.state != "idle" and (s.cfg or {}).get("tag", {}).get("kind", "").startswith("eval") for s in env.I)
            msg.update(ack=st["ver"], restarts=env.stats["restarts"], tw=tw.tolist())
            if len(env.episodes) > 4096: del env.episodes[:2048]; n_ep = len(env.episodes)   # sent already; the main keeps them
            t2 = time.perf_counter(); conn.send(msg); rep = conn.recv(); tw[2] += time.perf_counter() - t2; tw[3] += 1
            if rep is None: break
            A, ctl, xr = rep
            if ctl:
                evq.extend(ctl.pop("eval", [])); st.update(ctl)
                env.record = st["record"]
                if rec is not None and st.pop("rec_want", False): rec.want = True
            if rec is not None and B: rec.frame(env, ids, o, A, st["upd"], x=xr)
            if srec is not None and B: srec.frame(env, ids, o, A)
            env.send(ids if B else [], A if B else [])   # also steps ready instances whose agents had no observation
        env.close()
    except EOFError:
        try: env.close()
        except Exception: pass
    except Exception:
        try: conn.send({"error": traceback.format_exc()})
        except Exception: pass
        try: env.close()
        except Exception: pass


def shutdown(conns, procs, waiting, timeout=120):
    """every worker gets None as the reply to its next (or current) message, closes its instances and exits"""
    for w in list(waiting):
        try: conns[w].send(None)
        except Exception: pass
    t_end = time.time() + timeout; left = {w for w, p in enumerate(procs) if p.is_alive()}
    while left and time.time() < t_end:
        for c in mp_wait([conns[w] for w in left], timeout=0.5):
            w = conns.index(c)
            try: c.recv(); c.send(None)
            except Exception: left.discard(w)
        left = {w for w in left if procs[w].is_alive()}
    for w in left:
        print("worker %d did not stop: killed (its game instances may be left running)" % w, flush=True); procs[w].kill()


# ------------------------------------------------------------------------------------------------ main process
def main(argv=None):
    a = parse(argv)
    torch.manual_seed(a.seed); np.random.seed(a.seed)
    from nbpc.maenv import REWARD_W, TERMS
    import env_v5 as E, obs_v5 as O
    from train_ppo import Buffer, chunks, eval_summary, eval_items, eval_presets, eval_plan, split_params, gae, expl_var, live_targets, head_loss
    from train_ppo import aux_targets, aux_readout, scenario_items, scenario_eval, intent_stats, load_opt
    from train_ppo import imit_nll, imit_open, imit_pretrain, wmean, set_aim_lead
    import scenarios as SC
    from fast_act import StackedActor, OBS_W, _OFF
    NS = O.N_S
    out = os.path.join(E.WORK, "runs", a.run); os.makedirs(out, exist_ok=True)
    loc = a.loc or E.locations()[0]
    json.dump({**vars(a), "loc": loc, "reward_w": {**REWARD_W, **(json.loads(a.reward_w) if a.reward_w else {})}, "trainer": "train_fast"}, open(os.path.join(out, "config.json"), "w"), indent=1)
    shutil.copy(os.path.join(HERE, "viz.html"), os.path.join(out, "index.html"))
    # ---- what the workers need before they boot (no CUDA yet: they are forked)
    ck = torch.load(a.resume, map_location="cpu", weights_only=False) if a.resume else None
    upd, agent_steps = (ck["update"], ck["agent_steps"]) if ck else (0, 0)
    rng_b = np.random.default_rng(a.seed + 7)
    os.makedirs(os.path.join(out, "league"), exist_ok=True); M = a.opp_slots
    pool = sorted(glob.glob(os.path.join(out, "league", "u*.pt"))); pf_path = os.path.join(out, "league", "pfsp.json")
    pf = json.load(open(pf_path)) if os.path.exists(pf_path) else {}
    pfr = lambda p: pf.get(os.path.basename(p), [5.5, 0])[0]
    def pick_slot():
        w_ = np.array([((10 - pfr(p)) / 9) ** a.pfsp_p for p in pool]); return pool[int(rng_b.choice(len(pool), p=w_ / w_.sum()))]
    lpath = [pick_slot() for _ in range(M)] if pool else [None] * M
    lname = [os.path.basename(p) if p else None for p in lpath]
    bc = lambda: upd < a.bc_updates
    NWk = a.workers; cut = np.linspace(0, a.n, NWk + 1).round().astype(int)
    ctx = mp.get_context("fork"); procs, conns, shms, ashms = [], [], [], []
    init = {"bc": bc(), "lname": list(lname), "upd": upd, "record": a.bc_updates > 0, "ver": 0}
    for w in range(NWk):
        shm = mmap.mmap(-1, max(1, (cut[w + 1] - cut[w]) * 10) * OBS_W * 4)     # anonymous shared: up to 10 agents per instance
        ashm = mmap.mmap(-1, max(1, (cut[w + 1] - cut[w]) * 10) * E.AUX_W * 4) if a.aux_w else None   # aux labels, same rows
        pc, cc = ctx.Pipe()
        p = ctx.Process(target=worker, args=(w, int(cut[w]), int(cut[w + 1]), a, loc, out, cc, shm, init, ashm), daemon=True)
        p.start(); cc.close(); procs.append(p); conns.append(pc); shms.append(np.frombuffer(shm, np.float32).reshape(-1, OBS_W))
        ashms.append(np.frombuffer(ashm, np.float32).reshape(-1, E.AUX_W) if ashm is not None else None)
    # ---- GPU side (after the fork)
    from model import Policy, HID, masked_kl, dist_logp_ent
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")   # CPU: plumbing checks (--smoke) only
    def frozen(sd):
        m = Policy().to(dev).eval(); m.load_state_dict(sd, strict=False); [p.requires_grad_(False) for p in m.parameters()]
        return m
    net = Policy().to(dev); ref = bnet = enet = None; main_p, x_p = split_params(net)   # x_p: the heads that never act (own Adam)
    opt = torch.optim.Adam(main_p, lr=a.bc_lr, eps=1e-5); opt_x = torch.optim.Adam(x_p, lr=a.bc_lr, eps=1e-5)
    if ck:
        net.load_state_dict(ck["model"], strict=False)
        if ck.get("obs_version") != O.OBS_VERSION:   # older inputs: the new columns load zero-padded (model.load_state_dict), same actions
            print("checkpoint obs %s, this code %s: new input columns zero-padded" % (ck.get("obs_version", "< v5.4"), O.OBS_VERSION), flush=True)
        load_opt(opt, ck["opt"], net=net); load_opt(opt_x, ck.get("opt_x"), "optimizer state of the non-acting heads", net=net)
        if ck.get("ref"): ref = frozen(ck["ref"])
        bnet = frozen(torch.load(a.base, map_location="cpu", weights_only=False)["model"] if a.base else ck["model"])
    ck = None; set_aim_lead(a, net, ref)
    print("hero table rows: %d" % net.add_heroes([O.brawler_stats(c) for c in sorted(set(E.heroes()) | {a.brawler})]), flush=True)
    ds_i, imit_batch = imit_open(a)                  # --imit-*: own rng; the update thread (overlap) is the only one sampling during PPO
    imit_pre = lambda: imit_pretrain(a, net, opt, main_p, imit_batch, dev)
    if a.imit_updates and not bc(): imit_pre()       # no BC phase (resumed): before the first collect
    lnets = [frozen(net.state_dict()) for _ in range(M)]
    for k in range(M):
        if lpath[k]: lnets[k].load_state_dict(torch.load(lpath[k], map_location=dev), strict=False)
    def load_slot(k):
        p = pick_slot(); lnets[k].load_state_dict(torch.load(p, map_location=dev), strict=False); lname[k] = os.path.basename(p)
    anet = frozen(net.state_dict()) if a.overlap_update else net     # the weights that act
    actor = StackedActor(dev)
    # ---- control state for the workers (sent with the next reply when it changed)
    ctl = {"bc": bc(), "lname": list(lname), "upd": upd, "record": a.bc_updates > 0, "ver": 0}; sent = [0] * NWk; extra = [dict() for _ in range(NWk)]
    def push(**kw):
        ctl.update(kw); ctl["ver"] += 1
    ack, busy, restarts = [0] * NWk, [0] * NWk, [0] * NWk; tw = np.zeros((NWk, 4))
    ev = {"active": False, "t_last": 0.0 if a.resume else time.time()}
    episodes = []; waiting = set()                    # workers whose message has no reply yet
    buf = Buffer(a.rollout + 8192)
    pending, traj, final, hid = {}, {}, set(), {}
    epf = open(os.path.join(out, "episodes.jsonl"), "a"); evf = open(os.path.join(out, "evals.jsonl"), "a")
    evepf = open(os.path.join(out, "eval_episodes.jsonl"), "a")   # the policy's (player 0) eval rows: scorecard.py eval / per-preset groups
    prf = open(os.path.join(out, "progress.jsonl"), "a")
    scf = open(os.path.join(out, "scenarios.jsonl"), "a") if a.eval_scenarios else None   # --eval-scenarios: one row per scenario eval
    scef = open(os.path.join(out, "scenario_episodes.jsonl"), "a") if a.eval_scenarios else None
    sidx = SC.ScnIndex(out) if a.eval_scenarios else None    # replays/scn/index.json (the workers write the replays)
    t0 = time.time(); n_ep = 0; ep_rows = []; stop = {"now": False}; z = np.zeros(HID, np.float32)
    signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__("now", True))
    T = lambda x, dt=torch.float32: torch.as_tensor(x, device=dev).to(dt)
    th = {"t": None, "res": None}; t_wall = [time.time(), agent_steps]

    def save(path):
        torch.save({"model": net.state_dict(), "opt": opt.state_dict(), "opt_x": opt_x.state_dict(), "ref": ref.state_dict() if ref else None, "update": upd,
                    "agent_steps": agent_steps, "args": vars(a), "loc": loc, "obs_version": O.OBS_VERSION}, path)

    def start_eval():
        nonlocal enet
        enet = frozen(anet.state_dict())
        items = eval_items(a) + scenario_items(a, ev.get("n", 0), upd); ev.update(n=ev.get("n", 0) + 1, t_scn=None)
        cap = [w for w in range(NWk) if cut[w + 1] > a.n - a.eval_n] or list(range(NWk))   # workers with eval instances
        for j, it in enumerate(items): extra[cap[j % len(cap)]].setdefault("eval", []).append(it)
        push(); ev.update(active=True, update=upd, steps=agent_steps, t0=time.time(), n0=len(episodes), ver=ctl["ver"])
        save(os.path.join(out, "ckpt_u%04d.pt" % upd))

    def finish_eval():
        if any(k < ev["ver"] for k in ack) or any(busy): return
        by = lambda kd: list({r["seed"]: r for r in episodes[ev["n0"]:] if r["tag"]["kind"] == kd and r["player"] == 0}.values())
        sm = {"update": ev["update"], "agent_steps": ev["steps"], "minutes": round((time.time() - t0) / 60, 1),
              "eval_s": round(time.time() - ev["t0"], 1), **eval_summary(by("eval")),
              **{"b_" + k: v for k, v in eval_summary(by("evalb")).items() if k in ("episodes", "rank", "ci95", "win", "top3")},
              **eval_presets(episodes[ev["n0"]:]), **eval_plan(episodes[ev["n0"]:])}
        evf.write(json.dumps(sm) + "\n"); evf.flush(); print("[eval]", json.dumps(sm), flush=True); evepf.flush()
        if scf: scenario_eval(episodes[ev["n0"]:], ev, sm["minutes"], scf, scef)
        ev.update(active=False, t_last=time.time())
        epf.flush()   # scorecard.py (CPU, own process: the loop never waits) -> RUN/scorecard.json + one line in the log
        subprocess.Popen([sys.executable, os.path.join(HERE, "scorecard.py"), out], stdin=subprocess.DEVNULL)

    def prepare():
        """GAE + the update's tensors (a copy: the buffer can be refilled while a thread trains on this)"""
        is_bc = bc(); n = buf.n
        adv, ret = gae(traj, pending, final, buf.rew[:n], buf.val[:n], a.gamma, a.lam, buf.done[:n])   # bootstrap: the pending row
        use = [r for r in traj.values() if bool(buf.bc[r[0]]) == is_bc]
        C = torch.as_tensor(chunks(use, a.seq), device=dev); nrow = int((C >= 0).sum())
        g = {k: T(getattr(buf, k)[:n], dt) for k, dt in (("s", torch.float32), ("ent", torch.float32), ("grid", torch.uint8),
             ("h", torch.float32), ("priv", torch.float32), ("act", torch.long), ("logp", torch.float32), ("val", torch.float32))}
        rows = C[C >= 0].cpu().numpy()
        expl = expl_var(ret[rows], buf.val[rows])
        acts = buf.act[rows].copy()
        pu = upd - a.bc_updates
        beta = 0.0 if ref is None else max(a.kl_floor, a.kl_beta * (1 - pu / max(1, a.kl_updates)))
        X = {}; xrow = {}; tx = time.time()                # the heads that never act: targets, readouts (train_ppo helpers)
        if a.vlive:
            _, retl, xrow["expl_var_live"] = live_targets(a, net, g, buf, traj, pending, final, n, rows); X["RETL"] = T(retl)
        if a.aux_w: X.update(aux_targets(a, net, g, buf, traj, final, n, rows, xrow, T))
        if X: xrow["extra_s"] = round(time.time() - tx, 2)
        return {"is_bc": is_bc, "C": C, "nrow": nrow, "g": g, "ADV": T(adv), "RET": T(ret), "LIVE": T(~buf.dead[:n], torch.float32),
                "expl": expl, "acts": acts, "beta": beta, "X": X, "xrow": xrow}

    def train(P_):
        """train_ppo's update loop, unchanged"""
        tu = time.time(); is_bc, C, g, ADV, RET, LIVE, beta, X = P_["is_bc"], P_["C"], P_["g"], P_["ADV"], P_["RET"], P_["LIVE"], P_["beta"], P_["X"]
        for pg_ in opt.param_groups + opt_x.param_groups: pg_["lr"] = a.bc_lr if is_bc else a.lr
        stats = []; xst = []; mb = min(a.chunks, len(C))
        for _ in range(a.epochs if mb else 0):
            perm = torch.randperm(len(C), device=dev)
            for s0 in range(0, len(C) - mb + 1, mb):
                c = C[perm[s0:s0 + mb]]; mk = (c >= 0).flatten(); r = c.clamp(min=0); rf = r.flatten()[mk]
                lg, v, *xc = net.seq(g["s"][r], g["ent"][r], g["grid"][r], g["h"][r[:, 0]], g["priv"][r], feats=bool(X))
                lg = [x[mk] for x in lg]; v = v[mk]
                lp, ent, _ = dist_logp_ent(lg, g["act"][rf]); vl = 0.5 * ((v - RET[rf]) ** 2).mean()
                lv = LIVE[rf]; lm = lambda x: wmean(x, lv)
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
                if a.imit_w and not is_bc:           # --imit-w: the BC loss on the imitation rows next to the PPO loss
                    il, ist = imit_nll(net, imit_batch(), dev); loss = loss + a.imit_w * il; xst.append(ist)
                opt.zero_grad(set_to_none=True); opt_x.zero_grad(set_to_none=True); loss.backward()
                torch.nn.utils.clip_grad_norm_(main_p, 0.5); opt.step()
                if X: torch.nn.utils.clip_grad_norm_(x_p, 0.5); opt_x.step()
                stats.append(st)
        for k in sorted({k for d in xst for k in d}): P_["xrow"][k] = round(float(np.mean([d[k] for d in xst if k in d])), 5)
        P_["stats"] = stats; P_["update_s"] = time.time() - tu
        return P_

    def compact():
        nonlocal pending, traj, final
        keep = sorted(set(pending.values())); buf.compact(keep); remap = {j: i for i, j in enumerate(keep)}
        pending = {aid: remap[j] for aid, j in pending.items()}; traj = {}; final = set()

    def finish_update(P_, coll):
        """after an update: league, slot reloads, BC switch, log row (train_ppo's order)"""
        nonlocal upd, ref, bnet
        upd += 1; is_bc = P_["is_bc"]
        if is_bc and not bc():                           # BC done: freeze the anchor, PPO starts with an eval
            if a.imit_updates: imit_pre()                # the anchor is the policy after the imitation pretraining
            ref = frozen(net.state_dict()); bnet = ref if bnet is None else bnet
            push(record=False); save(os.path.join(out, "bc.pt"))
            if anet is not net: anet.load_state_dict(net.state_dict())
            start_eval()
        if not bc():
            if not pool or upd % a.league_every == 0:
                if len(pool) >= max(2, a.league_size):
                    old = pool.pop(int(np.argmax([pfr(p) for p in pool]))); os.remove(old); pf.pop(os.path.basename(old), None)
                pool.append(os.path.join(out, "league", "u%05d.pt" % upd)); torch.save(net.state_dict(), pool[-1])
            for k in [k for k in range(M) if lname[k] is None] or ([upd // a.opp_hold % M] if upd % a.opp_hold == 0 else []):
                load_slot(k)
            json.dump(pf, open(pf_path, "w"))
        if anet is not net: anet.load_state_dict(net.state_dict())
        extra[0]["rec_want"] = True; push(bc=bc(), lname=list(lname), upd=upd)   # rec_want: the worker with instance 0 records
        stats, acts = P_["stats"], P_["acts"]; fired = acts[acts[:, 1] > 0]
        s = np.mean(stats, 0) if stats else np.zeros(5); nonlocal ep_rows; recent = ep_rows[-400:]; ep_rows = recent
        ok = [r for r in recent if r["rank"] is not None and not r["truncated"]]
        mean = lambda xs: round(float(np.mean(xs)), 4) if len(xs) else None
        now = time.time(); wall = (agent_steps - t_wall[1]) / max(1e-9, now - t_wall[0]); t_wall[:] = [now, agent_steps]
        row = {"update": upd, "phase": "bc" if is_bc else "ppo", "agent_steps": agent_steps, "minutes": round((now - t0) / 60, 2),
               "decisions_per_s": round(coll["dps"], 1), "update_s": round(P_["update_s"], 2), "rows": P_["nrow"],
               "t_poll_build_act_rest": coll["tm"], "t_fast": coll["tf"], "wall_dps": round(wall, 1),
               "loss_pi": round(float(s[0]), 5), "vloss": round(float(s[1]), 4), "entropy": round(float(s[2]), 4),
               "kl_bc": round(float(s[3]), 5), "clipfrac": round(float(s[4]), 4), "beta": round(P_["beta"], 4), "expl_var": round(P_["expl"], 4),
               "episodes": len(episodes), "restarts": sum(restarts),
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
        row.update({k: (round(v, 4) if isinstance(v, float) else v) for k, v in P_["xrow"].items()})
        prf.write(json.dumps(row) + "\n"); prf.flush()
        print(json.dumps({k: v for k, v in row.items() if not k.endswith("_hist") and k != "pfsp"}), flush=True)
        if upd % 5 == 0: save(os.path.join(out, "ckpt_last.pt"))
        if a.overlap_update and not bc() and not ev["active"] and time.time() - ev["t_last"] > a.eval_min * 60: start_eval()

    def join_update():
        if th["t"] is None: return
        th["t"].join(); P_, coll = th["res"]; th["t"] = None
        if "exc" in P_: raise RuntimeError("update thread failed:\n" + P_["exc"])
        finish_update(P_, coll)

    def run_train(P_, coll):
        try: train(P_)
        except Exception: P_["exc"] = traceback.format_exc()
        th["res"] = (P_, coll)

    while not mp_wait(conns, timeout=1.0) and not stop["now"]: pass   # boot: --hours and the first rollout start after it (as train_ppo)
    t0 = time.time(); t_wall[0] = t0; print("[train_fast] %d workers, first instances ready" % NWk, flush=True)
    t_end = t0 + a.hours * 3600; smoke_end = upd + 3
    try:
        while time.time() < t_end and not stop["now"] and not (a.smoke and upd >= smoke_end):
            # ---------------- collect
            dec_t, dec_n = time.time(), 0; tm = np.zeros(4); tw0 = tw.copy(); n_call = n_rows = 0   # main: wait / - / act / rest
            while buf.n < a.rollout and not stop["now"]:
                if th["t"] is not None and not th["t"].is_alive(): join_update()
                tq = time.perf_counter(); rd = mp_wait(conns, timeout=1.0); tm[0] += time.perf_counter() - tq
                if not rd: continue
                msgs = []
                for c in rd:
                    w = conns.index(c); m_ = c.recv()
                    if "error" in m_: raise RuntimeError("worker %d failed:\n%s" % (w, m_["error"]))
                    msgs.append((w, m_)); waiting.add(w); ack[w], busy[w], restarts[w] = m_["ack"], m_["busy"], m_["restarts"]; tw[w] = m_["tw"]
                for w, m_ in msgs:
                    for (aid, rew, done, lab, tx_) in m_["tr"]:
                        j = pending.pop(aid, None)
                        if done: hid.pop(aid, None)
                        if j is None: continue
                        buf.rew[j] = rew; buf.done[j] = done; buf.complete[j] = True
                        buf.rew_int[j] = tx_.get("i_rew", 0.0)
                        if buf.bc[j] and lab is not None: buf.act[j] = lab
                        elif buf.bc[j]: continue                 # a BC row without a label (recording went off): not trained on
                        traj.setdefault(aid, []).append(j)
                        buf.te[j] = tx_.get("te", 0.0)
                        if done: final.add(aid)
                    for aid in m_["dropped"]: pending.pop(aid, None); hid.pop(aid, None)
                live = [(w, m_) for w, m_ in msgs if m_["B"]]; acts_by = {}; xr_by = {}
                if live:
                    ids = np.concatenate([m_["ids"] for _, m_ in live]); grp = np.concatenate([m_["grp"] for _, m_ in live]).astype(np.int64)
                    isbc = np.concatenate([m_["isbc"] for _, m_ in live]); dead = np.concatenate([m_["dead"] for _, m_ in live])
                    X = np.concatenate([shms[w][:m_["B"]] for w, m_ in live]); B = len(ids)
                    XA = np.concatenate([ashms[w][:m_["B"]] for w, m_ in live]) if a.aux_w else None
                    h = np.stack([hid.get(int(x), z) for x in ids])
                    tq = time.perf_counter()
                    A, lp, v, h2 = actor.act_block([anet, enet, bnet] + lnets, grp, X, h)
                    tm[2] += time.perf_counter() - tq; n_call += 1; n_rows += B
                    for x, hh in zip(ids, h2): hid[int(x)] = hh
                    m = (grp == 0) & (isbc == bc())          # BC battles still running after the switch are not collected
                    if m.any():
                        Xm = X[m]
                        rows = buf.add(s=Xm[:, :NS], ent=Xm[:, _OFF[1]:_OFF[2]].reshape(-1, O.N_ENT, O.F_ENT), grid=Xm[:, _OFF[2]:_OFF[3]].reshape(-1, O.G, O.G),
                                       h=h[m], priv=Xm[:, _OFF[3]:_OFF[4]], act=A[m], logp=lp[m], val=v[m], bc=isbc[m], dead=dead[m],
                                       **(E.aux_split(XA[m]) if XA is not None else {}))
                        for aid, j in zip(ids[m], rows): pending[int(aid)] = int(j)
                        agent_steps += int(m.sum()); dec_n += int(m.sum())
                    off = 0
                    for w, m_ in live:
                        acts_by[w] = A[off:off + m_["B"]]
                        if m_.get("rec") is not None:            # --aux-w: the aux heads' readout of the row the worker records
                            q = off + m_["rec"]; xq = X[q:q + 1]
                            xr_by[w] = aux_readout(anet, T(xq[:, :NS]), T(xq[:, _OFF[1]:_OFF[2]].reshape(1, O.N_ENT, O.F_ENT)),
                                                   T(xq[:, _OFF[2]:_OFF[3]].reshape(1, O.G, O.G), torch.uint8), T(h[q:q + 1]))
                        off += m_["B"]
                for w, m_ in msgs:
                    c_ = None
                    if sent[w] != ctl["ver"]:
                        c_ = {k: v_ for k, v_ in ctl.items()}; c_.update(extra[w]); extra[w] = {}; sent[w] = ctl["ver"]
                    conns[w].send((acts_by.get(w), c_, xr_by.get(w))); waiting.discard(w)
                for w, m_ in msgs:
                    episodes.extend(m_["eps"])
                    if m_.get("scn_rep"): sidx.add(m_["scn_rep"]); ev["t_scn"] = time.time()
                for r in episodes[n_ep:]:
                    tg = r["tag"]                            # PFSP score: only battles whose snapshot stayed loaded to the end
                    if (tg["kind"] == "sp" and r["player"] in tg["opp"] and tg.get("snap") and tg["snap"] == lname[tg["slot"]]
                            and r["rank"] is not None and not r["truncated"]):
                        e = pf.setdefault(tg["snap"], [5.5, 0]); e[0] += 0.02 * (r["rank"] - e[0]); e[1] += 1
                    if not r["tag"]["kind"].startswith("eval") and r["player"] not in r["tag"].get("opp", ()):
                        ep_rows.append(r); epf.write(json.dumps(r) + "\n")
                    elif r["tag"]["kind"].startswith("eval") and r["player"] == 0 and r["tag"]["kind"] != "evalscn": evepf.write(json.dumps(r) + "\n")
                n_ep = len(episodes)
                if ev["active"]: finish_eval()
                elif not a.overlap_update and not bc() and time.time() - ev["t_last"] > a.eval_min * 60: start_eval()
            if stop["now"]: break
            collect_s = time.time() - dec_t; dps = dec_n / max(1e-9, collect_s)
            dw = (tw - tw0); tm[1] = dw[:, 1].mean(); tm[3] = max(0.0, collect_s - tm[0] - tm[2])
            coll = {"dps": dps, "tm": [round(float(x), 1) for x in tm],
                    "tf": {"collect_s": round(collect_s, 2), "calls": n_call, "rows_per_call": round(n_rows / max(1, n_call), 1),
                           "act_ms": round(tm[2] / max(1, n_call) * 1e3, 2), "w_poll": round(float(dw[:, 0].mean()), 2),
                           "w_build": round(float(dw[:, 1].mean()), 2), "w_wait_main": round(float(dw[:, 2].mean()), 2), "workers": NWk,
                           "w_msgs": int(dw[:, 3].sum()), "w_poll_ms": round(float(dw[:, 0].sum() / max(1, dw[:, 3].sum()) * 1e3), 2)}}
            # ---------------- update
            join_update()                                    # overlap: the previous update must be done before the next
            epf.flush(); P_ = prepare(); compact()
            if a.overlap_update:
                th["t"] = threading.Thread(target=run_train, args=(P_, coll), daemon=True); th["t"].start()
            else:
                finish_update(train(P_), coll)
        join_update()
    finally:
        try: join_update()
        except Exception: traceback.print_exc()
        save(os.path.join(out, "ckpt_last.pt"))
        shutdown(conns, procs, waiting)
        if a.smoke and sys.exc_info()[0] is None:
            assert upd >= smoke_end and os.path.getsize(os.path.join(out, "progress.jsonl")) > 0
            print("smoke ok: %d updates, %d steps, replays %s" % (upd, agent_steps, sorted(os.listdir(os.path.join(out, "replays")))))


if __name__ == "__main__":
    sys.exit(main())
