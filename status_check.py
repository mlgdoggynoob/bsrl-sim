"""Live check of status effects and movement (issue #19) that super_audit cannot see: speed boosts, slows, stuns,
Draco's mount and Leon's invisibility in the observation. One boot, one battle on super_audit.MAP (storm off, every native
AI off), scenes in a row:
  1. walk speed: Max, Draco and a target walk WALK steps along a clear corridor; each speed must be within SPEED_TOL of
     its table Speed (the reference for the scenes below);
  2. Max's super (SpeedyUltiArea: SpeedyUltiAreaSpeedBoost, +300 u/s for 80 ticks) then a walk: faster by >= BOOST_MIN;
  3. Spike's super (CactusUltiExplosion: CactusUltiExplosionSlow, -400 u/s, 21 ticks, re-added while inside) lands on a
     target, which then walks: slower by >= SLOW_MIN (Bea's super would be the other projectile slow, but its bees,
     TravelType 3, do not move in this host);
  4. Frank's super (HammerDudeUltiProjectile, StunLengthMS 2000 = 40 ticks) hits a target, which then tries to walk and to
     attack: it moves less than STUN_MOVE and fires nothing, and walks again once the stun is over;
  5. Draco's super (MountUp): mounted he walks faster (DragonRiderUltiSpeed +20 %) and his attack fires another
     projectile than before the mount (the weapon swap to DragonRiderDragonWeapon);
  6. Leon's super (NinjaUlti, Invisibility, SeeInvisibilityDistance 1200): in the observation of an enemy 2000 units away
     his cell of grid channel 5 (enemy brawlers) is set before the super, empty while invisible, set again after he
     attacks (BreakInvisibilityOnAttack); an enemy 600 units away sees him throughout (obs v5.9, host encode.c).
A second battle on the same boot (issue #19 leftovers; NAMES2 shoot, every player has its hypercharge card):
  7. Ollie's super (SkaterUltiTaunt, 50 ticks) lands on a target, which then tries to walk away and to shoot him: it fires
     nothing and does not get away (gains < TAUNT_AWAY from him);
  8. Glowy's super (MenderUltiProjectile: MenderUltiFear, 40 ticks, when the target faces her) hits a target walking at her
     and shooting: it fires nothing and ends farther from her than it started;
  9. Starr Nova's super (MagicalGirlUltiStatus: LifeSteal 30) after the target shot her: she heals >= STEAL_MIN of the damage
     her super deals;
 10. Starr Nova's hypercharged super (MagicalGirlUltiStatusOvercharged: DecreaseReloadTimePercent 90, 30 ticks): after
     it and some quick attacks of her transformed weapon, its ammo refills at least RELOAD_MIN times as fast as after her
     normal super (the super swaps her weapon, so both are measured on the transformed one);
 11. Sandy's super (Sandy_def_ulti, SmokeScreen r2000) dropped at her feet: an enemy 1600 units away sees her before it and
     not inside it, one 600 units away sees her throughout (the level-1 reveal distance 1200 of obs v5.9).
python -m status_check            python -m status_check --check   (no host: the judging rules)
--host-args '--env-arg ...' passes extra host arguments; NB_SUPERFIX=0 in the environment turns the host parts off
(scenes 2-5 then fail), NB_SUPERFIX_CC=0 the stuns and Draco's swap (scenes 4, 5)."""
import argparse, math, sys, time
import numpy as np
import super_audit as SA

TILE = SA.TILE
WALK = 8                  # env steps of 2 ticks per walk measurement (0.8 s)
SPEED_TOL = 0.12          # plain walk vs the table Speed (the joystick target and the step boundary cost a little)
BOOST_MIN, SLOW_MIN = 150, 150   # u/s: Max's +300 and Spike's -400, with room for the measurement
STUN_MOVE = 120           # units a stunned target may still move (the stop lands within the hit's tick)
NAMES = ["Speedy", "Cactus", "HammerDude", "DragonRider", "Ninja"]   # shooters 0-4; targets 5-9
NAMES2 = ["Skater", "Mender", "MagicalGirl", "Sandstorm", "ShotgunGirl"]   # battle 2 (issue #19 leftovers)
TAUNT_AWAY = 150          # units a taunted target may gain from Ollie while it tries to walk away (6 steps walk ~460 u)
STEAL_MIN = 0.2           # Starr Nova's heal / her super's damage (LifeSteal 30 %, with room for regen and rounding)
RELOAD_MIN = 3.0          # refill after her hypercharged / normal super (reload 10x faster while it lasts: ~700 vs ~70 a tick)
TARGET = SA.FILLER
SPEED = {"Speedy": 820, "DragonRider": 720, "ShotgunGirl": 770}   # characters.csv Speed (u/s)


