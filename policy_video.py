"""One battle (or several, keeping the best) of a train_fast / train_ppo checkpoint rendered by the real game client
(libg + nbgl), as an MP4. Procedure, requirements and troubleshooting: docs/RECORDING.md.

    xvfb-run -a python -m policy_video --ckpt $SIM_WORK/runs/RUN/ckpt_last.pt --out $SIM_WORK/video/RUN --tries 5
    python -m policy_video --check          # no host: flags, run config, battle setup, ffmpeg

Client mode (MAEnv pixels=True), Solo Showdown, player 0 = the policy (the camera follows it), 9 native AI, the eval battle
setup of train_fast. Gadgets / hypercharge / star powers / gears follow the run's config.json next to the checkpoint (what
the policy was trained with); --gadgets / --hyper / --star-powers / --gears override it (-1 = from the config, else off).
The env steps 1 tick (50 ms) so the client draws a frame per tick (20 frames/s of game time); the policy decides every
--every ticks (2 = training's ticks=2, the obs is built only on those steps) and holds its move in between with no fire.
Frames go to ffmpeg at 20 fps (one try<k>_20fps.mp4 per battle); the best battle (lowest rank, then longest) is then
motion-interpolated to --fps (policy_<fps>fps.mp4). episodes.json lists every battle (seed, rank, ticks, kills, file).
Brawlers turn to their aim / walking direction: NBHOST_FACING=1 (set here unless already in the environment) switches on
the host's facing_sync (env.c, engine/patches/facing_sync.patch); without it, or with a host built before it, every brawler
faces the camera.
--overlay 1 (default 0) draws over every frame (overlay.py): a box with its showdown-vision det class tag above it for
every entity the client renders, and the rule planner's pick (planner.RulePlanner on the policy's observation, re-asked
every 10 decisions = 1 s): its rule and reason in a text panel, a white A* path over the walkable tiles from the policy to
the pick's target. The planner is display only: the policy plays on intent none, as in the evals.
--play-plan 1 (default 0) plays as evalp_plan does: battle tag "intent" "plan", Env.planner = RulePlanner(noisy=True), so the
policy gets the planner's intent block every planner tick (Env.INTENT_EVERY), and the overlay draws that active intent
(rule, reason, target, path) instead of a separate display-only pick. The episode lines then carry "intents"
{kind: [started, achieved, timeout, invalid]}."""
import argparse, json, os, subprocess, sys, time
import numpy as np
import torch
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ.setdefault("NBHOST_FACING", "1")   # rendering only: brawlers face their aim / walk (facing_sync.patch)
import env_v5 as E, obs_v5 as O
from model import Policy, HID, dist_logp_ent
from train_ppo import priv, policy_s
from nbpc import diversity as D


FEATURES = ("gadgets", "hyper", "star_powers", "gears")


def features(a):
    """{feature: 0/1}: the flag when set (0 / 1), else the run's config.json next to the checkpoint, else 0"""
    cfg = {}
    p = os.path.join(os.path.dirname(os.path.abspath(a.ckpt)), "config.json") if a.ckpt else ""
    if p and os.path.exists(p): cfg = json.load(open(p))
    return {k: int(getattr(a, k)) if getattr(a, k) >= 0 else int(cfg.get(k, 0) or 0) for k in FEATURES}


def battle_cfg(a, feat, sd, rng):
    """the eval battle of one seed: Solo Showdown on a.loc, everyone a.brawler, player 0 controlled, the run's loadouts"""
    chr_ = [a.brawler] * 10
    tag = {"loc": a.loc, "chr": chr_, "team_size": 1, "groups": [0] * 10, "kind": "eval", "opp": [],
           "intent": "plan" if getattr(a, "play_plan", 0) else "none"}
    cfg = {"div": D.make_div(location=a.loc, chr=chr_), "tag": tag, "end": "player0", "seed": sd, "ctl": [0]}
    if feat["gadgets"]: cfg = E.with_gadgets(cfg, rng)
    if feat["star_powers"]: cfg = E.with_star_powers(cfg, rng)
    if feat["gears"]: cfg = E.with_gears(cfg, rng)
    return E.with_hyper(cfg) if feat["hyper"] else cfg


