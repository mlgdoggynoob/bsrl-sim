"""Vision-shaped observation for the v5 policy: what the two vision models give a vision-based agent, nothing more.

    python -m obs_v5            # self-check (no game)
    python -m obs_v5 --live     # + 1 instance, 300 decisions: real MAEnv observations through the builder

    ob = ObsV5()                                     # one per MAEnv
    o = ob.build(obs["vec"], obs["grid"], env.last_meta, ids, who=env.last_who, gadget=env.gadget(ids), hyper=env.hyper(ids))
                                                     # gadget / hyper: optional
    o["self"] (B, 8)   hp fraction, ammo 0-1, super / gadget / hypercharge ready, in bush, own velocity x, y
    o["ent"]  (B, 39, 45)  present | class one-hot (ENT) | dx, dy (10 tiles, x right / y down) | vx, vy (tiles/tick) | hp fraction
                       | area effects: radius (10 tiles), harms me, helps me, slows me (0 for every other class)
                       | identity (ID0 20..33): brawler_stats (13) of the row's brawler (a player row) or of the projectile's
                         owner + known (1 = identity given; unknown = 13 zeros + 0; summons, boxes, cubes, areas: zeros)
                       | line of sight (LOS 34, 35; enemy / teammate rows): wall_between, water_between on o["grid"]
                       | power cubes (CUB 36, 37; enemy / teammate player rows): cubes held / 10 (clip 2), known
                       | brawler class (CLS 38..44, v5.11): one-hot of CLASSES (characters.csv ClassArchetype) of the
                         brawler the identity names (same rows, same given brawler: a wrong identity gives its class;
                         unknown = zeros)
    o["grid"] (B, 25, 25) uint8  seg class id (SEG) per tile around the player, UNKNOWN outside the camera view
    cond(brawler, sliders, team_size, cubes, left) (37,)  own brawler stats + behaviour weights + team size + HUD numbers
                       + own class one-hot (COND_CLS 30..36, v5.11)
    preset_vec(name) (12,)  the slider weights of a named play-style mode (PRESETS: balanced, bush_camper, aggressive, ...)
    intent block (N_INT 13): one-hot of INTENTS 1..9 | dx, dy | radius | time left (intent.encode; env_v5.Env.intents)
    policy input s = cat[self (8), cond (37), intent (13)] (N_S = 58; S_INT = 45 = the block's offset)

Source = the host's state2 vector + grid after nbpc.fair (already camera- and bush-limited). Needs the rl-round
host `nbhost_rl` (enemy features 14 / 15 = summon / on my team, self 18 = hypercharge fraction, grid channel 0 =
tiles.csv row + 1, item feature 5 of an area effect / bomb = its data id - 16999999); with an older host teammates read as
enemies, the tiles are wrong and area effects have no radius / kind. The grid follows the live map (live_state host: a
destroyed wall or bush reads as the open tile it became). Invisibility (v5.9, issue #19): the host's encoder leaves out
an invisible enemy brawler (a status's Invisibility, Leon's super until he attacks) farther than 1200 units, or at any
distance for "full" invisibility, from the enemy rows and grid channel 5, as the real client does not draw it; before
v5.9 invisible enemies were always in the observation. No shape change.
Identity (v5.6): `who` (B, N_ENT, 4) int = per row the owner player (-1 none), its brawler's id_lut row (-1), its side
(WHO_FOE 0 / WHO_MATE 1 / WHO_ME 2) and (v5.10) the owner's power cubes held (-1 none), from env_v5.Env.last_who (the host's state dump, matched to the rows by position).
Clean: every row with an owner is known. Noisy (NOISE id_*, per episode = per battle): a player's identity is known or
not, and a known enemy may be given a wrong brawler, both FIXED per player for the battle (live keeps them per track);
a projectile row's owner is linked per row and decision. who=None: every identity unknown. Summons stay unknown (live
cannot tie a bear / turret to its owner's countdown name).
Power cubes (v5.10): CUB = the cubes held by the owner of an enemy / teammate player row (who[..., 3]: NbePlayer
cubes_total, 0 after a team knock-out as the HUD shows it) / 10, clip 2; CUB + 1 = known. Live: the number the client
draws next to a player's HP bar, read per track by BSRL's HUD OCR. Clean: every player row with an owner is known.
Noisy (NOISE cube_*): a player's count is never read with a chance fixed per player for the battle (live: a track whose
number the OCR never reads), and a read count is off by one (+-1, not below 0) with a per-decision chance. A 3-column
who (before v5.10) or who=None: every count unknown. Summons, projectiles, boxes and items: 0, 0.
Line of sight: LOS_N samples on the straight line from my tile centre to the row's (noisy) position, my tile and its
tile left out; wall_between = a projectile-blocking class (_BLOCK_PJ), water_between = movement-only (_BLOCK_MV), on the
grid the policy gets (seg / HUD / bleed noise included; UNKNOWN blocks nothing); computed per frame before the latency.
Area effects (item rows with feature 4 != 0): radius and kind come from the game's tables through the data id (_area_lut:
area_effects_skin -> area_effects_logic Radius / Type / Damage / status effects; a bomb item through its TriggerAreaEffect),
relative to the observer: an enemy (or neutral bomb) area harms / slows me, an area of my team helps me.
Gadget (v5.7, issue #3): self 3 = the gadget can be used now (a use left, no cooldown), passed in as `gadget` (B,) from
the host's gadget state (env_v5.Env.gadget; 0 = no gadget, a host that publishes none, or a gadget kind the host cannot
activate yet). The fire head has the classes FIRE; a class with a FIRE_READY column is only allowed while that self column
is set (model.mask_fire), so with self 3 = 0 a policy acts exactly as before the gadget class existed.
Hypercharge (v5.8, issue #4): the fire class "hypercharge" (NbeAction.fire 4, no aim) is allowed while self 4 is set.
Self 4 = the hypercharge can be activated now, passed in as `hyper` (B,) from the host's hypercharge state
(env_v5.Env.hyper: the card equipped, the charge full, not active, in play); None = 0. Before v5.8 self 4 was "the
hypercharge fraction (state2 self 18) is full", which libg's charging reaches with or without a card (measured: 600 of
4000 per Shelly hit either way) while nothing could be activated; it would now open the class for an action that does
nothing, so it is retired: a v5.7 checkpoint sees self 4 = 0, as with an empty hypercharge bar.
shortcut: faded_bush / power_box tiles are render states the tile map does not have; add them to snap2 / encode.c when
the policy needs them.
shortcut: an area effect's radius is its table Radius (no ExpandOnDistance growth), and DontShowToEnemy areas stay visible.
shortcut: no box size (the sim has none; a per-class constant adds nothing to the one-hot); add with the agent adapter.
"""
import functools, os, sys
import numpy as np
from nbpc import fair as F, diversity as D

# same order as tools/libg_qemu/classes.py SEG_CLASSES (the seg model's class ids)
SEG = ("floor", "indestructible", "destructible_wall", "fragile_wall", "bush", "faded_bush", "water", "rope_fence",
       "bouncer", "gravity", "slow_tile", "fast_tile", "ice", "damage_tile", "power_box", "poison", "out_of_bounds",
       "destructible")
UNKNOWN = len(SEG)
ENT = ("enemy", "teammate", "enemy_summon", "teammate_summon", "power_box", "power_cube", "enemy_projectile",
       "teammate_projectile", "enemy_area_effect", "teammate_area_effect")
SLIDERS = ("bush_camp", "collect", "protect", "retreat", "kite", "peek", "focus", "aggressive", "third_party", "bush_control",
           "leash", "gas_safe")
# v5.3: + 4 area-effect columns (RAD, HARM, HELP, SLOW) at the end of each entity row; v5.4: slider 7 push -> aggressive,
# + sliders leash / gas_safe at the end of cond (COND_SLIDERS); v5.5: + the intent block (N_INT) at the end of s;
# v5.7: the fire head gained "gadget" (a 4th class, gated by self 3; no input shape change); v5.8: + "hypercharge" (a 5th,
# gated by self 4 = the host's "can activate now", no longer the state2 fraction being full; no input shape change);
# v5.9: invisible enemies are left out beyond their reveal distance (host encode.c; no shape change);
# v5.10: + 2 power-cube columns (CUB) at the end of each entity row, + intent kinds super / check_bush (the block's one-hot
# grows by 2 before dx, dy: model.pad_param inserts their zero columns into a v5.9 checkpoint's vec.0)
# v5.11: + the brawler class one-hot (CLASSES, 7) at the end of each entity row (CLS, zero input columns before the lead
# columns, as v5.6's) and at the end of cond (COND_CLS, before the intent block: model.pad_param inserts their zero
# columns into a v5.5-v5.10 checkpoint's vec.0 at the old S_INT); and an enemy brawler attacking from a bush is visible
# while its main attack runs (weapon ActiveTime, the client's reveal: host env.c g_attack / encode.c, issue #92)
OBS_VERSION = "v5.11"
FIRE = ("none", "attack", "super", "gadget", "hypercharge")   # fire head classes = NbeAction.fire codes 0-4 (host env.c apply_actions)
FIRE_READY = (None, None, 2, 3, 4)               # self column that must be >= 0.5 for the class to be allowed (model.mask_fire)
FIRE_AIM = (False, True, True, True, False)      # the aim head counts for the class (the host takes the gadget's aim as its
                                                 # direction; the hypercharge has none)