def dir_of(dx, dy):
    """move_dir 0..15 (22.5 degree steps, x right, y down) of a unit corridor vector"""
    return int(round(math.degrees(math.atan2(dy, dx)) / 22.5)) % 16


# ------------------------------------------------------------------ judging
def judge_walk(v, ref, name):
    return [] if abs(v - ref) <= SPEED_TOL * ref else ["%s walks %.0f u/s, table %d" % (name, v, ref)]


def judge_faster(v, v0, what, need=BOOST_MIN):
    return [] if v >= v0 + need else ["%s: %.0f u/s, not faster than %.0f by %d" % (what, v, v0, need)]


def judge_slower(v, v0, what, need=SLOW_MIN):
    return [] if v <= v0 - need else ["%s: %.0f u/s, not slower than %.0f by %d" % (what, v, v0, need)]


def judge_stun(hit, moved, fired, moved_after):
    if not hit: return ["Frank's super did not hit the target (no HP lost)"]
    bad = []
    if moved > STUN_MOVE: bad.append("the stunned target moved %.0f u" % moved)
    if fired: bad.append("the stunned target fired %d projectiles" % fired)
    if moved_after < 3 * STUN_MOVE: bad.append("the target did not walk again after the stun (%.0f u)" % moved_after)
    return bad


def judge_invis(far0, far1, far2, near1):
    bad = []
    if not far0: bad.append("Leon not seen from 2000 u before his super")
    if far1: bad.append("Leon seen from 2000 u while invisible")
    if not near1: bad.append("Leon not seen from 600 u while invisible")
    if not far2: bad.append("Leon still unseen from 2000 u after he attacked")
    return bad


def judge_taunt(hit, away, fired):
    if not hit: return ["Ollie's super did not hit the target"]
    bad = []
    if fired: bad.append("the taunted target fired %d projectiles" % fired)
    if away > TAUNT_AWAY: bad.append("the taunted target got %.0f u away from Ollie" % away)
    return bad


def judge_fear(hit, d0, d1, fired):
    if not hit: return ["Glowy's super did not reach the target (no status, no move)"]
    bad = []
    if fired: bad.append("the feared target fired %d projectiles" % fired)
    if d1 <= d0: bad.append("the feared target ended %.0f u from Glowy, started %.0f u" % (d1, d0))
    return bad


def judge_steal(dmg, heal):
    if dmg <= 0: return ["Starr Nova's super dealt no damage"]
    return [] if heal >= STEAL_MIN * dmg else ["Starr Nova healed %d of %d damage" % (heal, dmg)]


def judge_reload(g0, g1):
    if g0 <= 0: return ["Starr Nova's ammo did not refill after her normal super (%d)" % g0]
    return [] if g1 >= RELOAD_MIN * g0 else ["Starr Nova's ammo refilled %d after her hypercharged super, %d after her normal one" % (g1, g0)]


def judge_smoke(far0, far1, near1):
    bad = []
    if not far0: bad.append("Sandy not seen from 1600 u before her super")
    if far1: bad.append("Sandy seen from 1600 u in her sandstorm")
    if not near1: bad.append("Sandy not seen from 600 u in her sandstorm")
    return bad


def judge_mount(v, v0, proj0, proj1):
    bad = judge_faster(v, v0, "Draco mounted", need=0.12 * v0)
    if not proj0 or not proj1: bad.append("Draco's attack fired nothing (before %s, mounted %s)" % (sorted(proj0), sorted(proj1)))
    elif proj0 & proj1: bad.append("the same weapon before and while mounted (projectiles %s / %s)" % (sorted(proj0), sorted(proj1)))
    return bad


