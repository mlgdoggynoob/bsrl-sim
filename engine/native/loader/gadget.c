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
 *         walls where she grows bushes) and Meeple's RageQuit (HpBasedStun: not applied by the client build). Published
 *         as kind SPAWN; `python -m super_audit --gadget` checks each one's effects. The area is spawned
 *         at the brawler with the shipped helper 0xb35c40 (create 0xb2aefc, world add 0xb63198, start 0xb29494, the chain
 *         superfix.c's spawnAreaEffect uses), kind 2 and no extra damage, as at every shipped caller: the area's damage,
 *         heal, status and wall spawn then come from libg and the earlier rounds (superfix, spawnfix). ActivationDelay
 *         ticks (Tick: 20) are waited out first, and the area is placed where the brawler is then.
 *   SHOT  empty Type, no AreaEffect, a Skill whose BehaviorType is Attack with Projectiles (32 rows: Spike, Colt x2, Brock,
 *         Shelly, Emz x2, ...; published PROJECTILE): NumBulletsInOneAttack of the skill's first projectile over Spread degrees
 *         centred on the aim, to CastingRange, with the skill's Damage scaled by the brawler's damage percent (0xb4b660, as the
 *         attack path scales it), spawned with the projectile spawn 0xb78190 (spawnfix.c) at kind 4. What the projectile
 *         does on hit or at its end (areas, items, summons, pull / push) is libg's and the earlier rounds'. Not applied: the
 *         skill's timing (ActiveTime, MsBetweenAttacks waves), TwoGuns, AttackPattern.
 *   SKILL AREA  the same, but the skill has no projectile, only an AreaEffectObject (published SPAWN): Bull's Stomp (Attack:
 *         at the brawler), 8-Bit's Extra Credits (AimableArea: at the aim point at CastingRange).
 *   REPEAT  repeat_shot with a CustomObject projectile (6 rows, PROJECTILE): CustomValue1 projectiles over CustomValue2 degrees
 *         at the main attack's range and damage (the reading of the values is this host's, see repeat_fire).
 *   SPIN  spin_shoot with a CustomObject projectile (TntDude, BarrelBot, KickerDude_Mines; PROJECTILE): volleys around the
 *         brawler for ActiveTicks (spin_fire). The two rows without a projectile (KickerDude_Sweep, Painter_Push) stay unusable.
 *   ITEM  spawn rows whose CustomObject is an items.csv row (Bolt's trap, Gale's wind wall; SPAWN): the item at the
 *         brawler through the item factory 0xb55684.
 *   SUPER charge_ulti (R-T; published SUPER): the super charge to CustomValue1 % of its maximum.
 *   HEAL_NOW  heal_attached_and_self (Kit) and heal_damage_taken (Kenji) (HEAL): an instant heal through libg's heal 0xb41554.
 * Every other gadget publishes kind NONE (not usable): next_attack_change, summons / turrets, status buffs, shields,
 * Nori's fish heal (needs his fish count), the Charge skills (Brock's jump, Max's dash, ...), ... Each player gets GAD_USES
 * uses per battle (unlimited by default, as in the live game since February 2025) and the accessory's cooldown between
 * uses. The accessory's Type parses to the int at +0x24 (0xb2731c:
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
#define B(off) ((uint8_t *)g_libg->base + (off))
extern Module *g_libg;
extern int32_t g_div_gadget[NBE_MAXP];   /* env.c: the RESET's requested gadget cards (offline.c puts them in the configs) */
void *env_obj_by_id(void *sim, int id);  /* env.c */
int env_dash_start(uint8_t *ch, int tx, int ty, int speed);   /* env.c: -> path length, 0 = no dash */

