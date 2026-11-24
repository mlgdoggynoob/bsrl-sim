"""Showdown rules check (issue #21): the host's battle end, power-cube death drops and respawn protection, played by the
native AI in solo / duo / trio battles (one boot, every agent native-controlled and observed).

  1. end: a team battle ends (NbeResp.done) within one step of the tick where one team is left (alive, or respawning
     with a living mate), and never runs on with one team left; solo ends at one player. The winner (NbeResp.winner)
     is on the last team, which env_v5.team_ranks then ranks 1.
  2. drops: a brawler holding k cubes that is eliminated or knocked out (into respawn) leaves drop_count(k) cube items
     (items.csv BattleRoyaleBuff, 18000009) near where it fell: libg's own death drop, fed the cubes held (env.c
     sd_mirror_cubes). A respawning brawler that goes out with its team's wipe has no body and drops nothing.
  3. protection: a respawned brawler comes back with spawn protection (state2 chars spawnProt, character +0x431), except
     in Trio when it respawns inside the gas (host log, NB_SD_DBG=1: every respawn's gas / protect against resp_protect).
  4. storm (host log, NB_SD_DBG=1): every storm hit's percent of max HP follows gas_pct (Trio ramps after 1 s, Solo / Duo
     after 5 s); heals inside the gas are halved (env.c gas_tick; logged as heal cuts).
  5. --mods 3,5 (event_modifiers.csv Meteors, HealingMushrooms; showdown_mods.c through NB_SD_MODIFIERS): each meteor hit
     takes 2000 HP (or the rest, or nothing while protected), one meteor at a time with its 3 s circle, and each mushroom
     heal adds at most 1000 HP.
  The WallSpawn shape (spawnfix.c, tiles closer than the area's Radius) is checked here on paper (wall_shape) and live by
  `NB_SPAWNFIX_DBG=1 python -m super_audit --only Wally` ("wall shape ... N tiles").

python -m showdown_check --check                   # the bookkeeping rules on made-up responses (no host)
python -m showdown_check --n 2 --minutes 10        # live (boots the host)
python -m showdown_check --n 2 --minutes 6 --mods 3,5   # live with meteors and healing mushrooms"""
import argparse, collections, os, re, sys, time, numpy as np

CUBE_ITEM = 18000009
DROP_R = 1300         # cube items counted within this of where the brawler fell (spawner 0xb55b74: up to 1200 u in its last fallback)


