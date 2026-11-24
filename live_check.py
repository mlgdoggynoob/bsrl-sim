"""Live check of the host / env round (one boot, random agents, always teams):
  1. team reward (Env._finish_step hold-back): teammates' final transitions share team_place == (10 - best member rank) / 9;
  2. area effects (nbhost_rl encode.c item feature 4: 1 = bomb / enemy area, -1 = my team's area) reach the observation;
  3. generated maps (--gen k instances on $SIM_WORK/genmaps) play without restarts;
  4. teammate respawn (host, 17 s): knock-outs with a living mate come back at a mate's position, play on (can be
     knocked out again), dead steps carry terms["dead"] = 1 and a zero observation;
  5. HUD (obs_v5 noisy path, measured hud_ui.npy): tiles hidden live match the measured chance;
  6. live map: destroyed walls / bushes leave the slider masks (Env.MAP_EVERY) and read as open in the observation grid;
  7. cubes held (cubes_total) drop to 0 at a team knock-out (and the brawler's max HP by 400 per cube); half the battles
     are played by the native AI (cfg native_ctl), which collects cubes;
  8. area effects carry a radius (> 0) and a kind (harms / helps / slows me) in the observation;
  9. gas margin (env_v5.gas_margin from the latched storm step NbeResp.reserved[0], slider gas_safe) < 0 exactly where
     the host flags in_gas;
 10. power level 11 (#22 wiki findings: +10 % HP per level, since 05/09/23): a player in play has max HP = 2 x its
     characters.csv Hitpoints + 400 per cube held, from the spawn on and after every respawn (HP_OFF: known exceptions).
python -m live_check --n 2 --minutes 8 [--gen 1]"""
import argparse, collections, time, numpy as np
import env_v5 as E, obs_v5 as O
from nbpc import fair as F

RS = collections.Counter(); RD = []; RDN = []   # respawn stats; distance respawned -> nearest living mate (RDN: native-played battles)
MP = collections.Counter(); OPENED = {}; CB = collections.Counter()   # live map; battle -> {tile index: now open}; cubes
GS = collections.Counter()   # 9: alive player-steps, in gas, margin < 0 agrees with in_gas
HP = collections.Counter(); HPB = collections.Counter()   # 10: player-steps in play, at 2x; brawlers off it
HP_OFF = {"MechaDude"}   # Meg spawns in her mech (game rule, issue #6): MechaDudeBig's 3700 x 2 = 7400, not her 2400 x 2
LV = 2.0                 # power 11 = 1 + 10 x 10 % (env.c my_root scales damage by the same 2)
class T(E.Env):
    bg = {}; bl = {}
    def _finish_step(self, i, r):
        s = self.I[i]; g = s.cfg["tag"]["groups"]; prev = set(getattr(s, "wprev", set()))
        for p in range(10):                              # 7: knock-outs into respawn with cubes held
            if r.pl[p].reserved[3] > 0 and p not in prev and s.held.get(p, (0, 0))[0] > 0:
                c0, m0 = s.held[p]; CB["out_with_cubes"] += 1; CB["dropped"] += int(r.pl[p].cubes_total == 0)
                CB["max_hp_ok"] += int(r.pl[p].max_hp == m0 - 400 * c0); CB["cubes_step_neg"] += int(r.pl[p].cubes < 0)
            s.held[p] = (int(r.pl[p].cubes_total), int(r.pl[p].max_hp))
        for p in range(10):                              # 10: max HP at power 11
            pl, nm = r.pl[p], s.cfg["tag"]["chr"][p]
            if not pl.alive or pl.eliminated or pl.reserved[3] > 0: continue
            want = LV * int(O.D.table("characters.csv")[nm][1]["Hitpoints"]) + 400 * int(pl.cubes_total)
            HP["n"] += 1; HP["ok"] += int(pl.max_hp == want); HP["back"] += int(p in getattr(s, "back", set()))
            if pl.max_hp != want: HPB[nm] += 1
        for p in range(10):                              # 9: gas margin vs the host's in_gas flag
            pl = r.pl[p]
            if pl.alive and not pl.eliminated and pl.reserved[3] <= 0:
                m = E.gas_margin(pl.x, pl.y, int(r.reserved[0]), s.W, s.H)[0]
                GS["n"] += 1; GS["in_gas"] += int(pl.in_gas > 0); GS["match"] += int((pl.in_gas > 0) == (m < 0))
        old = s.map_tiles
        for p in prev:
            if r.pl[p].reserved[3] == 0 and not r.pl[p].eliminated and r.pl[p].alive:   # a wipe: hp 0 a step before eliminated
                m = [np.hypot(r.pl[q].x - r.pl[p].x, r.pl[q].y - r.pl[p].y) for q in range(10) if q != p and g[q] == g[p] and r.pl[q].alive and r.pl[q].reserved[3] == 0]
                (RDN if s.cfg.get("native_ctl") else RD).append(min(m) if m else -1); s.back = getattr(s, "back", set()) | {p}
        for p in getattr(s, "back", set()) - prev:
            if r.pl[p].reserved[3] > 0 or r.pl[p].eliminated: RS["again"] += 1; s.back.discard(p)   # out again after a respawn
        for p in range(10): RS["wait_steps"] += int(r.pl[p].reserved[3] > 0)
        b0, sl = s.battle, s.sl; MP["map_reads"] += int(r.map_written)
        super()._finish_step(i, r)
        if s.map_tiles is not old and old is not None:   # 6: Env refreshed the slider masks from the live tiles
            lut = O._tile_lut(); seg = lambda t: lut[np.clip(np.asarray(t) % 1000000 + 1, 0, 255)]
            a0, a1 = seg(old), seg(s.map_tiles); MP["refresh"] += 1
            cov = np.isin(np.arange(len(O.SEG)), E._COVER + [O.SEG.index("bush")])
            gone = cov[a0] & ~cov[a1]; MP["cover_or_bush_gone"] += int(gone.sum()); MP["bush_gone"] += int(((a0 == O.SEG.index("bush")) & ~(a1 == O.SEG.index("bush"))).sum())
            want = E.slider_map({}, s.map_tiles, s.W, s.H)
            MP["masks_live"] += int(np.array_equal(want["bush"], sl["bush"]) and np.array_equal(want["nearcover"], sl["nearcover"]))
            op = OPENED.setdefault(b0, {}); op.update({int(k): int(s.map_tiles[k]) for k in np.nonzero(gone)[0]})
    def _start_battle(self, i, r):
        super()._start_battle(i, r); tag = self.I[i].cfg["tag"]; self.bg[self.I[i].battle] = tag["groups"]; self.bl[self.I[i].battle] = tag["loc"]
        self.I[i].held = {}

ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=2); ap.add_argument("--minutes", type=float, default=8)
ap.add_argument("--gen", type=int, default=0)
a = ap.parse_args()
gen = E.use_genmaps(a.gen) if a.gen else None
bf = E.make_battle_fn(10, p_team=1.0, gen=gen, p_gen=1.0)
def battle_fn(rng, i):   # every other battle the native AI plays the agents (observed as usual): it collects cubes (check 7)
    cfg = bf(rng, i); cfg["native_ctl"] = rng.random() < 0.5; return cfg