#define GAD_USES 9999     /* no per-battle limit: gadgets "no longer have charges but are now based on cooldowns" and can be
                           * used "an unlimited amount of times in a match" (Supercell release notes, Feb 2025); the
                           * cooldown is the accessory's (accessories.csv Cooldown, e.g. Bibi 400 ticks = the 20 s of the
                           * Feb 2026 notes). NB_GAD_USES=3 restores the old 3 uses per battle (issue #22). */
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
    int spin_id, spin_next, spin_end, spin_ang;            /* spin_shoot: char id, next volley tick, end tick, volley angle */
    int hp_prev, hp_lost[100];                        /* damage taken per tick (ring by tick % 100), for HEAL_TAKEN */
};
static Gad g_gad[NBE_MAXP];
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
#define AREA_HPSTUN 43      /* HpBasedStun (Meeple's RageQuit): the area spawns, but the client build applies neither its stun
                             * nor its pushback (super_audit --gadget: no push), so the gadget would be a no-op: left out */
static int area_classify(void *ad, int type) {
    void *a = type == ACC_PLAIN ? PTR(ad, AD_AREA) : NULL;
    return a && I32(a, 0x118) != AREA_WALLSPAWN && I32(a, 0x118) != AREA_HPSTUN;
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
static int shoot(void *sim, uint8_t *ch, void *pd, double deg, int range, int dmg) {
    if (!pd || !PTR(ch, 0x20)) return 0;
    int X = I32(ch, 0x38), Y = I32(ch, 0x3c); double r = deg * M_PI / 180;
    int tx = (int)floor(X + range * cos(r) + 0.5), ty = (int)floor(Y + range * sin(r) + 0.5);
    void *p = ((SpawnProj)B(0xb78190))(X, Y, ch, ch, pd, tx, ty, dmg, dmg, 0, 0, NULL, sim, 0, GAD_PROJ_KIND, NULL);
    if (p) g_shots++;
    if (g_shots <= 4) LOG("[gadget] shot %p to %d,%d dmg %d (proj +0xd4 %d)\n", p, tx, ty, dmg, p ? I32(p, 0xd4) : -1);
    return p != NULL;
}
static void *lookup_by_name(uint64_t fn, void *str) {   /* getXByName(String*, referer) (0xad2f1c projectile, 0xad3c30 item) */
    return str && I32(str, 4) > 0 ? ((void *(*)(void *, void *))B(fn))(str, NULL) : NULL;
}
static void *custom_proj(void *ad) { return lookup_by_name(0xad2f1c, ((void *(*)(void *))B(AD_CUSTOM_OBJ))(ad)); }
static void *custom_item(void *ad) { return lookup_by_name(0xad3c30, ((void *(*)(void *))B(AD_CUSTOM_OBJ))(ad)); }
/* a volley of n projectiles over `spread` degrees centred on deg (n = 1: straight) -> how many spawned */
static int volley(void *sim, uint8_t *ch, void *pd, double deg, int n, double spread, int range, int dmg) {
    int k = 0;
    for (int i = 0; i < n; i++) k += shoot(sim, ch, pd, n > 1 ? deg - spread / 2 + spread * i / (n - 1) : deg, range, dmg);
    return k;
}

/* ---- SHOT: the gadget's own skill (Type empty, Skill set, BehaviorType not Charge) fires its projectile */
static void *skill_proj(void *sd) { void **a = sd ? PTR(sd, SD_PROJ) : NULL; return a && I32(sd, SD_PROJ + 0xc) > 0 ? a[0] : NULL; }
static int shot_classify(void *ad, int type) {
    void *sd = type == ACC_PLAIN ? PTR(ad, AD_SKILL) : NULL;
    return sd && !PTR(ad, AD_AREA) && I32(sd, SD_BEHAVIOR) == BT_ATTACK && skill_proj(sd);
}
static int shot_fire(void *sim, Gad *g, uint8_t *ch, double deg, int tick) {
    (void)g; (void)tick;
    void *sd = PTR(g->ad, AD_SKILL); if (I32(ch, 0x3c4) <= 0) return 0;
    int n = sd_get(sd, SD_NBULLETS), cr = sd_get(sd, SD_RANGE);
    n = n < 1 ? 1 : n > 16 ? 16 : n;   /* NumBulletsInOneAttack 1..5 in the gadget rows */
    return volley(sim, ch, skill_proj(sd), deg, n, sd_get(sd, SD_SPREAD), cr > 0 ? cr * 100 : 1000, dmg_scaled(ch, sd_get(sd, SD_DAMAGE))) > 0;
}

/* ---- SKILL AREA: the gadget's skill has no projectile, only an AreaEffectObject: an Attack skill's area at the brawler
 * (Bull's Stomp), an AimableArea skill's at the aim point at its CastingRange (8-Bit's Extra Credits) */
static int skill_area_classify(void *ad, int type) {
    void *sd = type == ACC_PLAIN ? PTR(ad, AD_SKILL) : NULL; int bt = sd ? I32(sd, SD_BEHAVIOR) : -1;
    return sd && !PTR(ad, AD_AREA) && (bt == BT_ATTACK || bt == BT_AIM_AREA) && !skill_proj(sd) && PTR(sd, SD_AREA);
}
static int skill_area_fire(void *sim, Gad *g, uint8_t *ch, double deg, int tick) {
    if (I32(ch, 0x3c4) <= 0 || g->area_at) return 0;
    void *sd = PTR(g->ad, AD_SKILL); int cr = sd_get(sd, SD_RANGE) * 100; double r = deg * M_PI / 180;
    g->area_id = I32(ch, 8); g->area_at = tick; g->area_data = PTR(sd, SD_AREA); g->area_here = I32(sd, SD_BEHAVIOR) != BT_AIM_AREA;
    g->area_x = (int)floor(I32(ch, 0x38) + cr * cos(r) + 0.5); g->area_y = (int)floor(I32(ch, 0x3c) + cr * sin(r) + 0.5);
    area_spawn(sim, g);
    return 1;
}

/* ---- REPEAT: repeat_shot, CustomObject = the projectile, CustomValue1 of them over CustomValue2 degrees (Leaper 5 / 25,
 * Bea 4 / 75, Gene 5 / 80: read as count / spread; a negative spread is taken as its size) at the brawler's main attack
 * range, each with the main attack's damage (the projectile rows have no Damage of their own). The real game's timing
 * (CustomValue3, ActiveTicks) and homing are the projectile's own or not applied. */
static int repeat_classify(void *ad, int type) { return type == ACC_REPEAT && custom_proj(ad) && ad_get(ad, AD_CV1) > 0; }
static int attack_range(uint8_t *ch) { void *sd = SKILL_ATTACK_SD(ch); int cr = sd ? sd_get(sd, SD_RANGE) : 0; return cr > 0 ? cr * 100 : 1000; }
static int attack_dmg(uint8_t *ch) { void *sd = SKILL_ATTACK_SD(ch); return sd ? dmg_scaled(ch, sd_get(sd, SD_DAMAGE)) : 0; }
static int repeat_fire(void *sim, Gad *g, uint8_t *ch, double deg, int tick) {
    (void)tick;
    if (I32(ch, 0x3c4) <= 0) return 0;
    int n = ad_get(g->ad, AD_CV1), sp = abs(ad_get(g->ad, AD_CV2));
    n = n > 16 ? 16 : n;
    return volley(sim, ch, custom_proj(g->ad), deg, n, sp > 360 ? 360 : sp, attack_range(ch), attack_dmg(ch)) > 0;
}

/* ---- SPIN: spin_shoot (Dynamike, Darryl, Mandy... rows with a CustomObject projectile): for ActiveTicks ticks, every
 * CustomValue3 ms a volley of CustomValue1 projectiles evenly around the brawler, turning CustomValue2 degrees per
 * volley, to CustomValue4 units, with the main attack's damage. (Read from the rows: Tnt 2 / 100 / 150 / 700 over 40
 * ticks, Darryl 1 / 25 / 125 / 2500 over 15; the meaning of each value is this reading, not the game's code.) */
static int spin_classify(void *ad, int type) {
    return type == ACC_SPIN && custom_proj(ad) && ad_get(ad, AD_CV1) > 0 && ad_get(ad, AD_ACTIVE_TICKS) > 0;
}
static void spin_volley(void *sim, Gad *g, uint8_t *ch) {
    int n = ad_get(g->ad, AD_CV1), range = ad_get(g->ad, AD_CV4); n = n > 16 ? 16 : n;
    for (int i = 0; i < n; i++) shoot(sim, ch, custom_proj(g->ad), g->spin_ang + 360.0 * i / n, range > 0 ? range : attack_range(ch), attack_dmg(ch));
    g->spin_ang += ad_get(g->ad, AD_CV2);
    int ms = ad_get(g->ad, AD_CV3); g->spin_next += ms > 50 ? ms / 50 : 1;
}
static int spin_fire(void *sim, Gad *g, uint8_t *ch, double deg, int tick) {
    if (I32(ch, 0x3c4) <= 0 || g->spin_end) return 0;
    g->spin_id = I32(ch, 8); g->spin_ang = (int)deg; g->spin_next = tick; g->spin_end = tick + ad_get(g->ad, AD_ACTIVE_TICKS);
    spin_volley(sim, g, ch);
    return 1;
}
static void spin_tick(void *sim, Gad *g, int tick) {
    uint8_t *ch = env_obj_by_id(sim, g->spin_id);
    if (!ch || I32(ch, 0x3c4) <= 0 || tick >= g->spin_end) { g->spin_end = 0; return; }
    while (g->spin_end && tick >= g->spin_next && g->spin_next < g->spin_end) spin_volley(sim, g, ch);
}

/* ---- ITEM: spawn rows whose CustomObject is an items.csv row (Bolt's ElectroTrap, Gale's WindWall): the item at the
 * brawler, through the item factory 0xb55684 as the shipped character-owned item at 0xb583cc calls it (1 item, at most
 * 1 per player: an older one is removed), without the follow call. Spawns of characters (turrets, clones) and areas
 * (meteor, air strike) need summon / targeting code the host does not have: not usable. */
static long g_items;
static int item_classify(void *ad, int type) { return type == ACC_SPAWN && custom_item(ad); }
static int item_fire(void *sim, Gad *g, uint8_t *ch, double deg, int tick) {
    (void)deg; (void)tick;
    if (I32(ch, 0x3c4) <= 0 || !PTR(ch, 0x20)) return 0;
    void *it = ((void *(*)(void *, int, int, int, int, int, int, int, int, int, void *, void *, void *, int))B(0xb55684))(
        custom_item(g->ad), I32(ch, 0x38), I32(ch, 0x3c), 1, 1, 0, 0, I32(ch, 0x80), I32(ch, 0x84), 0, ch, ch, sim, 6);
    if (it) g_items++;
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
    {NBE_GAD_PROJECTILE, repeat_classify, repeat_fire},
    {NBE_GAD_PROJECTILE, spin_classify, spin_fire},
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
    23000352,   /* HookDude_Homing: 5 projectiles, none hit (no homing here) */
    23000399,   /* AssaultShotgun_Bomb: no explosion, no damage */
    23000408,   /* Ninja_InvisibleArea: the invisibility area summon never spawns */
    23001247,   /* Gladiator_Amp: the healing item never spawns */
    23001255,   /* MagicalGirl_FlyArea: the area summon never spawns */
};
static int masked(int card) { for (unsigned k = 0; k < sizeof g_masked / sizeof *g_masked; k++) if (g_masked[k] == card) return 1; return 0; }

void gadget_clear(void) { memset(g_gad, 0, sizeof g_gad); }

/* RESET response (env.c div_publish), per player: its requested card and the accessory object the game made for it */
void gadget_reset_player(int i, void *acc) {
    if (i < 0 || i >= NBE_MAXP) return;
    Gad *g = &g_gad[i]; memset(g, 0, sizeof *g);
    if (!acc || !g_div_gadget[i]) return;
    g->card = g_div_gadget[i]; g->ad = PTR(acc, 0x10); g->pid = i;
    int type = g->type = I32(acc, 0x24);
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
int gadget_use(void *sim, int i, uint8_t *ch, double deg, int tick) {
    if (i < 0 || i >= NBE_MAXP || !g_gad[i].im) return 0;
    Gad *g = &g_gad[i];
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
        if (g_gad[i].spin_end) spin_tick(sim, &g_gad[i], tick);
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
