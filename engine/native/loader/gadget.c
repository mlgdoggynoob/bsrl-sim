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
 *   HEAL  type 8, SubType 2 (Bibi's Vitamin Booster, Byron's Shot in the Arm) and 4 (Meg's, only in her mech: characters.csv
 *         UniqueProperty 2 through 0xab3d04, as env.c mech_pop): heals CustomValue1 % of max hp per second (the card texts
 *         say "per second for N seconds") for ActiveTicks ticks, at most up to max hp, ended by the brawler's death or a
 *         change of character (Meg's eject). ConsumesAmmo (Byron; column word 0x123f7c0, read with the generic bool getter
 *         0xcf6a08) costs one ammo bar and needs one. SubType 6 (Buster) is an AREA, 1 (Sandy) a SELF sleep; 3 (Ash's
 *         rage) is not doable.
 *   AREA  empty Type (+0x24 == 0) with an AreaEffect (AccessoryData +0x70, resolved by createReferences at 0xa92568): the
 *         gadgets that only drop their area at the brawler (Barley's Slow, Poco's Regen and Cleanse, Tick's Explosion,
 *         Shade's Spooky, Trunk's Area; issue #46: Buster's heal, heal SubType 6 with ShieldTankHeal, healing once through
 *         superfix's Heal area path; its per-ally scaling, CustomValue 3, is not modelled: partial). Left out: Rosa's
 *         GrowBush (a WallSpawn area: spawnfix.c's wall ring would put walls where she grows bushes). Meeple's RageQuit
 *         (HpBasedStun) stuns and knocks back through superfix_cc.c (issues #19, #55); the spin_shoot rows without a
 *         projectile (Fang's KickerDude_Sweep, a LineOfSight stun area, and Painter_Push) are AREA too (their spin animation
 *         is the client's). Published as kind SPAWN; `python -m super_audit --gadget` checks each one's effects. The area is spawned
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
 *   BUOY  ulti_change SubType 1 with CustomValue5 (Buzz's Reserve Buoy; SUPER): the super filled, ready only while it is not
 *         full. The card's catch, a next torpedo that does not stun: the host's grapple (superfix_moves.c, Buzz's pull and
 *         landing stun, a server-side re-implementation) asks gadget_buoy_nostun at the landing, which answers yes once per
 *         buoy use for the first landing after it (and forgets it when Buzz dies or changes character).
 *   HEAL_NOW  heal_attached_and_self (Kit) and heal_damage_taken (Kenji: CustomValue2 % of the damage taken in the last
 *         CustomValue1 ticks, the percent as the client's preview 0xb27c5c reads it) (HEAL): an instant heal through libg's
 *         heal 0xb41554.
 *   REPEAT  repeat_shot and spin_shoot rows with a CustomObject projectile other than Piper's Auto Aimer (published PROJECTILE;
 *         issue #54 redo from the game data, see the REPEAT / SPIN block): Dynamike (spin), Gene, Mico, Barley's potion
 *         (repeat). Darryl, Fang's popcorn, Bea and Amber run the same code but stay in g_masked (see there: their
 *         projectiles need more than a plain spawn).
 *   NEXT  next_attack_change (type 23, issue #46; published STATUS): the modifier on the brawler's next main attack. The
 *         host sets the accessory pending (+0x3c), hands libg the accessory through the getter 0xb422c8 (a stub in this
 *         build, replaced by acc_of_char) so the skill tick arms it (+0x54) and the attack code runs its own SubType
 *         branch, clears it when libg calls the "modifier used" stub 0xb27cfc (hook_enter), and adds what the client code
 *         leaves to the server: SubType 2 / 33's enemy status on the shot's hit struct (0xb78c28 hook) and the hit
 *         struct's server-only fields after the damage (gadget_root_post from env.c: 11 sleep, 10 Pam's ammo sink; 3 stun
 *         and 29 lifesteal are coded but their rows are masked). Working live (super_audit --gadget): Mandy Slow, Finx,
 *         Pearl Poison and Healing, Cordelius, Janet, Pam, Doug x2, Sandy, Ollie, Byron, Otis, Belle, Piper, Squeak's
 *         longer throw (16 rows; Squeak's showed no damage until superfix_items.c made his blobs blow; Hank's slow, 32, is
 *         masked: its status never reaches a target).
 *         Not done: SubTypes 5, 6, 8, 13, 17, 18, 19, 25, 27, 28, 30 and Grom's burst (2 without a projectile / range): their
 *         effect has no client code. A pending modifier with no attack is dropped after NEXT_TIMEOUT, and at once when the
 *         brawler dies or changes character [?]. acc_of_char gives the accessory only for the player's own brawler with
 *         a NEXT gadget (summons and the other types get NULL, as the stub gave).
 *   SELF  the gadgets that act on the brawler itself (issue #46, gadget_self.c; published STATUS, Hank's and Lou's SHIELD):
 *         statuses in superfix's store (Jacky, Bonnie, Hank, Lou, Willow, Juju, Kit's box, Surge x2, Trunk, Moe), Draco's
 *         Last Stand, Sandy's sleep, Tara's and Buzz's bush vision. Its header lists what each one does and the guesses.
 * Readiness: a kind may have a ready() test (NEXT: not while a modifier is pending; HEAL: Meg out of her mech, Byron without
 * ammo; BUOY: the super full; SELF: an effect still running, a form gate); while it fails the gadget publishes a
 * cooldown of at least 1 and a fire is refused without spending a use. Cooldown: the accessory's +0xc4, else the Skill's
 * BonusSkillCooldown (getter 0xb0d878, the gadget value of the skill), else its Cooldown (ms / 50). A skill gadget whose
 * skill has MaxCharge > 1 (Shelly's Clay Pigeons, Colette's lifesteal shot: 3, "can be fired 3 times before cooldown")
 * fires that many times per cooldown, the skill's own Cooldown (ms) apart [?]; the cooldown starts after the last one.
 * Its UseWeaponAmmo (a shot costing weapon ammo [?]) is not applied.
 * Every other gadget publishes kind NONE (not usable): summons / turrets, the Charge skills (Brock's jump, Max's dash, ...),
 * weapon / super swaps, the masked rows (g_masked), the not-doable cards below, ... Each player gets GAD_USES uses per
 * battle (unlimited by default, as in the live game since February 2025) and the accessory's cooldown between uses.
 * The accessory's Type parses to the int at +0x24 (0xb2731c: dash 2, spin_shoot 3, heal 8, spawn 9, vision 12,
 * repeat_shot 13, next_attack_change 23, ulti_change 31, movement_speed 37, dive 46, invisible 49, heal_attached_and_self
 * 50, give_buff_to_self 54, charge_ulti 56, heal_damage_taken 58, voodoo_self_buff 60, give_status_effect 63;
 * gadget_self.c's T_* are the same enum).
 * The table is cleared when a new battle is built (env.c env_on_build, before its intro ticks: the old accessories are
 * freed with the old battle) and set up again at the RESET response (gadget_reset_player).
 * Not doable for now (state or code this host does not have; kind NONE): Ash Chill Pill and Rotten Banana (rage meter not
 * modelled), Gus Soul Switcher (spirit storage not found), Nori Sushi Snack (fish count not in the host), Clancy Snappy
 * Shooting (token counter), Kenji Dashi Dash (server attack chain), Alli Cold-Blooded (bloodhunt component state), Glowy
 * More Lumens (tether model), Melodie Perfect Pitch and Interlude (orbiting-note fields), Stu Breakthrough (wall-breaking
 * charge plus debris; CustomValues unknown), Chuck Ghost Train (his two-phase super never runs in the host), Lou Cryo Syrup
 * (no freeze meter when batch 2 was done; superfix_cc.c has one now: for a later batch), Sirius Master of Shadows (shadows
 * not spawned then; superfix_moves.c spawns them now: for a later batch), Eve Motherly Love (no egg-hatch hook), Jessie Recoil
 * Spring (turret attack-timer field not found), Lumi Grim and Frostbitten (no slippery), Amber Fire Starters
 * (PetrolDistribution and its ignition are server-only), Penny Trusty Spyglass (turret attack rules), Draco Upper Cut (no
 * knock-up state; consumed by MountUp at 0xba02b4), Grom Radio Check (burst not in the client code): 22 cards. Not done
 * yet (guesses for later): Edgar's consumable shield, Bolt's speed shield, Nani's Return to Sender, Chester's Candy Beans,
 * Kit's still-standing super charge.
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
#define VTOF(o) ((int)((uint8_t *)PTR(o, 0) - g_libg->base))
enum { VT_CHAR = 0x1209020, VT_ITEM = 0x1209240, VT_ITEM2 = 0x1208ca8, VT_PROJ = 0x1209318 };   /* env.c's vtables */
extern Module *g_libg;
void *hook_replace(Module *m, uint64_t off, void *repl);
void hook_enter(Module *m, uint64_t off, void (*fn)(uint64_t *ctx));
extern int32_t g_div_gadget[NBE_MAXP];   /* env.c: the RESET's requested gadget cards (offline.c puts them in the configs) */
void *env_obj_by_id(void *sim, int id);  /* env.c */
int env_dash_start(uint8_t *ch, int tx, int ty, int speed);   /* env.c: -> path length, 0 = no dash */
/* gadget_self.c: the SELF kinds (statuses, shields, sleep, last stand, vision) */
int gself_kind(void *ad, int type); int gself_published(int sk); int gself_ready(void *sim, int pid, uint8_t *ch, void *ad, int sk);
int gself_fire(void *sim, int pid, uint8_t *ch, void *ad, int card, int sk, int tick);
void gself_note_tick(void *sim, int tick); void gself_clear(void); void gself_root_post(uint8_t *victim, int removed);

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
    int (*ready)(void *sim, Gad *g, uint8_t *ch);   /* optional precondition: 0 = not usable now (published as a cooldown of
                                                     * 1 tick, refused without spending a use); NULL = always */
} GadImpl;
struct Gad {
    int pid, type, card, uses, cd, cd_until, used; void *ad; const GadImpl *im;
    int charges, charge_max, charge_gap;                   /* skill gadgets with MaxCharge > 1: shots left in this cooldown
                                                            * window, MaxCharge, ticks between two of them */
    uint8_t *acc; int not_ready;                           /* the accessory object (player +0x190); ready() said no at the
                                                            * last tick (gadget_tick), what gadget_publish reports */
    int next_at, next_idle, next_hit_tick, next_ch;        /* NEXT: tick of the fire, ticks armed while the attack is over,
                                                            * tick of the last consume (statuses of that attack's shots; -1 =
                                                            * none), the brawler's id at the fire */
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
    int buoy_ch;                                           /* BUOY: the brawler's id at the fire while its next super has not
                                                            * landed yet (0 = none; gadget_buoy_nostun) */
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
    int sub = type == ACC_HEAL ? ad_get(ad, AD_SUBTYPE) : 0;
    return (sub == 2 || sub == 4) && ad_get(ad, AD_CV1) > 0 && ad_get(ad, AD_ACTIVE_TICKS) > 0;
}
#define MECH 2   /* characters.csv UniqueProperty of Meg's mech (0xab3d04, as env.c mech_pop) */
static int consumes_ammo(void *ad) {   /* ConsumesAmmo (column index word 0x123f7c0, no getter in libg: the generic bool 0xcf6a08) */
    return ((int (*)(void *, int))B(0xcf6a08))(PTR(ad, 8), *(int32_t *)B(0x123f7c0));
}
static uint8_t *ammo_skill(uint8_t *ch) { uint8_t **sk = PTR(ch, 0x458); int n = I32(ch, 0x464); return sk && n >= 1 && n <= 16 ? sk[0] : NULL; }
/* Meg's (SubType 4) only in her mech; Byron's (ConsumesAmmo) only with one ammo bar (weapon skill instance +0x18, 1000 a bar)
 * left after his main attacks still queued for the next step start (env_pending_attacks, a bar each): they spend it before
 * the next step's gadget input, so a gadget published ready on the bar they take would be refused (gadget_check) */
int env_pending_attacks(int i);   /* env.c */
static int heal_ready(void *sim, Gad *g, uint8_t *ch) {
    (void)sim;
    if (!ch || I32(ch, 0x3c4) <= 0) return 0;
    if (ad_get(g->ad, AD_SUBTYPE) == 4) { void *cd = ((void *(*)(void *))B(0xb6a384))(ch); if (!cd || ((int (*)(void *))B(0xab3d04))(cd) != MECH) return 0; }
    if (consumes_ammo(g->ad)) { uint8_t *sk = ammo_skill(ch); if (!sk || I32(sk, 0x18) < 1000 * (1 + env_pending_attacks(g->pid))) return 0; }
    return 1;
}
static int heal_fire(void *sim, Gad *g, uint8_t *ch, double deg, int tick) {
    (void)deg;
    int dur = ad_get(g->ad, AD_ACTIVE_TICKS), maxhp = I32(ch, 0x3c8);
    if (I32(ch, 0x3c4) <= 0 || maxhp <= 0 || !heal_ready(sim, g, ch)) return 0;
    if (consumes_ammo(g->ad)) I32(ammo_skill(ch), 0x18) -= 1000;
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
static int area_classify(void *ad, int type) {   /* issue #19 final: also spin_shoot rows with an area and no projectile;
                                                 * issue #46: Buster's heal (heal SubType 6, ShieldTankHeal) */
    void *a = type == ACC_PLAIN || (type == ACC_SPIN && !custom_proj(ad)) || (type == ACC_HEAL && ad_get(ad, AD_SUBTYPE) == 6) ? PTR(ad, AD_AREA) : NULL;
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
/* SkillData MaxCharge (skills.csv; column name at 0x1ec27c, index word 0x1241000+1068): no getter reads it on this table, so
 * the generic int getter 0xcf6a18 (the one the SkillData getters tail-call) on the row, as consumes_ammo does */
static int sd_max_charge(void *sd) { return ((int (*)(void *, int))B(0xcf6a18))(PTR(sd, 8), *(int32_t *)B(0x1241000 + 1068)); }
#define SD_DAMAGE 0xb0dc14
#define SD_SPREAD 0xb0dc6c
#define SD_NBULLETS 0xb0dd0c
#define SD_RANGE 0xb0d948      /* CastingRange, tiles x 100 */
#define SD_FOLLOW 0xc0         /* SkillData +0xc0: AreaEffectFollowType (1 "follow": the area at the brawler; set at 0xb0bafc) */
#define SD_COOLDOWN 0xb0d868   /* Cooldown (skills.csv, ms as the table has it: the getter is the raw column #832) */
#define SD_BONUS_CD 0xb0d878   /* BonusSkillCooldown (skills.csv, ms; column name at 0x1d71fb, index word 0x1241000+1208), the
                                * getter divides by 50: ticks. The skill gadgets' real gadget cooldown (Colt 15000 ms) */
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

/* ---- BUOY: ulti_change SubType 1 with CustomValue5 (Buzz's Reserve Buoy): the super charge filled (+0x54 = +0x58). Ready only
 * while the super is not full (the row's TargetAlreadyActiveText ULTI_ALREADY_CHARGED). The weaker torpedo it brings ("his
 * next Super does not stun"): the fire remembers the brawler (buoy_ch), and the host's grapple (superfix_moves.c, Buzz's pull
 * and landing stun) asks gadget_buoy_nostun when his next torpedo ends, hit or miss; yes once, then the super stuns again.
 * A new brawler object (death, character change) has another id, so the catch is dropped with it [?]. */
#define AD_CV5 0xa93410
enum { ACC_ULTI_CHANGE = 31 };
static int buoy_classify(void *ad, int type) { return type == ACC_ULTI_CHANGE && ad_get(ad, AD_SUBTYPE) == 1 && ad_get(ad, AD_CV5) > 0; }
static int buoy_ready(void *sim, Gad *g, uint8_t *ch) {
    uint8_t *p = player_of(sim, g->pid); return p && ch && I32(ch, 0x3c4) > 0 && I32(p, 0x58) > 0 && I32(p, 0x54) < I32(p, 0x58);
}
static int buoy_fire(void *sim, Gad *g, uint8_t *ch, double deg, int tick) {
    (void)deg; (void)tick;
    uint8_t *p = player_of(sim, g->pid); if (!buoy_ready(sim, g, ch)) return 0;
    I32(p, 0x54) = I32(p, 0x58); g->buoy_ch = I32(ch, 8);
    return 1;
}
static long g_buoy_nostun;
/* superfix_moves.c's grapple, at the end of a torpedo of brawler ch: -> 1 = it is the first super after a buoy (no landing
 * stun), and the buoy's catch is used up */
int gadget_buoy_nostun(uint8_t *ch) {
    if (!ch) return 0;
    for (int i = 0; i < NBE_MAXP; i++)
        if (g_gad[i].buoy_ch && g_gad[i].buoy_ch == I32(ch, 8)) { g_gad[i].buoy_ch = 0; g_buoy_nostun++; return 1; }
    return 0;
}

/* ---- HEAL_NOW: instant heals through libg's heal 0xb41554 (capped at max hp, the game's heal modifiers apply)
 *   heal_attached_and_self (Kit's Cheeseburger): CustomValue1 % of max hp to Kit (the attached ally is not healed: the
 *     host's attach, superfix_moves.c, keeps no link this gadget reads yet; the card's flat <VALUE1> = Value 70 has an
 *     unknown scale, so CV1 30 is read as %)
 *   heal_damage_taken (Kenji): CustomValue2 % (50) of the damage taken in the last CustomValue1 ticks (60 = 3 s; the
 *     host keeps the hp lost per tick for every player with this gadget, gadget_tick). The client's preview 0xb27c5c computes
 *     (acc +0x88 - w1) * CustomValue2 / 100, so CustomValue2 is the percent; [?] CustomValue1 as the window in ticks */
static int heal_now_classify(void *ad, int type) {
    return (type == ACC_HEAL_SELF && ad_get(ad, AD_CV1) > 0) || (type == ACC_HEAL_TAKEN && ad_get(ad, AD_CV1) > 0 && ad_get(ad, AD_CV2) > 0);
}
static int damage_taken(Gad *g, int tick, int ticks) {
    int s = 0; ticks = ticks > 100 ? 100 : ticks;
    for (int t = tick - ticks + 1; t <= tick; t++) s += g->hp_lost[((t % 100) + 100) % 100];
    return s;
}
static int heal_now_fire(void *sim, Gad *g, uint8_t *ch, double deg, int tick) {
    (void)sim; (void)deg;
    int hp = I32(ch, 0x3c4), mx = I32(ch, 0x3c8), cv1 = ad_get(g->ad, AD_CV1), amt;
    if (hp <= 0 || mx <= 0) return 0;
    if (g->type == ACC_HEAL_TAKEN) amt = (int)((int64_t)damage_taken(g, tick, cv1) * ad_get(g->ad, AD_CV2) / 100);
    else amt = (int)((int64_t)mx * cv1 / 100);
    if (amt > 0 && hp < mx)   /* a use is spent even when there is nothing to heal (the game's button has no such check) */
        ((void (*)(void *, int, int, int, void *, int, int, int, long, long))B(0xb41554))(ch, g->pid, amt, 1, NULL, 0, 0, 0, 0, 0);
    return 1;
}
static void taken_tick(void *sim, Gad *g, int tick) {   /* hp lost this tick (a heal or a respawn counts as 0) */
    uint8_t *ch = char_of(sim, g->pid); int hp = ch ? I32(ch, 0x3c4) : 0, k = ((tick % 100) + 100) % 100;
    g->hp_lost[k] = hp > 0 && g->hp_prev > hp ? g->hp_prev - hp : 0; g->hp_prev = hp;
}

/* ---- NEXT: next_attack_change (Type 23): one modifier on the brawler's next main attack, used up by it. The client attack
 * code applies most SubTypes itself once the accessory is armed (see the header); the host only sets it pending (+0x3c),
 * gives libg the accessory (acc_of_char), clears it when libg consumes it, and adds the hit effects libg leaves to the
 * server (next_root_post) and SubType 2 / 33's enemy status (on_hit_struct). */
enum { ACC_NEXT = 23, ACC_ACTIVE = 0x3c, ACC_ARMED = 0x54, ACC_ARMED_SUPER = 0x55, AD_SE_ENEMY = 0x60 };
#define NEXT_TIMEOUT 200   /* ticks a pending modifier waits for an attack before the host drops it (10 s) [?] the game keeps
                            * it until the next attack (ActiveTicks 100000); the timeout guards against an attack path that
                            * never arms it */
#define NEXT_IDLE 20       /* ticks an armed modifier may sit with char +0x4f4 at 0 before the host drops it (1 s): libg
                            * consumes some SubTypes at the hit, not the shot (Alli 4 ticks after arming at 0xb3e1ac, Pearl's
                            * heal 10 ticks at 0xb3b800), and +0x4f4 stayed 0 for every armed attack the audit logged */
static int g_next_on = -1;   /* NB_GAD_NEXT=0: the kind is off (rows publish NONE) and its hooks are not installed */
static long g_next_fired, g_next_armed, g_next_consumed, g_next_fallback, g_next_timeout, g_next_dead, g_next_se, g_next_stun,
            g_next_sleep, g_next_wake, g_next_steal, g_next_ammo;
static uint64_t g_cons_lr[24]; static long g_cons_n[24];   /* consume sites (return address) and counts, for the log */
static int next_dbg(void) { static int d = -1; if (d < 0) { const char *e = getenv("NB_GAD_DBG"); d = e && atoi(e) > 0; } return d; }
static int next_classify(void *ad, int type) {
    if (type != ACC_NEXT || !g_next_on) return 0;
    switch (ad_get(ad, AD_SUBTYPE)) {
    case 2: return custom_proj(ad) || ad_get(ad, AD_CV1) > 0;   /* projectile swap / range; Grom's burst (neither) is not in libg */
    case 3: case 10: case 11: case 29: return 1;                /* server-only hit fields: next_root_post */
    case 7: case 14: case 15: case 16: case 21: case 23: case 24: case 32: case 33: return 1;   /* libg's own branches; 33: on_hit_struct */
    default: return 0;   /* 5, 6, 8, 13, 17, 18, 19, 25, 27, 28, 30: effects with no client code, not re-implemented yet */
    }
}
static void next_clear(uint8_t *acc) { U8(acc, ACC_ACTIVE) = 0; U8(acc, ACC_ARMED) = 0; U8(acc, ACC_ARMED_SUPER) = 0; }
static int next_ready(void *sim, Gad *g, uint8_t *ch) { (void)sim; (void)ch; return g->acc && !U8(g->acc, ACC_ACTIVE); }
static int next_fire(void *sim, Gad *g, uint8_t *ch, double deg, int tick) {
    (void)sim; (void)deg;
    if (!g->acc || I32(ch, 0x3c4) <= 0 || U8(g->acc, ACC_ACTIVE)) return 0;
    U8(g->acc, ACC_ACTIVE) = 1; U8(g->acc, ACC_ARMED) = 0; g->next_at = tick; g->next_idle = 0; g->next_ch = I32(ch, 8); g_next_fired++;
    if (next_dbg()) LOG("[gadget] next: player %d card %d subtype %d pending at tick %d\n", g->pid, g->card, ad_get(g->ad, AD_SUBTYPE), tick);
    return 1;
}
/* gadget_tick: an armed modifier whose attack is over (char +0x4f4, the attack's active ms, 0 for NEXT_IDLE ticks) without a consume
 * this host reaches, or a pending one no attack armed within NEXT_TIMEOUT, is dropped; so is any one whose brawler died or
 * changed (another character id) [?] the game is taken to clear it on death; without this the first attack after a
 * respawn could still carry it. A drop does not set next_hit_tick: only a real consume (on_consume) marks the shots of
 * its tick for on_hit_struct. */
static void next_tick(void *sim, Gad *g, int tick) {
    uint8_t *acc = g->acc, *ch = char_of(sim, g->pid); const char *why = NULL;
    if (!acc || !U8(acc, ACC_ACTIVE)) { g->next_idle = 0; return; }
    if (!ch || I32(ch, 0x3c4) <= 0 || I32(ch, 8) != g->next_ch) { next_clear(acc); g_next_dead++; why = "brawler dead or changed"; }
    else if (U8(acc, ACC_ARMED)) {
        if (I32(ch, 0x4f4) <= 0) { if (++g->next_idle >= NEXT_IDLE) { next_clear(acc); g_next_fallback++; why = "attack over"; } }
        else g->next_idle = 0;
    } else if (tick - g->next_at >= NEXT_TIMEOUT) { next_clear(acc); g_next_timeout++; why = "timeout"; }
    if (next_dbg() && why) LOG("[gadget] next: player %d dropped at tick %d (%s)\n", g->pid, tick, why);
}
static Gad *gad_of_acc(uint8_t *acc) { for (int i = 0; i < NBE_MAXP; i++) if (g_gad[i].acc == acc && g_gad[i].im) return &g_gad[i]; return NULL; }
static int sim_tick(void *obj) { uint8_t *sim = ((void *(*)(void *))B(0xb6a378))(obj); return sim ? I32(sim, 0x10) : -1; }
/* hook_replace of 0xb422c8 (`mov x0, xzr; ret`, 5 callers: the skill tick's arming at 0xb7b540 / 0xb81f9c and 0xb7fc10,
 * 0xb82464, 0xb842ac): the character's accessory, player(ch) +0x190. With it the arming at 0xb7b588 / 0xb81fe4 runs (acc
 * +0x3c set, type 0x17, the skill instance's kind +68 == 1 = weapon, char +0x4f4 > 0) and sets +0x54. Only for the
 * player's current brawler (0xb6a718 maps a summon with an owner index to its owner too: its skill tick must not arm or
 * use up the owner's modifier) and only for a NEXT gadget the host set up (0xb842ac's cooldown write for the other types
 * and 0xb7c1cc's +0x55 arming of ulti_change stay off, as with the stub): else NULL, the stub's answer. */
static void *acc_of_char(uint8_t *ch) {
    if (!ch || VTOF(ch) != VT_CHAR) return NULL;
    uint8_t *p = ((uint8_t *(*)(void *))B(0xb6a718))(ch), *sim = ((void *(*)(void *))B(0xb6a378))(ch);
    int pid = I32(ch, 0x80);
    if (!p || !sim || pid < 0 || pid >= NBE_MAXP || player_of(sim, pid) != p || char_of(sim, pid) != ch) return NULL;
    Gad *g = &g_gad[pid];
    return g->im && g->type == ACC_NEXT && g->acc && g->acc == PTR(p, 0x190) ? g->acc : NULL;
}
/* hook_enter of 0xb27cfc (a bare `ret`, 20 call sites; x0 = accessory, x1 = character): libg's "modifier used". For type
 * 0x17 the host clears it; other types (swap_weapon 0x3b, activate_skill 0x34) are not the host's */
static void on_consume(uint64_t *ctx) {
    uint8_t *acc = (uint8_t *)ctx[0];
    if (!acc || I32(acc, 0x24) != ACC_NEXT) return;
    Gad *g = gad_of_acc(acc); int armed = U8(acc, ACC_ARMED);
    if (armed) g_next_armed++;
    next_clear(acc); g_next_consumed++;
    if (g && ctx[1]) g->next_hit_tick = sim_tick((void *)ctx[1]);
    int k; for (k = 0; k < 24 && g_cons_lr[k] && g_cons_lr[k] != ctx[9]; k++) {}
    if (k < 24) { g_cons_lr[k] = ctx[9]; g_cons_n[k]++; }
    if (next_dbg()) LOG("[gadget] next: consumed (armed %d) player %d from %#lx\n", armed, g ? g->pid : -1, (unsigned long)(ctx[9] - (uint64_t)g_libg->base));
}
/* hook_enter of 0xb78c28(projectile, hit struct, flag) (the hit struct -> projectile +0x468 copy, 6 callers: the attack
 * 0xb4b79c's spawns, 0xb7d3a8, 0xb8f670). SubType 2 swaps (Ollie, Finx) and 33 (Mandy's slow) carry a StatusEffectEnemy that
 * libg's attack copies only for SubTypes 14 / 23: written to struct +0xd0 here (-> projectile +0x538, applied on hit at
 * 0xb721f0) for a shot of the owner's brawler while its modifier is armed, or consumed in this tick (SubType 2 consumes
 * before the spawn, 0xb4bf1c). */
static void on_hit_struct(uint64_t *ctx) {
    uint8_t *pr = (uint8_t *)ctx[0], *st = (uint8_t *)ctx[1], *ow = pr ? PTR(pr, 0xe0) : NULL;
    if (!st || !ow || VTOF(ow) != VT_CHAR) return;
    int pid = I32(ow, 0x80); if (pid < 0 || pid >= NBE_MAXP) return;
    Gad *g = &g_gad[pid]; if (!g->im || g->type != ACC_NEXT || !g->acc) return;
    int sub = ad_get(g->ad, AD_SUBTYPE); void *se = PTR(g->ad, AD_SE_ENEMY);
    if ((sub != 2 && sub != 33) || !se || PTR(st, 0xd0)) return;
    void *sim = ((void *(*)(void *))B(0xb6a378))(ow);
    if (!sim || char_of(sim, pid) != ow) return;   /* the brawler's own shot, not a summon's */
    int armed = U8(g->acc, ACC_ACTIVE) && U8(g->acc, ACC_ARMED);
    if (!armed && g->next_hit_tick != I32(sim, 0x10)) return;
    PTR(st, 0xd0) = se; g_next_se++;
    if (next_dbg()) LOG("[gadget] next: player %d shot %p gets status %p (subtype %d)\n", pid, pr, se, sub);
}
/* server-only hit fields the armed attack wrote into its hit struct (projectile +0x468, an area of it +0x168; no client
 * reader), applied from env.c's damage root after the hit (gadget_root_post): SubType 3 struct +0x10 stun ticks (Dynamike
 * 30), 11 +0x174 / +0x178 sleep ticks / flag (Sandy 20: a stun the victim's next damage ends), 29 +0xc4 lifesteal percent
 * (Alli 100: libg's heal 0xb41554 of the damage dealt), 10 +0x16c / +0x170 (Pam 25 / 50: the victim loses that percent of
 * its full ammo, Pam gets that percent of it; ammo = weapon skill instance +0x18, 1000 a bar, full = 0xb7aea4 x 1000). Only
 * for a hit of the player's own brawler whose gadget has that SubType. Stuns go through superfix_cc (immunity, the stop).
 * Dynamike's (3) and Alli's (29) rows are masked: their hits reach the root with no source object / not at all. */
int superfix_cc_stun(uint8_t *ch, int ticks, const char *why) __attribute__((weak));
typedef struct { uint8_t *ch; int id, until; void *src; } Sleep;
static Sleep g_sleep[NBE_MAXP]; static int g_nsleep;
static int max_ammo(uint8_t *ch, uint8_t **sk0) {
    uint8_t **sk = PTR(ch, 0x458); int n = I32(ch, 0x464);
    *sk0 = sk && n >= 1 && n <= 16 ? sk[0] : NULL; if (!*sk0) return 0;
    int m = ((int (*)(void *, void *))B(0xb7aea4))(*sk0, ch) * 1000;
    return m > 1000 ? m : 1000;
}
void gadget_root_post(uint8_t *victim, uint8_t *attacker, uint8_t *src, int removed) {
    if (!victim || VTOF(victim) != VT_CHAR) return;
    gself_root_post(victim, removed);   /* the SELF kinds: CancelOnDamage, Sandy's sleep */
    int t = sim_tick(victim);
    for (int i = 0; i < g_nsleep; i++) {   /* a sleeping victim wakes on the next damage (not the hit that put it to sleep) */
        Sleep *s = &g_sleep[i];
        if (s->until <= t) { g_sleep[i--] = g_sleep[--g_nsleep]; continue; }   /* slept it out */
        if (s->ch != victim || s->id != I32(victim, 8) || removed <= 0 || src == s->src) continue;
        int left = s->until - t, st = I32(victim, 0xe1c);   /* only the sleep's own ticks: a longer stun from elsewhere stays */
        I32(victim, 0xe1c) = st > left ? st - left : 0; g_next_wake++; g_sleep[i--] = g_sleep[--g_nsleep];
        if (next_dbg()) LOG("[gadget] next: ch %d woken by damage at tick %d\n", I32(victim, 8), t);
    }
    if (!attacker || !src || VTOF(attacker) != VT_CHAR) return;
    int pid = I32(attacker, 0x80); if (pid < 0 || pid >= NBE_MAXP) return;
    Gad *g = &g_gad[pid]; if (!g->im || g->type != ACC_NEXT) return;
    int sub = ad_get(g->ad, AD_SUBTYPE); if (sub != 3 && sub != 10 && sub != 11 && sub != 29) return;
    int vs = VTOF(src); uint8_t *d = PTR(src, 0x10), *hs = NULL;
    if (vs == VT_PROJ) hs = src + 0x468;
    else if ((vs == VT_ITEM || vs == VT_ITEM2) && d && I32(d, 0x20) / 1000000 == 17) hs = src + 0x168;   /* an area (data type 17) */
    if (!hs) return;
    void *sim = ((void *(*)(void *))B(0xb6a378))(attacker);
    if (!sim || char_of(sim, pid) != attacker) return;
    if (sub == 3 && I32(hs, 0x10) > 0 && superfix_cc_stun) { superfix_cc_stun(victim, I32(hs, 0x10), "gadget next attack"); g_next_stun++; }
    if (sub == 11 && U8(hs, 0x178) && I32(hs, 0x174) > 0 && superfix_cc_stun && superfix_cc_stun(victim, I32(hs, 0x174), "gadget sleep")) {
        int k; for (k = 0; k < g_nsleep && !(g_sleep[k].ch == victim && g_sleep[k].id == I32(victim, 8)); k++) {}
        if (k == g_nsleep && g_nsleep < NBE_MAXP) g_nsleep++;
        if (k < g_nsleep) g_sleep[k] = (Sleep){victim, I32(victim, 8), t + I32(hs, 0x174), src};
        g_next_sleep++;
    }
    if (sub == 29 && I32(hs, 0xc4) > 0 && removed > 0 && I32(attacker, 0x3c4) > 0) {
        int amt = (int)((int64_t)removed * I32(hs, 0xc4) / 100);
        if (amt > 0) ((void (*)(void *, int, int, int, void *, int, int, int, long, long))B(0xb41554))(attacker, pid, amt, 1, NULL, 0, 0, 0, 0, 0);
        g_next_steal++;
        if (next_dbg()) LOG("[gadget] next: player %d lifesteal %d of %d\n", pid, amt, removed);
    }
    if (sub == 10 && I32(hs, 0x16c) > 0 && removed > 0) {
        uint8_t *vk, *ak; int vm = max_ammo(victim, &vk), am = max_ammo(attacker, &ak);
        if (vk && ak) {
            int take = (int)((int64_t)vm * I32(hs, 0x16c) / 100); if (take > I32(vk, 0x18)) take = I32(vk, 0x18); if (take < 0) take = 0;
            int give = (int)((int64_t)take * I32(hs, 0x170) / 100);
            I32(vk, 0x18) -= take; I32(ak, 0x18) = I32(ak, 0x18) + give < am ? I32(ak, 0x18) + give : am;
            g_next_ammo++;
            if (next_dbg()) LOG("[gadget] next: player %d ammo sink: victim -%d, Pam +%d\n", pid, take, give);
        }
    }
}
static void next_install(void) {
    const char *e = getenv("NB_GAD_NEXT"); g_next_on = !(e && !atoi(e));
    if (!g_next_on) { LOG("[gadget] next attack gadgets off (NB_GAD_NEXT=0)\n"); return; }
    if (*(uint32_t *)B(0xb422c8) != 0xaa1f03e0 || *(uint32_t *)B(0xb422cc) != 0xd65f03c0 ||   /* mov x0, xzr; ret */
        *(uint32_t *)B(0xb27cfc) != 0xd65f03c0 ||                                              /* ret */
        *(uint32_t *)B(0xb78c28) != 0xa9be7bfd) {                                              /* stp x29, x30, [sp, #-32]! */
        LOG("[gadget] libg bytes differ from v68.279: next attack gadgets off\n"); g_next_on = 0; return;
    }
    hook_replace(g_libg, 0xb422c8, (void *)acc_of_char);
    hook_enter(g_libg, 0xb27cfc, on_consume);
    hook_enter(g_libg, 0xb78c28, on_hit_struct);
    LOG("[gadget] next attack gadgets: accessory getter 0xb422c8, consume 0xb27cfc, hit struct 0xb78c28 hooked\n");
}

/* ---- SELF: statuses, shields, a sleep, a last stand, bush vision on the brawler itself (gadget_self.c) */
static int self_shield_classify(void *ad, int type) { int k = gself_kind(ad, type); return k && gself_published(k) == NBE_GAD_SHIELD; }
static int self_status_classify(void *ad, int type) { int k = gself_kind(ad, type); return k && gself_published(k) == NBE_GAD_STATUS; }
static int self_ready(void *sim, Gad *g, uint8_t *ch) { return gself_ready(sim, g->pid, ch, g->ad, gself_kind(g->ad, g->type)); }
static int self_fire(void *sim, Gad *g, uint8_t *ch, double deg, int tick) {
    (void)deg; return gself_fire(sim, g->pid, ch, g->ad, g->card, gself_kind(g->ad, g->type), tick);
}

static const GadImpl g_impl[] = {
    {NBE_GAD_DASH, dash_classify, dash_fire},
    {NBE_GAD_HEAL, heal_classify, heal_fire, heal_ready},
    {NBE_GAD_SPAWN, area_classify, area_fire},
    {NBE_GAD_PROJECTILE, shot_classify, shot_fire},
    {NBE_GAD_SPAWN, skill_area_classify, skill_area_fire},
    {NBE_GAD_PROJECTILE, auto_aim_classify, auto_aim_fire},
    {NBE_GAD_PROJECTILE, rep_classify, rep_fire},
    {NBE_GAD_SPAWN, item_classify, item_fire},
    {NBE_GAD_SUPER, super_classify, super_fire},
    {NBE_GAD_HEAL, heal_now_classify, heal_now_fire},
    {NBE_GAD_STATUS, next_classify, next_fire, next_ready},
    {NBE_GAD_SUPER, buoy_classify, buoy_fire, buoy_ready},
    {NBE_GAD_SHIELD, self_shield_classify, self_fire, self_ready},
    {NBE_GAD_STATUS, self_status_classify, self_fire, self_ready},
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
    /* REPEAT rows whose shots fly but do not work (super_audit --gadget, then a traced test build): */
    23000260,   /* BarrelBot_Spin: each shot stops ~1280 u out and hits only there (600 on a target 1500 u away); enemies it
                 * passes on the way (300, 875 u) take nothing */
    23000440,   /* KickerDude_Mines: the kernels rise and vanish ~670 u out; the mines they leave never pop, no damage */
    23000312,   /* BeeSniper_ExtraBee: the circling bees spawn at the map origin (0, 0) and stay there, not around Bea */
    23000488,   /* FireDude_FlameShield: the orbiting flames spawn at the map origin (0, 0) and stay there, not around Amber */
    23000294,   /* TntDude_Stun: armed and consumed, but the explosion's damage reaches env.c's root with no source object, so
                 * the hit struct's stun (+0x10) is never read: no stun */
    23000522,   /* ShieldTank_Pull: consumed (0xb4e314), no pull */
    23000546,   /* Beamer_Pierce: armed, never consumed in 20 ticks, no pierce */
    23000678,   /* InsectMan_Pierce: armed, never consumed in 20 ticks, no pierce */
    23000991,   /* Stalker_Lifesteal: consumed at the hit (0xb3e1ac), but the dash damage never reaches env.c's root: no heal */
    23000579,   /* FishTank_Slow: armed and consumed (0xb7fcd0, which puts the row's StatusEffectEnemy in the attack's hit struct
                 * +0xf8), but no FishTankGadgetAreaSlow is ever added to a target (NB_SUPERFIX_DBG): a plain attack */
};
static int masked(int card) { for (unsigned k = 0; k < sizeof g_masked / sizeof *g_masked; k++) if (g_masked[k] == card) return 1; return 0; }

/* a new battle was built (env.c env_on_build) and its RESET response (div_publish): the last battle's NEXT counters (when any
 * modifier was used; logged once, then zeroed), then a clean table. Called at the build too because the old battle's
 * accessories are freed by then and its intro ticks run gadget_tick before the RESET response. */
void gadget_clear(void) {
    if (g_next_fired) {
        LOG("[gadget] next attack: %ld pending, %ld consumed (%ld armed), dropped %ld (attack over) / %ld (timeout); statuses on shots %ld, "
            "stuns %ld, sleeps %ld (woken %ld), lifesteals %ld, ammo sinks %ld; brawler dead / changed %ld\n", g_next_fired,
            g_next_consumed, g_next_armed, g_next_fallback, g_next_timeout, g_next_se, g_next_stun, g_next_sleep, g_next_wake,
            g_next_steal, g_next_ammo, g_next_dead);
        for (int k = 0; k < 24 && g_cons_lr[k]; k++) LOG("[gadget] next attack: consume from %#lx x%ld\n", (unsigned long)(g_cons_lr[k] - (uint64_t)g_libg->base), g_cons_n[k]);
    }
    g_next_fired = g_next_armed = g_next_consumed = g_next_fallback = g_next_timeout = g_next_dead = g_next_se = g_next_stun = 0;
    g_next_sleep = g_next_wake = g_next_steal = g_next_ammo = 0; memset(g_cons_lr, 0, sizeof g_cons_lr); memset(g_cons_n, 0, sizeof g_cons_n);
    if (g_buoy_nostun) LOG("[gadget] reserve buoy: %ld torpedoes without the landing stun\n", g_buoy_nostun);
    g_buoy_nostun = 0;
    memset(g_gad, 0, sizeof g_gad); g_nsleep = 0; gself_clear();
}

/* RESET response (env.c div_publish), per player: its requested card and the accessory object the game made for it */
void gadget_reset_player(int i, void *acc) {
    if (i < 0 || i >= NBE_MAXP) return;
    Gad *g = &g_gad[i]; memset(g, 0, sizeof *g); g->next_hit_tick = -1;
    if (!acc || !g_div_gadget[i]) return;
    g->card = g_div_gadget[i]; g->ad = PTR(acc, 0x10); g->pid = i; g->acc = acc;
    int type = g->type = I32(acc, 0x24); g_cls_card = g->card;
    for (const GadImpl *im = g_impl; g->ad && !masked(g->card) && im->classify; im++)
        if (im->classify(g->ad, type)) {
            static int uses = -1; if (uses < 0) { const char *e = getenv("NB_GAD_USES"); uses = e && atoi(e) > 0 ? atoi(e) : GAD_USES; }
            g->im = im; g->uses = uses; g->cd = I32(acc, 0xc4) > 0 ? I32(acc, 0xc4) : 0;
            /* the skill gadgets' rows leave Cooldown empty: their skill's BonusSkillCooldown (skills.csv, ms, the getter
             * gives ticks: Colt's Speedloader 15000 ms = 300 ticks), else its Cooldown (ms / 50 = ticks; no classified row
             * has an empty BonusSkillCooldown) */
            if (!g->cd && PTR(g->ad, AD_SKILL)) {
                void *sd = PTR(g->ad, AD_SKILL); int c = sd_get(sd, SD_BONUS_CD), mc = c > 0 ? sd_max_charge(sd) : 1;
                if (c <= 0) c = sd_get(sd, SD_COOLDOWN) / 50;
                g->cd = c > 0 ? c : 0;
                if (mc > 1 && mc <= 9) {   /* MaxCharge shots per cooldown, the skill's Cooldown (ms: 250 = 5 ticks) apart [?] */
                    int gap = sd_get(sd, SD_COOLDOWN) / 50;
                    g->charge_max = g->charges = mc; g->charge_gap = gap > 0 ? gap : 1;
                }
            }
            if (type == ACC_NEXT) next_clear(acc);   /* nothing pending from the accessory's construction */
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
    if (g->im->ready && (g->not_ready || !g->im->ready(sim, g, ch))) return 1;   /* published as not ready: refused, nothing spent */
    if (g->im->fire(sim, g, ch, deg, tick)) {
        g->uses--; g->used++; g->cd_until = tick + g->cd;
        if (g->charge_max > 1) {   /* a shot of a MaxCharge window: the next one after charge_gap, the cooldown after the last */
            if (--g->charges > 0) g->cd_until = tick + g->charge_gap; else g->charges = g->charge_max;
        }
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
        if (g_gad[i].im && g_gad[i].type == ACC_NEXT) next_tick(sim, &g_gad[i], tick);
        if (g_gad[i].im && g_gad[i].im->ready) g_gad[i].not_ready = !g_gad[i].im->ready(sim, &g_gad[i], char_of(sim, i));
    }
    gself_note_tick(sim, tick);   /* SELF: Sandy's wake-up heal; the tick gadget_vision answers for */
}
/* env.c, right before gadget_publish: ready() again on the state the response describes. gadget_tick's answer is from the
 * start of the step's last tick, before that tick's attacks (Byron's ammo bar spent by his attack read as ready, and the
 * fire on the next step was refused: gadget_check "use not spent"; heal_ready also counts the attacks queued for the
 * next step start) */
void gadget_ready_refresh(void *sim) {
    for (int i = 0; i < NBE_MAXP; i++)
        if (g_gad[i].im && g_gad[i].im->ready) g_gad[i].not_ready = !g_gad[i].im->ready(sim, &g_gad[i], char_of(sim, i));
}

void gadget_publish(NbeResp *r, int tick) {   /* every response */
    r->gad_valid = 1;
    for (int i = 0; i < NBE_MAXP; i++) {
        const Gad *g = &g_gad[i];
        r->gad_card[i] = g->card; r->gad_kind[i] = g->im ? g->im->kind : NBE_GAD_NONE; r->gad_charges[i] = g->im ? g->uses : 0;
        r->gad_cd[i] = g->im && g->cd_until > tick ? g->cd_until - tick : 0; r->gad_used[i] = g->used;
        if (g->im && g->not_ready && r->gad_cd[i] < 1) r->gad_cd[i] = 1;   /* ready() said no: "not usable now" without an obs change */
    }
}

void gadget_install(void) { next_install(); }   /* env.c's install, once at startup: the NEXT kind's hooks */