env = T(a.n, battle_fn, ticks=2, fair=True, max_ticks=4000)
rng = np.random.default_rng(1); ob = O.ObsV5(noise=dict(O.NOISE, latency=(0, 0)), seed=1)  # no latency: compare with the same frame
HUD = collections.Counter(); t0 = None; fins = []; steps = 0; area = collections.Counter()
try:
    while t0 is None or time.time() - t0 < a.minutes * 60:
        obs, ids, tr = env.poll(min_ready=1, max_wait=0.01)
        fins += [t for t in tr if t[2]]; RS["dead_tr"] += sum(1 for t in tr if t[3].get("dead"))
        if not len(ids): continue
        it = obs["vec"][:, F.IT0:F.IT0 + F.IT_K * F.IT_F].reshape(len(ids), F.IT_K, F.IT_F)
        dd = env.dead(ids); RS["dead_obs"] += int(dd.sum()); RS["dead_obs_nonzero"] += int(np.abs(obs["vec"][dd]).sum(1).astype(bool).sum())
        on = it[..., 0] > 0.5; area["enemy_or_bomb"] += int((on & (it[..., 4] > 0.5)).sum()); area["mine"] += int((on & (it[..., 4] < -0.5)).sum())
        area["cube"] += int((on & (it[..., 3] > 0.5)).sum()); area["other"] += int((on & (abs(it[..., 4]) < 0.5) & (it[..., 3] < 0.5)).sum())
        cl = O.from_state2(obs["vec"], obs["grid"], env.last_meta); c = cl["grid"]; n_ = ob.build(obs["vec"], obs["grid"], env.last_meta, ids)["grid"]
        ae = cl["ent"][..., 1 + O.ENT.index("enemy_area_effect")] + cl["ent"][..., 1 + O.ENT.index("teammate_area_effect")] > 0.5   # 8
        area["rows"] += int(ae.sum()); area["radius>0"] += int((cl["ent"][..., O.RAD] > 0)[ae].sum())
        for k, nm in enumerate(("harms", "helps", "slows")): area[nm] += int((cl["ent"][..., O.RAD + 1 + k] > 0.5)[ae].sum())
        for b, aid in enumerate(ids):                    # 6: an opened tile in the window reads as its live tile in grid channel 0
            op = OPENED.get(int(aid) >> 4)
            if not op or not obs["grid"][b].any(): continue
            W_, H_ = int(env.last_meta[b, 3]), int(env.last_meta[b, 4]); tx, ty = int(env.last_meta[b, 0]) // 300, int(env.last_meta[b, 1]) // 300
            for k, tid in op.items():
                gx, gy = k % W_ - tx + 12, k // W_ - ty + 12
                if 0 <= gx < 25 and 0 <= gy < 25: MP["grid_open_ok" if obs["grid"][b, 0, gy, gx] == tid % 1000000 + 1 else "grid_open_bad"] += 1
        vis = c != O.UNKNOWN; HUD["hidden"] += int((vis & (n_ == O.UNKNOWN)).sum()); HUD["expect"] += float(O.hud_p(env.last_meta)[vis].sum()); HUD["vis"] += int(vis.sum())
        t0 = t0 or time.time(); B = len(ids); steps += B
        env.send(ids, np.stack([rng.integers(0, 17, B), rng.integers(0, 3, B), rng.integers(0, 360, B), rng.integers(0, 8, B)], 1))
