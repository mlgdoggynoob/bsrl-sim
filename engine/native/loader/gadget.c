/* gadget round (bsrl-sim issue #3): the host's own gadget activation.
 *
 * The shipped libg v68.279 is a client build: the gadget activation that input kind 8 reaches (NbeAction.fire 3 -> env.c
 * gadget_input -> 0xc2cef4 -> 0xb27c58(player+0x190, char, x, y, 0)) is a bare ret, and with it the server's bookkeeping of
 * uses and cooldown. Here the host keeps that state per player for the battle and runs a re-implemented activation per
 * gadget kind (NBE_GAD_*), the way spawnfix.c re-implements the compiled-out children of explosions with libg's own functions.
 * The state goes to Python in NbeResp gad_* (every response); bsrl-sim's env_v5.Env.gadget turns it into obs_v5 self 3.
 *
 * What the game gives the host: every player with a gadget card has an accessory object at player+0x190 (0xe0 B, built by
 * 0xb2731c(acc, AccessoryData, player)): +0x10 its AccessoryData (accessories.csv row), +0x24 the type enum the constructor
 * parses from the Type column (2 dash, 8 heal, ...), +0xc4 the cooldown in ticks (the row's Cooldown, scaled by gear).
 * AccessoryData columns are read with libg's own getters (SubType 0xa93258, ActiveTicks 0xa932c8, CustomValue1/2
 * 0xa933d0 / 0xa933e0).
 *
 * Implemented kinds (RE-IMPLEMENTED, not the game's server code, which is compiled out):
 *   DASH  type 2 (the 7 dash rows: Cannon Girl, Maisie, Twins, Crab, Digger, Lightyear, Skater): the brawler moves
 *         CustomValue1 units (600..1300) along the aim at CustomValue2 u/s (2000..3500) with the native charge mover
 *         (env.c env_dash_start). Movement only: a row's extras (Maisie's damage area, Skater's taunt, CustomValue3/4) are
 *         not applied, and the "requires ..." conditions (MissingTargetText) are not checked.
 *   HEAL  type 8, SubType 2 (Bibi's Vitamin Booster, Byron's Shot in the Arm): heals CustomValue1 % of max hp per second
 *         (the card texts say "per second for N seconds") for ActiveTicks ticks, at most up to max hp, ended by the
 *         brawler's death. Byron's ammo cost (ConsumesAmmo) is not applied. The other heal SubTypes need state the host
 *         does not have (Ash's rage, Meg's mech, Sandy's sleep, area heals) and stay unimplemented.
 *   AREA  empty Type (+0x24 == 0) with an AreaEffect (AccessoryData +0x70, resolved by createReferences at 0xa92568): the
 *         gadgets that only drop their area at the brawler (Barley's Slow, Poco's Regen and Cleanse, Tick's Explosion,
 *         Shade's Spooky, Trunk's Area). Left out: Rosa's GrowBush (a WallSpawn area: spawnfix.c's wall ring would put
 *         walls where she grows bushes). Meeple's RageQuit (HpBasedStun) stuns and knocks back through superfix_cc.c (issues #19, #55);
 *         the spin_shoot rows without a projectile (Fang's KickerDude_Sweep, a LineOfSight stun area, and Painter_Push) are
 *         AREA too (their spin animation is the client's). Published
 *         as kind SPAWN; `python -m super_audit --gadget` checks each one's effects. The area is spawned
 *         at the brawler with the shipped helper 0xb35c40 (create 0xb2aefc, world add 0xb63198, start 0xb29494, the chain
 *         superfix.c's spawnAreaEffect uses), kind 2 and no extra damage, as at every shipped caller: the area's damage,
 *         heal, status and wall spawn then come from libg and the earlier rounds (superfix, spawnfix). ActivationDelay
 *         ticks (Tick: 20) are waited out first, and the area is placed where the brawler is then. A row's ShieldPercent
 *         for ShieldTicks (Tick: 50 % for 21) starts at the fire (superfix_status_shield, issue #55).
 *   SHOT  empty Type, no AreaEffect, a Skill whose BehaviorType is Attack with Projectiles (32 rows: Spike, Colt x2, Brock,
 *         Shelly, Emz x2, ...; published PROJECTILE): NumBulletsInOneAttack of the skill's first projectile over Spread degrees
 *         centred on the aim, to CastingRange, with the skill's Damage scaled by the brawler's damage percent (0xb4b660, as the
 *         attack path scales it), spawned with the projectile spawn 0xb78190 (spawnfix.c) at kind 4. What the projectile
 *         does on hit or at its end (areas, items, summons, pull / push) is libg's and the earlier rounds'. A projectile
 *         row with DamageOnlyWithOneProj (Emz's spray) damages each target with one projectile of the volley only, through
 *         the attack path's sibling list (volley). The skill's timing (ActiveTime, MsBetweenAttacks waves) is not read:
 *         g_waves lists the cards whose description names more waves (Colt's Gunslinger_Reload: two shots, issue #55).
 *         Not applied: TwoGuns, AttackPattern.
 *   SKILL AREA  the same, but the skill has no projectile, only an AreaEffectObject (published SPAWN): Bull's Stomp (Attack:
 *         at the brawler), 8-Bit's Extra Credits (AimableArea: at the aim point at CastingRange).
 *   AUTO AIMER  Piper's Sniper_HandGun (repeat_shot; card 23000268 only; published PROJECTILE): one CustomObject projectile
 *         (PiperHandgunProjectile) at the nearest living enemy brawler (another team) within the row's Range (tiles, 300 u
 *         each), whatever the aim, flying to that range, with the main attack's Damage x CustomValue1 % scaled as SHOT scales
 *         it. No enemy in range: refused (RequireEnemyInRange; no use, no cooldown). The push on hit is the projectile's own
 *         PushbackStrength, applied by libg's projectile hit (0xb7816c -> knockback 0xb49834). Not applied: ActiveTicks (5)
 *         and CustomValue2 (5).
 *   ITEM  spawn rows whose CustomObject is an items.csv row (Belle's trap, Gale's Twister; SPAWN): the item at the brawler
 *         through the item factory 0xb55684, with the main attack's Damage x CustomValue1 % as its damage; Gale's WindWall
 *         also gets env's repel zone (env_repel_zone), which this libg lacks.
 *   SUPER charge_ulti (R-T; published SUPER): the super charge to CustomValue1 % of its maximum.
 *   HEAL_NOW  heal_attached_and_self (Kit) and heal_damage_taken (Kenji) (HEAL): an instant heal through libg's heal 0xb41554.
 *   REPEAT  repeat_shot and spin_shoot rows with a CustomObject projectile other than Piper's Auto Aimer (published PROJECTILE;
 *         issue #54 redo from the game data, see the REPEAT / SPIN block): Dynamike (spin), Gene, Mico, Barley's potion
 *         (repeat). Darryl, Fang's popcorn, Bea and Amber run the same code but stay in g_masked: no hit seen live.
 * Every other gadget publishes kind NONE (not usable): next_attack_change, summons / turrets, status buffs, shields, Nori's
 * fish heal (needs his fish count), the Charge skills (Brock's jump, Max's dash, ...), ... Each player gets GAD_USES uses per battle (unlimited by default, as in the live game since February 2025) and
 * the accessory's cooldown between uses. The accessory's Type parses to the int at +0x24 (0xb2731c:
 * spin_shoot 3, spawn 9, repeat_shot 13, heal_attached_and_self 50, charge_ulti 56, heal_damage_taken 58).
 *
 * To add a kind: write classify (accessory -> 1 if this implementation handles it) and fire (the effect at the brawler, with
 * libg's own functions where they exist), add the entry to g_impl, then run `python -m gadget_check` (bsrl-sim) on the built
 * host: it fires each published kind and asserts that a use was spent and that the kind's effect happened. */