# per-second goals (intent.py, behaviour design 4): block = one-hot of kinds 1..9 (none = all zeros) | dx, dy (10-tile
# units, clip +-2.5) | radius / 10 tiles | time left 1 -> 0. s = cat[self, cond, intent]: at the tail, so an older
# checkpoint's vec.0 zero-pads those columns and free play (none) is exactly its input; v5.6: + identity (14) and line of
# sight (2) columns at the end of each entity row (model inserts their zero input weights before the lead columns)
INTENTS = ("none", "move_to", "avoid", "hold", "engage", "farm", "regroup", "hide", "super", "check_bush")
N_INT_V59 = 7 + 4                        # intent block width v5.5 .. v5.9 (7 kinds; model.pad_param widens it)
N_INT = len(INTENTS) - 1 + 4
I_XY, I_RAD, I_LEFT = len(INTENTS) - 1, len(INTENTS) + 1, len(INTENTS) + 2   # block columns after the one-hot
N_SELF, N_ENT, G = 8, F.EN_K + F.PJ_K + F.BX_K + F.IT_K, 25
XY, VEL, HP, RAD = 1 + len(ENT), 3 + len(ENT), 5 + len(ENT), 6 + len(ENT)   # RAD, RAD + 1..3 = radius, harms / helps / slows me
F_ENT_V52 = 1 + len(ENT) + 5             # entity row width up to v5.2 (model.load_state_dict pads old checkpoints)
F_ENT_V55 = 1 + len(ENT) + 9             # entity row width v5.3 .. v5.5
N_ID = 13 + 1                            # identity block: brawler_stats (13) + known
ID0, ID_KNOWN, LOS = F_ENT_V55, F_ENT_V55 + 13, F_ENT_V55 + N_ID   # LOS = wall_between, LOS + 1 = water_between
F_ENT_V59 = LOS + 2                      # entity row width v5.6 .. v5.9
CUB = F_ENT_V59                          # CUB = cubes held / 10, CUB + 1 = known (v5.10)
F_ENT_V510 = CUB + 2                     # entity row width v5.10
CLASSES = ("damage_dealer", "tank", "assassin", "support", "controller", "marksman", "artillery")   # ClassArchetype values
CLS = F_ENT_V510                         # CLS .. CLS + 6 = class one-hot of the identified brawler (v5.11)
F_ENT = CLS + len(CLASSES)
WHO_FOE, WHO_MATE, WHO_ME = 0, 1, 2      # who[..., 2]: side of the row's owner seen from the observer
N_COND_V510 = 13 + len(SLIDERS) + 3 + 2  # + own cubes, teams / players left (Showdown HUD; BSRL brain/hud.py live)
N_COND = N_COND_V510 + len(CLASSES)      # + own class one-hot (v5.11)
COND_CLS = np.arange(N_COND_V510, N_COND)
N_COND_V53 = 28                          # cond width up to v5.3 (10 sliders); the 2 newer sliders sit at the end
# cond index of each slider (order SLIDERS): the first 10 after the 13 stats, the ones added later at the end, so an older
# checkpoint's input weights zero-pad at the end (model.load_state_dict) and act the same
COND_SLIDERS = np.r_[13:23, N_COND_V53:N_COND_V510]
N_S = N_SELF + N_COND + N_INT            # policy vector input s = cat[self, cond, intent]; S_INT = the intent block's offset
S_INT = N_SELF + N_COND
LEFT0 = {1: 10, 2: 5, 3: 4}              # teams left at the start by team size (sim trio = 3 x 3 + 1 solo, live 4 x 3)
_S, _E = SEG.index, ENT.index
_AREA_C = [ENT.index("enemy_area_effect"), ENT.index("teammate_area_effect")]

# Ranges, sampled once per episode. Measured by rl/measure_noise.py on the v6 models (HISTORY 61): 0 .. 2 x measured.
VEL_K = 3   # entity velocity = mean of the last <= VEL_K matched one-decision differences (then an EMA 1 / VEL_K): one
# difference of two jittered boxes was mostly noise (sigma .138 vs signal .12 tiles / tick, HISTORY 77); sim + live alike


def smooth_vel(raw, m, pest, page):
    """raw (..., 2) one-decision velocity of detections matched (m) to a last-decision track with estimate pest / age page
    (gathered at the match) -> (estimate, age); unmatched: 0, 0. Age 1 = raw (no start bias)."""
    age = np.where(m, page + 1, 0)
    est = np.where(m[..., None], pest + (raw - pest) / np.clip(age, 1, VEL_K)[..., None], 0.0).astype(np.float32)
    return est, age


NOISE = {"jitter": (0.0, 0.039),   # box centre sigma, 10-tile units (measured .0195)
         "drop": (0.0, 0.0),       # extra pooled chance per entity and decision of a miss (on top of drop_cls)
         "drop_cls": (0.5, 1.5),   # per-episode factor on the measured per-class miss chance DROP_CLS
         "fp": (0.0, 0.060),       # chance per empty slot and decision of a false detection (measured .030)
         "seg": (0.0, 0.137),      # chance per visible tile and decision of a wrong class (measured .068)
         "latency": (1, 2),        # decisions between the frame and the action (inclusive)
         "bleed": (0.0, 0.0),      # factor on BLEED_ROW x BLEED_CLS: off, v6 labels / models show 0.3-0.7 % (HISTORY 61)
         # identity (v5.6). GUESSES until the live reader (countdown name OCR + nickname per track) is measured:
         "id_known": (0.2, 1.0),       # chance per enemy player and battle that its brawler is known (the countdown only
                                       # shows the players on screen then; a track lost and re-found keeps its name)
         "id_known_mate": (0.8, 1.0),  # the same for a teammate (lobby / countdown show the team; on screen together)
         "id_wrong": (0.0, 0.05),      # chance per known enemy and battle that it is given a wrong brawler (OCR / name match)
         "pj_owner_known": (0.3, 1.0), # chance per projectile row and decision that it is linked to its shooter (by origin)
         # power cubes (v5.10). GUESSES until BSRL's per-track cube OCR is measured live:
         "cube_known": (0.5, 1.0),     # chance per player and battle that its cube number is ever read (small text, HUD OCR <= 1 Hz)
         "cube_misread": (0.0, 0.1)}   # chance per read row and decision that the count is off by one (+-1, not below 0)

# measured miss chance per class, det_v6 vs labels on 1000 val frames (HISTORY 61), ENT order
DROP_CLS = np.array([.079, .085, .198, .101, .032, .241, .527, .457, .449, .263], np.float32)

# wall bleed, measured (sim_vs_labels.py, HISTORY 53): the adapter reads a not-tall tile right behind (row - 1) a tall one
# as that tall tile with chance row factor (by grid row = ry bin + 12) x front-class factor; out_of_bounds never bleeds
BLEED_ROW = np.array([.6, .6] + [.4] * 4 + [.25] * 4 + [.11] * 7 + [.6] * 8, np.float32)   # rows -12..+12
_TALL = ("indestructible", "destructible_wall", "fragile_wall", "bush", "faded_bush", "rope_fence", "destructible")
_TALL_M = np.isin(np.arange(len(SEG) + 1), [SEG.index(n) for n in _TALL])                         # index UNKNOWN: False
_BLEED_CLS = np.array([{"indestructible": 1.3, "destructible_wall": 1.1, "bush": .8, "destructible": .2, "rope_fence": .2}.get(n, 1.0)
                       for n in SEG] + [0.0], np.float32)


@functools.lru_cache(None)
def _tile_lut():
    """host grid channel 0 (tiles.csv row + 1; 0 = outside the map) -> seg class id.
    The rule of tools/libg_qemu/classes.py seg_class, on this game version's tiles.csv."""
    lut = np.full(256, _S("floor"), np.uint8); lut[0] = _S("out_of_bounds")
    for name, (i, r) in D.table("tiles.csv").items():
        t = lambda k: r.get(k) == "true"
        num = lambda k: int(r.get(k) or 0)
        if t("IsForest"): c = "bush"
        elif t("IsBouncer"): c = "bouncer"
        elif name.startswith("Gravity"): c = "gravity"
        elif name == "Fragile": c = "destructible"
        elif t("BlocksMovement") and t("BlocksProjectiles"):
            c = ("fragile_wall" if t("IsDestructibleNormalWeapon") or num("Health") > 0 else
                 "destructible_wall" if t("IsDestructible") else "indestructible")
        elif t("BlocksMovement"): c = "rope_fence" if t("IsDestructible") else "water"
        elif num("SpeedChange") < 0: c = "slow_tile"
        elif num("SpeedChange") > 0: c = "fast_tile"
        elif name == "Ice": c = "ice"
        elif num("Damage") > 0 or name == "IntervalDamage": c = "damage_tile"
        else: c = "floor"
        if 0 <= i % 1000000 < 255: lut[i % 1000000 + 1] = _S(c)
    return lut


AREA_ITEM0 = 1000000   # item feature 5 code: 1 + area_effects_skin row (17xxxxxx), AREA_ITEM0 + 1 + items row (18xxxxxx)
_HARM_T = {"Damage", "Dot", "DamageAndStatusEffect", "HealAndDamage", "HotAndDot", "DelayedDamage", "BulletExplosion", "Stun", "Pushback"}
_HELP_T = {"Heal", "Hot", "HealRegen", "HealAndDamage", "HotAndDot", "DamageBoost", "ExtraSuperCharge"}


@functools.lru_cache(None)
def _area_lut():
    """(n, 4) float32 per item feature-5 code (index: area skin row + 1, then AREA_ITEM0 rows from index NA): radius / 3000
    (10-tile units, as dx / dy), harms enemies, helps allies, slows enemies; row 0 / unknown = 0. From area_effects_skin
    (Logic) -> area_effects_logic (Radius, Type, Damage) + status_effects_logic of StatusEffectEnemy / Ally; an item
    through its TriggerAreaEffect (the bomb's explosion)."""
    named = lambda f: [r for r in D._rows(f) if r.get("Name")]
    lg = {r["Name"]: r for r in named("area_effects_logic.csv")}; se = {r["Name"]: r for r in named("status_effects_logic.csv")}
    num = lambda r, k: int((r.get(k) or "0").split(";")[0] or 0)   # one row has Radius '720;1200' (first = the base)

    def row(L):
        if L is None: return [0.0] * 4
        en, al = se.get(L.get("StatusEffectEnemy"), {}), se.get(L.get("StatusEffectAlly"), {})
        harm = L.get("Type") in _HARM_T or num(L, "Damage") > 0 or num(en, "Damage") > 0 or en.get("FullStun", "").lower() == "true"
        help_ = L.get("Type") in _HELP_T or any(num(al, k) > 0 for k in ("Healing", "SpeedBoostPercent", "SpeedBoostAbsolute", "DamageBoostPercent", "ShieldPercent"))
        slow = num(en, "SpeedReducePercent") > 0 or num(en, "SpeedReduceAbsolute") > 0
        return [num(L, "Radius") / 3000.0, harm, help_, slow]
    sk, items = named("area_effects_skin.csv"), named("items.csv")
    lut = np.zeros((1 + len(sk) + 1 + len(items), 4), np.float32)
    for k, r in enumerate(sk): lut[1 + k] = row(lg.get(r.get("Logic") or r["Name"]))
    skl = {r["Name"]: r.get("Logic") or r["Name"] for r in sk}   # TriggerAreaEffect names a skin row or a logic row
    for k, r in enumerate(items):
        t = r.get("TriggerAreaEffect"); lut[1 + len(sk) + 1 + k] = row(lg.get(t) or lg.get(skl.get(t)))
    return lut, 1 + len(sk)