finally:
    env.close()
grp = collections.defaultdict(list); nogroup_final = 0
for aid, rew, fin, t, rank in fins:
    b, p = aid >> 4, aid & 15; g = env.bg.get(b)
    if g is None or not g[p]: continue
    if "team_place" not in t: nogroup_final += 1; continue      # crashed battle: own placement only
    grp[(b, g[p])].append((t["team_place"], rank, t["place"]))
n_ok = n_full = bad = 0
for k, v in grp.items():
    tps = {round(x[0], 6) for x in v}; assert len(tps) == 1, ("teammates differ", k, v)
    b, gid = k; size = sum(1 for x in env.bg[b] if x == gid)
    if len(v) == size:
        n_full += 1; best = min(x[1] for x in v)
        if abs(v[0][0] - (10 - best) / 9) < 1e-6: n_ok += 1
        else: bad += 1; print("MISMATCH", k, v)
mine = [x[0] for v in grp.values() for x in v]
locs = collections.Counter(env.bl.values()); genb = sum(c for l, c in locs.items() if not l.startswith("Survival"))
print("steps %d battles %d episodes %d restarts %d | grouped finals %d in %d team-battles, full teams %d, rank match %d, mismatch %d, no-team_place finals %d"
      % (steps, env.stats["battles"], len(env.episodes), env.stats["restarts"], len(mine), len(grp), n_full, n_ok, bad, nogroup_final))
print("team_place mean %.3f min %.3f max %.3f; own place mean %.3f" % (np.mean(mine), min(mine), max(mine), np.mean([x[2] for v in grp.values() for x in v])))
print("item rows seen (agent-steps x slots):", dict(area), "| battles on generated maps %d of %d" % (genb, len(env.bl)), "| crashes", [c.get("loc") for c in env.crashes])
assert n_full and not bad
assert area["mine"] > 0, "no own-team area effect seen (host encode.c not rebuilt?)"
print("respawn:", env.resp, dict(RS), "| dist to mate at respawn: n %d median %.0f max %.0f" % (len(RD), np.median(RD) if RD else -1, max(RD) if RD else -1),
      "| final dead transitions", sum(1 for f in fins if f[3].get("dead")))
print("native-played battles: respawns %d, > 600 from a mate %d (max %.0f; not asserted)" % (len(RDN), sum(1 for d in RDN if d > 600), max(RDN, default=-1)))
if a.gen: assert genb > 0
assert env.resp["out"] > 0 and env.resp["back"] > 0 and RD and max(RD) < 600 and RS["dead_obs_nonzero"] == 0
print("HUD: hidden %d of %d visible tiles, expected %.0f from hud_ui.npy" % (HUD["hidden"], HUD["vis"], HUD["expect"]))
assert HUD["hidden"] > 0 and abs(HUD["hidden"] - HUD["expect"]) < 4 * HUD["expect"] ** .5 + 10
print("live map:", dict(MP), "| cubes at knock-outs:", dict(CB))
assert MP["refresh"] > 0 and MP["cover_or_bush_gone"] > 0 and MP["masks_live"] == MP["refresh"]
assert MP["grid_open_ok"] > 0 and MP["grid_open_bad"] <= 0.01 * MP["grid_open_ok"], "observation grid not live"
assert CB["out_with_cubes"] > 0 and CB["dropped"] == CB["out_with_cubes"] == CB["max_hp_ok"] and not CB["cubes_step_neg"]
print("gas margin vs in_gas:", dict(GS))
print("max HP at power 11: %d of %d player-steps (%d after a respawn); off by brawler %s" % (HP["ok"], HP["n"], HP["back"], dict(HPB)))
assert HP["n"] and HP["back"] and not set(HPB) - HP_OFF, dict(HPB)
assert GS["in_gas"] > 0 and GS["n"] - GS["match"] <= 0.02 * GS["in_gas"], dict(GS)
assert area["radius>0"] > 0.8 * area["rows"] and area["harms"] > 0 and area["helps"] + area["slows"] > 0, dict(area)