# ------------------------------------------------------------------ live
class Run:
    def __init__(self, inst):
        from nbpc import proto as P
        self.inst, self.P = inst, P
        self.idle = {i: (-1, 0, 0.0, 0.0) for i in range(10)}

    def step(self, acts=None, ticks=2, obs_mask=0):
        a = dict(self.idle); a.update(acts or {})
        return self.inst.step(actions=a, ticks=ticks, flags=self.P.F_STATE | (self.P.F_OBS if obs_mask else 0), native_mask=0,
                              obs_mask=obs_mask)

    def place(self, pos):
        self.inst.setup(positions={i: (int(x), int(y)) for i, (x, y) in pos.items()}, ai_off=list(range(10)), unprotect=list(range(10)))
        for _ in range(3): r = self.step()
        return r

    def walk(self, i, d, steps=WALK, fire=0, aim=0.0):
        """-> (speed u/s over the steps, distance, projectiles fired by i)"""
        r = self.step(); x0, y0, t0 = r.pl[i].x, r.pl[i].y, r.tick; seen = set(self.projs(i)); n0 = len(seen)
        for _ in range(steps):
            r = self.step({i: (d, fire, aim, 0.0)}); seen |= set(self.projs(i))
        dist = float(np.hypot(r.pl[i].x - x0, r.pl[i].y - y0))
        return dist * 20.0 / max(1, r.tick - t0), dist, len(seen) - n0

    def projs(self, i):
        st = SA.parse_state(self.inst.state_bytes())
        return [] if st is None else [int(p[0]) for p in st["pj"] if int(p[2]) == i]

    def proj_kinds(self, i):
        st = SA.parse_state(self.inst.state_bytes())
        return set() if st is None else {int(p[1]) for p in st["pj"] if int(p[2]) == i}

    def sees(self, obs, other):
        """is player other's cell of grid channel 5 set in player obs's observation (this step)"""
        P = self.P
        r = self.step(obs_mask=1 << obs)
        assert (int(r.obs_written) >> obs) & 1, "no observation written for player %d" % obs
        g = self.inst.obs_f32.reshape(P.MAXP, P.OBS_VEC + P.OBS_GRID)[obs, P.OBS_VEC:].reshape(6, 25, 25)
        o, t = r.pl[obs], r.pl[other]
        gx, gy = int(t.x // TILE) - int(o.x // TILE) + 12, int(t.y // TILE) - int(o.y // TILE) + 12
        return bool(0 <= gx < 25 and 0 <= gy < 25 and g[5, gy, gx] > 0)

    def fire(self, s, aim, sd=1.0, kind=2):
        if kind == 2: self.inst.setup(super_fill=[s]); self.step(ticks=1)
        return self.step({s: (-1, kind, aim, sd)}, 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="self-check of the judging (no host)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--host-args", default="", help="extra game host arguments")
    ap.add_argument("--verbose", action="store_true", help="print raw values of the leftover scenes")
    ap.add_argument("--tag", default="sc", help="instance tag (two checks at once need two tags)")
    a = ap.parse_args()
    if a.check: return _check()
    from nbpc import diversity as D
    from nbpc.instance import Instance
    spots = SA.find_spots(SA.MAP); info = {n: SA.expected(n) for n in NAMES}
    inst = Instance(0, tag=a.tag, extra_args=a.host_args.split()); t0 = time.time(); inst.start(); inst.wait_ready()
    print("status_check: host ready in %.0f s" % (time.time() - t0), flush=True)
    fails = {}
    try:
        names = NAMES + [TARGET] * (10 - len(NAMES))
        inst.reset(93600000 + a.seed, gas=0, flags=0, native_mask=0, obs_mask=0, div=D.make_div(location=SA.MAP, chr=names))
        R = Run(inst); R.step(ticks=10)
        home = {i: spots[i][:2] for i in range(10)}
        R.place(home)

        def at(i, k=0):   # player i on spot k, facing its corridor
            x, y, (dx, dy) = spots[k][0], spots[k][1], spots[k][2][0]
            return (x, y), (dx, dy), dir_of(dx, dy)

        # 1. plain walks
        v = {}
        for i, n in ((0, "Speedy"), (3, "DragonRider"), (5, TARGET)):
            p, _, d = at(i, i); R.place({i: p}); v[n], _, _ = R.walk(i, d)
            print("status_check: %s walks %.0f u/s (table %d)" % (n, v[n], SPEED[n]), flush=True)
        fails["walk speeds"] = sum((judge_walk(v[n], SPEED[n], n) for n in v), [])

        # 2. Max's super, then a walk
        p, (dx, dy), d = at(0, 0); R.place({0: p})
        R.fire(0, float(np.degrees(np.arctan2(dy, dx)))); R.step(ticks=4)
        vb, _, _ = R.walk(0, d); print("status_check: Max after his super %.0f u/s" % vb, flush=True)
        fails["Max super speed boost"] = judge_faster(vb, v["Speedy"], "Max after his super")

        # 3. Spike's super on target 5 (spot 1, d = 900 along its corridor), then the target walks on along it
        p, (dx, dy), d = at(1, 1); tp = (p[0] + dx * 900, p[1] + dy * 900)
        r = R.place({1: p, 5: tp}); hp0 = r.pl[5].hp
        R.fire(1, float(np.degrees(np.arctan2(dy, dx))), min(1.0, 900 / info["Cactus"]["range"]))
        for _ in range(15):   # the lob lands, then its explosion area slows
            r = R.step()
            if r.pl[5].hp < hp0: break
        hp1 = r.pl[5].hp; R.step()
        vs, _, _ = R.walk(5, d)
        print("status_check: target after Spike's super %.0f u/s (hp %d -> %d)" % (vs, hp0, hp1), flush=True)
        fails["Spike super slow"] = (["Spike's super did not hit the target"] if hp1 >= hp0 else
                                     judge_slower(vs, v[TARGET], "target after Spike's super"))

        # 4. Frank's super on target 6 (spot 2, d = 900)
        p, (dx, dy), d = at(2, 2); tp = (p[0] + dx * 900, p[1] + dy * 900)
        r = R.place({2: p, 6: tp}); hp0 = r.pl[6].hp
        R.fire(2, float(np.degrees(np.arctan2(dy, dx))), min(1.0, 900 / info["HammerDude"]["range"]))
        hit = False
        for _ in range(20):   # his super winds up, then lands: wait for the hit (<= 40 ticks)
            r = R.step()
            if r.pl[6].hp < hp0: hit = True; break
        back = (d + 8) % 16   # away from Frank, shooting at him
        _, moved, fired = R.walk(6, back, steps=6, fire=1, aim=float(np.degrees(np.arctan2(-dy, -dx))))
        for _ in range(16): R.step()   # the rest of the 40-tick stun
        _, moved_after, _ = R.walk(6, back, steps=6)
        print("status_check: Frank's super hit %s; target moved %.0f u and fired %d while stunned, then moved %.0f u" %
              (hit, moved, fired, moved_after), flush=True)
        fails["Frank super stun"] = judge_stun(hit, moved, fired, moved_after)

        # 5. Draco: an attack before the mount, the super, then a walk and an attack mounted
        p, (dx, dy), d = at(3, 3); R.place({3: p}); aim = float(np.degrees(np.arctan2(dy, dx)))
        R.fire(3, aim, kind=1); R.step(); k0 = R.proj_kinds(3)
        for _ in range(10): R.step()
        R.fire(3, aim);
        for _ in range(8): R.step()   # CastingTime 500 ms
        vm, _, _ = R.walk(3, d)
        R.fire(3, aim, kind=1); R.step(); k1 = R.proj_kinds(3) - k0
        print("status_check: Draco mounted %.0f u/s (unmounted %.0f); projectiles before %s, mounted %s" %
              (vm, v["DragonRider"], sorted(k0), sorted(k1)), flush=True)
        fails["Draco mount"] = judge_mount(vm, v["DragonRider"], k0, k1)

        # 6. Leon on spot 4, enemies 7 (2000 u along the corridor) and 8 (600 u)
        p, (dx, dy), d = at(4, 4); aim = float(np.degrees(np.arctan2(dy, dx)))
        R.place({4: p, 7: (p[0] + dx * 2000, p[1] + dy * 2000), 8: (p[0] + dx * 600, p[1] + dy * 600)})
        far0 = R.sees(7, 4)
        R.fire(4, aim)
        for _ in range(3): R.step()
        far1, near1 = R.sees(7, 4), R.sees(8, 4)
        R.fire(4, aim + 90, kind=1)   # an attack away from both
        for _ in range(3): R.step()
        far2 = R.sees(7, 4)
        print("status_check: Leon seen from 2000 u before / during / after attacking %s %s %s, from 600 u during %s" %
              (far0, far1, far2, near1), flush=True)
        fails["Leon invisible"] = judge_invis(far0, far1, far2, near1)

        # battle 2 (issue #19 leftovers)
        names = NAMES2 + [TARGET] * (10 - len(NAMES2)); info2 = {n: SA.expected(n) for n in NAMES2[:4]}
        div = D.make_div(location=SA.MAP, chr=names); div["hyper"] = list(range(10))
        inst.reset(93600001 + a.seed, gas=0, flags=0, native_mask=0, obs_mask=0, div=div)
        R = Run(inst); R.step(ticks=10); R.place(home)

        def dist(r, i, j): return float(np.hypot(r.pl[i].x - r.pl[j].x, r.pl[i].y - r.pl[j].y))

        # 7. Ollie's super on target 5 (600 u), then the target walks away from him, shooting at him
        p, (dx, dy), d = at(0, 0); tp = (p[0] + dx * 600, p[1] + dy * 600); aim = float(np.degrees(np.arctan2(dy, dx)))
        r = R.place({0: p, 5: tp}); hp0 = r.pl[5].hp
        R.fire(0, aim, min(1.0, 600 / info2["Skater"]["range"]))
        hit = False
        for _ in range(30):   # he jumps, lands (1500 ms), then the taunt area hits: wait for the damage (<= 60 ticks)
            r = R.step()
            if r.pl[5].hp < hp0: hit = True; break
        R.step(); r = R.step(); d0 = dist(r, 0, 5)
        if a.verbose: print("  ollie hp", hp0, r.pl[5].hp, "pos", r.pl[0].x, r.pl[0].y, r.pl[5].x, r.pl[5].y, flush=True)
        _, _, fired = R.walk(5, d, steps=6, fire=1, aim=aim + 180)
        r = R.step(); away = dist(r, 0, 5) - d0
        print("status_check: Ollie's super hit %s; taunted target fired %d, distance to Ollie %.0f -> %.0f" %
              (hit, fired, d0, d0 + away), flush=True)
        fails["Ollie super taunt"] = judge_taunt(hit, away, fired)

        # 8. Glowy's super on target 6 (spot 1, 700 u), which walks at her and shoots (it faces her)
        p, (dx, dy), d = at(1, 1); tp = (p[0] + dx * 700, p[1] + dy * 700); aim = float(np.degrees(np.arctan2(dy, dx)))
        r = R.place({1: p, 6: tp}); R.step({6: ((d + 8) % 16, 0, aim + 180, 0.0)}); r = R.step(); d0 = dist(r, 1, 6)
        R.fire(1, aim, min(1.0, 700 / info2["Mender"]["range"]))
        for _ in range(4): R.step({6: ((d + 8) % 16, 0, aim + 180, 0.0)})
        _, _, fired = R.walk(6, (d + 8) % 16, steps=6, fire=1, aim=aim + 180)
        r = R.step(); d1 = dist(r, 1, 6)
        print("status_check: Glowy's super: feared target fired %d, distance to Glowy %.0f -> %.0f" % (fired, d0, d1), flush=True)
        fails["Glowy super fear"] = judge_fear(True, d0, d1, fired)

        # 9. Starr Nova (spot 2): target 7 (500 u) shoots her, then her super hits it
        p, (dx, dy), d = at(2, 2); tp = (p[0] + dx * 500, p[1] + dy * 500); aim = float(np.degrees(np.arctan2(dy, dx)))
        r = R.place({2: p, 7: tp})
        R.step({7: (-1, 1, aim + 180, 0.0)}, 1)
        for _ in range(6): r = R.step()
        hp_s, hp_t = r.pl[2].hp, r.pl[7].hp
        R.fire(2, aim, min(1.0, 600 / info2["MagicalGirl"]["range"]))
        for _ in range(10): r = R.step()
        dmg, heal = hp_t - r.pl[7].hp, r.pl[2].hp - hp_s
        print("status_check: Starr Nova's super dealt %d, she healed %d (hp %d -> %d)" % (dmg, heal, hp_s, r.pl[2].hp), flush=True)
        fails["Starr Nova lifesteal"] = judge_steal(dmg, heal)

        # 10. Starr Nova's transformed attacks after her normal and her hypercharged super: ammo left after 4 of them
        def after_super(hyper):
            for _ in range(40): R.step()   # the earlier transformation over, ammo full
            inst.setup(super_fill=[2], hyper_fill=[2] if hyper else []); R.step(ticks=1)
            if hyper: R.step({2: (-1, 4, aim, 0.0)}, 1)
            R.step({2: (-1, 2, aim, 1.0)}, 1)
            for _ in range(2): R.step()   # the dash
            s = []
            for _ in range(4): R.step({2: (-1, 1, aim + 90, 0.0)}, 1); s.append(R.step(ticks=3).pl[2].ammo)
            if a.verbose: print("  ammo", s, flush=True)
            return max((y - x for x, y in zip(s, s[1:]) if x < 3000), default=0)   # refill between attacks, ammo not full
        p, (dx, dy), d = at(2, 2); R.place({2: p})
        g0 = after_super(False); g1 = after_super(True)
        print("status_check: Starr Nova's ammo refill between attacks %d after her normal super, %d after her hypercharged one" % (g0, g1), flush=True)
        fails["Starr Nova reload"] = judge_reload(g0, g1)

        # 11. Sandy's super at her feet (spot 3); enemies 8 (1600 u) and 9 (600 u)
        p, (dx, dy), d = at(3, 3); aim = float(np.degrees(np.arctan2(dy, dx)))
        R.place({3: p, 8: (p[0] + dx * 1600, p[1] + dy * 1600), 9: (p[0] + dx * 600, p[1] + dy * 600)})
        far0 = R.sees(8, 3)
        R.fire(3, aim + 180, 0.05)
        for _ in range(8): R.step()
        far1, near1 = R.sees(8, 3), R.sees(9, 3)
        print("status_check: Sandy seen from 1600 u before / in her sandstorm %s %s, from 600 u in it %s" % (far0, far1, near1), flush=True)
        fails["Sandy smoke screen"] = judge_smoke(far0, far1, near1)
    finally:
        inst.close()
    bad = 0
    for k, f in fails.items():
        print("%-24s %s" % (k, "ok" if not f else "FAIL: " + "; ".join(f))); bad += bool(f)
    sys.exit(1 if bad else 0)


def _check():
    assert dir_of(1, 0) == 0 and dir_of(0, 1) == 4 and dir_of(-1, 0) == 8 and dir_of(0, -1) == 12
    assert not judge_walk(800, 820, "Max") and judge_walk(600, 820, "Max")
    assert not judge_faster(1100, 820, "x") and judge_faster(900, 820, "x")
    assert not judge_slower(400, 770, "x") and judge_slower(700, 770, "x")
    assert not judge_stun(True, 40, 0, 900) and judge_stun(False, 0, 0, 900) and judge_stun(True, 500, 0, 900)
    assert judge_stun(True, 0, 2, 900) and judge_stun(True, 0, 0, 50)
    assert not judge_mount(860, 720, {1}, {2}) and judge_mount(730, 720, {1}, {2}) and judge_mount(860, 720, {1}, {1})
    assert judge_mount(860, 720, set(), {2})
    assert not judge_taunt(True, 20, 0) and judge_taunt(False, 0, 0) and judge_taunt(True, 400, 0) and judge_taunt(True, 0, 1)
    assert not judge_fear(True, 600, 900, 0) and judge_fear(True, 600, 500, 0) and judge_fear(True, 600, 900, 2)
    assert not judge_steal(600, 180) and judge_steal(600, 20) and judge_steal(0, 0)
    assert not judge_reload(71, 714) and judge_reload(71, 150) and judge_reload(0, 700)
    assert not judge_smoke(True, False, True) and judge_smoke(True, True, True) and judge_smoke(False, False, True)
    assert not judge_invis(True, False, True, True) and judge_invis(True, True, True, True) and judge_invis(True, False, False, True)
    print("status_check judging ok")


if __name__ == "__main__":
    main()
