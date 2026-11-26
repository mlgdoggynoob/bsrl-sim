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
A third battle (issue #19 final; NAMES3, every player has its hypercharge card, teams of two: 0+5, 1+6, ...):
 12. Max's hypercharged super (SpeedyOverchargedProjectile drinks to each teammate; SpeedyOverchargedArea2, ChargeSuper
     CustomValue 1000): her teammate's super charge grows by >= DRINK_MIN;
 13. then her hypercharged main attack (SpeedyWeaponOverchargedBuddy; on an enemy hit SpeedyOverchargedBuddyWeaponArea,
     GiveUlti Damage 300) hits an enemy: her teammate's super charge grows again by >= GIVE_MIN;
 14. Edgar's hypercharged super (EnragerOverchargedUlti, EnragerOverchargeSuper CustomValue 50 / CustomValue2 150): his ammo
     refills >= EDGAR_RELOAD times as fast and his hits on a target charge his super >= EDGAR_CHARGE times as much as before it;
 15. Darryl's hypercharged roll (BarrelBotOverchargeChargeArea, BulletSpin): he fires BarrelBotOverchargedProjectile shots;
 16. Pam's turret (HealingStationHeal, issue #22): her teammate, shot first, gains TURRET_PCT % of Pam's max HP per heal,
     TURRET_EVERY ticks apart (the owner's clip: power 11, 10000 HP, +1400 a second); then her hypercharged turret
     (MinigunOverchargedHealingStationHeal, HotAndOverheals as Hot): the teammate, shot after the turret landed, gains
     >= TURRET_HEAL HP within 30 ticks (the turret's heal, before regeneration starts);
 17. Angelo's super (InsectManUltiSwitchSkillArea, SwitchSkill) at his feet: his attack inside fires another projectile
     (InsectManWeaponPoison's) than before.
A fourth battle (gadgets):
 18. Fang's Roundhouse Kick (KickerDudeSweepStun: Stun 10 ticks, RequireLineOfSight) next to a wall: an enemy 600 units
     away in the open is stunned (moves < STUN_MOVE), one 600 units away behind the wall is not;
 19. Meeple's RageQuit (MeepleRageQuitArea, HpBasedStun) after she took damage: an enemy 600 units away is stunned (moves
     < STUN_MOVE beyond the knockback, rage_knock);
 20. Damian's wall gadget (GladiatorGadgetSkillWallArea, GladiatorWallSpawn 26): tiles around its landing become
     GladiatorWallDefault (live map).
A fifth battle (issue #46, gadgets on the brawler itself, gadget_self.c; NAMES5 with GADGETS5, targets ShotgunGirl):
 21. Jacky's speed boost (DrillerGadgetSpeedBoost, +25 %): she walks faster by >= JACKY_MIN of her plain walk;
 22. Hank's shield (ShieldPercent 40, 60 ticks): a target's shot takes <= SHIELD_MAX of what the same shot took before;
 23. Draco's Last Stand (40 ticks): under the fire of three targets he stays alive and reaches exactly 1 HP;
 24. Trunk's inverse damage (DomainInverseDamageGadget: ReceiveDamageInversion, CancelOnDamage): the first hit after it
     heals him instead (the shot's first pellet; the rest of that shot hurts), so that shot takes less than the next one,
     which hurts in full;
 25. Surge's shield (PowerLevelerGadgetShield: CancelOnDamage, then 2 ammo): with his ammo spent, the first shot that hits
     him gives >= AMMO_MIN ammo at once.
A sixth battle (issue #46; NAMES6 with GADGETS6; Tara is player 0, the local player whose view state2's visible flag is):
 26. Tara's vision (80 ticks): an enemy in a bush VISION_D units away is not visible before it and visible while it runs;
 27. Moe's Dodgy Digging (UltiChargeBoostPercent 50): his attack on a target charges his super >= MOE_CHARGE times as
     much per damage as one before it (one attack each, so the super does not fill up and cap the gain);
 28. Sandy's Sleep Stimulator (30 ticks asleep, then full HP): asleep she moves < STUN_MOVE, then her HP is full;
 29. Lou's Freeze (ShieldPercent 100, 20 ticks): a target's shot takes nothing, the same shot before it took HP.
A seventh battle (issue #46; NAMES7 with GADGETS7, Buzz twice with his two cards; player 0 is the local player):
 30. Buzz's X-Ray Shades (240 ticks, BUZZ_VISION_D tiles, inside his 1800): as 26, an enemy in a bush is seen only while
     it runs;
 31. Byron's Shot in the Arm (ConsumesAmmo): with his ammo spent (< 1 bar) a fire is refused (no use spent, published
     cooldown 1); with ammo it spends a use and >= AMMO_COST ammo and heals him;
 32. Buzz's Reserve Buoy: with a full super a fire is refused; after his super it fills the super to the maximum;
 33. Juju's Voodoo Chile on open ground (VoodooGadgetShield, ShieldPercent 30): a target's shot takes <= JUJU_MAX of what
     the same shot took before;
 34. Bonnie's Sugar Rush (CannonGirlGadgetSpeedBoost, +30 %): she walks faster by >= BONNIE_MIN of her plain walk.
An eighth battle (issue #46; NAMES8 with GADGETS8):
 35. Meg's Jolting Volts in her mech (7 % of max HP a second for 100 ticks): within 20 ticks of the fire she gains
     >= MEG_MIN of her max HP (regeneration waits 3 s after the last hit);
 36. Surge's Power Surge (PowerLevelerExtraUltiCharge, UltiChargeBoostPercent 30): as 27, >= SURGE_CHARGE times the super
     charge per damage;
 37. Kenji's heal (CustomValue2 50 % of the damage taken in the last CustomValue1 60 ticks): after a shot took HP, the
     gadget heals KENJI_PCT of it;
 38. Willow's Dive (ShieldPercent 100 and LosePlayerControl for 40 ticks): a target's shot takes HP before it and
     nothing while it runs;
 39. Kit's Cardboard Box (Invisibility 1 for 60 ticks): an enemy 2000 u away sees him before it and not while it runs.
python -m status_check            python -m status_check --check   (no host: the judging rules)
--battles 3,4 runs only those battles (default all eight).
--host-args '--env-arg ...' passes extra host arguments; NB_SUPERFIX=0 in the environment turns the host parts off
(scenes 2-5 then fail, and the scenes of gadget_self.c's status kinds, which need superfix's status store: 21-25, 27-29,
33, 34, 36, 38, 39), NB_SUPERFIX_CC=0 the stuns and Draco's swap (scenes 4, 5), NB_GAD_SELF=0 every gadget_self.c kind
(scenes 21-30, 33, 34, 36, 38, 39)."""
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
NAMES3 = ["Speedy", "Enrager", "BarrelBot", "MinigunDude", "InsectMan"]   # battle 3 (issue #19 final), teams i / i + 5
NAMES4 = ["KickerDude", "Meeple", "Gladiator"]                          # battle 4 (gadgets)
GADGETS4 = {"KickerDude": 23000464, "Meeple": 23000878, "Gladiator": 23001248}   # KickerDude_Sweep, Meeple_RageQuit, Gladiator_Wall
DRINK_MIN = 900           # super charge from Max's drink (ChargeSuper CustomValue 1000 of 4000)
GIVE_MIN = 250            # super charge from one GiveUlti area (Damage 300)
EDGAR_RELOAD = 1.3        # ammo refill after / before his hypercharged super (CustomValue 50 %: 1.5x)
EDGAR_CHARGE = 1.8        # super charge per damage dealt after / before (CustomValue2 150 %: 2.5x)
TURRET_HEAL = 300         # HP in 30 ticks from the hypercharged turret's Hot (one heal of 1400 at least, with room)
TURRET_PCT, TURRET_EVERY = 14, 20   # Pam's turret: % of her max HP per heal, ticks between heals (the owner's clip, #22)
GLAD_WALL = 27000000 + 69 # tiles.csv row of GladiatorWallDefault (DynamicCode 26) as a tile data id (checked in _check)
NAMES5 = ["Driller", "FishTank", "DragonRider", "Domain", "PowerLeveler"]   # battle 5 (issue #46)
GADGETS5 = {"Driller": 23000256, "FishTank": 23000580, "DragonRider": 23000737, "Domain": 23001001, "PowerLeveler": 23000485}
NAMES6 = ["BlackHole", "Digger", "Sandstorm", "IceDude"]                    # battle 6 (issue #46)
GADGETS6 = {"BlackHole": 23000266, "Digger": 23000806, "Sandstorm": 23000270, "IceDude": 23000326}
JACKY_MIN = 0.15          # her walk after / before - 1 (SpeedBoostPercent 25, with room for the measurement)
SHIELD_MAX = 0.8          # shot damage with / without Hank's 40 % shield (0.6, with room for spread)
AMMO_MIN = 1500           # ammo Surge gets at the hit that ends his shield (2 bars = 2000; reload adds < 100 a tick)
MOE_CHARGE = 1.3          # super charge per damage after / before Moe's gadget (+50 %: 1.5x)
VISION_D = (5, 6)         # tiles from Tara to the bush enemy (hidden beyond 900 u, inside the view)
BUSH_TILES = {27000007, 27000008, 27000017, 27000068}   # encode.c BUSH_ROWS as tile data ids (Forest, ...)
NAMES7 = ["RopeDude", "SnakeOil", "RopeDude", "Voodoo", "CannonGirl"]   # battle 7 (issue #46): cards by player, not by name
GADGETS7 = [23000490, 23000333, 23000392, 23000851, 23000480]   # RopeDude_Vision, SnakeOil_Heal, RopeDude_WeakUlti, Voodoo_SelfBuff, CannonGirl_Speed
NAMES8 = ["MechaDude", "PowerLeveler", "Samurai", "Puppeteer", "Attacher"]   # battle 8 (issue #46)
GADGETS8 = {"MechaDude": 23000423, "PowerLeveler": 23000285, "Samurai": 23000818, "Puppeteer": 23000564, "Attacher": 23000648}
# MechaDude_Heal, PowerLeveler_ExtraLevels, Samurai_HealDamageTaken, Puppeteer_Dive, Attacher_Cardboardbox
BUZZ_VISION_D = (4, 5)    # tiles from Buzz to the bush enemy (hidden beyond 900 u, inside his 1800)
AMMO_COST = 900           # ammo Byron's gadget takes (one bar = 1000; reload adds < 100 in the step)
JUJU_MAX = 0.85           # shot damage with / without VoodooGadgetShield's 30 % (0.7, with room for spread)
BONNIE_MIN = 0.15         # her walk after / before - 1 (SpeedBoostPercent 30, with room for the measurement)
MEG_MIN = 0.04            # HP gained in 20 ticks / max HP (7 % a second: 0.07, with room for the tick rounding)
SURGE_CHARGE = 1.15       # super charge per damage after / before Surge's gadget (+30 %: 1.3x)
KENJI_PCT = (0.3, 0.7)    # heal / the shot's damage (CustomValue2 50 %)
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


def judge_gain(g, need, what):
    return [] if g >= need else ["%s: super charge +%d, want >= %d" % (what, g, need)]


def judge_ratio(a, b, need, what):
    if b <= 0: return ["%s: nothing to compare with (before %s, after %s)" % (what, b, a)]
    return [] if a >= need * b else ["%s: %.3g after vs %.3g before (want x%.1f)" % (what, a, b, need)]


def judge_kinds(k0, k1, what):
    if not k0 or not k1: return ["%s: nothing fired (before %s, after %s)" % (what, sorted(k0), sorted(k1))]
    return [] if not (k0 & k1) else ["%s: the same projectile before and after (%s / %s)" % (what, sorted(k0), sorted(k1))]


def judge_turret(gains, pam_max):
    """gains: [(tick, hp gained)] of the teammate beside Pam's turret; >= 2 heals of TURRET_PCT % of pam_max (regeneration
    and the cap give other sizes), consecutive ones TURRET_EVERY ticks apart"""
    want = pam_max * TURRET_PCT // 100; ts = [t for t, g in gains if abs(g - want) <= 1]
    if len(ts) < 2: return ["Pam's turret: heals %s, want 2+ of %d (%d %% of %d)" % (gains, want, TURRET_PCT, pam_max)]
    gaps = sorted({b - a for a, b in zip(ts, ts[1:])})
    return [] if gaps == [TURRET_EVERY] else ["Pam's turret: heals of %d at ticks %s, want %d apart" % (want, ts, TURRET_EVERY)]


def rage_knock(hp, max_hp):
    """Meeple's RageQuit knockback (units) at her hp: superfix_cc.c scales PushbackStrength 120 by the stun's share of
    CustomValue 30 (stun 5 + 25 x the missing HP fraction ticks); the game's knockback moves 6 u per strength"""
    ticks = 5 + int(25 * (max_hp - min(hp, max_hp)) / max_hp) if max_hp > 0 else 5
    return 6 * int(120 * ticks / 30)


def judge_los(open_moved, wall_moved, knock=0):
    """also Meeple's RageQuit: the stunned enemy, then the same enemy once the stun is over; knock: the knockback the
    stunned enemy may move on top of STUN_MOVE"""
    bad = []
    if open_moved > STUN_MOVE + knock: bad.append("the enemy in the open moved %.0f u after Fang's kick" % open_moved)
    if wall_moved < 2 * STUN_MOVE: bad.append("the enemy behind the wall moved only %.0f u (stunned through the wall?)" % wall_moved)
    return bad


def judge_shield(a, b):
    if a <= 0: return ["the shot before Hank's shield took nothing (%d)" % a]
    return [] if b <= SHIELD_MAX * a else ["Hank's shield: the shot took %d, %d before it" % (b, a)]


def judge_stand(alive, hmin):
    if not alive: return ["Draco was knocked out during his Last Stand"]
    return [] if hmin == 1 else ["Draco's Last Stand: lowest HP %d, want 1 (the fire did not reach it, or no clamp)" % hmin]


def judge_invert(h0, h1, h2):
    bad = []
    if h0 - h1 >= h1 - h2: bad.append("Trunk: the first shot after his gadget took %d, no less than the next (%d)" % (h0 - h1, h1 - h2))
    if h2 >= h1: bad.append("Trunk: the next shot did not hurt him (hp %d -> %d)" % (h1, h2))
    return bad


def judge_freeze(a, b):
    if a <= 0: return ["the shot before Lou's freeze took nothing (%d)" % a]
    return [] if b <= 0 else ["Lou's freeze: the shot took %d" % b]


def judge_sleep(moved, hp, mx):
    bad = []
    if moved > STUN_MOVE: bad.append("Sandy moved %.0f u asleep" % moved)
    if hp < mx: bad.append("Sandy woke with hp %d of %d" % (hp, mx))
    return bad


def judge_vision(v0, v1, who="Tara"):
    bad = []
    if v0: bad.append("the bush enemy was visible before %s's vision" % who)
    if not v1: bad.append("the bush enemy was not visible during %s's vision" % who)
    return bad


def judge_refused(u0, u1, cd, what):
    """gad_used before / after a fire that must be refused, gad_cd published before it"""
    bad = [] if u1 == u0 else ["%s: a use was spent (used %d -> %d)" % (what, u0, u1)]
    return bad + ([] if cd >= 1 else ["%s: published as ready (gad_cd %d)" % (what, cd)])


def judge_byron(u0, u1, a0, a1, h0, h1):
    bad = [] if u1 == u0 + 1 else ["Byron's gadget with ammo: no use spent (used %d -> %d)" % (u0, u1)]
    if a0 - a1 < AMMO_COST: bad.append("Byron's gadget took %d ammo (%d -> %d), want >= %d" % (a0 - a1, a0, a1, AMMO_COST))
    if h1 <= h0: bad.append("Byron's gadget did not heal him (hp %d -> %d)" % (h0, h1))
    return bad


def judge_buoy(sc0, sc1, sm):
    if sc0 >= sm: return ["Buzz's super was already full before the buoy (%d of %d)" % (sc0, sm)]
    return [] if sc1 >= sm else ["Buzz's buoy: super %d -> %d of %d" % (sc0, sc1, sm)]


def judge_less(a, b, f, what):
    if a <= 0: return ["%s: the shot before took nothing (%d)" % (what, a)]
    return [] if b <= f * a else ["%s: the shot took %d, %d before" % (what, b, a)]


def judge_none(a, b, what):   # a shot before a full shield took HP, the same shot during it nothing
    if a <= 0: return ["%s: the shot before took nothing (%d)" % (what, a)]
    return [] if b <= 0 else ["%s: the shot took %d" % (what, b)]


def judge_hidden(before, during, what):   # seen by the far enemy before, not while invisible
    bad = [] if before else ["%s not seen from 2000 u before" % what]
    return bad + (["%s seen from 2000 u while invisible" % what] if during else [])


def judge_kenji(loss, heal):
    if loss <= 0: return ["the shot on Kenji took nothing"]
    lo, hi = KENJI_PCT
    return [] if lo * loss <= heal <= hi * loss else ["Kenji's gadget healed %d of a %d shot, want %.0f-%.0f %%" % (heal, loss, 100 * lo, 100 * hi)]


def bush_spot(location=SA.MAP, vd=VISION_D):
    """an open tile and a bush tile vd tiles to its right on the same row, the open one away from the map's sides
    (the camera follows it unclamped): -> (open, bush) world positions"""
    from nbpc import diversity as D
    ids, rows = D.map_reference(location); H, W = len(rows), len(rows[0]); T = D.table("tiles.csv")
    walk = {i for _, (i, r) in T.items() if r.get("BlocksMovement") != "true" and r.get("BlocksProjectiles") != "true"}
    g = np.array(ids).reshape(H, W); raw = np.array([list(r) for r in rows])
    op = np.isin(g, list(walk - BUSH_TILES)) & ~np.char.isdigit(raw); bu = np.isin(g, list(BUSH_TILES))
    for y in range(3, H - 3):
        for x in range(11, W - 11 - max(vd)):
            for k in vd:
                if op[y, x] and bu[y, x + k] and not bu[y, x + 1:x + 3].any():
                    c = lambda tx: ((tx + 0.5) * TILE, (y + 0.5) * TILE)
                    return c(x), c(x + k)
    return None


def wall_spot(location=SA.MAP):
    """a row with 5 open tiles, a wall tile (walls above and below too), 3 open tiles: -> (fang, open enemy, walled enemy)
    world positions (Fang next to the wall, the enemies 2 tiles from him on either side)"""
    from nbpc import diversity as D
    ids, rows = D.map_reference(location); H, W = len(rows), len(rows[0]); T = D.table("tiles.csv")
    blk = {i for _, (i, r) in T.items() if r.get("BlocksProjectiles") == "true"}
    walk = {i for _, (i, r) in T.items() if r.get("BlocksMovement") != "true" and r.get("BlocksProjectiles") != "true"}
    g = np.array(ids).reshape(H, W); raw = np.array([list(r) for r in rows])
    op = np.isin(g, list(walk)) & ~np.char.isdigit(raw); wl = np.isin(g, list(blk))
    for y in range(2, H - 2):
        for x in range(6, W - 4):
            if wl[y - 1:y + 2, x].all() and op[y, x - 5:x].all() and op[y, x + 1:x + 4].all() and op[y - 1:y + 2, x - 5:x].all():
                c = lambda tx: ((tx + 0.5) * TILE, (y + 0.5) * TILE)
                return c(x - 1), c(x - 3), c(x + 1)
    return None


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
    ap.add_argument("--battles", default="1,2,3,4,5,6,7,8", help="which battles to run (1-8)")
    a = ap.parse_args()
    if a.check: return _check()
    from nbpc import diversity as D
    from nbpc.instance import Instance
    spots = SA.find_spots(SA.MAP); info = {n: SA.expected(n) for n in NAMES}
    inst = Instance(0, tag=a.tag, extra_args=a.host_args.split()); t0 = time.time(); inst.start(); inst.wait_ready()
    print("status_check: host ready in %.0f s" % (time.time() - t0), flush=True)
    fails = {}; B = {int(x) for x in a.battles.split(",") if x}
    try:
        battles(inst, a, spots, info, fails, B)
    finally:
        inst.close()
    bad = 0
    for k, f in fails.items():
        print("%-24s %s" % (k, "ok" if not f else "FAIL: " + "; ".join(f))); bad += bool(f)
    sys.exit(1 if bad else 0)


def battles(inst, a, spots, info, fails, B):
    from nbpc import diversity as D
    home = {i: spots[i][:2] for i in range(10)}

    def at(i, k=0):   # player i on spot k, facing its corridor
        x, y, (dx, dy) = spots[k][0], spots[k][1], spots[k][2][0]
        return (x, y), (dx, dy), dir_of(dx, dy)

    def dist(r, i, j): return float(np.hypot(r.pl[i].x - r.pl[j].x, r.pl[i].y - r.pl[j].y))
    if 1 in B:
        names = NAMES + [TARGET] * (10 - len(NAMES))
        inst.reset(93600000 + a.seed, gas=0, flags=0, native_mask=0, obs_mask=0, div=D.make_div(location=SA.MAP, chr=names))
        R = Run(inst); R.step(ticks=10)
        R.place(home)

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

    if 2 in B:   # battle 2 (issue #19 leftovers)
        names = NAMES2 + [TARGET] * (10 - len(NAMES2)); info2 = {n: SA.expected(n) for n in NAMES2[:4]}
        div = D.make_div(location=SA.MAP, chr=names); div["hyper"] = list(range(10))
        inst.reset(93600001 + a.seed, gas=0, flags=0, native_mask=0, obs_mask=0, div=div)
        R = Run(inst); R.step(ticks=10); R.place(home)

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
    if 3 in B:   # battle 3 (issue #19 final): hypercharged supers and Angelo; teams i / i + 5
        names = NAMES3 + [TARGET] * (10 - len(NAMES3))
        div = D.make_div(location=SA.MAP, chr=names); div["hyper"] = list(range(10)); div["team_groups"] = [1, 2, 3, 4, 5] * 2
        inst.reset(93600002 + a.seed, gas=0, flags=0, native_mask=0, obs_mask=0, div=div)
        R = Run(inst); R.step(ticks=10); R.place(home)

        def hyper_super(i, aim, sd):
            inst.setup(super_fill=[i], hyper_fill=[i]); R.step(ticks=1)
            R.step({i: (-1, 4, aim, 0.0)}, 1); return R.step({i: (-1, 2, aim, sd)}, 1)

        def sc(r, i): return int(r.pl[i].super_charge)

        # 12. Max (spot 0), teammate 5 at 600 u, enemy 6 at 500 u the other way
        p, (dx, dy), d = at(0, 0); aim = float(np.degrees(np.arctan2(dy, dx)))
        r = R.place({0: p, 5: (p[0] + dx * 600, p[1] + dy * 600), 6: (p[0] - dx * 500, p[1] - dy * 500)}); c0 = sc(r, 5)
        hyper_super(0, aim, 0.5)
        for _ in range(25): r = R.step()   # the drink flies (ConstantFlyTime) and lands
        c1 = sc(r, 5)
        print("status_check: Max's hypercharged super: teammate's super charge %d -> %d" % (c0, c1), flush=True)
        fails["Max drink ChargeSuper"] = judge_gain(c1 - c0, DRINK_MIN, "teammate after Max's drink")
        # 13. still hypercharged: two main attacks at enemy 6
        mk = set()
        for _ in range(2):
            R.step({0: (-1, 1, aim + 180, 0.0)}, 1)
            for _ in range(6): r = R.step(); mk |= {SA.data_name(k) for k in R.proj_kinds(0)}
        if a.verbose: print("  max projectiles", sorted(mk), "hyper left", int(r.hyp_left[0]), flush=True)
        c2 = sc(r, 5)
        print("status_check: Max's hypercharged attacks: teammate's super charge %d -> %d (enemy hp %d)" % (c1, c2, r.pl[6].hp), flush=True)
        if "SpeedyOverchargedBuddyProjectile" in mk:   # GiveUlti comes with the buddy weapon only (notes/issue19-final.md)
            fails["Max attack GiveUlti"] = judge_gain(c2 - c1, GIVE_MIN, "teammate after Max's hypercharged hits")

        # 14. Edgar (spot 1): target 7 (another team) at 250 u; reload and charge per hit before and after his hypercharged super
        def edgar_round(tag):
            s = []; c0 = sc(R.step(), 1); h0 = int(R.step().pl[7].hp)
            for _ in range(3):
                R.step({1: (-1, 1, aim1, 0.0)}, 1); r = R.step(ticks=3); s.append(int(r.pl[1].ammo))
            for _ in range(3): r = R.step()
            refill = max((y - x for x, y in zip(s, s[1:]) if x < 3000), default=0)
            if a.verbose: print("  edgar", tag, "ammo", s, "charge", c0, sc(r, 1), "target hp", h0, int(r.pl[7].hp), flush=True)
            return refill, (sc(r, 1) - c0) / max(1, h0 - int(r.pl[7].hp))   # super charge per damage dealt
        p, (dx, dy), d = at(1, 1); aim1 = float(np.degrees(np.arctan2(dy, dx)))
        R.place({1: p, 7: (p[0] + dx * 250, p[1] + dy * 250)})
        for _ in range(20): R.step()
        g0, h0 = edgar_round("before")
        R.place({1: p, 7: (p[0] + dx * 250, p[1] + dy * 250)})
        hyper_super(1, aim1 + 180, 0.3)   # the jump away from the target, back after the landing
        for _ in range(10): R.step()
        R.place({1: p, 7: (p[0] + dx * 250, p[1] + dy * 250)})
        for _ in range(20): R.step()   # ammo full again (the area lives 7 s)
        g1, h1 = edgar_round("after")
        print("status_check: Edgar: ammo refill %d -> %d, super charge per damage %.3f -> %.3f after his hypercharged super" % (g0, g1, h0, h1), flush=True)
        fails["Edgar hyper reload / charge"] = judge_ratio(g1, g0, EDGAR_RELOAD, "Edgar's ammo refill") + judge_ratio(h1, h0, EDGAR_CHARGE, "Edgar's super charge per damage")

        # 15. Darryl (spot 2): his hypercharged roll along the corridor
        p, (dx, dy), d = at(2, 2); aim = float(np.degrees(np.arctan2(dy, dx))); R.place({2: p})
        hyper_super(2, aim, 0.8); kinds = set()
        for _ in range(20): R.step(); kinds |= {SA.data_name(k) for k in R.proj_kinds(2)}
        print("status_check: Darryl's hypercharged roll: projectiles %s" % sorted(kinds), flush=True)
        fails["Darryl BulletSpin"] = [] if "BarrelBotOverchargedProjectile" in kinds else ["Darryl's roll fired no BarrelBotOverchargedProjectile (%s)" % sorted(kinds)]

        # 16. Pam (spot 3): teammate 8 at 600 u, the turret thrown 300 u (between them); enemy 9 shoots 8 from 500 u to the
        # side (a clear corridor of the spot, perpendicular), clear of the turret. First her normal turret, after one shot
        p, (dx, dy), d = at(3, 3); aim = float(np.degrees(np.arctan2(dy, dx)))
        qx, qy = next(((u, v) for u, v in spots[3][2] if u * dx + v * dy == 0), (-dy, dx))
        t8 = (p[0] + dx * 600, p[1] + dy * 600); r = R.place({3: p, 8: t8, 9: (t8[0] + qx * 500, t8[1] + qy * 500)})
        aim9 = float(np.degrees(np.arctan2(-qy, -qx))); R.step({9: (-1, 1, aim9, 0.0)}, 1)
        for _ in range(4): r = R.step()
        pam_max = int(r.pl[3].max_hp)
        R.fire(3, aim, min(1.0, 300 / SA.expected("MinigunDude")["range"])); last, gains = int(r.pl[8].hp), []
        for _ in range(70):
            r = R.step(ticks=1); h = int(r.pl[8].hp)
            if h > last: gains.append((int(r.tick), h - last))
            last = h
        print("status_check: Pam's turret: teammate gains %s (Pam max hp %d)" % (gains, pam_max), flush=True)
        fails["Pam turret heal 14 %"] = judge_turret(gains, pam_max)
        # then her hypercharged turret, the enemy's shots after its instant heal
        R.place({3: p, 8: t8, 9: (t8[0] + qx * 500, t8[1] + qy * 500)})
        hyper_super(3, aim, min(1.0, 300 / SA.expected("MinigunDude", True)["range"]))
        for _ in range(20): R.step()   # the turret lands, its instant heal is over
        aim9 = float(np.degrees(np.arctan2(-qy, -qx)))
        for _ in range(2):
            R.step({9: (-1, 1, aim9, 0.0)}, 1)
            for _ in range(3): r = R.step()
        hp0 = int(r.pl[8].hp)
        if a.verbose:
            st = SA.parse_state(inst.state_bytes())
            print("  pam objects", sorted(SA.data_name(c[1]) for c in st["ch"] if int(c[2]) == 3),
                  sorted(SA.data_name(t[1]) for t in st["it"] if int(t[2]) == 3), flush=True)
        for _ in range(15): r = R.step()
        hp1 = int(r.pl[8].hp)
        print("status_check: Pam's hypercharged turret: teammate hp %d -> %d in 30 ticks (max %d)" % (hp0, hp1, r.pl[8].max_hp), flush=True)
        fails["Pam turret HotAndOverheals"] = ([] if hp0 < r.pl[8].max_hp and hp1 - hp0 >= TURRET_HEAL else
                                               ["Pam's teammate: hp %d -> %d (max %d), want +%d" % (hp0, hp1, r.pl[8].max_hp, TURRET_HEAL)])

        # 17. Angelo (spot 4): an attack, then his super at his feet, then an attack inside it
        p, (dx, dy), d = at(4, 4); aim = float(np.degrees(np.arctan2(dy, dx))); R.place({4: p})
        R.fire(4, aim, kind=1); R.step(); k0 = {SA.data_name(k) for k in R.proj_kinds(4)}
        for _ in range(15): R.step()
        R.fire(4, aim + 180, 0.05)
        for _ in range(10): R.step()
        k1 = set()
        R.fire(4, aim, kind=1)
        for _ in range(3): R.step(); k1 |= {SA.data_name(k) for k in R.proj_kinds(4)}
        k1 -= k0 | {"InsectManUltiProjectile"}
        print("status_check: Angelo's attack before his super %s, inside it %s" % (sorted(k0), sorted(k1)), flush=True)
        fails["Angelo SwitchSkill"] = judge_kinds(k0, k1, "Angelo's attack in his super")
    if 4 in B:   # battle 4 (issue #19 final): gadgets
        names = NAMES4 + [TARGET] * (10 - len(NAMES4))
        div = D.make_div(location=SA.MAP, chr=names); div["gadget"] = [GADGETS4.get(n, 0) for n in names]
        inst.reset(93600003 + a.seed, gas=0, flags=0, native_mask=0, obs_mask=0, div=div)
        R = Run(inst); R.step(ticks=10); R.place(home)

        # 18. Fang next to a wall: enemy 5 in the open, 6 behind the wall, both 600 u away, both walk away from him
        ws = wall_spot()
        if ws is None: fails["Fang LoS stun"] = ["no wall spot on %s" % SA.MAP]
        else:
            f, eo, ew = ws; R.place({0: f, 5: eo, 6: ew})
            R.step({0: (-1, 3, 0.0, 0.0)}, 1)
            _, mo, _ = R.walk(5, 8, steps=3)   # 5 walks -x while stunned (10 ticks), then 6 walks +x
            _, mw, _ = R.walk(6, 0, steps=3)
            print("status_check: Fang's kick at %s: enemy in the open moved %.0f u, behind the wall %.0f u" % (f, mo, mw), flush=True)
            fails["Fang LoS stun"] = judge_los(mo, mw)

        # 19. Meeple (spot 1): enemy 7 (250 u) shoots her once, then her RageQuit; 7 walks away, and again later
        p, (dx, dy), d = at(1, 1); aim = float(np.degrees(np.arctan2(dy, dx)))
        R.place({1: p, 7: (p[0] + dx * 250, p[1] + dy * 250)})
        for _ in range(1):
            R.step({7: (-1, 1, aim + 180, 0.0)}, 1)
            for _ in range(8): r = R.step()
            if a.verbose: print("  meeple hp", r.pl[1].hp, flush=True)
        hp = int(r.pl[1].hp); R.step({1: (-1, 3, aim, 0.0)}, 1)
        _, mv, _ = R.walk(7, d, steps=3)
        for _ in range(20): R.step()
        _, mv2, _ = R.walk(7, (d + 8) % 16, steps=3)
        print("status_check: Meeple's RageQuit at hp %d / %d: the enemy moved %.0f u, later %.0f u" % (hp, r.pl[1].max_hp, mv, mv2), flush=True)
        fails["Meeple RageQuit stun"] = judge_los(mv, mv2, rage_knock(hp, r.pl[1].max_hp))   # issue #55: it knocks back too

        # 20. Damian (spot 2): his wall gadget thrown 900 u along the corridor
        p, (dx, dy), d = at(2, 2); aim = float(np.degrees(np.arctan2(dy, dx))); R.place({2: p})
        inst.step(actions={**R.idle, 2: (-1, 3, aim, 1.0)}, ticks=1, flags=R.P.F_STATE | R.P.F_MAP, native_mask=0, obs_mask=0)
        n = 0
        for _ in range(12):
            inst.step(actions=R.idle, ticks=2, flags=R.P.F_STATE | R.P.F_MAP, native_mask=0, obs_mask=0)
            n = max(n, int((inst.map_tiles() == GLAD_WALL).sum()))
        print("status_check: Damian's wall gadget: %d GladiatorWallDefault tiles" % n, flush=True)
        fails["Damian wall gadget"] = [] if n > 0 else ["no GladiatorWallDefault tile after Damian's wall gadget"]
    if B & {5, 6, 7, 8}: self_battles(inst, a, spots, fails, B, home, at)


def self_battles(inst, a, spots, fails, B, home, at):
    """battles 5 to 8 (issue #46): the gadgets on the brawler itself (gadget_self.c, gadget.c HEAL / BUOY / HEAL_NOW)"""
    from nbpc import diversity as D

    def gadget(R, i, aim=0.0): return R.step({i: (-1, 3, aim, 0.0)}, 1)

    def shot_loss(R, s, t, aim_t, steps=5):   # t shoots s once: s's HP lost over the next steps
        h0 = int(R.step().pl[s].hp); R.step({t: (-1, 1, aim_t, 0.0)}, 1); lo = h0
        for _ in range(steps): lo = min(lo, int(R.step().pl[s].hp))
        return h0 - lo

    def charge_round(R, s, t, aim):   # one attack of s on t: super charge per damage (one: more would fill the super and cap it)
        r = R.step(); c0, h0 = int(r.pl[s].super_charge), int(r.pl[t].hp)
        R.step({s: (-1, 1, aim, 0.0)}, 1)
        for _ in range(5): r = R.step()
        if a.verbose: print("  charge", c0, int(r.pl[s].super_charge), "of", int(r.pl[s].super_max), "target hp", h0, int(r.pl[t].hp), flush=True)
        return (int(r.pl[s].super_charge) - c0) / max(1, h0 - int(r.pl[t].hp))

    def seen(R, i):   # is player i's brawler visible to the local player 0 (state2's visible flag)
        R.step(); st = SA.parse_state(inst.state_bytes()); cid = SA.brawler_ids(st).get(i)
        row = st["ch"][st["ch"][:, 0] == cid]
        return bool(len(row) and row[0][19] == 1)

    def setup(names, gads, seed):   # gads: {name: card}, or a list of cards by player
        cards = list(gads) if isinstance(gads, list) else [gads.get(n, 0) for n in names]
        names = names + [TARGET] * (10 - len(names))
        div = D.make_div(location=SA.MAP, chr=names); div["gadget"] = cards + [0] * (10 - len(cards))
        inst.reset(seed + a.seed, gas=0, flags=0, native_mask=0, obs_mask=0, div=div)
        R = Run(inst); R.step(ticks=10); R.place(home); return R

    if 5 in B:
        R = setup(NAMES5, GADGETS5, 93600004)
        # 21. Jacky (spot 0): a plain walk, then her gadget and the same walk
        p, (dx, dy), d = at(0, 0); aim = float(np.degrees(np.arctan2(dy, dx)))
        R.place({0: p}); v0, _, _ = R.walk(0, d)
        R.place({0: p}); gadget(R, 0, aim); v1, _, _ = R.walk(0, d)
        print("status_check: Jacky walks %.0f u/s, %.0f u/s after her gadget" % (v0, v1), flush=True)
        fails["Jacky speed gadget"] = judge_faster(v1, v0, "Jacky after her gadget", need=JACKY_MIN * v0)

        # 22. Hank (spot 1): target 5 at 300 u shoots him, without and with the shield (place heals him in between)
        p, (dx, dy), d = at(1, 1); aim = float(np.degrees(np.arctan2(dy, dx))); tp = (p[0] + dx * 300, p[1] + dy * 300)
        R.place({1: p, 5: tp}); a0 = shot_loss(R, 1, 5, aim + 180)
        for _ in range(10): R.step()   # target's ammo back
        R.place({1: p, 5: tp}); gadget(R, 1, aim); a1 = shot_loss(R, 1, 5, aim + 180)
        print("status_check: Hank loses %d to a shot, %d with his shield" % (a0, a1), flush=True)
        fails["Hank shield gadget"] = judge_shield(a0, a1)

        # 23. Draco (spot 2): targets 6, 7 at 250 u on two corridors, 8 at 400 u; one shot first, then the gadget and the fire
        p, _, d = at(2, 2); dirs = spots[2][2]; (ux, uy), (vx, vy) = dirs[0], dirs[1 % len(dirs)]
        tp = {6: (p[0] + ux * 250, p[1] + uy * 250), 7: (p[0] + vx * 250, p[1] + vy * 250), 8: (p[0] + ux * 400, p[1] + uy * 400)}
        aims = {6: float(np.degrees(np.arctan2(-uy, -ux))), 7: float(np.degrees(np.arctan2(-vy, -vx))), 8: float(np.degrees(np.arctan2(-uy, -ux)))}
        R.place({2: p, **tp}); R.step({6: (-1, 1, aims[6], 0.0)}, 1)
        for _ in range(4): r = R.step()
        h1 = int(r.pl[2].hp); gadget(R, 2); hmin, alive = h1, True
        for k in range(16):   # 33 ticks of fire, inside the 40-tick Last Stand
            r = R.step({t: (-1, 1, aims[t], 0.0) for t in tp} if k % 3 == 0 else None)
            hmin = min(hmin, int(r.pl[2].hp)); alive &= bool(r.pl[2].alive and r.pl[2].hp > 0)
        print("status_check: Draco's Last Stand from hp %d: lowest %d, alive %s" % (h1, hmin, alive), flush=True)
        fails["Draco last stand"] = judge_stand(alive, hmin)

        # 24. Trunk (spot 3): target 9 at 300 u shoots him once, then his gadget, then two more shots
        p, (dx, dy), d = at(3, 3); aim = float(np.degrees(np.arctan2(dy, dx))); tp = (p[0] + dx * 300, p[1] + dy * 300)
        R.place({3: p, 9: tp}); shot_loss(R, 3, 9, aim + 180)
        for _ in range(6): r = R.step()
        h0 = int(r.pl[3].hp); gadget(R, 3, aim); R.step({9: (-1, 1, aim + 180, 0.0)}, 1)
        for _ in range(5): r = R.step()
        h1 = int(r.pl[3].hp); R.step({9: (-1, 1, aim + 180, 0.0)}, 1)
        for _ in range(5): r = R.step()
        h2 = int(r.pl[3].hp)
        print("status_check: Trunk hp %d, after the first shot with his gadget %d, after the next %d" % (h0, h1, h2), flush=True)
        fails["Trunk inverse damage"] = judge_invert(h0, h1, h2)

        # 25. Surge (spot 4): three attacks away from target 5 (ammo spent), his shield, then 5 (300 u) shoots him
        p, (dx, dy), d = at(4, 4); aim = float(np.degrees(np.arctan2(dy, dx))); tp = (p[0] + dx * 300, p[1] + dy * 300)
        R.place({4: p, 5: tp})
        for _ in range(3): R.step({4: (-1, 1, aim + 90, 0.0)}, 1); R.step(ticks=3)
        gadget(R, 4, aim); r = R.step(); am0 = int(r.pl[4].ammo); am1 = am0
        R.step({5: (-1, 1, aim + 180, 0.0)}, 1)
        for _ in range(3): am1 = max(am1, int(R.step().pl[4].ammo))
        print("status_check: Surge's ammo %d -> %d at the hit on his shield" % (am0, am1), flush=True)
        fails["Surge shield ammo"] = [] if am1 - am0 >= AMMO_MIN else ["Surge's ammo %d -> %d at the hit, want +%d" % (am0, am1, AMMO_MIN)]

    if 6 in B:
        R = setup(NAMES6, GADGETS6, 93600005)
        # 26. Tara (player 0) on open ground, enemy 5 in a bush VISION_D tiles away
        bs = bush_spot()
        if bs is None: fails["Tara vision"] = ["no bush spot on %s" % SA.MAP]
        else:
            R.place({0: bs[0], 5: bs[1]}); v0 = seen(R, 5)
            gadget(R, 0); R.step(); v1 = seen(R, 5)
            print("status_check: Tara at %s, bush enemy at %s visible before / during her vision %s %s" % (bs[0], bs[1], v0, v1), flush=True)
            fails["Tara vision"] = judge_vision(v0, v1)

        # 27. Moe (spot 1): target 6 at 250 u; super charge per damage of one attack before and one after his gadget
        p, (dx, dy), d = at(1, 1); aim = float(np.degrees(np.arctan2(dy, dx))); tp = (p[0] + dx * 250, p[1] + dy * 250)
        R.place({1: p, 6: tp}); m0 = charge_round(R, 1, 6, aim)
        for _ in range(20): R.step()
        R.place({1: p, 6: tp}); gadget(R, 1, aim); m1 = charge_round(R, 1, 6, aim)
        print("status_check: Moe's super charge per damage %.3f, %.3f after his gadget" % (m0, m1), flush=True)
        fails["Moe charge gadget"] = judge_ratio(m1, m0, MOE_CHARGE, "Moe's super charge per damage")

        # 28. Sandy (spot 2): target 7 (300 u) shoots her once, then her sleep; she tries to walk, then wakes
        p, (dx, dy), d = at(2, 2); aim = float(np.degrees(np.arctan2(dy, dx))); tp = (p[0] + dx * 300, p[1] + dy * 300)
        R.place({2: p, 7: tp}); shot_loss(R, 2, 7, aim + 180)
        for _ in range(3): R.step()
        gadget(R, 2); _, moved, _ = R.walk(2, (d + 8) % 16, steps=6)
        for _ in range(10): r = R.step()   # 34 ticks after the fire
        print("status_check: Sandy asleep moved %.0f u, woke at hp %d of %d" % (moved, r.pl[2].hp, r.pl[2].max_hp), flush=True)
        fails["Sandy sleep gadget"] = judge_sleep(moved, int(r.pl[2].hp), int(r.pl[2].max_hp))

        # 29. Lou (spot 3): target 8 at 300 u shoots him, without and with his freeze
        p, (dx, dy), d = at(3, 3); aim = float(np.degrees(np.arctan2(dy, dx))); tp = (p[0] + dx * 300, p[1] + dy * 300)
        R.place({3: p, 8: tp}); a0 = shot_loss(R, 3, 8, aim + 180)
        for _ in range(10): R.step()
        R.place({3: p, 8: tp}); gadget(R, 3, aim); a1 = shot_loss(R, 3, 8, aim + 180)
        print("status_check: Lou loses %d to a shot, %d frozen" % (a0, a1), flush=True)
        fails["Lou freeze gadget"] = judge_freeze(a0, a1)
    if 7 in B or 8 in B: more_self_battles(setup=setup, gadget=gadget, shot_loss=shot_loss, charge_round=charge_round,
                                           seen=seen, inst=inst, spots=spots, fails=fails, B=B, at=at)


def more_self_battles(setup, gadget, shot_loss, charge_round, seen, inst, spots, fails, B, at):
    """battles 7 and 8 (issue #46): the rows battles 5 and 6 do not reach"""
    def used(r, i): return int(r.gad_used[i])

    if 7 in B:
        R = setup(NAMES7, GADGETS7, 93600006)
        # 30. Buzz's vision (player 0) on open ground, enemy 5 in a bush BUZZ_VISION_D tiles away
        bs = bush_spot(vd=BUZZ_VISION_D)
        if bs is None: fails["Buzz vision"] = ["no bush spot on %s" % SA.MAP]
        else:
            R.place({0: bs[0], 5: bs[1]}); v0 = seen(R, 5)
            gadget(R, 0); R.step(); v1 = seen(R, 5)
            print("status_check: Buzz at %s, bush enemy at %s visible before / during his vision %s %s" % (bs[0], bs[1], v0, v1), flush=True)
            fails["Buzz vision"] = judge_vision(v0, v1, "Buzz")

        # 31. Byron (spot 1): ammo spent -> refused; ammo back, a target's shot, then the gadget
        p, (dx, dy), d = at(1, 1); aim = float(np.degrees(np.arctan2(dy, dx))); tp = (p[0] + dx * 300, p[1] + dy * 300)
        R.place({1: p, 6: tp})
        for _ in range(12):   # attacks away from the target until less than one bar is left
            R.step({1: (-1, 1, aim + 90, 0.0)}, 1); r = R.step(ticks=4)
            if int(r.pl[1].ammo) < 1000: break
        r = R.step(ticks=1); am, u0, cd = int(r.pl[1].ammo), used(r, 1), int(r.gad_cd[1])
        r = gadget(R, 1, aim); r = R.step(); bad = judge_refused(u0, used(r, 1), cd, "Byron's gadget without ammo")
        if am >= 1000: bad.append("Byron's ammo not spent (%d) before the refusal test" % am)
        for _ in range(40):
            r = R.step()
            if int(r.pl[1].ammo) >= 1500: break
        shot_loss(R, 1, 6, aim + 180)
        r = R.step(); a0, h0, u0 = int(r.pl[1].ammo), int(r.pl[1].hp), used(r, 1)
        r = gadget(R, 1, aim); a1, u1 = int(r.pl[1].ammo), used(r, 1)
        for _ in range(10): r = R.step()
        print("status_check: Byron without ammo (%d): refused %s; with ammo %d -> %d, hp %d -> %d" % (am, not bad, a0, a1, h0, int(r.pl[1].hp)), flush=True)
        fails["Byron heal gadget"] = bad + judge_byron(u0, u1, a0, a1, h0, int(r.pl[1].hp))

        # 32. Buzz's buoy (player 2, spot 2): super full -> refused; his super, then the buoy fills it
        p, (dx, dy), d = at(2, 2); aim = float(np.degrees(np.arctan2(dy, dx)))
        R.place({2: p}); inst.setup(super_fill=[2]); R.step(ticks=1); r = R.step(); u0, cd = used(r, 2), int(r.gad_cd[2])
        gadget(R, 2, aim); r = R.step(); bad = judge_refused(u0, used(r, 2), cd, "Buzz's buoy with a full super")
        R.step({2: (-1, 2, aim, 1.0)}, 1)
        for _ in range(5): r = R.step()
        sc0 = int(r.pl[2].super_charge); gadget(R, 2, aim); r = R.step(); sc1, sm = int(r.pl[2].super_charge), int(r.pl[2].super_max)
        print("status_check: Buzz's buoy refused on a full super %s; super %d -> %d of %d" % (not bad, sc0, sc1, sm), flush=True)
        fails["Buzz buoy gadget"] = bad + judge_buoy(sc0, sc1, sm)

        # 33. Juju (spot 3, open ground): target 8 at 300 u shoots her, without and with her gadget
        p, (dx, dy), d = at(3, 3); aim = float(np.degrees(np.arctan2(dy, dx))); tp = (p[0] + dx * 300, p[1] + dy * 300)
        R.place({3: p, 8: tp}); a0 = shot_loss(R, 3, 8, aim + 180)
        for _ in range(10): R.step()
        R.place({3: p, 8: tp}); gadget(R, 3, aim); a1 = shot_loss(R, 3, 8, aim + 180)
        print("status_check: Juju loses %d to a shot, %d after her gadget" % (a0, a1), flush=True)
        fails["Juju shield gadget"] = judge_less(a0, a1, JUJU_MAX, "Juju's gadget on open ground")

        # 34. Bonnie (spot 4): a plain walk, then her gadget and the same walk
        p, (dx, dy), d = at(4, 4); aim = float(np.degrees(np.arctan2(dy, dx)))
        R.place({4: p}); v0, _, _ = R.walk(4, d)
        R.place({4: p}); gadget(R, 4, aim); v1, _, _ = R.walk(4, d)
        print("status_check: Bonnie walks %.0f u/s, %.0f u/s after her gadget" % (v0, v1), flush=True)
        fails["Bonnie speed gadget"] = judge_faster(v1, v0, "Bonnie after her gadget", need=BONNIE_MIN * v0)

    if 8 in B:
        R = setup(NAMES8, GADGETS8, 93600007)
        # 35. Meg (spot 0, in her mech): two shots of target 5, then her gadget; HP gained in the next 20 ticks
        p, (dx, dy), d = at(0, 0); aim = float(np.degrees(np.arctan2(dy, dx))); tp = (p[0] + dx * 300, p[1] + dy * 300)
        R.place({0: p, 5: tp}); shot_loss(R, 0, 5, aim + 180)
        for _ in range(4): R.step()
        shot_loss(R, 0, 5, aim + 180)
        r = R.step(); h0, mx = int(r.pl[0].hp), int(r.pl[0].max_hp); gadget(R, 0, aim)
        for _ in range(10): r = R.step()
        g = int(r.pl[0].hp) - h0
        print("status_check: Meg's mech at hp %d of %d gains %d in 20 ticks after her gadget" % (h0, mx, g), flush=True)
        fails["Meg heal gadget"] = [] if h0 < mx and g >= MEG_MIN * mx else ["Meg's gadget: hp %d of %d, +%d in 20 ticks, want +%.0f" % (h0, mx, g, MEG_MIN * mx)]

        # 36. Surge (spot 1): target 6 at 400 u (measured: his shot starts about 350 u out, so it passes a target at 250 u,
        # and does not reach one at 600 u); super charge per damage of one attack before and one after his gadget
        p, (dx, dy), d = at(1, 1); aim = float(np.degrees(np.arctan2(dy, dx))); tp = (p[0] + dx * 400, p[1] + dy * 400)
        R.place({1: p, 6: tp}); m0 = charge_round(R, 1, 6, aim)
        for _ in range(20): R.step()
        R.place({1: p, 6: tp}); gadget(R, 1, aim); m1 = charge_round(R, 1, 6, aim)
        print("status_check: Surge's super charge per damage %.3f, %.3f after his gadget" % (m0, m1), flush=True)
        fails["Surge charge gadget"] = judge_ratio(m1, m0, SURGE_CHARGE, "Surge's super charge per damage")

        # 37. Kenji (spot 2): target 7 at 300 u shoots him once, then his gadget
        p, (dx, dy), d = at(2, 2); aim = float(np.degrees(np.arctan2(dy, dx))); tp = (p[0] + dx * 300, p[1] + dy * 300)
        R.place({2: p, 7: tp}); loss = shot_loss(R, 2, 7, aim + 180)
        r = R.step(); h0 = int(r.pl[2].hp); gadget(R, 2, aim); r = R.step(); heal = int(r.pl[2].hp) - h0
        print("status_check: Kenji lost %d to a shot, his gadget healed %d" % (loss, heal), flush=True)
        fails["Kenji heal gadget"] = judge_kenji(loss, heal)

        # 38. Willow (spot 3): target 8 at 300 u shoots her, without and with her dive
        p, (dx, dy), d = at(3, 3); aim = float(np.degrees(np.arctan2(dy, dx))); tp = (p[0] + dx * 300, p[1] + dy * 300)
        R.place({3: p, 8: tp}); a0 = shot_loss(R, 3, 8, aim + 180)
        for _ in range(10): R.step()
        R.place({3: p, 8: tp}); gadget(R, 3, aim); a1 = shot_loss(R, 3, 8, aim + 180)
        print("status_check: Willow loses %d to a shot, %d diving" % (a0, a1), flush=True)
        fails["Willow dive gadget"] = judge_none(a0, a1, "Willow's dive")

        # 39. Kit (spot 4): enemy 9 2000 u along the corridor, before and during his box (as Leon's scene 6)
        p, (dx, dy), d = at(4, 4); aim = float(np.degrees(np.arctan2(dy, dx)))
        R.place({4: p, 9: (p[0] + dx * 2000, p[1] + dy * 2000)}); far0 = R.sees(9, 4)
        gadget(R, 4, aim)
        for _ in range(3): R.step()
        far1 = R.sees(9, 4)
        print("status_check: Kit seen from 2000 u before / in his box %s %s" % (far0, far1), flush=True)
        fails["Kit box gadget"] = judge_hidden(far0, far1, "Kit")


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
    assert not judge_gain(1000, DRINK_MIN, "x") and judge_gain(0, DRINK_MIN, "x")
    assert not judge_ratio(150, 100, 1.3, "x") and judge_ratio(110, 100, 1.3, "x") and judge_ratio(100, 0, 1.3, "x")
    assert not judge_kinds({"a"}, {"b"}, "x") and judge_kinds({"a"}, {"a"}, "x") and judge_kinds(set(), {"b"}, "x")
    assert not judge_los(20, 400) and judge_los(300, 400) and judge_los(20, 50)
    assert rage_knock(4800, 6600) == 264 and rage_knock(6600, 6600) == 120 and not judge_los(230, 400, 264) and judge_los(400, 400, 264)
    assert not judge_turret([(238, 1400), (258, 1400), (271, 1014), (278, 200)], 10000)
    assert judge_turret([(238, 304), (258, 304)], 10000) and judge_turret([(238, 1400), (268, 1400)], 10000)
    assert judge_turret([(238, 1400)], 10000)
    from nbpc import diversity as D
    assert D.table("tiles.csv")["GladiatorWallDefault"][0] == GLAD_WALL
    ws = wall_spot(); assert ws is not None and ws[0][1] == ws[1][1] == ws[2][1] and ws[2][0] - ws[1][0] == 4 * TILE
    assert not judge_shield(1000, 600) and judge_shield(1000, 900) and judge_shield(0, 0)
    assert not judge_stand(True, 1) and judge_stand(False, 1) and judge_stand(True, 800)
    assert not judge_invert(3000, 3600, 2800) and judge_invert(3000, 2500, 2000) and judge_invert(3000, 3600, 3600)
    assert not judge_invert(7400, 5600, 2600) and judge_invert(7400, 4400, 1400)
    assert not judge_freeze(900, 0) and judge_freeze(900, 300) and judge_freeze(0, 0)
    assert not judge_sleep(10, 4000, 4000) and judge_sleep(400, 4000, 4000) and judge_sleep(10, 3000, 4000)
    assert not judge_vision(False, True) and judge_vision(True, True) and judge_vision(False, False)
    assert not judge_refused(3, 3, 1, "x") and judge_refused(3, 4, 1, "x") and judge_refused(3, 3, 0, "x")
    assert not judge_byron(0, 1, 2500, 1500, 3000, 3300) and judge_byron(0, 0, 2500, 1500, 3000, 3300)
    assert judge_byron(0, 1, 2500, 2450, 3000, 3300) and judge_byron(0, 1, 2500, 1500, 3000, 3000)
    assert not judge_buoy(0, 4000, 4000) and judge_buoy(0, 0, 4000) and judge_buoy(4000, 4000, 4000)
    assert not judge_less(1000, 700, JUJU_MAX, "x") and judge_less(1000, 950, JUJU_MAX, "x") and judge_less(0, 0, JUJU_MAX, "x")
    assert not judge_kenji(1000, 500) and judge_kenji(1000, 0) and judge_kenji(1000, 1000) and judge_kenji(0, 0)
    assert not judge_none(3000, 0, "x") and judge_none(3000, 600, "x") and judge_none(0, 0, "x")
    assert not judge_hidden(True, False, "x") and judge_hidden(False, False, "x") and judge_hidden(True, True, "x")
    gs = SA.all_gadgets()   # the battles' gadget cards are the brawlers' cards (cards.csv ids)
    assert all(any(c == gads[b] for c, _, _ in gs[b]) for gads in (GADGETS4, GADGETS5, GADGETS6, GADGETS8) for b in gads), "gadget card ids"
    rows8 = {b: {c: n for c, n, _ in gs[b]} for b in GADGETS8}
    assert [rows8[b][GADGETS8[b]] for b in NAMES8] == ["MechaDude_Heal", "PowerLeveler_ExtraLevels", "Samurai_HealDamageTaken",
                                                     "Puppeteer_Dive", "Attacher_Cardboardbox"], rows8
    assert len(NAMES7) == len(GADGETS7) and all(any(c == k for c, _, _ in gs[b]) for b, k in zip(NAMES7, GADGETS7)), "battle 7 cards"
    T = D.table("tiles.csv"); assert {T[n][0] for n in ("Forest", "RespawningForest", "ExtraBush", "ExtraBushTemp")} == BUSH_TILES
    bs = bush_spot(); assert bs is not None and bs[0][1] == bs[1][1] and (bs[1][0] - bs[0][0]) / TILE in VISION_D, bs
    bs = bush_spot(vd=BUZZ_VISION_D); assert bs is not None and (bs[1][0] - bs[0][0]) / TILE in BUZZ_VISION_D, bs
    print("status_check judging ok")


if __name__ == "__main__":
    main()