def area_feats(code, side):
    """(..., 4) entity columns RAD.. of item rows: feature-5 code (host data id - 16999999), side = item feature 4
    (1 enemy / neutral, -1 my team) -> radius, harms me, helps me, slows me"""
    lut, na = _area_lut(); c = np.rint(code).astype(np.int64)
    i = np.where(c > AREA_ITEM0, na + np.clip(c - AREA_ITEM0, 0, len(lut) - na - 1), np.clip(c, 0, na - 1))
    f = lut[i].copy(); foe = side > 0.5
    f[..., 1] *= foe; f[..., 3] *= foe; f[..., 2] *= side < -0.5
    return f


def from_state2(vec, grid, meta, who=None, derived=True, gadget=None, hyper=None):
    """fair state2 vec (B, 436), grid (B, 6, 25, 25), meta (B, 5) = x, y, tick, W, H (MAEnv.last_meta), who (B, N_ENT, 3)
    (module doc; None = identities and cube counts unknown), gadget (B,) the gadget can be used now (env_v5.Env.gadget; None = 0), hyper
    (B,) the hypercharge can be activated now (env_v5.Env.hyper; None = 0) -> clean
    obs (every row with an owner known). derived=False: identity, line-of-sight and cube columns left 0 (the noisy build
    computes them itself)"""
    B = len(vec)
    s = np.zeros((B, N_SELF), np.float32)
    s[:, 0] = vec[:, 0]; s[:, 1] = np.minimum(vec[:, 2], 1.0); s[:, 2] = vec[:, 5] >= 1.0; s[:, 5] = vec[:, 8]
    if gadget is not None: s[:, 3] = np.asarray(gadget, np.float32).reshape(B) >= 0.5
    if hyper is not None: s[:, 4] = np.asarray(hyper, np.float32).reshape(B) >= 0.5   # v5.8: was vec[:, 18] >= 1 (module doc)
    s[:, 6:8] = vec[:, 12:14] * (40 / 300)
    ent = np.zeros((B, N_ENT, F_ENT), np.float32)

    def fill(k0, blk, cls, vel=None, hp=None):
        e = ent[:, k0:k0 + blk.shape[1]]
        e[..., 0] = blk[..., 0] > 0.5
        e[..., XY:XY + 2] = blk[..., 1:3]
        if vel: e[..., VEL:VEL + 2] = blk[..., 3:5] * vel
        if hp: e[..., HP] = blk[..., hp]
        np.put_along_axis(e, (1 + cls)[..., None], 1.0, axis=2)
        e *= e[..., :1]
        return k0 + blk.shape[1]

    blk = lambda off, K, Fn: vec[:, off:off + K * Fn].reshape(B, K, Fn)
    en, pj, bx, it = blk(F.EN0, F.EN_K, F.EN_F), blk(F.PJ0, F.PJ_K, F.PJ_F), blk(F.BX0, F.BX_K, F.BX_F), blk(F.IT0, F.IT_K, F.IT_F)
    # ENT order: enemy, teammate, enemy_summon, teammate_summon = 2 * summon (14) + on my team (15)
    k = fill(0, en, (2 * (en[..., 14] > 0.5) + (en[..., 15] > 0.5)).astype(np.int64), vel=40 / 300, hp=5)
    k = fill(k, pj, np.where(pj[..., 5] > 0.5, _E("teammate_projectile"), _E("enemy_projectile")), vel=200 / 300)
    k = fill(k, bx, np.full(bx.shape[:2], _E("power_box")), hp=3)
    it = it.copy(); it[..., 0] *= (it[..., 3] > 0.5) | (np.abs(it[..., 4]) > 0.5)  # other items are not detected classes
    # item 4: 1 = showdown bomb or enemy area effect, -1 = area effect of my team (nbhost_rl encode.c)
    fill(k, it, np.select([it[..., 3] > 0.5, it[..., 4] < -0.5], [_E("power_cube"), _E("teammate_area_effect")], _E("enemy_area_effect")))
    area = (it[..., 0] > 0.5) & (it[..., 3] < 0.5) & (np.abs(it[..., 4]) > 0.5)
    ent[:, k:k + F.IT_K, RAD:RAD + 4] = area_feats(it[..., 5], it[..., 4]) * area[..., None]

    g = _tile_lut()[grid[:, 0]]
    g[(grid[:, 3] > 0) & (g == _S("floor"))] = _S("poison")
    g[grid[:, 4] > 0] = _S("out_of_bounds")
    rx, ry = _cam(meta)
    seen = (np.abs(rx) < F.VIEW_X)[:, None, :] & ((ry > -F.VIEW_UP) & (ry < F.VIEW_DOWN))[:, :, None]
    g[~seen] = UNKNOWN
    if not derived: return {"self": s, "ent": ent, "grid": g}
    if who is not None:
        w = np.asarray(who); ok = (w[..., 1] >= 0) & (ent[..., 0] > 0.5)
        id_cols(ent, np.where(ok, w[..., 1], -1))
        cube_cols(ent, cubes_held(ent, w))
    ent[..., LOS:LOS + 2] = los(ent, g)
    return {"self": s, "ent": ent, "grid": g}


# line of sight (v5.6): projectile-blocking classes (BlocksMovement + BlocksProjectiles in tiles.csv: every wall class,
# bouncer, gravity, Fragile; power_box = a live render state of the boxes) vs movement-only (water, rope fence)
_BLOCK_PJ = np.isin(np.arange(len(SEG) + 1), [SEG.index(n) for n in ("indestructible", "destructible_wall", "fragile_wall", "bouncer",
                                                                     "gravity", "power_box", "destructible")])
_BLOCK_MV = np.isin(np.arange(len(SEG) + 1), [SEG.index(n) for n in ("water", "rope_fence")])
LOS_N = 32                                 # samples per line: <= 0.5 tile apart up to 16 tiles (the view's diagonal)
_LOS_T = ((np.arange(LOS_N) + 0.5) / LOS_N).astype(np.float32)