def check(a, feat):
    """no host: features from flags / config, a battle config per combination, ffmpeg present"""
    import shutil, tempfile
    with tempfile.TemporaryDirectory() as d:
        json.dump({"gadgets": 0, "hyper": 1, "star_powers": 1, "gears": 1}, open(os.path.join(d, "config.json"), "w"))
        ck = os.path.join(d, "ckpt_last.pt")
        f = features(argparse.Namespace(ckpt=ck, gadgets=-1, hyper=-1, star_powers=-1, gears=-1))
        assert f == {"gadgets": 0, "hyper": 1, "star_powers": 1, "gears": 1}, f
        f = features(argparse.Namespace(ckpt=ck, gadgets=1, hyper=0, star_powers=-1, gears=-1))
        assert f == {"gadgets": 1, "hyper": 0, "star_powers": 1, "gears": 1}, f
        f = features(argparse.Namespace(ckpt=os.path.join(d, "x", "c.pt"), gadgets=-1, hyper=-1, star_powers=-1, gears=-1))
        assert f == dict.fromkeys(FEATURES, 0), f
    rng = np.random.default_rng(0)
    plain = battle_cfg(a, dict.fromkeys(FEATURES, 0), 1, rng)
    assert plain["ctl"] == [0] and plain["end"] == "player0" and plain["tag"]["team_size"] == 1 and len(plain["tag"]["chr"]) == 10
    assert plain["tag"]["intent"] == ("plan" if a.play_plan else "none")
    assert battle_cfg(argparse.Namespace(**dict(vars(a), play_plan=1)), dict.fromkeys(FEATURES, 0), 1, rng)["tag"]["intent"] == "plan"
    assert pick_of({"act": None, "why": "no plan fits: free play"}) == {"rule": "none", "reason": "no plan fits: free play", "kind": "none"}
    it = {"kind": "engage", "q": 3, "pt": None, "rule": "engage", "reason": "enemy 5 tiles E at 40 %: engaging"}
    assert pick_of({"act": it}) == {"rule": "engage", "reason": it["reason"], "kind": "engage", "q": 3, "pt": None}
    assert pick_of({"act": dict(it, rule=None, reason="random")})["rule"] == "random"
    for k in FEATURES:
        c = battle_cfg(a, dict(dict.fromkeys(FEATURES, 0), **{k: 1}), 1, np.random.default_rng(0))
        assert c is not None and c["seed"] == 1, k
    assert shutil.which("ffmpeg"), "ffmpeg not found (apt install ffmpeg)"
    assert os.environ.get("NBHOST_FACING") is not None
    import overlay; overlay._check()                 # --overlay: boxes, path, drawing (synthetic state)
    print("policy_video check ok (features %s)" % feat)