#include "nbhost.h"
#include "nbenv_proto.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

#define I32(p, o) (*(volatile int32_t *)((uint8_t *)(p) + (o)))
#define PTR(p, o) (*(void *volatile *)((uint8_t *)(p) + (o)))
#define U8(p, o) (*(volatile uint8_t *)((uint8_t *)(p) + (o)))
#define B(off) ((uint8_t *)g_libg->base + (off))
extern Module *g_libg;
extern int32_t g_div_gadget[NBE_MAXP];   /* env.c: the RESET's requested gadget cards (offline.c puts them in the configs) */
void *env_obj_by_id(void *sim, int id);  /* env.c */
int env_dash_start(uint8_t *ch, int tx, int ty, int speed);   /* env.c: -> path length, 0 = no dash */

#define GAD_USES 9999     /* no per-battle limit: gadgets "no longer have charges but are now based on cooldowns" and can be
                           * used "an unlimited amount of times in a match" (Supercell release notes, Feb 2025); the
                           * cooldown is the accessory's (accessories.csv Cooldown, e.g. Bibi 400 ticks = the 20 s of the
                           * Feb 2026 notes). NB_GAD_USES=3 restores the old 3 uses per battle (issue #22). */
#define REP_MAX 20        /* REPEAT / SPIN: shots per use at most (Gene 100 / 5) */
#define TICKS_PER_S 20    /* 50 ms ticks */
enum { ACC_PLAIN = 0, ACC_DASH = 2, ACC_SPIN = 3, ACC_HEAL = 8, ACC_SPAWN = 9, ACC_REPEAT = 13, ACC_HEAL_SELF = 50,
       ACC_CHARGE_ULTI = 56, ACC_HEAL_TAKEN = 58 };   /* the `mov w8, #N` per Type string in 0xb2731c (spin_shoot 3, ...) */   /* accessory +0x24 type enum (0xb2731c's Type parser; 0 = empty Type) */

typedef int (*AdGet)(void *ad);
static int ad_get(void *ad, uint64_t getter) { return ((AdGet)B(getter))(ad); }
#define AD_SUBTYPE 0xa93258
#define AD_ACTIVE_TICKS 0xa932c8
#define AD_CV1 0xa933d0
#define AD_CV2 0xa933e0
#define AD_ACT_DELAY 0xa932b8   /* ActivationDelay (column index at 0x123f000+1952, the getters' pattern) */
#define AD_AREA 0x70            /* AccessoryData +0x70: AreaEffect -> AreaEffectData (0xa92568 stores it) */
#define AD_SHIELD_PCT 0xa93368  /* ShieldPercent (column index at 0x123f000+0x7fc, the getters' pattern; issue #55) */
#define AD_SHIELD_TICKS 0xa93378 /* ShieldTicks (+0x800) */
void superfix_status_shield(uint8_t *ch, int pct, int ticks) __attribute__((weak));

typedef struct Gad Gad;
typedef struct {
    int kind;                                                                     /* NBE_GAD_* */
    int (*classify)(void *ad, int type);                                          /* 1 = handles this accessory */
    int (*fire)(void *sim, Gad *g, uint8_t *ch, double deg, int tick);           /* 1 = activated (a use is spent) */
} GadImpl;
struct Gad {
    int pid, type, card, uses, cd, cd_until, used; void *ad; const GadImpl *im;
    int hot_id, hot_start, hot_end, hot_total, hot_done;   /* heal over time: char id, ticks, hp to give, hp given */
    int area_id, area_at;                                  /* area: char id, tick to spawn at (0 = none pending) */
    void *area_data; int area_x, area_y, area_here;        /* the area to spawn (NULL = the accessory's AreaEffect) and where
                                                            * (area_here 1 = at the brawler when it spawns, 0 = area_x / y) */
    int rep_id, rep_n, rep_i, rep_next, rep_gap, rep_dmg, rep_rng, rep_cnt, rep_tgt[REP_MAX];   /* REPEAT / SPIN: char id,
                                                            * shots, next shot, its tick, ticks between, damage, range,
                                                            * projectiles per shot, target char per shot (0 = by angle) */
    double rep_ang, rep_spread;                            /* first shot's angle, a shot's spread */
    int burst_id, burst_left, burst_next, burst_gap, burst_deg;   /* SHOT waves after the first (g_waves): char id, volleys
                                                                   * still to fire, next tick, ticks between, angle */
    double dist;                                           /* the fire's super_dist (0, 1] (0 = full range): thrown shots
                                                            * and AimableArea areas land this share of CastingRange out */
    int hp_prev, hp_lost[100];                        /* damage taken per tick (ring by tick % 100), for HEAL_TAKEN */
};
static Gad g_gad[NBE_MAXP]; static int g_rep_log;
static long g_fired[8], g_areas, g_areas_lost;

/* ---- DASH */
static int dash_classify(void *ad, int type) { return type == ACC_DASH && ad_get(ad, AD_CV1) > 0 && ad_get(ad, AD_CV2) > 0; }
static int dash_fire(void *sim, Gad *g, uint8_t *ch, double deg, int tick) {
    (void)sim; (void)tick;
    int dist = ad_get(g->ad, AD_CV1), spd = ad_get(g->ad, AD_CV2), X = I32(ch, 0x38), Y = I32(ch, 0x3c);
    double r = deg * M_PI / 180;
    return env_dash_start(ch, (int)floor(X + dist * cos(r) + 0.5), (int)floor(Y + dist * sin(r) + 0.5), spd) > 0;
}

/* ---- HEAL (over time) */
static int heal_classify(void *ad, int type) {
    return type == ACC_HEAL && ad_get(ad, AD_SUBTYPE) == 2 && ad_get(ad, AD_CV1) > 0 && ad_get(ad, AD_ACTIVE_TICKS) > 0;
}
static int heal_fire(void *sim, Gad *g, uint8_t *ch, double deg, int tick) {
    (void)sim; (void)deg;
    int dur = ad_get(g->ad, AD_ACTIVE_TICKS), maxhp = I32(ch, 0x3c8);
    if (I32(ch, 0x3c4) <= 0 || maxhp <= 0) return 0;
    g->hot_id = I32(ch, 8); g->hot_start = tick; g->hot_end = tick + dur; g->hot_done = 0;
    g->hot_total = (int)floor((double)maxhp * ad_get(g->ad, AD_CV1) / 100.0 * dur / TICKS_PER_S + 0.5);
    return 1;
}
static void heal_tick(void *sim, Gad *g, int tick) {
    uint8_t *ch = env_obj_by_id(sim, g->hot_id);
    if (!ch || I32(ch, 0x3c4) <= 0 || tick <= g->hot_start) { if (!ch || I32(ch, 0x3c4) <= 0) g->hot_end = 0; return; }
    int t = tick < g->hot_end ? tick : g->hot_end, dur = g->hot_end - g->hot_start;
    int due = (int)floor((double)g->hot_total * (t - g->hot_start) / dur + 0.5), d = due - g->hot_done;   /* spread evenly */
    g->hot_done = due;
    int hp = I32(ch, 0x3c4), mx = I32(ch, 0x3c8);
    if (d > 0 && hp < mx) I32(ch, 0x3c4) = hp + d < mx ? hp + d : mx;
    if (tick >= g->hot_end) g->hot_end = 0;
}

/* ---- AREA (at the brawler) */
#define AREA_WALLSPAWN 15   /* AreaEffectData +0x118 type: spawnfix.c's wall ring would build walls (Sprout / Wally tiles),
                             * not Rosa's bushes: left out until a bush ring exists */
static void *custom_proj(void *ad);
static int area_classify(void *ad, int type) {   /* issue #19 final: also spin_shoot rows with an area and no projectile */
    void *a = type == ACC_PLAIN || (type == ACC_SPIN && !custom_proj(ad)) ? PTR(ad, AD_AREA) : NULL;
    return a && I32(a, 0x118) != AREA_WALLSPAWN;
}
static void area_spawn(void *sim, Gad *g) {
    uint8_t *ch = env_obj_by_id(sim, g->area_id); g->area_at = 0;
    if (!ch || I32(ch, 0x3c4) <= 0 || !PTR(ch, 0x20)) { g_areas_lost++; return; }   /* died during the delay: nothing */
    void *d = g->area_data ? g->area_data : PTR(g->ad, AD_AREA);
    int x = g->area_here ? I32(ch, 0x38) : g->area_x, y = g->area_here ? I32(ch, 0x3c) : g->area_y;
    void *a = ((void *(*)(void *, void *, int, int, int, int, void *))B(0xb35c40))(ch, d, x, y, 0, 2, NULL);
    if (a) g_areas++; else g_areas_lost++;
    if (g_areas + g_areas_lost <= 10) LOG("[gadget] area %p (data type %d) at %d,%d\n", a, I32(d, 0x118), x, y);
}
static int area_fire(void *sim, Gad *g, uint8_t *ch, double deg, int tick) {
    (void)deg;
    if (I32(ch, 0x3c4) <= 0 || g->area_at) return 0;
    int delay = ad_get(g->ad, AD_ACT_DELAY);
    g->area_id = I32(ch, 8); g->area_at = tick + (delay > 0 ? delay : 0); g->area_data = NULL; g->area_here = 1;
    /* the row's own shield over the delay (Tick: 50 % for 21 ticks, then the burst at 20; issue #55) */
    int sp = ad_get(g->ad, AD_SHIELD_PCT), st = ad_get(g->ad, AD_SHIELD_TICKS);
    if (sp > 0 && st > 0 && superfix_status_shield) superfix_status_shield(ch, sp, st);
    if (delay <= 0) area_spawn(sim, g);
    return 1;
}

/* ---- helpers for the kinds below */
static uint8_t *player_of(void *sim, int i) {   /* sim +0x70 players, +0x7c count (env.c players()) */
    int np = I32(sim, 0x7c); void **ps = PTR(sim, 0x70);
    return ps && i >= 0 && i < np && np <= 64 ? ps[i] : NULL;
}
static uint8_t *char_of(void *sim, int i) {     /* the player's brawler (env.c player_char_id: +0x1e4, else +0x10) */
    uint8_t *p = player_of(sim, i); if (!p) return NULL;
    int id = I32(p, 0x1e4) ? I32(p, 0x1e4) : I32(p, 0x10);
    return env_obj_by_id(sim, id);
}
static int sd_get(void *sd, uint64_t getter) { return ((AdGet)B(getter))(sd); }
#define SD_DAMAGE 0xb0dc14
#define SD_SPREAD 0xb0dc6c
#define SD_NBULLETS 0xb0dd0c
#define SD_RANGE 0xb0d948      /* CastingRange, tiles x 100 */
#define SD_FOLLOW 0xc0         /* SkillData +0xc0: AreaEffectFollowType (1 "follow": the area at the brawler; set at 0xb0bafc) */
#define SD_COOLDOWN 0xb0d868
#define SD_PROJ 0x58           /* SkillData +0x58 ProjectileData* array, +0x64 its size (createReferences, getter 0xb0dbb0) */
#define SD_AREA 0xa0           /* SkillData +0xa0 AreaEffectObject (AreaEffectData*) */
#define SD_BEHAVIOR 0x1a8      /* BehaviorType enum (superfix_moves.c) */
#define BT_ATTACK 0         /* the parser 0xb0b53c..0xb0b980: Attack 0, Charge 2, AimableArea 28 */
#define BT_AIM_AREA 28
#define AD_SKILL 0x80          /* AccessoryData +0x80: Skill -> SkillData* (createReferences 0xa92474, lookup 0xad2b7c) */
#define AD_CUSTOM_OBJ 0xa933a8 /* -> String* of CustomObject's first ';' token (not resolved by createReferences) */
#define AD_CV3 0xa933f0
#define AD_CV4 0xa93400
#define SKILL_ATTACK_SD(ch) ((void *(*)(void *))B(0xb35c00))(ch)   /* env.c SKILL_ATTACK */
#define GAD_PROJ_KIND 4        /* projectile kind word (+0x418): 1 = main attack, 2 = super; 4 = the skill path that spawns
                                * directly (0xb7e93c), so a gadget shot does not count as an attack or a super */
typedef void *(*SpawnProj)(int, int, void *, void *, void *, int, int, int, int, int, int, void *, void *, int, int, void *);
/* the brawler's damage percent (0xb4b660: char +0x47c, +0x968, buffs), as the attack path scales SkillData Damage before
 * the spawn. It reads 0 for the host's brawlers (the env's damage model scales in the damage root instead, env.c): 0 is
 * taken as 100 %, so the projectile carries the skill's Damage as the table gives it */
static int dmg_scaled(uint8_t *ch, int dmg) {
    int pct = ((int (*)(void *))B(0xb4b660))(ch);
    return dmg > 0 ? (int)((int64_t)dmg * (pct > 0 ? pct : 100) / 100) : 0;
}
/* one projectile from the brawler along `deg` (math degrees) to `range` units, through the projectile spawn 0xb78190 as
 * spawnfix.c calls it (owner twice, no lateral offset, no inherited hit list) -> 1 = spawned */
static long g_shots;
static void *g_last_shot;   /* the projectile the last shoot() spawned (NULL = none), for volley's sibling list */
static int shoot(void *sim, uint8_t *ch, void *pd, double deg, int range, int dmg) {
    g_last_shot = NULL;
    if (!pd || !PTR(ch, 0x20)) return 0;
    int X = I32(ch, 0x38), Y = I32(ch, 0x3c); double r = deg * M_PI / 180;
    int tx = (int)floor(X + range * cos(r) + 0.5), ty = (int)floor(Y + range * sin(r) + 0.5);
    void *p = ((SpawnProj)B(0xb78190))(X, Y, ch, ch, pd, tx, ty, dmg, dmg, 0, 0, NULL, sim, 0, GAD_PROJ_KIND, NULL);
    if (p) g_shots++;
    g_last_shot = p;
    if (g_shots <= 4) LOG("[gadget] shot %p to %d,%d dmg %d (proj +0xd4 %d)\n", p, tx, ty, dmg, p ? I32(p, 0xd4) : -1);
    return p != NULL;
}
static void *lookup_by_name(uint64_t fn, void *str) {   /* getXByName(String*, referer) (0xad2f1c projectile, 0xad3c30 item) */
    return str && I32(str, 4) > 0 ? ((void *(*)(void *, void *))B(fn))(str, NULL) : NULL;
}
static void *custom_proj(void *ad) { return lookup_by_name(0xad2f1c, ((void *(*)(void *))B(AD_CUSTOM_OBJ))(ad)); }
static void *custom_item(void *ad) { return lookup_by_name(0xad3c30, ((void *(*)(void *))B(AD_CUSTOM_OBJ))(ad)); }
/* a volley of n projectiles over `spread` degrees centred on deg (n = 1: straight) -> how many spawned. A projectile row with
 * DamageOnlyWithOneProj (ProjectileData +0x1ed, getter 0xafaa08; Emz's spray) damages a target with one projectile of the
 * attack only, as the attack path does it: it keeps the attack's projectiles in a list (char +0xd38, 0xb4dc6c) and, after
 * the volley, gives each one the ids of the others (0xb791dc(proj, list) -> proj +0x1a8, at 0xb4e350); on a hit, libg's
 * projectile hit (0xb730bc -> 0xb77894) then puts the target on every sibling's hit list (proj +0x160) for good. */
typedef struct { void **data; int cap, count; } LArr;   /* LogicArrayList: data, capacity, count (0xb791dc reads +0, +12) */
static int volley(void *sim, uint8_t *ch, void *pd, double deg, int n, double spread, int range, int dmg) {
    int k = 0; void *ps[16]; LArr l = { ps, 16, 0 };
    for (int i = 0; i < n; i++) {
        k += shoot(sim, ch, pd, n > 1 ? deg - spread / 2 + spread * i / (n - 1) : deg, range, dmg);
        if (g_last_shot && l.count < 16) ps[l.count++] = g_last_shot;
    }
    if (l.count > 1 && (((int (*)(void *))B(0xafaa08))(pd) & 1))
        for (int i = 0; i < l.count; i++) ((void (*)(void *, void *))B(0xb791dc))(ps[i], &l);
    return k;
}

/* ---- SHOT: the gadget's own skill (Type empty, Skill set, BehaviorType not Charge) fires its projectile */
static void *skill_proj(void *sd) { void **a = sd ? PTR(sd, SD_PROJ) : NULL; return a && I32(sd, SD_PROJ + 0xc) > 0 ? a[0] : NULL; }
static int shot_classify(void *ad, int type) {
    void *sd = type == ACC_PLAIN ? PTR(ad, AD_SKILL) : NULL;
    return sd && !PTR(ad, AD_AREA) && I32(sd, SD_BEHAVIOR) == BT_ATTACK && skill_proj(sd);
}
/* SHOT gadgets that fire more than one wave (issue #55: python -m desc_audit compares the description): card, waves,
 * ticks between them. The skill's ActiveTime / MsBetweenAttacks do not pin the count (Colt's 300 / 100 would be 3 waves). */
static const struct { int card, waves, gap; } g_waves[] = {
    {23000273, 2, 2},   /* Gunslinger_Reload: "fires two quick shots", MsBetweenAttacks 100 ms = 2 ticks */
};
#define PD_INDIRECT 0xb8   /* ProjectileData +0xb8: Indirect (a thrown shot that lands at its target point; byte set at 0xaf8128) */
#define AIM_MIN 300        /* units: the nearest a thrown gadget lands (one tile) */
static int aimed_range(int range, double dist) { return dist > 0 && dist < 1 ? (int)fmax(AIM_MIN, range * dist) : range; }
static int shot_volley(void *sim, Gad *g, uint8_t *ch, double deg) {
    void *sd = PTR(g->ad, AD_SKILL), *pd = skill_proj(sd);
    int n = sd_get(sd, SD_NBULLETS), cr = sd_get(sd, SD_RANGE), range = cr > 0 ? cr * 100 : 1000;
    n = n < 1 ? 1 : n > 16 ? 16 : n;   /* NumBulletsInOneAttack 1..5 in the gadget rows */
    if (pd && U8(pd, PD_INDIRECT)) range = aimed_range(range, g->dist);   /* issue #55: Griff's coins land where aimed */
    return volley(sim, ch, pd, deg, n, sd_get(sd, SD_SPREAD), range, dmg_scaled(ch, sd_get(sd, SD_DAMAGE)));
}
static int shot_fire(void *sim, Gad *g, uint8_t *ch, double deg, int tick) {
    if (I32(ch, 0x3c4) <= 0 || g->burst_left) return 0;
    if (shot_volley(sim, g, ch, deg) <= 0) return 0;
    for (unsigned k = 0; k < sizeof g_waves / sizeof *g_waves; k++)
        if (g_waves[k].card == g->card && g_waves[k].waves > 1) {
            g->burst_id = I32(ch, 8); g->burst_left = g_waves[k].waves - 1; g->burst_gap = g_waves[k].gap > 0 ? g_waves[k].gap : 1;
            g->burst_next = tick + g->burst_gap; g->burst_deg = (int)deg;
        }
    return 1;
}
static void burst_tick(void *sim, Gad *g, int tick) {   /* the later waves, along the first wave's angle */
    uint8_t *ch = env_obj_by_id(sim, g->burst_id);
    if (!ch || I32(ch, 0x3c4) <= 0) { g->burst_left = 0; return; }
    while (g->burst_left > 0 && tick >= g->burst_next) { shot_volley(sim, g, ch, g->burst_deg); g->burst_left--; g->burst_next += g->burst_gap; }
}

/* ---- SKILL AREA: the gadget's skill has no projectile, only an AreaEffectObject: an Attack skill's area at the brawler
 * (Bull's Stomp) or one whose AreaEffectFollowType is follow (8-Bit's Extra Credits), any other AimableArea skill's at
 * the aim point, super_dist of its CastingRange out */
static int skill_area_classify(void *ad, int type) {
    void *sd = type == ACC_PLAIN ? PTR(ad, AD_SKILL) : NULL; int bt = sd ? I32(sd, SD_BEHAVIOR) : -1;
    return sd && !PTR(ad, AD_AREA) && (bt == BT_ATTACK || bt == BT_AIM_AREA) && !skill_proj(sd) && PTR(sd, SD_AREA);
}
static int skill_area_fire(void *sim, Gad *g, uint8_t *ch, double deg, int tick) {
    if (I32(ch, 0x3c4) <= 0 || g->area_at) return 0;
    void *sd = PTR(g->ad, AD_SKILL); int cr = aimed_range(sd_get(sd, SD_RANGE) * 100, g->dist); double r = deg * M_PI / 180;
    g->area_id = I32(ch, 8); g->area_at = tick; g->area_data = PTR(sd, SD_AREA); g->area_here = I32(sd, SD_BEHAVIOR) != BT_AIM_AREA || I32(sd, SD_FOLLOW) == 1;
    g->area_x = (int)floor(I32(ch, 0x38) + cr * cos(r) + 0.5); g->area_y = (int)floor(I32(ch, 0x3c) + cr * sin(r) + 0.5);
    area_spawn(sim, g);
    return 1;
}

/* ---- AUTO AIMER: Piper's Sniper_HandGun (issue #54, redone from the game data; the other repeat_shot rows stay off) */
#define CARD_AUTO_AIMER 23000268   /* cards.csv Sniper_HandGun (a data id, as g_masked) */
#define AD_RANGE 0xa93348          /* Range (column slot 0x123f000+2032, filled by the column-index init that ends at 0xa93244) */
#define AD_RANGE_U 300             /* accessory Range is in tiles: the client's aim guide (bl 0xa93348 at 0x876558) draws it as
                                    * Range x 3 in the 100 u steps of CastingRange, i.e. 300 u per tile (Piper: 7 -> 2100 u) */
static int g_cls_card;             /* the card being classified (gadget_reset_player) */
static int auto_aim_classify(void *ad, int type) {
    return type == ACC_REPEAT && g_cls_card == CARD_AUTO_AIMER && custom_proj(ad) && ad_get(ad, AD_RANGE) > 0;
}
/* the nearest living enemy brawler (team +0x84 not the brawler's) within `range` units of it, NULL = none */
static uint8_t *nearest_enemy_char(void *sim, uint8_t *ch, int range) {
    int team = I32(ch, 0x84), X = I32(ch, 0x38), Y = I32(ch, 0x3c), np = I32(sim, 0x7c);
    uint8_t *best = NULL; int64_t bd = (int64_t)range * range;
    for (int i = 0; i < np && i < 64; i++) {
        uint8_t *c = char_of(sim, i);
        if (!c || c == ch || I32(c, 0x84) == team || I32(c, 0x3c4) <= 0 || !PTR(c, 0x20)) continue;
        int64_t dx = I32(c, 0x38) - X, dy = I32(c, 0x3c) - Y, d2 = dx * dx + dy * dy;
        if (d2 <= bd) { bd = d2; best = c; }
    }
    return best;
}
/* texts.csv value code 50: main attack Damage x CustomValue1 %; Piper 1800 x 5 % = 90 (level-1 table), cf. Belle's Nest Egg 30 % */
static int auto_aim_dmg(uint8_t *ch, void *ad) {
    void *sd = SKILL_ATTACK_SD(ch);
    return sd ? dmg_scaled(ch, (int)((int64_t)sd_get(sd, SD_DAMAGE) * ad_get(ad, AD_CV1) / 100)) : 0;
}
static int auto_aim_fire(void *sim, Gad *g, uint8_t *ch, double deg, int tick) {
    (void)deg; (void)tick;   /* the policy's aim is not used: the shot goes at the nearest enemy */
    if (I32(ch, 0x3c4) <= 0) return 0;
    int range = ad_get(g->ad, AD_RANGE) * AD_RANGE_U;
    uint8_t *e = nearest_enemy_char(sim, ch, range);
    if (!e) return 0;        /* RequireEnemyInRange: refused, no use or cooldown spent */
    double a = atan2(I32(e, 0x3c) - I32(ch, 0x3c), I32(e, 0x38) - I32(ch, 0x38)) * 180 / M_PI;
    return shoot(sim, ch, custom_proj(g->ad), a, range, auto_aim_dmg(ch, g->ad));
}

/* ---- REPEAT / SPIN (issue #54 redo, from the game data): repeat_shot and spin_shoot rows with a CustomObject projectile.
 * The numbers are those the game's own card text shows: libg's value-code formatter (0x90d548, jump table 0x1fc2e0, index
 * code - 1) reads code 19 ("Bea unleashes <VALUE1> bees") as ActiveTicks / CustomValue1, codes 50 / 51 / 54 as WeaponSkill
 * Damage x CustomValue1 / 2 / 3 %, code 59 as Hitpoints x CustomValue2 %, code 3 as |CustomValue3|. So a row fires
 * ActiveTicks / CustomValue1 shots, one every CustomValue1 ticks (Piper 5 / 5 = the one Auto Aimer shot, Bea 16 / 4 = 4 bees).
 * [?] the rest is this reading of the rows (the activation is compiled out of the client):
 *   SPIN (Dynamike, Darryl, Fang's popcorn): each shot turns CustomValue2 degrees from the aim (Darryl 15 x 25, Fang 7 x 50:
 *     one turn), flies CustomValue4 units, damage Damage x CustomValue3 % (Dynamike's text: scaleaccessoryvalue3; code 54).
 *   REPEAT by SubType, damage Damage x CustomValue2 % (codes 51 / 68; Mico's text: scaleaccessoryvalue2):
 *     1 (Gene; Barley with TargetFriends): one shot at each target within Range tiles (enemies, or allies and the brawler
 *       himself), nearest first; Gene's RequireEnemyInRange refuses with none. Barley's potion carries Hitpoints x
 *       |CustomValue2| % (code 59, "heals <VALUE1> health per second") for the BarkeepHealingArea its skin spawns.
 *     2 (Bea): the bees leave along the aim, turned 360 / n degrees each, to the main attack's range.
 *     4 (Amber): |CustomValue3| flames at once, evenly around her (code 3, "creates <VALUE3> orbiting flames").
 *     5 (Mico): |CustomValue3| projectiles over CustomValue4 degrees at the nearest enemy within Range; none: refused.
 *   The projectile's own data (homing, circling, DamagePercentStart / End, delays, areas) is libg's. */
static int attack_range(uint8_t *ch) { void *sd = SKILL_ATTACK_SD(ch); int cr = sd ? sd_get(sd, SD_RANGE) : 0; return cr > 0 ? cr * 100 : 1000; }
static int attack_dmg_pct(uint8_t *ch, int pct) {
    void *sd = SKILL_ATTACK_SD(ch); return sd ? dmg_scaled(ch, (int)((int64_t)sd_get(sd, SD_DAMAGE) * abs(pct) / 100)) : 0;
}
/* TargetFriends has no getter of its own in this build: libg's bool column read 0xcf6a08(row, column index), as the getters
 * do (e.g. RequireEnemyInRange 0xa93358), with the index the column-index init stores at 0x123f000 + 2036 ("TargetFriends") */
static int ad_target_friends(void *ad) { return ((int (*)(void *, int))B(0xcf6a08))(PTR(ad, 8), I32(B(0x123f000), 2036)) & 1; }
static int rep_classify(void *ad, int type) {
    return (type == ACC_REPEAT || type == ACC_SPIN) && g_cls_card != CARD_AUTO_AIMER && custom_proj(ad) && ad_get(ad, AD_CV1) > 0
        && ad_get(ad, AD_ACTIVE_TICKS) > 0;
}
/* up to `max` brawlers within `range` of ch, nearest first: enemies (friends 0) or allies and ch itself (friends 1) */
static int targets(void *sim, uint8_t *ch, int range, int friends, int *ids, int max) {
    int team = I32(ch, 0x84), X = I32(ch, 0x38), Y = I32(ch, 0x3c), np = I32(sim, 0x7c), n = 0; int64_t d2s[REP_MAX];
    for (int i = 0; i < np && i < 64; i++) {
        uint8_t *c = char_of(sim, i);
        if (!c || I32(c, 0x3c4) <= 0 || !PTR(c, 0x20) || (I32(c, 0x84) == team) != friends || (!friends && c == ch)) continue;
        int64_t dx = I32(c, 0x38) - X, dy = I32(c, 0x3c) - Y, d2 = dx * dx + dy * dy;
        if (d2 > (int64_t)range * range) continue;
        int k = n < max ? n++ : max - 1; if (k == max - 1 && n == max && d2 >= d2s[k]) continue;
        while (k > 0 && d2s[k - 1] > d2) { d2s[k] = d2s[k - 1]; ids[k] = ids[k - 1]; k--; }
        d2s[k] = d2; ids[k] = I32(c, 8);
    }
    return n;
}
static void rep_shot(void *sim, Gad *g, uint8_t *ch) {   /* shot number g->rep_i */
    void *pd = custom_proj(g->ad); int i = g->rep_i, sub = ad_get(g->ad, AD_SUBTYPE);
    double deg = g->rep_ang; int range = g->rep_rng;
    if (g->rep_tgt[i]) {   /* at a target's position now */
        uint8_t *t = env_obj_by_id(sim, g->rep_tgt[i]);
        if (t && I32(t, 0x3c4) > 0) {
            double dx = I32(t, 0x38) - I32(ch, 0x38), dy = I32(t, 0x3c) - I32(ch, 0x3c);
            deg = atan2(dy, dx) * 180 / M_PI; range = (int)fmax(AIM_MIN, sqrt(dx * dx + dy * dy));
            if (!U8(pd, PD_INDIRECT) && g->type == ACC_REPEAT && sub != 1) range = g->rep_rng;
        } else if (t == ch || g->rep_tgt[i] == I32(ch, 8)) range = AIM_MIN;
        else { g->rep_i++; return; }   /* the target died or left: no shot */
    }
    if (g->type == ACC_SPIN) deg += (double)ad_get(g->ad, AD_CV2) * i;
    else if (sub == 2) deg += 360.0 * i / g->rep_n;
    if (g->rep_cnt > 1 && g->rep_spread >= 360) for (int k = 0; k < g->rep_cnt; k++) shoot(sim, ch, pd, deg + 360.0 * k / g->rep_cnt, range, g->rep_dmg);
    else volley(sim, ch, pd, deg, g->rep_cnt, g->rep_spread, range, g->rep_dmg);
    g->rep_i++;
}
static int rep_fire(void *sim, Gad *g, uint8_t *ch, double deg, int tick) {
    if (I32(ch, 0x3c4) <= 0 || g->rep_n) return 0;
    void *ad = g->ad; int sub = ad_get(ad, AD_SUBTYPE), cv1 = ad_get(ad, AD_CV1), act = ad_get(ad, AD_ACTIVE_TICKS);
    int n = act / cv1, cv3 = abs(ad_get(ad, AD_CV3)); n = n < 1 ? 1 : n > REP_MAX ? REP_MAX : n;
    int rng = ad_get(ad, AD_RANGE) * AD_RANGE_U;
    memset(g->rep_tgt, 0, sizeof g->rep_tgt); g->rep_cnt = 1; g->rep_spread = 0; g->rep_ang = deg; g->rep_rng = attack_range(ch);
    if (g->type == ACC_SPIN) {
        int r4 = ad_get(ad, AD_CV4); if (r4 > 0) g->rep_rng = r4;
        g->rep_dmg = attack_dmg_pct(ch, ad_get(ad, AD_CV3));
    } else {
        g->rep_dmg = attack_dmg_pct(ch, ad_get(ad, AD_CV2));
        if (sub == 1) {
            int fr = ad_target_friends(ad);
            n = targets(sim, ch, rng > 0 ? rng : g->rep_rng, fr, g->rep_tgt, n < REP_MAX ? n : REP_MAX);
            if (fr) {   /* the potion: its heal for the healing area (Hitpoints x |CustomValue2| %, code 59) */
                void *cd = ((void *(*)(void *))B(0xb6a384))(ch);
                g->rep_dmg = cd ? (int)((int64_t)((int (*)(void *))B(0xab31e8))(cd) * abs(ad_get(ad, AD_CV2)) / 100) : 0;
            }
            if (!n) return 0;   /* Gene: RequireEnemyInRange */
        } else if (sub == 4) { g->rep_cnt = cv3 > 0 ? (cv3 > 16 ? 16 : cv3) : 1; g->rep_spread = 360; n = 1; }
        else if (sub == 5) {
            int id; if (!targets(sim, ch, rng, 0, &id, 1)) return 0;   /* RequireEnemyInRange */
            uint8_t *t = env_obj_by_id(sim, id);
            g->rep_ang = atan2(I32(t, 0x3c) - I32(ch, 0x3c), I32(t, 0x38) - I32(ch, 0x38)) * 180 / M_PI;
            g->rep_rng = rng; g->rep_cnt = cv3 > 0 ? (cv3 > 16 ? 16 : cv3) : 1; g->rep_spread = abs(ad_get(ad, AD_CV4));
        }
    }
    g->rep_id = I32(ch, 8); g->rep_n = n; g->rep_i = 0; g->rep_gap = cv1; g->rep_next = tick + cv1;
    if (g_rep_log++ < 6) LOG("[gadget] repeat card %d type %d sub %d: %d shots every %d ticks, x%d, dmg %d, range %d\n",
                             g->card, g->type, sub, n, cv1, g->rep_cnt, g->rep_dmg, g->rep_rng);
    rep_shot(sim, g, ch);
    if (g->rep_i >= g->rep_n) g->rep_n = 0;
    return 1;
}
static void rep_tick(void *sim, Gad *g, int tick) {
    uint8_t *ch = env_obj_by_id(sim, g->rep_id);
    if (!ch || I32(ch, 0x3c4) <= 0) { g->rep_n = 0; return; }
    while (g->rep_n && tick >= g->rep_next) { rep_shot(sim, g, ch); g->rep_next += g->rep_gap; if (g->rep_i >= g->rep_n) g->rep_n = 0; }
}

/* ---- ITEM: spawn rows whose CustomObject is an items.csv row (Belle's ElectroTrap, Gale's WindWall): the item at the
 * brawler, through the item factory 0xb55684 as the shipped character-owned item at 0xb583cc calls it (1 item, at most
 * 1 per player: an older one is removed), without the follow call. The factory's damage pair (item +0xe0, handed to the
 * item's TriggerAreaEffect) is the main attack's Damage x CustomValue1 %, as the card's text reads it (Belle's trap:
 * "weaponskill.damage.scaleaccessoryvalue1", CustomValue1 30: 1040 x 30 % = 312, x2 power level in the damage root); no
 * CustomValue1 (Gale): 0. Spawns of characters (turrets, clones) and areas
 * (meteor, air strike) need summon / targeting code the host does not have: not usable. */
static long g_items;
/* Gale's Twister (Blower_Stopper): the WindWall item spawns, and env repels enemies around it (env_repel_zone), for the item's
 * Lifetime (items.csv WindWall 100 ticks). [?] reach and strength are not in the data: items.csv Value 600 is read as the push
 * distance (the knockback moves 6 x strength u: strength 100), the reach as one tile around the item */
#define ITEM_WINDWALL 36       /* ItemData +0x54: the WindWall type the client's draw code tests (0x5371fc) */
#define WINDWALL_TICKS 100
#define WINDWALL_PUSH 100
#define WINDWALL_R 300
void env_repel_zone(void *sim, uint8_t *ch, int x, int y, int r, int ticks, int push);   /* env.c */
static int item_classify(void *ad, int type) { return type == ACC_SPAWN && custom_item(ad); }
static int item_fire(void *sim, Gad *g, uint8_t *ch, double deg, int tick) {
    (void)deg; (void)tick;
    if (I32(ch, 0x3c4) <= 0 || !PTR(ch, 0x20)) return 0;
    void *sd = SKILL_ATTACK_SD(ch); int cv1 = ad_get(g->ad, AD_CV1);
    int dmg = cv1 > 0 && sd ? (int)((int64_t)dmg_scaled(ch, sd_get(sd, SD_DAMAGE)) * cv1 / 100) : 0;
    void *it = ((void *(*)(void *, int, int, int, int, int, int, int, int, int, void *, void *, void *, int))B(0xb55684))(
        custom_item(g->ad), I32(ch, 0x38), I32(ch, 0x3c), 1, 1, dmg, dmg, I32(ch, 0x80), I32(ch, 0x84), 0, ch, ch, sim, 6);
    if (it) g_items++;
    if (it && I32(custom_item(g->ad), 0x54) == ITEM_WINDWALL) env_repel_zone(sim, ch, I32(ch, 0x38), I32(ch, 0x3c), WINDWALL_R, WINDWALL_TICKS, WINDWALL_PUSH);
    return it != NULL;
}

/* ---- SUPER: charge_ulti (R-T): the super charge (player +0x54) to CustomValue1 % of its maximum (+0x58) */
static int super_classify(void *ad, int type) { return type == ACC_CHARGE_ULTI && ad_get(ad, AD_CV1) > 0; }
static int super_fire(void *sim, Gad *g, uint8_t *ch, double deg, int tick) {
    (void)deg; (void)tick;
    uint8_t *p = player_of(sim, g->pid); if (!p || I32(ch, 0x3c4) <= 0 || I32(p, 0x58) <= 0) return 0;
    int want = (int)((int64_t)I32(p, 0x58) * ad_get(g->ad, AD_CV1) / 100);
    if (I32(p, 0x54) < want) I32(p, 0x54) = want;   /* a use is spent even on a full super, as any gadget use */
    return 1;
}

/* ---- HEAL_NOW: instant heals through libg's heal 0xb41554 (capped at max hp, the game's heal modifiers apply)
 *   heal_attached_and_self (Kit's Cheeseburger): CustomValue1 % of max hp to Kit (the attached ally is not modelled:
 *     the host has no attach state; the card's flat <VALUE1> = Value 70 has an unknown scale, so CV1 30 is read as %)
 *   heal_damage_taken (Kenji): CustomValue1 % (60) of the damage taken in the last CustomValue2 ticks (50 = 2.5 s; the
 *     host keeps the hp lost per tick for every player with this gadget, gadget_tick) */
static int heal_now_classify(void *ad, int type) { return (type == ACC_HEAL_SELF || type == ACC_HEAL_TAKEN) && ad_get(ad, AD_CV1) > 0; }
static int damage_taken(Gad *g, int tick, int ticks) {
    int s = 0; ticks = ticks > 100 ? 100 : ticks;
    for (int t = tick - ticks + 1; t <= tick; t++) s += g->hp_lost[((t % 100) + 100) % 100];
    return s;
}
static int heal_now_fire(void *sim, Gad *g, uint8_t *ch, double deg, int tick) {
    (void)sim; (void)deg;
    int hp = I32(ch, 0x3c4), mx = I32(ch, 0x3c8), cv1 = ad_get(g->ad, AD_CV1), amt;
    if (hp <= 0 || mx <= 0) return 0;
    if (g->type == ACC_HEAL_TAKEN) amt = (int)((int64_t)damage_taken(g, tick, ad_get(g->ad, AD_CV2)) * cv1 / 100);
    else amt = (int)((int64_t)mx * cv1 / 100);
    if (amt > 0 && hp < mx)   /* a use is spent even when there is nothing to heal (the game's button has no such check) */
        ((void (*)(void *, int, int, int, void *, int, int, int, long, long))B(0xb41554))(ch, g->pid, amt, 1, NULL, 0, 0, 0, 0, 0);
    return 1;
}
static void taken_tick(void *sim, Gad *g, int tick) {   /* hp lost this tick (a heal or a respawn counts as 0) */
    uint8_t *ch = char_of(sim, g->pid); int hp = ch ? I32(ch, 0x3c4) : 0, k = ((tick % 100) + 100) % 100;
    g->hp_lost[k] = hp > 0 && g->hp_prev > hp ? g->hp_prev - hp : 0; g->hp_prev = hp;
}

static const GadImpl g_impl[] = {
    {NBE_GAD_DASH, dash_classify, dash_fire},
    {NBE_GAD_HEAL, heal_classify, heal_fire},
    {NBE_GAD_SPAWN, area_classify, area_fire},
    {NBE_GAD_PROJECTILE, shot_classify, shot_fire},
    {NBE_GAD_SPAWN, skill_area_classify, skill_area_fire},
    {NBE_GAD_PROJECTILE, auto_aim_classify, auto_aim_fire},
    {NBE_GAD_PROJECTILE, rep_classify, rep_fire},
    {NBE_GAD_SPAWN, item_classify, item_fire},
    {NBE_GAD_SUPER, super_classify, super_fire},
    {NBE_GAD_HEAL, heal_now_classify, heal_now_fire},
    {NBE_GAD_NONE, NULL, NULL}};

/* cards whose kind classifies but whose effect did not show in `python -m super_audit --gadget` (cards.csv data ids, fixed
 * by the shipped tables): left unusable (kind NONE) so the policy cannot spend a fire on them. bsrl-sim super_audit.MASKED
 * lists the same rows. */
static const int g_masked[] = {
    23000263,   /* BowDude_Totem: the projectile flies, the totem summon never spawns */
    23000311,   /* Speedy_Rewind: its projectile is a marker; the rewind (teleport back) is not implemented */
    23000351,   /* HammerDude_Pull: no pull, no damage on the target */
    23000399,   /* AssaultShotgun_Bomb: no explosion, no damage */
    23000408,   /* Ninja_InvisibleArea: the invisibility area summon never spawns */
    23001247,   /* Gladiator_Amp: the healing item never spawns */
    23001255,   /* MagicalGirl_FlyArea: the area summon never spawns */
    /* REPEAT rows that fire but showed no hit live (super_audit --gadget, both attempts): */
    23000260,   /* BarrelBot_Spin: the shot aimed straight at the target 300 / 875 u away passes it, no damage */
    23000440,   /* KickerDude_Mines: every kernel lands at CustomValue4 (1500 u); the game scatters them, the spread is not in the data */
    23000312,   /* BeeSniper_ExtraBee: the circling bees never reach the target 450 u away; the curve is not checked */
    23000488,   /* FireDude_FlameShield: the orbiting flames never reach the target 450 u away; the orbit is not checked */
};
static int masked(int card) { for (unsigned k = 0; k < sizeof g_masked / sizeof *g_masked; k++) if (g_masked[k] == card) return 1; return 0; }

void gadget_clear(void) { memset(g_gad, 0, sizeof g_gad); }

/* RESET response (env.c div_publish), per player: its requested card and the accessory object the game made for it */
void gadget_reset_player(int i, void *acc) {
    if (i < 0 || i >= NBE_MAXP) return;
    Gad *g = &g_gad[i]; memset(g, 0, sizeof *g);
    if (!acc || !g_div_gadget[i]) return;
    g->card = g_div_gadget[i]; g->ad = PTR(acc, 0x10); g->pid = i;
    int type = g->type = I32(acc, 0x24); g_cls_card = g->card;
    for (const GadImpl *im = g_impl; g->ad && !masked(g->card) && im->classify; im++)
        if (im->classify(g->ad, type)) {
            static int uses = -1; if (uses < 0) { const char *e = getenv("NB_GAD_USES"); uses = e && atoi(e) > 0 ? atoi(e) : GAD_USES; }
            g->im = im; g->uses = uses; g->cd = I32(acc, 0xc4) > 0 ? I32(acc, 0xc4) : 0;
            /* the skill gadgets' rows leave Cooldown empty: their skill's Cooldown (skills.csv, ticks as the accessory's:
             * Shelly's Clay Pigeons 250, getter 0xb0d868) */
            if (!g->cd && PTR(g->ad, AD_SKILL)) { int c = sd_get(PTR(g->ad, AD_SKILL), SD_COOLDOWN); g->cd = c > 0 ? c : 0; }
            break;
        }
    static int nlog; if (nlog++ < 20) LOG("[gadget] player %d card %d type %d: %s, %d uses, cooldown %d ticks\n", i, g->card, type,
                                          g->im ? "implemented" : "kind not implemented (not usable)", g->uses, g->cd);
}

/* NbeAction.fire 3 for player i at sim tick `tick`: -> 1 = the host handled it (activated, or refused: no use left / cooldown /
 * the effect could not start), 0 = no implementation for this gadget (the caller sends the raw input kind 8 as before) */
int gadget_use(void *sim, int i, uint8_t *ch, double deg, double dist, int tick) {
    if (i < 0 || i >= NBE_MAXP || !g_gad[i].im) return 0;
    Gad *g = &g_gad[i]; g->dist = dist;
    if (g->uses <= 0 || tick < g->cd_until || !ch) return 1;
    if (g->im->fire(sim, g, ch, deg, tick)) {
        g->uses--; g->used++; g->cd_until = tick + g->cd;
        if (g_fired[g->im->kind & 7]++ < 10) LOG("[gadget] player %d kind %d fired at tick %d, %d uses left\n", i, g->im->kind, tick, g->uses);
    }
    return 1;
}

void gadget_tick(void *sim, int tick) {   /* env.c pre_snapshot, once per tick */
    for (int i = 0; i < NBE_MAXP; i++) {
        if (g_gad[i].hot_end) heal_tick(sim, &g_gad[i], tick);
        if (g_gad[i].area_at && tick >= g_gad[i].area_at) area_spawn(sim, &g_gad[i]);
        if (g_gad[i].rep_n) rep_tick(sim, &g_gad[i], tick);
        if (g_gad[i].burst_left) burst_tick(sim, &g_gad[i], tick);
        if (g_gad[i].im && g_gad[i].type == ACC_HEAL_TAKEN) taken_tick(sim, &g_gad[i], tick);
    }
}

void gadget_publish(NbeResp *r, int tick) {   /* every response */
    r->gad_valid = 1;
    for (int i = 0; i < NBE_MAXP; i++) {
        const Gad *g = &g_gad[i];
        r->gad_card[i] = g->card; r->gad_kind[i] = g->im ? g->im->kind : NBE_GAD_NONE; r->gad_charges[i] = g->im ? g->uses : 0;
        r->gad_cd[i] = g->im && g->cd_until > tick ? g->cd_until - tick : 0; r->gad_used[i] = g->used;
    }
}