def los(ent, g):
    """(B, N_ENT, 2) float32 wall_between, water_between of the present enemy / teammate rows of ent (B, N_ENT, F_ENT)
    on the seg grid g (B, G, G): any sample of the line from my tile centre (cell 12.5, 12.5) to the row's dx, dy on a
    _BLOCK_PJ / _BLOCK_MV tile, my own tile and the row's tile left out; 0 for every other row"""
    out = np.zeros(ent.shape[:2] + (2,), np.float32)
    m = (ent[..., 0] > 0.5) & (ent[..., 1:1 + len(ENT)].argmax(-1) <= _E("teammate"))
    bi, ki = np.nonzero(m)
    if not len(bi): return out
    d = ent[bi, ki, XY:XY + 2] * np.float32(10.0)                                        # tiles, (x, y)
    c = np.floor(np.float32(G / 2) + d[:, None, :] * _LOS_T[None, :, None]).astype(np.int64)   # (n, LOS_N, 2) cells
    end = np.floor(np.float32(G / 2) + d).astype(np.int64)
    ok = ((c >= 0) & (c < G)).all(-1) & ~(c == G // 2).all(-1) & ~(c == end[:, None]).all(-1)
    t = g[bi[:, None], np.clip(c[..., 1], 0, G - 1), np.clip(c[..., 0], 0, G - 1)]
    out[bi, ki, 0] = (_BLOCK_PJ[t] & ok).any(1); out[bi, ki, 1] = (_BLOCK_MV[t] & ok).any(1)
    return out


def id_draws(n, r):
    """per-episode identity draws (ObsV5._episode / FastObsV5._episode, after the older draws, same order): known chance
    enemy / mate, wrong chance, projectile link chance, then per player slot (16) u_known, u_wrong and the wrong pick
    offset (1 .. n_heroes - 1, never the true one). Keys missing from the noise dict: identity perfect"""
    nh = len(id_lut()[0])
    return (r.uniform(*n.get("id_known", (1, 1))), r.uniform(*n.get("id_known_mate", (1, 1))), r.uniform(*n.get("id_wrong", (0, 0))),
            r.uniform(*n.get("pj_owner_known", (1, 1))), r.random(16), r.random(16), r.integers(1, max(nh, 2), 16),
            r.uniform(*n.get("cube_known", (1, 1))), r.uniform(*n.get("cube_misread", (0, 0))), r.random(16))


_PJ_ROW = (np.arange(N_ENT) >= F.EN_K) & (np.arange(N_ENT) < F.EN_K + F.PJ_K)   # ent slots of the projectile block


def noisy_id(ent, who, eps_id, link):
    """identity columns in place on noisy rows: eps_id = per row of the batch its id_draws tuple, link (B, N_ENT)
    uniforms of this decision (projectile owner linked iff < its chance). A player's identity (known, given brawler) is a
    function of the episode draws only, so it stays fixed for the battle; me: always known, never wrong; mates: never wrong"""
    names, lut = id_lut(); nh = len(names)
    pk_en, pk_m, pw, ppj = (np.array([e[i] for e in eps_id], np.float32) for i in range(4))
    uk, uw, pick = (np.stack([e[i] for e in eps_id]) for i in (4, 5, 6))
    w = np.asarray(who); q = np.clip(w[..., 0], 0, 15).astype(np.int64); hero, side = w[..., 1].astype(np.int64), w[..., 2]
    tk = lambda a: np.take_along_axis(a, q, 1)
    kp = (side == WHO_ME) | (tk(uk) < np.where(side == WHO_MATE, pk_m[:, None], pk_en[:, None]))
    wrong = (side == WHO_FOE) & (tk(uw) < pw[:, None])
    given = np.where(wrong, (hero + tk(pick)) % max(nh, 1), hero)
    known = (hero >= 0) & (w[..., 0] >= 0) & (ent[..., 0] > 0.5) & kp & (~_PJ_ROW[None] | (side == WHO_ME) | (link < ppj[:, None]))
    id_cols(ent, np.where(known, given, -1))


def id_cols(ent, row):
    """identity columns in place: row (B, N_ENT) = the id_lut row each entity row names (-1 = unknown) -> its
    brawler_stats, known, and its class one-hot (CLS, v5.11)"""
    ent[..., ID0:ID0 + 13] = id_lut()[1][row]; ent[..., ID_KNOWN] = row >= 0; ent[..., CLS:CLS + len(CLASSES)] = cls_lut()[row]


_PLAYER_C = [1 + ENT.index("enemy"), 1 + ENT.index("teammate")]


def cubes_held(ent, who):
    """(B, N_ENT) int64 cubes held per player row with an owner (who[..., 3]), -1 = none (a 3-column who: all -1)"""
    w = np.asarray(who)
    if w.shape[-1] < 4: return np.full(w.shape[:-1], -1, np.int64)
    pl = (ent[..., 0] > 0.5) & (ent[..., _PLAYER_C].sum(-1) > 0.5) & (w[..., 0] >= 0)
    return np.where(pl, w[..., 3], -1).astype(np.int64)


def cube_cols(ent, c):
    """CUB columns in place from cubes held c (B, N_ENT) (-1 = unknown)"""
    ent[..., CUB] = np.where(c >= 0, np.minimum(c, 20) / 10.0, 0.0); ent[..., CUB + 1] = c >= 0


def noisy_cubes(ent, who, eps_id, u):
    """CUB columns in place on noisy rows: eps_id = per row of the batch its id_draws tuple, u (B, N_ENT, 2) uniforms of
    this decision. A player's count is read or never read for the whole battle (episode draws); a read one is off by one
    with the per-decision chance (u[..., 0]; u[..., 1] picks the sign)"""
    c = cubes_held(ent, who)
    pk, pm = (np.array([e[i] for e in eps_id], np.float32) for i in (7, 8))
    uc = np.stack([e[9] for e in eps_id]); q = np.clip(np.asarray(who)[..., 0], 0, 15).astype(np.int64)
    c = np.where(np.take_along_axis(uc, q, 1) < pk[:, None], c, -1)
    off = np.where(u[..., 0] < pm[:, None], np.where(u[..., 1] < 0.5, -1, 1), 0)
    cube_cols(ent, np.where(c >= 0, np.maximum(c + off, 0), -1))


def _cam(meta):
    """tile centres relative to the camera, the rule of nbpc.fair: rx (B, G) from the camera x, ry (B, G) from the player y"""
    mx, my, W = meta[:, 0].astype(np.float64), meta[:, 1].astype(np.float64), meta[:, 3]
    off = (np.arange(G) - G // 2) * F.TILE + F.TILE / 2
    rx = (mx // F.TILE * F.TILE)[:, None] + off - np.clip(mx, 3000.0, W * F.TILE - 3000.0)[:, None]
    return rx, (my // F.TILE * F.TILE - my)[:, None] + off


# measured by sim_vs_labels.py (HISTORY 53): per tile bin (ry, rx as in _cam, floor(r / TILE) + G // 2) the share of 2815
# label frames where every on-screen base sample of the tile is seg 'ui' (the adapter then reads UNKNOWN); max 0.5.
# Shares < 5 % are dropped (stray ui pixels; 51 of 625 bins stay).
HUD_UI = np.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "hud_ui.npy")); HUD_UI[HUD_UI < 0.05] = 0


def hud_p(meta):
    """(B, G, G) measured chance that the HUD hides each tile"""
    rx, ry = _cam(meta)
    bx = np.clip(np.floor(rx / F.TILE).astype(int) + G // 2, 0, G - 1); by = np.clip(np.floor(ry / F.TILE).astype(int) + G // 2, 0, G - 1)
    return HUD_UI[by[:, :, None], bx[:, None, :]]


def hud_mask(meta, rng=None):
    """(B, G, G) bool: tiles the HUD hides. rng given: each tile hidden with its measured chance, else those > 0.5 (none)"""
    p = hud_p(meta)
    return rng.random(p.shape) < p if rng is not None else p > 0.5


class ObsV5:
    """builder + per-episode noise; noise=None gives the clean observation. Noisy: entity velocity = differenced noisy
    positions (0 on first sight), HUD-covered tiles UNKNOWN."""

    GATE = 0.1   # 1 tile: a detection within this of where a last-decision detection of its class should be = the same object

    def __init__(self, noise=NOISE, seed=0, ticks=2):
        self.noise, self.rng, self.ep, self.ticks = noise, np.random.default_rng(seed), {}, ticks   # ticks per decision (Env)

    def _episode(self, aid):
        """agent id -> [jitter, drop, fp, seg, latency, frames, last decision's detections, bleed factor, drop_cls factor,
        identity draws (id_draws)]"""
        e = self.ep.get(aid)
        if e is None:
            n, r = self.noise, self.rng
            e = self.ep[aid] = [r.uniform(*n["jitter"]), r.uniform(*n["drop"]), r.uniform(*n["fp"]), r.uniform(*n["seg"]),
                                int(r.integers(n["latency"][0], n["latency"][1] + 1)), [], None, r.uniform(*n.get("bleed", (0, 0))),
                                r.uniform(*n.get("drop_cls", (0, 0))), id_draws(n, r)]
            if len(self.ep) > 4096:   # shortcut: ended episodes are never reported here, so drop the oldest half
                for k in list(self.ep)[:2048]: del self.ep[k]
        return e

    def build(self, vec, grid, meta, ids, cmd=None, who=None, gadget=None, hyper=None):
        """cmd (B, 2) tiles / tick (sim_plan A2, train_fast --cmd-vel): own velocity = the commanded move, as the agent gets
        it live (BSRL brain / play_live: move direction x brawler speed); entity velocities then carry the same error
        (live: matched position difference + commanded own velocity). Noisy path only. who (B, N_ENT, 4): the rows'
        owners (env_v5.Env.last_who; module doc), None = every identity unknown. gadget (B,): from_state2's (self 3; like
        the rest of self it reaches the policy with the episode's latency), hyper (B,): from_state2's (self 4, the same)."""
        o = from_state2(vec, grid, meta, who, derived=self.noise is None or not len(ids), gadget=gadget, hyper=hyper)
        if self.noise is None or not len(ids):
            return o
        r, B = self.rng, len(ids)
        err = np.zeros((B, 2), np.float32)
        if cmd is not None:
            err = (np.asarray(cmd, np.float32) - o["self"][:, 6:8]).astype(np.float32); o["self"][:, 6:8] = cmd
        eps = [self._episode(int(a)) for a in ids]
        jit, drop, fp, seg = (np.array([e[i] for e in eps], np.float32) for i in range(4))
        ent, g = o["ent"], o["grid"]
        here = ent[..., 0] > 0.5
        false = ~here & (r.random(here.shape) < fp[:, None])
        dcf = np.array([e[8] for e in eps], np.float32)
        pd = drop[:, None] + DROP_CLS[ent[..., 1:1 + len(ENT)].argmax(-1)] * dcf[:, None]
        ent[here & (r.random(here.shape) < pd)] = 0.0
        nse = r.normal(size=(B, N_ENT, 2)).astype(np.float32) * jit[:, None, None] * ent[..., :1]
        ent[..., XY:XY + 2] += nse
        rj = r.normal(size=(B, N_ENT)).astype(np.float32) * jit[:, None] * (ent[..., RAD] > 0)   # radius from the drawn ring:
        ent[..., RAD] = np.maximum(ent[..., RAD] + rj, 0.0)                                       # the centre's sigma (not measured)
        n = int(false.sum())
        if n:
            row = np.zeros((n, F_ENT), np.float32); row[:, 0] = 1.0
            fc = r.integers(len(ENT), size=n); row[np.arange(n), 1 + fc] = 1.0
            row[:, XY] = r.uniform(-1.5, 1.5, n); row[:, XY + 1] = r.uniform(-F.VIEW_UP, F.VIEW_DOWN, n) / F.R
            row[:, HP] = r.random(n)
            row[:, RAD] = np.isin(fc, _AREA_C) * r.uniform(0.1, 0.5, n)   # a false area effect: a 300-1500 radius, no kind
            ent[false] = row
        hud = hud_mask(meta, r); g[hud] = UNKNOWN          # the seg model labels the HUD controls 'ui'
        bl = np.array([e[7] for e in eps], np.float32)
        front = np.full_like(g, UNKNOWN); front[:, :-1] = g[:, 1:]
        bleed = ~_TALL_M[g] & (g != _S("out_of_bounds")) & (g != UNKNOWN) & _TALL_M[front]
        bleed &= r.random(g.shape) < BLEED_ROW[None, :, None] * _BLEED_CLS[front] * bl[:, None, None]
        g[bleed] = front[bleed]
        wrong = (g != UNKNOWN) & (r.random(g.shape) < seg[:, None, None])
        g[wrong] = r.integers(len(SEG), size=int(wrong.sum()))
        link = r.random((B, N_ENT))                       # identity (v5.6): projectile owner links of this decision
        cu = r.random((B, N_ENT, 2))                      # power cubes (v5.10): misreads of this decision
        if who is None: ent[..., ID0:ID0 + N_ID] = 0.0; ent[..., CUB:CUB + 2] = 0.0; ent[..., CLS:F_ENT] = 0.0
        else:
            wh = np.where(here[..., None], who, -1)        # false detections: unknown
            noisy_id(ent, wh, [e[9] for e in eps], link); noisy_cubes(ent, wh, [e[9] for e in eps], cu)
        ent[..., LOS:LOS + 2] = los(ent, g)               # on the noisy rows / grid of this frame
        # velocity as the agent gets it: the difference of two noisy detections, 0 for one not matched to the last decision
        on, cls = ent[..., 0] > 0.5, ent[..., 1:1 + len(ENT)].argmax(-1)
        move = (ent[..., VEL:VEL + 2] - o["self"][:, None, 6:8]) * (self.ticks / 10)   # tiles/tick -> 10-tile units per decision
        for b, e in enumerate(eps):
            v = np.zeros((N_ENT, 2), np.float32); age = np.zeros(N_ENT, np.int64)
            if e[6] is not None:
                pon, pcls, pxy, pn, pest, page = e[6]
                d = np.linalg.norm(ent[b, :, None, XY:XY + 2] - move[b, :, None] - pxy[None], axis=2)
                d[~(on[b][:, None] & pon[None] & (cls[b][:, None] == pcls[None]))] = np.inf
                m = d.min(1) < self.GATE; jj = d.argmin(1)
                raw = ent[b, :, VEL:VEL + 2] + (nse[b] - pn[jj]) * (10 / self.ticks) + err[b]
                v, age = smooth_vel(raw, m, pest[jj], page[jj])
            e[6] = (on[b], cls[b], ent[b, :, XY:XY + 2].copy(), nse[b], v, age)
            ent[b, :, VEL:VEL + 2] = v
        for b, e in enumerate(eps):                       # latency: the policy acts on the frame of e[4] decisions ago
            q = e[5]; q.append({k: v[b].copy() for k, v in o.items()})
            if len(q) > e[4] + 1: q.pop(0)
            for k in o: o[k][b] = q[0][k]
        return o


@functools.lru_cache(None)
def _tables():
    return ({r["Name"]: r for r in D._rows("skills.csv")}, {r["Name"]: r for r in D._rows("projectiles_logic.csv")})


@functools.lru_cache(None)
def brawler_stats(name):
    """(13,) range, speed, reload, projectile speed, spread, bullets, thrown, melee, hp, super attack / charge / other,
    super range; from characters.csv / skills.csv / projectiles_logic.csv, scaled to about 0-1"""
    sk, pj = _tables()
    c = D.table("characters.csv")[name][1]
    w, u = sk.get(c.get("WeaponSkill"), {}), sk.get(c.get("UltimateSkill"), {})
    p = pj.get(w.get("Projectiles"), {})
    num = lambda r, k: float(r.get(k) or 0)
    ub = u.get("BehaviorType")
    v = np.array([num(w, "CastingRange") / 30, num(c, "Speed") / 1000, num(w, "RechargeTime") / 3000, num(p, "Speed") / 4000,
                  num(w, "Spread") / 300, num(w, "NumBulletsInOneAttack") / 10, p.get("Indirect") == "true", not p,
                  num(c, "Hitpoints") / 10000, ub == "Attack", ub == "Charge", ub not in ("Attack", "Charge"),
                  num(u, "CastingRange") / 30], np.float32)
    return np.minimum(v, 2.0)    # a few rows are far out (a 29000-speed projectile, 120-tile supers)


@functools.lru_cache(None)
def hero_names():
    """identity names = Hero rows that own cards (drops bosses and the hashed unreleased rows), table order: the playable
    brawlers and the forms they turn into in battle (env_v5.heroes = the playable ones, the battle pool; env_v5.forms =
    the rest). Sizes the identity table (id_lut), so it is part of the observation contract."""
    import re
    owners = {r["Target"] for r in D._rows("cards.csv")}
    return tuple(n for n, (_, r) in D.table("characters.csv").items()
                 if r.get("Type") == "Hero" and r.get("Disabled") != "true" and n in owners and not re.fullmatch(r"[0-9a-f]{40}", n))


@functools.lru_cache(None)
def id_lut():
    """(names, (n + 1, 13) float32): the brawlers an identity can name (hero_names) and their brawler_stats; the last row
    (index -1) = zeros = unknown. id_row(name) / id_row_of_data(characters data id) -> row, -1 if not a hero"""
    names = hero_names()
    return names, np.concatenate([np.stack([brawler_stats(n) for n in names]), np.zeros((1, 13), np.float32)]).astype(np.float32)


def brawler_class(name):
    """(len(CLASSES),) float32 one-hot of a brawler's characters.csv ClassArchetype (zeros for one outside CLASSES)"""
    c = D.table("characters.csv")[name][1].get("ClassArchetype"); out = np.zeros(len(CLASSES), np.float32)
    if c in CLASSES: out[CLASSES.index(c)] = 1.0
    return out


@functools.lru_cache(None)
def cls_lut():
    """(n + 1, len(CLASSES)) float32: the class one-hot of each id_lut row; the last row (index -1) = zeros = unknown"""
    return np.concatenate([np.stack([brawler_class(n) for n in id_lut()[0]]), np.zeros((1, len(CLASSES)), np.float32)])


@functools.lru_cache(None)
def _id_rows():
    t = D.table("characters.csv"); names = id_lut()[0]
    return {n: k for k, n in enumerate(names)}, {t[n][0]: k for k, n in enumerate(names)}


def id_row(name):
    return _id_rows()[0].get(name, -1)


def id_row_of_data(data_id):
    return _id_rows()[1].get(int(data_id), -1)


# play-style modes: slider weights (0-2) per named preset, sliders not listed = 1.0 (the uniform sampler's mean).
# Inference: cond(..., sliders=preset_vec(name)). 2 = the style's own sliders, 0-0.5 = what the style gives up.
PRESETS = {
    "balanced": {},
    "bush_camper": {"bush_camp": 2, "collect": .5, "retreat": 1.5, "aggressive": 0, "third_party": 1.5, "bush_control": .5, "gas_safe": 1.5},
    "aggressive": {"bush_camp": 0, "collect": .5, "retreat": .5, "kite": .3, "peek": .5, "focus": 2, "aggressive": 2, "third_party": .5,
                   "bush_control": .5, "gas_safe": .5},
    "cube_farmer": {"bush_camp": .5, "collect": 2, "protect": .5, "retreat": 1.5, "peek": .5, "aggressive": .3, "leash": .5, "gas_safe": 1.5},
    "third_partier": {"protect": .5, "kite": 1.5, "focus": 1.5, "aggressive": .3, "third_party": 2, "leash": .5},
    "marksman": {"bush_camp": .5, "protect": .5, "retreat": 1.5, "kite": 2, "peek": 1.5, "aggressive": 0, "leash": .5},
    "team_player": {"bush_camp": .5, "collect": .5, "protect": 2, "focus": 2, "third_party": .5, "bush_control": .5, "leash": 2},
}


def preset_vec(name):
    """(len(SLIDERS),) float32 slider weights of a PRESETS entry"""
    p = PRESETS[name]
    return np.array([p.get(k, 1.0) for k in SLIDERS], np.float32)


def cond(brawler, sliders, team_size=1, cubes=0, left=None):
    """conditioning vector: brawler stats (13) + slider weights 0-2 (the first 10 of SLIDERS) + team size 1-3 one-hot
    + own power cubes / 10 (max 2) + teams (solo: players) left / 10, the two Showdown HUD numbers + the later sliders
    (leash, gas_safe) + own class one-hot (COND_CLS, v5.11). COND_SLIDERS = each slider's index."""
    t = np.zeros(3, np.float32); t[team_size - 1] = 1.0; w = np.asarray(sliders, np.float32)
    hud = np.array([min(cubes, 20) / 10.0, (LEFT0[team_size] if left is None else left) / 10.0], np.float32)
    return np.concatenate([brawler_stats(brawler), w[:10], t, hud, w[10:], brawler_class(brawler)])


def _check():
    vec = np.zeros((2, 436), np.float32); grid = np.zeros((2, 6, 25, 25), np.uint8)
    meta = np.array([[9150, 9150, 100, 60, 60], [150, 9150, 100, 60, 60]], np.int32)   # mid-map; left edge
    vec[:, 0] = 0.5; vec[:, 2] = 2 / 3; vec[:, 5] = 1.0; vec[:, 12] = 1.0
    row = lambda off, Fn, k, v: vec.__setitem__((0, slice(off + k * Fn, off + k * Fn + len(v))), v)
    row(F.EN0, F.EN_F, 0, [1, 0.5, -0.2, 1, 0, 0.8])
    row(F.EN0, F.EN_F, 1, [1, 0.6, 0, 0, 0, 1] + [0] * 9 + [1]); row(F.EN0, F.EN_F, 2, [1, 0.7, 0, 0, 0, 1] + [0] * 8 + [1, 0])
    row(F.EN0, F.EN_F, 3, [1, 0.8, 0, 0, 0, 1] + [0] * 8 + [1, 1]); vec[0, 18] = 1.0
    tile = lambda n: D.table("tiles.csv")[n][0] % 1000000 + 1
    grid[:, 0] = tile("Open")
    row(F.PJ0, F.PJ_F, 0, [1, 0.1, 0.1, 1, 0, 1, 0]); row(F.PJ0, F.PJ_F, 1, [1, 0.2, 0.1, 0, 1, 0, 1])
    row(F.BX0, F.BX_F, 0, [1, 0.3, 0.3, 0.6])
    lut, na = _area_lut(); slow = int(np.nonzero(lut[1:na, 3])[0][0]) + 1        # codes: 1 Brock_def_atk_area (damage, 450), 155 Heal
    row(F.IT0, F.IT_F, 0, [1, 0.4, 0, 1, 0]); row(F.IT0, F.IT_F, 1, [1, 0.4, 0, 0, 1, 1]); row(F.IT0, F.IT_F, 2, [1, 0.4, 0, 0, 0]); row(F.IT0, F.IT_F, 3, [1, 0.4, 0, 0, -1, 155])
    row(F.IT0, F.IT_F, 4, [1, 0.4, 0, 0, 1, slow]); row(F.IT0, F.IT_F, 5, [1, 0.4, 0, 0, -1, 1]); row(F.IT0, F.IT_F, 6, [1, 0.4, 0, 0, 1, AREA_ITEM0 + 1 + 35])
    grid[0, 0, 12, 13] = tile("Indestructible"); grid[0, 0, 12, 14] = tile("Forest"); grid[0, 3, 12, 14] = 1
    grid[0, 0, 12, 15] = tile("Wall1"); grid[0, 0, 12, 16] = tile("Water"); grid[0, 0, 12, 17] = tile("RopeFence")
    grid[0, 3, 5, 5] = 1; grid[0, 4, 3, 3] = 1; grid[0, 0, 3, 3] = 0
    o = from_state2(vec, grid, meta)
    assert o["self"].shape == (2, N_SELF) and o["ent"].shape == (2, N_ENT, F_ENT) and o["grid"].shape == (2, G, G)
    assert np.allclose(o["self"][0], [0.5, 2 / 3, 1, 0, 0, 0, 40 / 300, 0])   # self 4: 0 without hyper, though the fraction is full
    og = from_state2(vec, grid, meta, gadget=np.array([1, 0]))   # self 3 = gadget ready, nothing else changes
    assert og["self"][0, 3] == 1 and og["self"][1, 3] == 0 and np.array_equal(np.delete(og["self"], 3, 1), np.delete(o["self"], 3, 1))
    assert all(np.array_equal(og[k], o[k]) for k in ("ent", "grid"))
    assert len(FIRE) == len(FIRE_READY) == len(FIRE_AIM) and FIRE[:3] == ("none", "attack", "super") and FIRE_READY[3] == 3
    oh = from_state2(vec, grid, meta, hyper=np.array([0, 1]))    # self 4 from the host's state, not the fraction
    assert oh["self"][0, 4] == 0 and oh["self"][1, 4] == 1 and np.array_equal(np.delete(oh["self"], 4, 1), np.delete(o["self"], 4, 1))
    assert FIRE[4] == "hypercharge" and FIRE_READY[4] == 4 and not FIRE_AIM[4] and OBS_VERSION == "v5.11"
    e = o["ent"][0]; cls = lambda k: ENT[int(e[k, 1:1 + len(ENT)].argmax())]
    got = [(k, cls(k)) for k in np.nonzero(e[:, 0])[0]]
    assert got == [(0, "enemy"), (1, "teammate"), (2, "enemy_summon"), (3, "teammate_summon"), (9, "teammate_projectile"),
                   (10, "enemy_projectile"), (25, "power_box"), (31, "power_cube"), (32, "enemy_area_effect"), (34, "teammate_area_effect"), (35, "enemy_area_effect"),
                   (36, "teammate_area_effect"), (37, "enemy_area_effect")], got
    assert np.allclose(e[0, XY:RAD], [0.5, -0.2, 40 / 300, 0, 0.8]) and np.allclose(e[10, VEL:VEL + 2], [0, 200 / 300])
    assert e[:, 1:1 + len(ENT)].sum() == 13 and not o["ent"][1].any()
    # area columns: radius, harms / helps / slows me; an area of my team never harms me; the Piper bomb = its explosion
    assert np.allclose(e[32, RAD:RAD + 4], [0.15, 1, 0, 0]) and np.allclose(e[34, RAD:RAD + 4], [800 / 3000, 0, 1, 0]), (e[32, RAD:RAD + 4], e[34, RAD:RAD + 4])
    assert e[35, RAD] > 0 and e[35, RAD + 3] == 1 and np.allclose(e[36, RAD:RAD + 4], [0.15, 0, 0, 0]) and np.allclose(e[37, RAD:RAD + 4], [0.2, 1, 0, 0])
    assert not e[:32, RAD:RAD + 4].any() and lut[1:na, 0].mean() > 0.1 and lut[1:na, 1:].sum(0).min() > 50   # every kind occurs in the tables
    g = o["grid"][0]
    assert (g[12, 13], g[12, 14], g[5, 5], g[3, 3], g[12, 12]) == (_S("indestructible"), _S("bush"), _S("poison"),
                                                                 _S("out_of_bounds"), _S("floor"))
    assert (g[12, 15], g[12, 16], g[12, 17]) == (_S("destructible_wall"), _S("water"), _S("rope_fence"))
    assert (g[:2] == UNKNOWN).all() and (g[2] != UNKNOWN).all() and (g[19] != UNKNOWN).all() and (g[20:] == UNKNOWN).all()   # view -3090..+2330
    assert (g[2:20] != UNKNOWN).all()                          # +-12 tiles is inside the +-12.7 tile view mid-map
    g1 = o["grid"][1]                                          # x = 150: camera centred 10 tiles right, sees x > -800
    assert (g1[5, :9] == UNKNOWN).all() and (g1[5, 9:] != UNKNOWN).all()

    ids = np.array([16, 17])
    clean = ObsV5(noise=None).build(vec, grid, meta, ids)
    assert all(np.array_equal(clean[k], o[k]) for k in o)
    lat = ObsV5(noise={"jitter": (0, 0), "drop": (0, 0), "fp": (0, 0), "seg": (0, 0), "latency": (2, 2)})
    outs = []
    for t in range(5):
        v = vec.copy(); v[:, 0] = t / 10
        outs.append(lat.build(v, grid, meta, ids)["self"][0, 0])
    assert np.allclose(outs, [0, 0, 0, 0.1, 0.2]), outs       # 2 decisions late, the first frame repeated until then
    hi = {"jitter": (0.03, 0.03), "drop": (0.5, 0.5), "fp": (0.2, 0.2), "seg": (0.2, 0.2), "latency": (0, 0)}
    hud = hud_p(meta) > 0   # tiles the HUD can hide (measured); none under the player
    assert not hud_mask(meta).any() and not hud[0, 12, 12] and 0 < hud[0].sum() < 80, hud[0].sum()
    nz = ObsV5(noise=hi); kept = fps = flips = 0; d = []; on0 = False; back = vback = 0
    for t in range(300):
        n = nz.build(vec, grid, meta, ids)
        assert all(n[k].shape == o[k].shape and n[k].dtype == o[k].dtype for k in o) and n["grid"].max() <= UNKNOWN
        assert not ((n["grid"] == UNKNOWN) & (o["grid"] != UNKNOWN) & ~hud).any() and (n["grid"][o["grid"] == UNKNOWN] == UNKNOWN).all() and np.array_equal(n["self"], o["self"])
        ar = np.isin(n["ent"][..., 1:1 + len(ENT)].argmax(-1), _AREA_C) & (n["ent"][..., 0] > 0)   # radius only on area rows, >= 0
        assert (n["ent"][..., RAD] >= 0).all() and not n["ent"][~ar][:, RAD:RAD + 4].any() and (n["ent"][ar][:, RAD] > 0).mean() > 0.9
        on = n["ent"][0, :, 0] > 0; was = o["ent"][0, :, 0] > 0
        kept += (on & was).sum(); fps += (on & ~was).sum(); flips += (n["grid"] != o["grid"]).mean()
        if on[0]: d.append(n["ent"][0, 0, XY] - 0.5)
        back += on[0] and not on0; vback += on[0] and not on0 and n["ent"][0, 0, VEL:VEL + 2].any()
        on0 = on[0]
    assert back > 50 and vback <= 3, (back, vback)       # back after a drop: no velocity (rare: matched to a false positive)
    assert 0.4 < kept / (300 * 13) < 0.6 and 0.15 < fps / (300 * (N_ENT - 13)) < 0.25, (kept, fps)
    assert 0.1 < flips / 300 < 0.2 and 0.02 < np.std(d) < 0.04, (flips, np.std(d))
    dc = ObsV5(noise=dict(hi, jitter=(0, 0), drop=(0, 0), drop_cls=(2, 2), fp=(0, 0), seg=(0, 0)))   # per-class miss chance
    was = o["ent"][0, :, 0] > 0; pk = 1 - np.minimum(1, 2 * DROP_CLS[o["ent"][0, was, 1:1 + len(ENT)].argmax(-1)])
    kc = np.mean([(dc.build(vec, grid, meta, ids)["ent"][0, was, 0] > 0).mean() for _ in range(400)])
    assert abs(kc - pk.mean()) < 0.03, (kc, pk.mean())
    vj = ObsV5(noise=dict(hi, drop=(0, 0), fp=(0, 0), seg=(0, 0))); dv = []   # enemy 0: moves with the player (rel. 0)
    for t in range(300):
        e0 = vj.build(vec, grid, meta, ids)["ent"][0, 0]
        if t == 0: assert not e0[VEL:VEL + 2].any()       # first sight: no velocity
        elif e0[VEL:VEL + 2].any(): dv.append(e0[VEL:VEL + 2] - [40 / 300, 0])
    # differenced jitter is ~0.2-0.28 tiles / tick raw; smooth_vel (mean of <= 3 differences + EMA, HISTORY 77) cuts it
    # to ~0.07 (measured 0.069 / 0.078 on 2026-11-17; this bound was still the raw 0.17-0.26 after batch 1)
    sd = np.std(dv, 0)
    assert len(dv) > 250 and (0.05 < sd).all() and (sd < 0.10).all(), (len(dv), sd)
    ex = ObsV5(noise=dict(hi, jitter=(0, 0), drop=(0, 0), fp=(0, 0), seg=(0, 0))); ex.build(vec, grid, meta, ids)
    assert np.allclose(ex.build(vec, grid, meta, ids)["ent"][0, 0, VEL:VEL + 2], [40 / 300, 0])   # no jitter: exact
    many = ObsV5(); [many._episode(a) for a in range(5000)]
    assert len(many.ep) <= 4096 and 4999 in many.ep

    import env_v5
    hs = env_v5.heroes()
    st = np.stack([brawler_stats(h) for h in hs])
    assert st.shape == (len(hs), 13) and np.isfinite(st).all() and st.min() >= 0 and st.max() <= 2, (st.min(), st.max())
    assert np.allclose(brawler_stats("ShotgunGirl")[[0, 1, 3, 6, 7, 8]], [23 / 30, 0.77, 3100 / 4000, 0, 0, 0.39])
    assert brawler_stats("Barkeep")[6] == 1 and brawler_stats("Undertaker")[7] == 1
    c = cond("Sniper", np.ones(len(SLIDERS)), 3)
    assert c.shape == (N_COND,) and c[25] == 1 and c[23] == 0 and c[26] == 0 and abs(c[27] - 0.4) < 1e-6
    assert np.allclose(cond("Sniper", np.ones(len(SLIDERS)), 1, cubes=3, left=7)[26:28], [0.3, 0.7])
    w = np.arange(len(SLIDERS), dtype=np.float32) / 10; c = cond("Sniper", w, 2)
    assert np.allclose(c[COND_SLIDERS], w) and N_COND == 37 and N_COND_V510 == 30 and len(COND_SLIDERS) == len(SLIDERS) and np.allclose(c[:13], brawler_stats("Sniper"))
    assert c[:N_COND_V53].shape == (28,) and np.allclose(c[13:23], w[:10]) and c[24] == 1   # the v5.3 layout is the first 28
    assert np.array_equal(c[COND_CLS], brawler_class("Sniper")) and c[COND_CLS].sum() == 1 and c[COND_CLS][CLASSES.index("marksman")] == 1
    assert set(PRESETS) >= {"balanced", "bush_camper", "aggressive", "cube_farmer"} and all(set(v) <= set(SLIDERS) for v in PRESETS.values())
    pv = np.stack([preset_vec(k) for k in PRESETS])
    assert pv.shape == (len(PRESETS), len(SLIDERS)) and pv.min() >= 0 and pv.max() <= 2 and (preset_vec("balanced") == 1).all()
    assert preset_vec("bush_camper")[SLIDERS.index("bush_camp")] == 2 and len({tuple(r) for r in pv}) == len(PRESETS)
    assert N_INT == 13 and len(INTENTS) == 10 and INTENTS[0] == "none" and N_S == N_SELF + N_COND + N_INT == 58 and S_INT == 45
    assert (I_XY, I_RAD, I_LEFT) == (9, 11, 12) and OBS_VERSION == "v5.11" and N_INT_V59 == 11 and INTENTS[8:] == ("super", "check_bush")
    assert (F_ENT_V55, ID0, ID_KNOWN, LOS, F_ENT_V59, CUB, F_ENT_V510, CLS, F_ENT) == (20, 20, 33, 34, 36, 36, 38, 38, 45)
    _check_id(vec, grid, meta)
    _check_cubes(vec, grid, meta)
    print("obs_v5 ok (%s): %d brawlers, %d thrown, %d melee, cond %d, intent %d, s %d, ent %dx%d" % (
        OBS_VERSION, len(hs), st[:, 6].sum(), st[:, 7].sum(), N_COND, N_INT, N_S, N_ENT, F_ENT))


def _check_id(vec, grid, meta):
    """v5.6 identity + line of sight: true stats + known 1 when given, zeros + 0 when not, fixed per battle under noise,
    wrong picks never the truth, projectile links per decision; wall_between / water_between on a synthetic grid"""
    names, lut = id_lut(); nh = len(names)
    assert lut.shape == (nh + 1, 13) and not lut[-1].any() and id_row("ShotgunGirl") == 0 and id_row("Boss") == -1
    assert id_row_of_data(D.table("characters.csv")["Sniper"][0]) == id_row("Sniper") and id_row_of_data(16000120) == -1
    who = np.full((2, N_ENT, 3), -1, np.int16)
    who[0, 0] = [3, id_row("Sniper"), WHO_FOE]; who[0, 1] = [5, id_row("BullDude"), WHO_MATE]
    who[0, 9] = [0, id_row("ShotgunGirl"), WHO_ME]; who[0, 10] = [3, id_row("Sniper"), WHO_FOE]   # own / enemy projectile
    o = from_state2(vec, grid, meta, who); e = o["ent"][0]
    for k, n in ((0, "Sniper"), (1, "BullDude"), (9, "ShotgunGirl"), (10, "Sniper")):
        assert np.array_equal(e[k, ID0:ID0 + 13], brawler_stats(n)) and e[k, ID_KNOWN] == 1, k
        assert np.array_equal(e[k, CLS:F_ENT], brawler_class(n)) and e[k, CLS:F_ENT].sum() == 1, k   # v5.11: its class
    assert not e[2:9, ID0:ID0 + N_ID].any() and not e[11:, ID0:ID0 + N_ID].any() and not o["ent"][1, :, ID0:].any()   # summons, boxes, areas: 0
    assert not from_state2(vec, grid, meta)["ent"][..., ID0:ID0 + N_ID].any()                  # who None: every identity unknown
    assert not e[2:9, CLS:].any() and not e[11:, CLS:].any() and not from_state2(vec, grid, meta)["ent"][..., CLS:].any()   # no identity: no class
    assert cls_lut().shape == (nh + 1, len(CLASSES)) and not cls_lut()[-1].any() and (cls_lut()[:-1].sum(1) == 1).all()
    # line of sight: me at cell (12, 12); a wall 2 tiles right, water 3 tiles down, nothing up-left
    g = np.zeros((1, G, G), np.uint8); g[0, 12, 14] = _S("indestructible"); g[0, 15, 12] = _S("water"); g[0, 9, 9] = _S("rope_fence")
    en = np.zeros((1, N_ENT, F_ENT), np.float32); en[0, :6, 0] = 1
    for k, c, xy in ((0, "enemy", (0.5, 0)), (1, "teammate", (0, 0.5)), (2, "enemy", (0.5, -0.5)), (3, "enemy", (0.2, 0)),
                     (4, "power_box", (0.5, 0)), (5, "enemy", (-0.55, -0.55))):
        en[0, k, 1 + _E(c)] = 1; en[0, k, XY:XY + 2] = xy
    L = los(en, g)[0]                                     # 5 right: wall on the line; 5 down: water only; up-right: clear;
    assert L[:6].tolist() == [[1, 0], [0, 1], [0, 0], [0, 0], [0, 0], [0, 1]], L[:6]   # 2 right = on the wall: own tile left out;
    g2 = g.copy(); g2[0, 12, 14] = _S("bush"); g2[0, 12, 13] = UNKNOWN                   # a box: no line; a rope fence up-left
    assert not los(en, g2)[0, 0].any() and los(en, g2)[0, 1, 1] == 1 and _BLOCK_PJ[[_S("destructible_wall"), _S("fragile_wall"), _S("bouncer")]].all()
    assert not _BLOCK_PJ[[_S("water"), _S("rope_fence"), _S("bush"), UNKNOWN]].any() and _BLOCK_MV.sum() == 2
    assert np.array_equal(o["ent"][..., LOS:LOS + 2], los(o["ent"], o["grid"])) and o["ent"][0, 0, LOS] == 1   # enemy 0: the Indestructible at 12, 13
    # noisy: per battle fixed identity, per decision projectile links
    q0 = {k: (0.0, 0.0) for k in NOISE if not k.startswith(("id_", "pj_"))}; q0["latency"] = (0, 0)
    nz = dict(q0, id_known=(0.5, 0.5), id_known_mate=(0.9, 0.9), id_wrong=(1, 1), pj_owner_known=(0.5, 0.5))
    W = np.full((1, N_ENT, 3), -1, np.int16); v1, g1, m1 = vec[:1], grid[:1], meta[:1]
    W[0, 0] = [3, id_row("Sniper"), WHO_FOE]; W[0, 1] = [5, id_row("BullDude"), WHO_MATE]; W[0, 10] = [3, id_row("Sniper"), WHO_FOE]
    W[0, 9] = [0, id_row("ShotgunGirl"), WHO_ME]
    ob = ObsV5(noise=nz, seed=4); kn = {0: [], 1: [], 9: [], 10: []}; st0 = set(); per = []
    for aid in range(16, 16 + 16 * 400, 16):              # 400 battles of agent 0, 6 decisions each
        ks = []
        for t in range(6):
            e = ob.build(v1, g1, m1, [aid], who=W)["ent"][0]; ks.append([e[k, ID_KNOWN] for k in kn])
            if e[0, ID_KNOWN]: st0.add((aid, e[0, ID0:ID0 + 13].tobytes()))
            if e[1, ID_KNOWN]: assert np.array_equal(e[1, ID0:ID0 + 13], brawler_stats("BullDude"))   # mates: never wrong
            if e[0, ID_KNOWN]: assert not np.array_equal(e[0, ID0:ID0 + 13], brawler_stats("Sniper"))  # id_wrong 1: never the truth
            for k in np.flatnonzero(e[:, ID_KNOWN] > 0.5):                       # the class is the given brawler's (wrong or not)
                r_ = int(((lut[:-1] - e[k, ID0:ID0 + 13]) ** 2).sum(1).argmin()); assert np.array_equal(e[k, CLS:F_ENT], cls_lut()[r_]), k
            assert not e[e[:, ID_KNOWN] < 0.5, CLS:].any()
            assert e[9, ID_KNOWN] == 1 and np.array_equal(e[9, ID0:ID0 + 13], brawler_stats("ShotgunGirl"))   # mine: always
            assert e[10, ID_KNOWN] <= e[0, ID_KNOWN] and (not e[10, ID_KNOWN] or np.array_equal(e[10, ID0:ID0 + 13], e[0, ID0:ID0 + 13]))
            assert not e[[2, 3, 25, 31], ID0:ID0 + N_ID].any()
        ks = np.array(ks); per.append(ks)
        assert (ks[:, :3] == ks[:1, :3]).all()            # players: fixed for the battle
    per = np.array(per)
    assert len({a for a, _ in st0}) == len(st0) and 0.44 < per[:, 0, 0].mean() < 0.56 and 0.85 < per[:, 0, 1].mean() < 0.95, per[:, 0, :2].mean(0)
    pjv = per[per[:, 0, 0] > 0][:, :, 3]
    assert 0.42 < pjv.mean() < 0.58 and (pjv.min(1) != pjv.max(1)).mean() > 0.8, pjv.mean()   # links: per decision
    assert not ObsV5(noise=nz).build(v1, g1, m1, [16])["ent"][..., ID0:ID0 + N_ID].any()
    perfect = ObsV5(noise=q0, seed=1).build(v1, g1, m1, [16], who=W)["ent"][0]                # no id_* keys: identity perfect
    assert np.array_equal(perfect[:, ID0:ID0 + N_ID], from_state2(v1, g1, m1, W)["ent"][0, :, ID0:ID0 + N_ID])


def _check_cubes(vec, grid, meta):
    """v5.10 power cubes: held / 10 (clip 2) + known on enemy / teammate player rows with an owner, 0 elsewhere and for a
    3-column who; noisy: read or never read per player for the battle, +-1 misreads per decision (never below 0)"""
    W = np.full((1, N_ENT, 4), -1, np.int16); v1, g1, m1 = vec[:1], grid[:1], meta[:1]
    W[0, 0] = [3, id_row("Sniper"), WHO_FOE, 7]; W[0, 1] = [5, id_row("BullDude"), WHO_MATE, 25]
    W[0, 2] = [4, -1, WHO_FOE, 3]; W[0, 10] = [3, id_row("Sniper"), WHO_FOE, 7]   # a summon row, a projectile row: no count
    e = from_state2(v1, g1, m1, W)["ent"][0]
    assert np.allclose(e[:3, CUB:CUB + 2], [[0.7, 1], [2.0, 1], [0, 0]]) and not e[3:, CUB:CUB + 2].any(), e[:4, CUB:CUB + 2]
    assert np.array_equal(e[:, :CUB], from_state2(v1, g1, m1, W[..., :3])["ent"][0, :, :CUB])   # nothing else changes
    assert not from_state2(v1, g1, m1, W[..., :3])["ent"][..., CUB:CUB + 2].any() and not from_state2(v1, g1, m1)["ent"][..., CUB:CUB + 2].any()
    q0 = {k: (0.0, 0.0) for k in NOISE if not k.startswith(("id_", "pj_", "cube_"))}; q0["latency"] = (0, 0)
    perfect = ObsV5(noise=q0, seed=1).build(v1, g1, m1, [16], who=W)["ent"][0]                # no cube_* keys: counts perfect
    assert np.array_equal(perfect[:, CUB:CUB + 2], e[:, CUB:CUB + 2])
    ob = ObsV5(noise=dict(q0, cube_known=(0.5, 0.5), cube_misread=(0.5, 0.5)), seed=5); kn, mis = [], []
    for aid in range(16, 16 + 16 * 400, 16):              # 400 battles of agent 0, 6 decisions each
        ks = []
        for t in range(6):
            o = ob.build(v1, g1, m1, [aid], who=W)["ent"][0]; ks.append(o[:2, CUB + 1].copy())
            assert not o[2:, CUB:CUB + 2].any()
            if o[0, CUB + 1]: assert np.round(o[0, CUB] * 10) in (6, 7, 8); mis.append(np.round(o[0, CUB] * 10) != 7)
            if o[1, CUB + 1]: assert np.round(o[1, CUB] * 10) in (19, 20)           # 25 +-1 still clips at 20
        ks = np.array(ks); assert (ks == ks[:1]).all(); kn.append(ks[0])            # read or not: fixed for the battle
    kn = np.array(kn)
    assert 0.44 < kn[:, 0].mean() < 0.56 and 0.44 < kn[:, 1].mean() < 0.56 and 0.44 < np.mean(mis) < 0.56, (kn.mean(0), np.mean(mis))
    z = np.zeros((1, N_ENT), np.int64); z[0, 0] = 0; W0 = W.copy(); W0[0, 0, 3] = 0
    o = ObsV5(noise=dict(q0, cube_known=(1, 1), cube_misread=(1, 1)), seed=2).build(v1, g1, m1, [16], who=W0)["ent"][0]
    assert o[0, CUB + 1] == 1 and o[0, CUB] in (0.0, np.float32(0.1))   # 0 - 1 stays 0


def _live(decisions=300):
    import collections, time, env_v5
    env = env_v5.Env(1, env_v5.make_battle_fn(10, p_team=1.0), ticks=2, fair=True, max_ticks=4000)
    ob, rng, n, seen, t = ObsV5(noise=None), np.random.default_rng(0), 0, collections.Counter(), 0.0   # clean: a real class census
    try:
        while n < decisions:
            obs, ids, _ = env.poll(min_ready=1, max_wait=0.003)
            if not len(ids): continue
            if not n:                                     # the host's teams (player +0xc) = the requested groups
                s = env.I[0]; gr = s.cfg["tag"]["groups"]; tm = [s.inst.resp.pl[p].reserved[2] for p in range(10)]
                same = [[tm[a] == tm[b] for b in range(10)] for a in range(10)]
                want = [[a == b or (gr[a] and gr[a] == gr[b]) for b in range(10)] for a in range(10)]
                assert same == want, (gr, tm)
                print("teams ok: groups %s -> teams %s" % (gr, tm), flush=True)
            t0 = time.perf_counter(); o = ob.build(obs["vec"], obs["grid"], env.last_meta, ids, who=env.last_who); t += time.perf_counter() - t0
            _live_who(env, obs["vec"], ids, o, seen)
            assert all(np.isfinite(v).all() for v in o.values()) and o["self"][:, :2].max() <= 1.0, o["self"].max(0)
            assert np.abs(o["ent"][..., XY:XY + 2]).max() < 2.0 and o["grid"].max() <= UNKNOWN
            for c in o["ent"][..., 1:1 + len(ENT)].sum((0, 1)).nonzero()[0]: seen[ENT[c]] += 1
            for c in np.unique(o["grid"]): seen["seg:" + (SEG + ("unknown",))[c]] += 1
            n += len(ids)
            env.send(ids, np.stack([rng.integers(0, 17, len(ids)), rng.integers(0, 3, len(ids)),
                                    rng.integers(0, 360, len(ids)), rng.integers(0, 8, len(ids))], 1))
    finally:
        env.close()
    print("live ok: %d decisions, %.0f us per decision, polls with class: %s" % (n, t / n * 1e6, {k: v for k, v in seen.items() if not k.startswith("id:")}))
    idc = {k[3:]: v for k, v in seen.items() if k.startswith("id:")}; print("identity / line of sight:", idc)
    assert idc.get("player_rows", 0) > 100 and idc.get("player_owned", 0) == idc["player_rows"] and not idc.get("bad", 0), idc
    assert idc.get("pj_rows", 0) > 100 and idc.get("pj_owned", 0) >= 0.98 * idc["pj_rows"] and idc.get("summon_owned", 0) == 0 and idc.get("other_owned", 0) == 0, idc


def _live_who(env, vec, ids, o, c):
    """--live: Env.last_who against the true state: every brawler row of the enemy block has its owner, on the side its
    feature 15 says, at the owner's true position, with the tag's brawler; summons none; projectiles their owner (own =
    feature 5); the clean identity columns = the owner's stats"""
    w = env.last_who; B = len(ids); en = vec[:, F.EN0:F.EN0 + F.EN_K * F.EN_F].reshape(B, F.EN_K, F.EN_F)
    pj = vec[:, F.PJ0:F.PJ0 + F.PJ_K * F.PJ_F].reshape(B, F.PJ_K, F.PJ_F); by = {s.battle: s for s in env.I}
    for b, a in enumerate(ids):
        s = by[int(a) >> 4]; p = int(a) & 15; r = s.inst.resp; chr_ = s.cfg["tag"]["chr"]
        for k in np.flatnonzero(en[b, :, 0] > 0.5):
            q, h, sd = (int(x) for x in w[b, k])
            if en[b, k, 14] > 0.5: c["id:summon_rows"] += 1; c["id:summon_owned"] += q >= 0; continue
            c["id:player_rows"] += 1; c["id:player_owned"] += q >= 0
            if q < 0: continue
            pos = np.hypot(r.pl[p].x + en[b, k, 1] * F.R - r.pl[q].x, r.pl[p].y + en[b, k, 2] * F.R - r.pl[q].y)
            c["id:bad"] += int(sd != (WHO_MATE if en[b, k, 15] > 0.5 else WHO_FOE) or h != id_row(chr_[q]) or pos > 1.0 or q == p)
            c["id:bad"] += int(not np.array_equal(o["ent"][b, k, ID0:ID0 + 13], id_lut()[1][h]) or o["ent"][b, k, ID_KNOWN] != 1)
            c["id:wall_between"] += int(o["ent"][b, k, LOS]); c["id:water_between"] += int(o["ent"][b, k, LOS + 1])
        for k in np.flatnonzero(pj[b, :, 0] > 0.5):
            q, sd = int(w[b, F.EN_K + k, 0]), int(w[b, F.EN_K + k, 2]); c["id:pj_rows"] += 1; c["id:pj_owned"] += q >= 0
            if q >= 0: c["id:bad"] += int((sd == WHO_ME) != (pj[b, k, 5] > 0.5)); c["id:pj_mate"] += sd == WHO_MATE
        c["id:other_owned"] += int((w[b, F.EN_K + F.PJ_K:, 0] >= 0).sum())


if __name__ == "__main__":
    _check()
    if "--live" in sys.argv: _live()