def pick_of(st):
    """--play-plan: the overlay pick {rule, reason, kind, q, pt} of agent state st (Env.it[p]): its active intent, else none"""
    it = (st or {}).get("act")
    if it is None: return {"rule": "none", "reason": (st or {}).get("why") or "free play", "kind": "none"}
    return {"rule": it.get("rule") or "random", "reason": it.get("reason", ""), "kind": it["kind"], "q": it.get("q", -1), "pt": it.get("pt")}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default=""); ap.add_argument("--out", default="")
    ap.add_argument("--seed0", type=int, default=91_000_000); ap.add_argument("--tries", type=int, default=1)
    ap.add_argument("--size", default="1920x864"); ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--every", type=int, default=2); ap.add_argument("--brawler", default="Sniper"); ap.add_argument("--loc", default="Survival604")
    ap.add_argument("--max-ticks", type=int, default=4000); ap.add_argument("--tick", type=int, default=1); ap.add_argument("--debug", type=int, default=0)
    for f in ("gadgets", "hyper", "star-powers", "gears"):
        ap.add_argument("--" + f, type=int, default=-1, help="1 / 0 = on / off; -1 = as the run's config.json (none: off)")
    ap.add_argument("--overlay", type=int, default=0, help="1 = det-class boxes + the rule planner's pick and path drawn over the frames")
    ap.add_argument("--play-plan", type=int, default=0, help="1 = the policy plays on the rule planner's intents (as evalp_plan); "
                    "the overlay then shows the intent it is given")
    ap.add_argument("--check", action="store_true", help="self-check without the host")
    a = ap.parse_args(argv)
    if not a.check and not (a.ckpt and a.out): ap.error("--ckpt and --out are required")
    feat = features(a)
    if a.check: return check(a, feat)
    os.makedirs(a.out, exist_ok=True)
    W, H = (int(x) for x in a.size.split("x"))
    torch.set_num_threads(1)
    net = Policy().eval(); ck = torch.load(a.ckpt, map_location="cpu", weights_only=False)
    net.load_state_dict(ck["model"], strict=False); net.add_heroes([O.brawler_stats(c) for c in sorted(set(E.heroes()))])
    print("ckpt %s: update %s, obs %s, features %s, facing %s" % (a.ckpt, ck.get("update"), ck.get("obs_version"), feat,
                                                                 os.environ.get("NBHOST_FACING")), flush=True)
    queue = [a.seed0 + k for k in range(a.tries)]

    def bf(rng, i):
        return battle_cfg(a, feat, queue.pop(0), rng) if queue else None

    E.Env.slider_scale = 0.0
    if a.play_plan:
        import planner as PL
        E.Env.planner = PL.RulePlanner(noisy=True); E.Env.intent_scale = 0.25   # non-zero: Env.intents runs (the reward is unused here)
    env = E.Env(1, bf, ticks=a.tick, fair=True, pixels=True, obs_size=(W, H), max_ticks=a.max_ticks, verbose=True, tag="vid%d" % os.getpid())
    ob = O.ObsV5(noise=O.NOISE, seed=0, ticks=a.every * a.tick)
    T = lambda x, dt=torch.float32: torch.as_tensor(x).to(dt)
    z = np.zeros(HID, np.float32); h = z; hold = None; step = 0; n_ep = 0; ff = None; part = None; results = []; t0 = time.time()
    ov = {"pick": None, "path": [], "n": 0}
    if a.overlay:
        import overlay as OV, planner as PL, state2 as S2
        planner = PL.RulePlanner(noisy=True); title = "%s u%s" % (os.path.basename(os.path.dirname(os.path.abspath(a.ckpt))), ck.get("update"))

    def overlay_frame(img):
        """the frame with --overlay's boxes, planner text and path (overlay.py)"""
        s0 = env.I[0]; r = s0.inst.resp
        if not r.cam_valid: return img
        cam = (float(r.cam_x), float(r.cam_y))
        try: view = S2.StateView(s0.inst.state_bytes(), {}, None)
        except ValueError: return img
        bx = OV.boxes(view, 0, cam, W, H); pk = ov["pick"]; line, tgt, txt = (), None, [title]
        if pk is not None:
            txt += ["planner: " + pk["rule"], pk["reason"]]
            if pk["kind"] != "none":
                me = view.player_char(0)
                tx, ty = (float(r.pl[pk["q"]].x), float(r.pl[pk["q"]].y)) if pk.get("q", -1) >= 0 else pk["pt"]
                if me is not None:
                    walk = s0.sl["walk"]; Ht, Wt = walk.shape
                    a0 = (min(Wt - 1, max(0, int(me[3]) // 300)), min(Ht - 1, max(0, int(me[4]) // 300)))
                    b0 = (min(Wt - 1, max(0, int(tx) // 300)), min(Ht - 1, max(0, int(ty) // 300)))
                    if ov["path"][-1:] != [b0] or ov["path"][:1] != [a0]: ov["path"] = OV.path(walk, a0, b0)
                    line = OV.ground(ov["path"], cam, W, H)
                    if line: line[0] = OV.ground([(int(me[3]) / 300 - 0.5, int(me[4]) / 300 - 0.5)], cam, W, H)[0]
                tgt = OV.ground([(tx / 300 - 0.5, ty / 300 - 0.5)], cam, W, H)[0]
        return OV.draw(img, bx, line, txt, tgt)

    def open_ff(k):
        p = os.path.join(a.out, "try%d_20fps.mp4" % k)
        return p, subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", "20",
                                    "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", p], stdin=subprocess.PIPE)
    try:
        while True:
            obs, ids, _ = env.poll(min_ready=1, max_wait=0.01)
            for r in env.episodes[n_ep:]:
                if r["player"] != 0: continue
                if ff: ff.stdin.close(); ff.wait()
                results.append({"seed": r["seed"], "rank": r["rank"], "ticks": r["ticks"], "file": part, "kills": r["terms"].get("kills"),
                                "frames": step, **({"intents": r.get("intents")} if a.play_plan else {})}); print("[video] episode", json.dumps(results[-1]), flush=True)
                ff = None; h = z; hold = None; step = 0; ov.update(pick=None, path=[], n=0)
            n_ep = len(env.episodes)
            if all(s.state == "idle" for s in env.I): break
            if not len(ids): continue
            f = env.I[0].inst.pixels_rgba()
            if f is not None and f.shape[:2] == (H, W):
                if ff is None: part, ff = open_ff(len(results))
                img = np.ascontiguousarray(f[::-1, :, :3])
                if a.overlay: img = overlay_frame(img)
                ff.stdin.write(np.ascontiguousarray(img).tobytes())
            if step % a.every == 0 or hold is None:
                o = ob.build(obs["vec"], obs["grid"], env.last_meta, ids, who=env.last_who, gadget=env.gadget(ids), hyper=env.hyper(ids))
                s = policy_s(env, ids, o)
                with torch.no_grad():
                    lg, _, h2 = net(T(s), T(o["ent"]), T(o["grid"], torch.uint8), T(h[None]), T(priv(env, ids)))
                    _, _, A = dist_logp_ent(lg)
                A = A.numpy(); h = h2.numpy()[0]; hold = A.copy(); hold[:, 1:] = 0   # in-between ticks: same move, no fire
                if a.overlay and a.play_plan:          # the intent the policy was just given
                    ov["pick"] = pick_of((getattr(env.I[0], "it", None) or {}).get(0))
                elif a.overlay and ov["n"] % 10 == 0:   # the planner's 1 Hz tick (design 4.4), display only
                    ov["pick"] = planner.plan(env, env.I[0], 0, 0, env._world(env.I[0]), o, env.cond(ids))
                if a.overlay: ov["n"] += 1
            else:
                A = hold
            if a.debug and step % (a.every * 10) == 0:
                pl = env.I[0].inst.resp.pl[0]; print("[dbg] step %d act %s pos %d %d hp %d" % (step, A[0].tolist(), pl.x, pl.y, pl.hp), flush=True)
            env.send(ids, A); step += 1
            if step % 400 == 0: print("[video] step %d (%.1f s game, %.0f s wall)" % (step, step / 20, time.time() - t0), flush=True)
    finally:
        if ff: ff.stdin.close(); ff.wait()
        env.close()
    json.dump(results, open(os.path.join(a.out, "episodes.json"), "w"), indent=1)
    ok = [r for r in results if r["file"]]
    if not ok: print("no frames recorded"); return
    best = min(ok, key=lambda r: (r["rank"], -r["ticks"]))
    final = os.path.join(a.out, "policy_%dfps.mp4" % a.fps)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", best["file"], "-vf", "minterpolate=fps=%d:mi_mode=mci:mc_mode=aobmc:me_mode=bidir" % a.fps,
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", final], check=True)
    print("[video] best try: %s -> %s" % (json.dumps(best), final), flush=True)


if __name__ == "__main__":
    main()
