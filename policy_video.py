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
faces the camera."""
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
    tag = {"loc": a.loc, "chr": chr_, "team_size": 1, "groups": [0] * 10, "kind": "eval", "opp": [], "intent": "none"}
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
    for k in FEATURES:
        c = battle_cfg(a, dict(dict.fromkeys(FEATURES, 0), **{k: 1}), 1, np.random.default_rng(0))
        assert c is not None and c["seed"] == 1, k
    assert shutil.which("ffmpeg"), "ffmpeg not found (apt install ffmpeg)"
    assert os.environ.get("NBHOST_FACING") is not None
    print("policy_video check ok (features %s)" % feat)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default=""); ap.add_argument("--out", default="")
    ap.add_argument("--seed0", type=int, default=91_000_000); ap.add_argument("--tries", type=int, default=1)
    ap.add_argument("--size", default="1920x864"); ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--every", type=int, default=2); ap.add_argument("--brawler", default="Sniper"); ap.add_argument("--loc", default="Survival604")
    ap.add_argument("--max-ticks", type=int, default=4000); ap.add_argument("--tick", type=int, default=1); ap.add_argument("--debug", type=int, default=0)
    for f in ("gadgets", "hyper", "star-powers", "gears"):
        ap.add_argument("--" + f, type=int, default=-1, help="1 / 0 = on / off; -1 = as the run's config.json (none: off)")
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
    env = E.Env(1, bf, ticks=a.tick, fair=True, pixels=True, obs_size=(W, H), max_ticks=a.max_ticks, verbose=True, tag="vid%d" % os.getpid())
    ob = O.ObsV5(noise=O.NOISE, seed=0, ticks=a.every * a.tick)
    T = lambda x, dt=torch.float32: torch.as_tensor(x).to(dt)
    z = np.zeros(HID, np.float32); h = z; hold = None; step = 0; n_ep = 0; ff = None; part = None; results = []; t0 = time.time()

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
                                "frames": step}); print("[video] episode", json.dumps(results[-1]), flush=True)
                ff = None; h = z; hold = None; step = 0
            n_ep = len(env.episodes)
            if all(s.state == "idle" for s in env.I): break
            if not len(ids): continue
            f = env.I[0].inst.pixels_rgba()
            if f is not None and f.shape[:2] == (H, W):
                if ff is None: part, ff = open_ff(len(results))
                ff.stdin.write(np.ascontiguousarray(f[::-1, :, :3]).tobytes())
            if step % a.every == 0 or hold is None:
                o = ob.build(obs["vec"], obs["grid"], env.last_meta, ids, who=env.last_who, gadget=env.gadget(ids), hyper=env.hyper(ids))
                s = policy_s(env, ids, o)
                with torch.no_grad():
                    lg, _, h2 = net(T(s), T(o["ent"]), T(o["grid"], torch.uint8), T(h[None]), T(priv(env, ids)))
                    _, _, A = dist_logp_ent(lg)
                A = A.numpy(); h = h2.numpy()[0]; hold = A.copy(); hold[:, 1:] = 0   # in-between ticks: same move, no fire
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