def drop_count(k, team_size=1):
    """cube items a brawler holding k cubes leaves: min(k / 3 + 1, MaxPowerCubesToDrop), 5 in Solo / Duo Showdown, 2 in
    Trio (game_mode_variations.csv; libg's death drop in the damage root)"""
    return min(k // 3 + 1, 2 if team_size >= 3 else 5)


def teams_left(groups, live):
    """number of teams with a player still in (live: (10,) bool); group 0 = alone (its own team)"""
    return len({(g if g else 100 + p) for p, (g, l) in enumerate(zip(groups, live)) if l})


def live_players(r):
    """(10,) in the battle: present, not eliminated (alive, or respawning: hp 0 with reserved[3] > 0)"""
    return np.array([bool(r.pl[p].present) and not r.pl[p].eliminated and (r.pl[p].alive or r.pl[p].reserved[3] > 0)
                     for p in range(10)])


def new_cubes(items, seen, x, y, r=DROP_R):
    """cube items in state2 `items` not in `seen` (ids) within r of (x, y); adds them to seen"""
    n = 0
    for it in items:
        if it["dataId"] != CUBE_ITEM or it["id"] in seen: continue
        if np.hypot(it["x"] - x, it["y"] - y) <= r: n += 1; seen.add(it["id"])
    return n


def gas_pct(secs, team_size=1):
    """storm hit, % of max HP (env.c gas_tick, one hit per second): 20, +5 per second after the ramp start, which is 5 s in
    Solo / Duo and 1 s in Trio (#22 comment: wiki and patch notes)"""
    ramp = 1 if team_size >= 3 else 5
    return 20 + max(0.0, secs - ramp) * 5


def resp_protect(team_size, in_gas):
    """spawn protection after a respawn (env.c respawn_tick): always, except in Trio on a tile inside the gas ("teammates
    will spawn without an immunity shield when respawning inside the poison", since 04/09/24, #22 wiki findings)"""
    return not (team_size >= 3 and in_gas)


def wall_shape(radius):
    """WallSpawn tiles (dx, dy) around the area's tile (spawnfix.c in_shape): tile centres closer than Radius"""
    k = radius // 300 + 1
    return {(dx, dy) for dx in range(-k, k + 1) for dy in range(-k, k + 1) if 90000 * (dx * dx + dy * dy) < radius * radius}


MET_DMG, MET_WARN, MET_GAP_MIN, MUSH_HEAL = 2000, 50, 60, 1000   # showdown_mods.c (MET_WARN: ExplosionSpawn 2.5 s)


def parse_log(lines):
    """host log lines -> counters and the rule violations (storm hits, meteors, mushrooms) of the rules above"""
    S = collections.Counter(); bad = []; last_impact = None
    for ln in lines:
        m = re.search(r"\[gas\] hit player \d+ group (\d+) tick \d+ secs ([\d.]+) pct ([\d.]+)", ln)
        if m:
            g, secs, pct = int(m[1]), float(m[2]), float(m[3]); S["gas hits g%d" % g] += 1
            if abs(pct - gas_pct(secs, g)) > 0.11: bad.append(ln.strip())
            if g >= 3 and secs > 1: S["trio ramped"] += 1
            continue
        if "[gas] heal cut" in ln: S["heal cuts"] += 1; continue
        m = re.search(r"\[resp\] player \d+ group (\d+) tick \d+ gas (\d) protect (\d)", ln)
        if m:
            g, gas, prot = int(m[1]), int(m[2]), int(m[3]); S["respawns g%d%s" % (g, " in gas" if gas else "")] += 1
            if bool(prot) != resp_protect(g, gas): bad.append(ln.strip())
            continue
        if "[sdmod] battle start" in ln: last_impact = None; continue
        m = re.search(r"\[sdmod\] meteor hit ch \d+ hp (-?\d+) -> (-?\d+)", ln)
        if m:
            a, b = int(m[1]), int(m[2]); S["meteor hits"] += 1
            # exact 2000, the rest, nothing (protected), or back to full hp (a grouped brawler knocked out into respawn,
            # env.c); anything else is a victim's damage modifier (shield, damage reduce / received boost in my_root)
            S["meteor " + ("exact" if b == a - MET_DMG else "lethal" if b <= 0 else "protected" if b == a else
                           "knocked out" if b > a else "status-modified")] += 1
            continue
        m = re.search(r"\[sdmod\] meteor impact tick (\d+)", ln)
        if m:
            t = int(m[1]); S["meteors"] += 1
            if last_impact is not None and t - last_impact < MET_WARN + MET_GAP_MIN: bad.append(ln.strip())
            last_impact = t; continue
        m = re.search(r"\[sdmod\] mushroom heal ch \d+ hp (-?\d+) -> (-?\d+)", ln)
        if m:
            a, b = int(m[1]), int(m[2]); S["mushroom heals"] += 1
            if not 0 <= b - a <= MUSH_HEAL: bad.append(ln.strip())
            continue
        if "[sdmod] mushroom tick" in ln: S["mushrooms"] += 1
    if S["meteor status-modified"] > 0.05 * max(1, S["meteor hits"]): bad.append("meteor hits off 2000 without a reason: %d of %d"
                                                                             % (S["meteor status-modified"], S["meteor hits"]))
    return S, bad


def selfcheck():
    from types import SimpleNamespace as NS
    g = [1, 1, 2, 2, 3, 3, 0, 0, 4, 4]
    assert teams_left(g, [True] * 10) == 6
    assert teams_left(g, [True, False] + [False] * 8) == 1
    assert teams_left(g, [False] * 6 + [True, True] + [False] * 2) == 2      # two solo players
    assert teams_left([0] * 10, [True] * 2 + [False] * 8) == 2
    pl = lambda **o: NS(**{"present": 1, "eliminated": 0, "alive": 1, "reserved": [0, 0, 0, 0], **o})
    r = NS(pl=[pl(), pl(alive=1, reserved=[0, 0, 0, 120]), pl(eliminated=1, alive=0)] + [pl(present=0, alive=0)] * 7)
    assert live_players(r).tolist()[:4] == [True, True, False, False]
    items = [{"id": 1, "dataId": CUBE_ITEM, "x": 100, "y": 100}, {"id": 2, "dataId": CUBE_ITEM, "x": 5000, "y": 100},
             {"id": 3, "dataId": 18000000, "x": 100, "y": 100}]
    seen = set(); assert new_cubes(items, seen, 0, 0) == 1 and new_cubes(items, seen, 0, 0) == 0 and seen == {1}
    assert [drop_count(k) for k in (0, 2, 3, 14, 30)] == [1, 1, 2, 5, 5] and drop_count(9, 3) == 2
    assert gas_pct(3, 1) == 20 and gas_pct(7, 2) == 30 and gas_pct(3, 3) == 30 and gas_pct(0, 3) == 20
    assert resp_protect(2, 1) and resp_protect(3, 0) and not resp_protect(3, 1)
    S, bad = parse_log(["[resp] player 1 group 3 tick 900 gas 1 protect 0", "[resp] player 2 group 2 tick 900 gas 1 protect 1",
                        "[resp] player 3 group 3 tick 900 gas 0 protect 1"])
    assert not bad and S["respawns g3 in gas"] == 1 and S["respawns g2 in gas"] == 1 and S["respawns g3"] == 1, (S, bad)
    S, bad = parse_log(["[resp] player 1 group 3 tick 900 gas 1 protect 1", "[resp] player 2 group 2 tick 900 gas 1 protect 0"])
    assert len(bad) == 2, bad
    assert wall_shape(600) == {(x, y) for x in (-1, 0, 1) for y in (-1, 0, 1)}          # Rosa's Grow Light: 3x3 (wiki)
    assert wall_shape(400) == {(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)} and wall_shape(100) == {(0, 0)}
    assert len(wall_shape(500)) == 9
    S, bad = parse_log(["[gas] hit player 2 group 3 tick 900 secs 3.00 pct 30.0 max 6000 dmg 1800",
                        "[gas] hit player 0 group 1 tick 900 secs 3.00 pct 20.0 max 6000 dmg 1200",
                        "[sdmod] meteor impact tick 700 at 1,2: 1 hit", "[sdmod] meteor hit ch 5 hp 5000 -> 3000",
                        "[sdmod] meteor hit ch 6 hp 1500 -> 0", "[sdmod] meteor impact tick 820 at 1,2: 0 hit",
                        "[sdmod] mushroom heal ch 5 hp 3000 -> 4000"])
    assert not bad and S["meteors"] == 2 and S["meteor hits"] == 2 and S["trio ramped"] == 1, (S, bad)
    S, bad = parse_log(["[gas] hit player 2 group 3 tick 900 secs 3.00 pct 20.0 max 6000 dmg 1200",
                        "[sdmod] meteor hit ch 5 hp 5000 -> 4000", "[sdmod] mushroom heal ch 5 hp 3000 -> 4500",
                        "[sdmod] meteor impact tick 700 at 1,2: 1 hit", "[sdmod] meteor impact tick 760 at 1,2: 1 hit"])
    assert len(bad) == 4 and S["meteor status-modified"] == 1, bad
    S, bad = parse_log(["[sdmod] meteor hit ch 5 hp 1500 -> 7800"] * 30 + ["[sdmod] meteor hit ch 5 hp 5000 -> 4400"])
    assert not bad and S["meteor knocked out"] == 30, (S, bad)
    print("showdown_check ok")


def live(a):
    import env_v5 as E, state2 as S2
    ST = collections.Counter(); MISS = collections.Counter(); ENDS = []; DROPS = []; PROT = []
    os.environ["NB_SD_DBG"] = "1"                                   # the host logs storm hits / events (checks 4, 5)
    if a.mods: os.environ["NB_SD_MODIFIERS"] = a.mods

    class T(E.Env):
        def _start_battle(self, i, r):
            super()._start_battle(i, r); s = self.I[i]
            s.sd = {"one_tick": None, "prev": None, "seen": set(), "pend": [], "back": set()}

        def _finish_step(self, i, r):
            s = self.I[i]; sd = getattr(s, "sd", None); g = s.cfg["tag"]["groups"]; size = s.cfg["tag"]["team_size"]
            if sd is not None:
                st = S2.parse(s.inst.state_bytes()) if r.state_ints else None
                items = [dict(zip(S2.I_F, map(int, row))) for row in st["items"]] if st else []   # state2 rows -> named
                lv = live_players(r); tl = teams_left(g, lv)
                if tl <= 1 and sd["one_tick"] is None: sd["one_tick"] = int(r.tick)
                if r.done:
                    w = int(r.winner); wl = w >= 0 and lv[w]
                    ENDS.append((size, int(r.tick), sd["one_tick"], tl, w, bool(wl)))
                for d in sd["pend"]:                       # 2: count new cube items near each fall for 3 steps
                    d[3] += new_cubes(items, sd["seen"], d[1], d[2]); d[4] -= 1
                done_p = [d for d in sd["pend"] if d[4] <= 0 or r.done]; sd["pend"] = [d for d in sd["pend"] if d not in done_p]
                DROPS.extend((d[0], d[3], d[5]) for d in done_p); MISS.update((d[6], d[7], d[0], d[3]) for d in done_p if d[3] != drop_count(d[0], d[5]))
                prev = sd["prev"]
                if prev is not None:
                    for p in range(10):
                        pl, (k, x, y, wt, el) = r.pl[p], prev[p]
                        out = (pl.eliminated and not el) or (pl.reserved[3] > 0 and not wt)
                        gs = sum(1 for q in g if q and q == g[p]) if g[p] else 1
                        if out and not wt: sd["pend"].append([k, x, y, 0, 3, gs, "elim" if pl.eliminated else "ko", int(r.done)])
                        if wt and pl.reserved[3] <= 0 and not pl.eliminated: sd["back"].add(p)   # respawned this step
                if st and sd["back"]:
                    for p in list(sd["back"]):
                        cid = int(r.pl[p].char_id); c = [row for row in st["chars"] if int(row[S2.C_F.index("id")]) == cid]
                        gs = sum(1 for q in g if q and q == g[p]) if g[p] else 1
                        if c: PROT.append((gs, int(r.pl[p].in_gas > 0), int(c[0][S2.C_F.index("spawnProt")]))); sd["back"].discard(p)
                # held cubes, position (the last live one), waiting, eliminated
                sd["prev"] = [(int(r.pl[p].cubes_total), r.pl[p].x if r.pl[p].alive else (prev[p][1] if prev else 0),
                               r.pl[p].y if r.pl[p].alive else (prev[p][2] if prev else 0), r.pl[p].reserved[3] > 0, bool(r.pl[p].eliminated))
                              for p in range(10)]
                for it in items:                               # cubes already lying around (boxes) before a fall are not drops
                    if it["dataId"] == CUBE_ITEM and not sd["pend"]: sd["seen"].add(it["id"])
            super()._finish_step(i, r)

    bf = E.make_battle_fn(10, p_team=a.p_team)
    def battle_fn(rng, i):
        cfg = bf(rng, i); cfg["native_ctl"] = True; return cfg
    env = T(a.n, battle_fn, ticks=2, fair=True, max_ticks=a.max_ticks, want_state=True)
    logs = {s.inst.log_path: 0 for s in env.I}
    logs = {p: os.path.getsize(p) if os.path.exists(p) else 0 for p in logs}   # read only what this run writes
    rng = np.random.default_rng(a.seed); t0 = None
    try:
        while t0 is None or time.time() - t0 < a.minutes * 60:
            obs, ids, tr = env.poll(min_ready=1, max_wait=0.01)
            if not len(ids): continue
            t0 = t0 or time.time(); B = len(ids)
            env.send(ids, np.stack([rng.integers(0, 17, B), rng.integers(0, 3, B), rng.integers(0, 360, B), rng.integers(0, 8, B)], 1))
    finally:
        env.close()
    by = collections.defaultdict(list)
    for e in ENDS: by[e[0]].append(e)
    for size, v in sorted(by.items()):
        lag = [e[1] - e[2] for e in v if e[2] is not None]
        print("team size %d: %d ends, tick mean %.0f, end - one-team-left ticks max %s, teams left at end %s, winner on last team %d"
              % (size, len(v), np.mean([e[1] for e in v]), max(lag) if lag else None, collections.Counter(e[3] for e in v), sum(e[5] for e in v)))
    ok_drop = sum(1 for k, n, gs in DROPS if n == drop_count(k, gs))
    print("cube drops: %d falls, %d with the expected count; (held, seen, team size) %s" % (len(DROPS), ok_drop, collections.Counter(DROPS).most_common(10)))
    print("misses (fall, at the end, held, seen):", MISS.most_common(12))
    print("respawns (team size, in gas, protected):", collections.Counter(PROT), "| restarts", env.stats["restarts"])
    LS, bad = collections.Counter(), []
    # one instance at a time: the read starts after each instance's first "battle start" line, so one joined log would
    # compare an instance's first meteor with the previous instance's last one
    for p, off in logs.items():
        with open(p, errors="replace") as f: f.seek(off); s, b = parse_log(f.readlines())
        LS.update(s); bad += b
    print("storm and events (host log):", dict(LS), "| rule misses %d" % len(bad), bad[:5])
    assert not bad, "storm / event rule misses"
    assert sum(v for k, v in LS.items() if k.startswith("gas hits")), "no storm hit logged"
    if a.mods and "3" in a.mods.split(","): assert LS["meteors"] and LS["meteor hits"], "no meteor fell or hit"
    if a.mods and "5" in a.mods.split(","): assert LS["mushrooms"] and LS["mushroom heals"], "no mushroom healed"
    assert ENDS and all(e[3] <= 1 for e in ENDS), "a battle ended with more than one team left"
    assert all(e[1] - e[2] <= 4 for e in ENDS if e[2] is not None), "the end lags the last team"
    assert all(e[5] for e in ENDS if e[0] > 1 and e[3] == 1), "winner not on the last team"
    if a.p_team > 0: assert any(e[0] > 1 for e in ENDS), "no team battle ended"
    assert DROPS and ok_drop >= 0.9 * len(DROPS), "cube drops"
    want = [x for x in PROT if resp_protect(x[0], x[1])]   # state2 at the step's end; the exact rule is the log's (above)
    if want: assert sum(1 for x in want if x[2]) >= 0.9 * len(want), "respawned without spawn protection"
    print("showdown_check live ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--check", action="store_true")
    ap.add_argument("--n", type=int, default=2); ap.add_argument("--minutes", type=float, default=10)
    ap.add_argument("--p-team", type=float, default=0.75); ap.add_argument("--max-ticks", type=int, default=6000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--mods", default="", help="event modifier ids for the host (NB_SD_MODIFIERS), e.g. 3,5")
    a = ap.parse_args()
    selfcheck() if a.check else live(a)
