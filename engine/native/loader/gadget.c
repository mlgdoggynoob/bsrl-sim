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
 *         (env.c env_dash_start). Extras (issue #46 batch 4): a row's AreaEffect at the start point (Maisie's MaisieDashArea,
 *         a Stun area: superfix_cc stuns the enemies in it for its CustomValue, 10 ticks), and SubType 3's CustomValue3 / 100
 *         ammo bars back (Clancy). Not applied: Bonnie's and Moe's knockback and damage (CustomValue3 / 4), Moe's wall
 *         breaking, Ollie's taunt (CustomObject), the Twins' dash to each other and heal, and the "requires ..." conditions
 *         (MissingTargetText).
 *   CHARGE  an empty Type with a Skill whose BehaviorType is Charge (Brock, Max, Shelly, Glowy, Bolt, Wendy), and
 *         activate_skill (52) naming a Charge skill in CustomObject (Angelo; issue #46 batch 4; published DASH): the skill's
 *         own charge with its ChargeType and speed through env.c env_charge_start, its areas at take-off / landing, its
 *         ActivationSelfStatusEffects (Max's shield while dashing) and its Reload flag (Shelly's full reload). See the
 *         CHARGE block for the distances and the guesses.
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
 *   SHOT  empty Type, no AreaEffect, a Skill whose BehaviorType is Attack with Projectiles (31 rows: Spike, Colt x2, Brock,
 *         Shelly, Emz x2, ...; published PROJECTILE): NumBulletsInOneAttack of the skill's first projectile over Spread degrees
 *         centred on the aim, to CastingRange, with the skill's Damage scaled by the brawler's damage percent (0xb4b660, as the
 *         attack path scales it), spawned with the projectile spawn 0xb78190 (spawnfix.c) at kind 4. A skill with
 *         SummonedCharacters or a SpawnedItem gets its projectiles armed the way libg's attack path arms them (arm_shot:
 *         0xb703c8 / 0xb79130, which 0xb78190 alone skips), so the projectile's end spawns the summon (Bo's totem, Leon's
 *         smoke, Starr Nova's fly area, Spike's cactus) or the item (Damian's microphone; issue #64). What the projectile
 *         does on hit or at its end (areas, items, summons, pull / push) is then libg's and the earlier rounds'. A projectile
 *         row with DamageOnlyWithOneProj (Emz's spray) damages each target with one projectile of the volley only, through
 *         the attack path's sibling list (volley). The skill's timing (ActiveTime, MsBetweenAttacks waves) is not read:
 *         g_waves lists the cards whose description names more waves (Colt's Gunslinger_Reload: two shots, issue #55).
 *         Not applied: TwoGuns, AttackPattern. Type 76 aim_with_gadget_collision (Rico's Multiball Launcher) is a SHOT too: the
 *         type only bends the client's aim line; the container its shot leaves bursts into bouncing bullets when it is
 *         destroyed by libg itself (issue #46 batch 3b: a live run, TrickshotDudeAccessoryExplosion and its 8 bullets through
 *         spawnfix.c's BulletExplosion). A skill with UseWeaponAmmo (Frank's Pull, Shelly's Clay Pigeons, ...) needs
 *         and spends one weapon ammo bar per fire [?] (shot_ready, issue #64).
 *   REWIND  Max's Speedy_Rewind (card 23000311 only; published PROJECTILE; issue #64): the skill's bolt at the aim, whose
 *         end spawns its SpeedyRewindArea (libg); when the area runs out (3 s), or at a second fire while it is up (the
 *         card's "reactivate"), the host teleports Max to it (superfix_teleport) and heals her back to her HP at the throw.
 *         No cooldown while the rewind is pending; Max's death drops it. See the REWIND block.
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
 *   SUMMON  spawn rows whose CustomObject is a characters.csv row, SubType 1 / 2 / 5 (issue #46 batch 3b; SPAWN): the summon
 *         from libg's summon factory 0xb56e00 at the brawler (1: Penny, Bea, Grom, Janet, Stu; 2: Leon's clone) or
 *         CustomValue1 of them CustomValue2 out (5: Tara and Charlie around the brawler, Ruffs' sandbags in an arc towards the
 *         aim with CustomValue4 % of his max HP); Tara's shadows go after CustomValue3 ticks, Grom's watchtower answers the
 *         bush hiding (gadget_summon_vision). See the SUMMON block for the guesses.
 *   SUPER charge_ulti (R-T; published SUPER): the super charge to CustomValue1 % of its maximum.
 *   BUOY  ulti_change SubType 1 with CustomValue5 (Buzz's Reserve Buoy; SUPER): the super filled, ready only while it is not
 *         full. The card's catch, a next torpedo that does not stun: the host's grapple (superfix_moves.c, Buzz's pull and
 *         landing stun, a server-side re-implementation) asks gadget_buoy_nostun at the landing, which answers yes once per
 *         buoy use for the first landing after it (and forgets it when Buzz dies or changes character).
 *   HEAL_NOW  heal_attached_and_self (Kit) and heal_damage_taken (Kenji: CustomValue2 % of the damage taken in the last
 *         CustomValue1 ticks, the percent as the client's preview 0xb27c5c reads it) (HEAL): an instant heal through libg's
 *         heal 0xb41554.
 *   REPEAT  repeat_shot and spin_shoot rows with a CustomObject projectile other than Piper's Auto Aimer (published PROJECTILE;
 *         issue #54 redo from the game data, see the REPEAT / SPIN block): Dynamike, Darryl and Fang's popcorn (spin), Gene,
 *         Mico, Barley's potion, Bea's bees and Amber's flames (repeat; the last four of these since issue #63: Darryl's
 *         super charge per hit, the circling fields of Bea's and Amber's projectiles, hyper.c's spiral for the bees).
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
 * Readiness: a kind may have a ready() test (DASH / CHARGE: alive and not already in a charge; NEXT: not while a modifier is pending; HEAL: Meg out of her mech, Byron without
 * ammo; SHOT: a UseWeaponAmmo skill without an ammo bar; BUOY: the super full; SELF: an effect still running, a form gate); while it fails the gadget publishes a
 * cooldown of at least 1 and a fire is refused without spending a use. Cooldown: the accessory's +0xc4, else the Skill's
 * BonusSkillCooldown (getter 0xb0d878, the gadget value of the skill), else its Cooldown (ms / 50). A skill gadget whose
 * skill has MaxCharge > 1 (Shelly's Clay Pigeons, Colette's lifesteal shot: 3, "can be fired 3 times before cooldown")
 * fires that many times per cooldown, the skill's own Cooldown (ms) apart [?]; the cooldown starts after the last one.
 * Every other gadget publishes kind NONE (not usable): the other summons / turrets (meteor, air strike, ...),
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
int env_charge_start(uint8_t *ch, int tx, int ty, int speed, int type, int push, void *area_start, void *area_end, int straight);
/* gadget_self.c: the SELF kinds (statuses, shields, sleep, last stand, vision) */
int gself_kind(void *ad, int type); int gself_published(int sk); int gself_ready(void *sim, int pid, uint8_t *ch, void *ad, int sk);
int gself_fire(void *sim, int pid, uint8_t *ch, void *ad, int card, int sk, int tick);
void gself_note_tick(void *sim, int tick); void gself_clear(void); void gself_root_post(uint8_t *victim, int removed);

#define GAD_USES 9999     /* no per-battle limit: gadgets "no longer have charges but are now based on cooldowns" and can be
                           * used "an unlimited amount of times in a match" (Supercell release notes, Feb 2025); the
                           * cooldown is the accessory's (accessories.csv Cooldown, e.g. Bibi 400 ticks = the 20 s of the
                           * Feb 2026 notes). NB_GAD_USES=3 restores the old 3 uses per battle (issue #22). */
#define REP_MAX 20        /* REPEAT / SPIN: shots per use at most (Gene 100 / 5) */
#define SUM_MAX 8         /* SUMMON: summons per use at most (the SubType 5 rows have CustomValue1 3) */
#define TICKS_PER_S 20    /* 50 ms ticks */
enum { ACC_PLAIN = 0, ACC_DASH = 2, ACC_SPIN = 3, ACC_HEAL = 8, ACC_SPAWN = 9, ACC_REPEAT = 13, ACC_HEAL_SELF = 50,
       ACC_CHARGE_ULTI = 56, ACC_HEAL_TAKEN = 58, ACC_AIM_GADGET = 76 };   /* the `mov w8, #N` per Type string in 0xb2731c (spin_shoot 3, ...) */   /* accessory +0x24 type enum (0xb2731c's Type parser; 0 = empty Type) */

typedef int (*AdGet)(void *ad);
static int ad_get(void *ad, uint64_t getter) { return ((AdGet)B(getter))(ad); }
#define AD_SUBTYPE 0xa93258
#define AD_ACTIVE_TICKS 0xa932c8
#define AD_CV1 0xa933d0
#define AD_CV2 0xa933e0
#define AD_CV3 0xa933f0
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
    int (*again)(void *sim, Gad *g, uint8_t *ch, int tick);   /* optional: a fire while the last use is still running (Max's
                                                     * reactivation), tried before the cooldown test; 1 = handled (no use) */
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
    int rep_charge;                                        /* SPIN: super charge per enemy hit (CustomValue6, Darryl 1000) */
    int burst_id, burst_left, burst_next, burst_gap, burst_deg;   /* SHOT waves after the first (g_waves): char id, volleys
                                                                   * still to fire, next tick, ticks between, angle */
    int sum_id[SUM_MAX], sum_n, sum_until;                 /* SUMMON: the last use's summons (char ids), and the tick they are
                                                            * retired at (CustomValue3 lifetime; 0 = none) */
    int vis_id, vis_team, vis_r;                           /* SUMMON with a Vision area (Grom): the tower, its team, radius */
    double dist;                                           /* the fire's super_dist (0, 1] (0 = full range): thrown shots
                                                            * and AimableArea areas land this share of CastingRange out */
    int hp_prev, hp_lost[100];                        /* damage taken per tick (ring by tick % 100), for HEAL_TAKEN */
    int buoy_ch;                                           /* BUOY: the brawler's id at the fire while its next super has not
                                                            * landed yet (0 = none; gadget_buoy_nostun) */
    int rw_ch, rw_area, rw_until, rw_x, rw_y, rw_hp, rw_at;   /* REWIND: the brawler's id while a rewind is pending (0 = none),
                                                            * the bolt's marker area's id (0 = not found yet), the tick of the
                                                            * rewind, where the bolt lands, HP at the throw, tick of the throw */
};
static Gad g_gad[NBE_MAXP]; static int g_rep_log;
static long g_fired[8], g_areas, g_areas_lost;

/* ---- DASH (and CHARGE's ready) */
static int max_ammo(uint8_t *ch, uint8_t **sk0);
#define DASH_RELOAD 3   /* dash SubType 3 (Clancy's Crab_Dash): CustomValue3 / 100 ammo bars refilled (card value code 72); Digger_Dash's
                         * CustomValue3 (SubType 4) is its knockback, not ammo */
static long g_dash_areas, g_dash_reloads;
static int dash_classify(void *ad, int type) { return type == ACC_DASH && ad_get(ad, AD_CV1) > 0 && ad_get(ad, AD_CV2) > 0; }
static int dash_ready(void *sim, Gad *g, uint8_t *ch) { (void)sim; (void)g; return ch && I32(ch, 0x3c4) > 0 && !U8(ch, 0x490); }   /* not mid-charge */
static int dash_fire(void *sim, Gad *g, uint8_t *ch, double deg, int tick) {
    (void)sim; (void)tick;
    int dist = ad_get(g->ad, AD_CV1), spd = ad_get(g->ad, AD_CV2), X = I32(ch, 0x38), Y = I32(ch, 0x3c);
    double r = deg * M_PI / 180;
    if (env_dash_start(ch, (int)floor(X + dist * cos(r) + 0.5), (int)floor(Y + dist * sin(r) + 0.5), spd) <= 0) return 0;
    void *ar = PTR(g->ad, AD_AREA);   /* Maisie's MaisieDashArea (a Stun area: superfix_cc stuns for its CustomValue ticks) where she starts */
    if (ar && PTR(ch, 0x20)) { ((void *(*)(void *, void *, int, int, int, int, void *))B(0xb35c40))(ch, ar, X, Y, 0, 2, NULL); g_dash_areas++; }
    int cv3 = ad_get(g->ad, AD_CV3);
    if (ad_get(g->ad, AD_SUBTYPE) == DASH_RELOAD && cv3 > 0) {   /* Clancy: CustomValue3 x 10 ammo (1000 = one bar), capped at full */
        uint8_t *sk0; int mx = max_ammo(ch, &sk0);
        if (sk0) { int a = I32(sk0, 0x18) + cv3 * 10; I32(sk0, 0x18) = a < mx ? a : mx; g_dash_reloads++; }
    }
    return 1;
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
#define AD_CV4 0xa93400
#define AD_CV6 0xa93420    /* CustomValue6 (the getter after CustomValue5's 0xa93410; value code 10 reads it / 40 as a percent) */
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
static long g_shots, g_armed_summon, g_armed_item;
static void *g_last_shot;   /* the projectile the last shoot() spawned (NULL = none), for volley's sibling list */
static void *g_arm_sd;      /* SHOT: the gadget's skill while shot_volley fires (its summon / item ride on each projectile) */
#define SD_NUMSPAWNS 0xb0dd5c   /* NumSpawns (skills.csv; column word 0x1241000+896) */
#define SD_MAXSPAWNS 0xb0dd6c   /* MaxSpawns (+900) */
#define SD_SUMMON 0xb0ddf8      /* SummonedCharacters[i] (SkillData +0x80, count +0x8c) -> CharacterData* */
#define SD_ITEM 0xb0de70        /* SpawnedItem (SkillData +0xd8) -> ItemData* */
/* issue #64: what libg's attack path hands each projectile of a skill that summons or drops an item, done for a SHOT
 * gadget's projectiles (shoot() spawns them directly, so the skill's Attack handler and the character's attack tick, which
 * do it in the game, never run for them). The projectile's end (0xb75998: 0xb75b00 -> 0xb77344, 0xb75b28 -> item factory
 * 0xb55684) then spawns the summon / item where it lands, as for Nita's bear or Jessie's turret.
 *   summon: the attack tick's 0xb703c8(proj, SummonedCharacters[0], NumSpawns, MaxSpawns, +0xacc, +0xad4, char byte +0xaf1,
 *     owner CharacterData +636 < 1, 0, 0, 0, 0) (0xb4cab8..0xb4cb20; the Attack handler's setSummon 0xb5a6b4 is where the
 *     character's fields come from). The two bonus words (char +0xacc / +0xad4, summon HP and damage bonuses the Attack
 *     handler scales from the level) are 0 [?]: this build's level scale 0xb565a8 is the identity and the host has no gear
 *     that adds to them.
 *   item: the attack path's 0xb79130(proj, SpawnedItem, NumSpawns, 0xb6e680(ch, skill) (MaxSpawns plus bonuses), damage,
 *     second damage word, 0 (any end reason), 1) (0xb4f288..0xb4f2a4, from char +0xacc / +0xad0 that the Attack handler
 *     sets through 0xb5a6ec at 0xb7ed38: the damage and the skill's getter 0xb0dc14); here the projectile's damage and
 *     0xb0dc14(skill). */
static void arm_shot(uint8_t *ch, void *sd, uint8_t *p) {
    void *cd = ((void *(*)(void *, int))B(SD_SUMMON))(sd, 0), *it = ((void *(*)(void *))B(SD_ITEM))(sd);
    int n = sd_get(sd, SD_NUMSPAWNS);
    if (cd) {
        uint8_t *ocd = ((void *(*)(void *))B(0xb6a384))(ch); int mx = sd_get(sd, SD_MAXSPAWNS);
        ((void (*)(void *, void *, int, int, int, int, int, int, long, long, long, long))B(0xb703c8))(
            p, cd, n > 0 ? n : 1, mx > 0 ? mx : 1, 0, 0, U8(ch, 0xaf1), ocd && I32(ocd, 636) < 1, 0, 0, 0, 0);
        g_armed_summon++;
    }
    if (it) {
        int mx = ((int (*)(void *, void *))B(0xb6e680))(ch, sd);
        ((void (*)(void *, void *, int, int, int, int, int, int))B(0xb79130))(p, it, n > 0 ? n : 1, mx > 0 ? mx : 1, I32(p, 0xd4), sd_get(sd, 0xb0dc14), 0, 1);
        g_armed_item++;
    }
    if ((cd || it) && g_armed_summon + g_armed_item <= 6) LOG("[gadget] shot %p carries summon %p / item %p (count %d)\n", p, cd, it, n);
}
static int shoot(void *sim, uint8_t *ch, void *pd, double deg, int range, int dmg) {
    g_last_shot = NULL;
    if (!pd || !PTR(ch, 0x20)) return 0;
    int X = I32(ch, 0x38), Y = I32(ch, 0x3c); double r = deg * M_PI / 180;
    int tx = (int)floor(X + range * cos(r) + 0.5), ty = (int)floor(Y + range * sin(r) + 0.5);
    void *p = ((SpawnProj)B(0xb78190))(X, Y, ch, ch, pd, tx, ty, dmg, dmg, 0, 0, NULL, sim, 0, GAD_PROJ_KIND, NULL);
    if (p) g_shots++;
    if (p && g_arm_sd) arm_shot(ch, g_arm_sd, p);
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
static int shot_classify(void *ad, int type) {   /* Type 76 aim_with_gadget_collision (Rico): only the client's aim line */
    void *sd = type == ACC_PLAIN || type == ACC_AIM_GADGET ? PTR(ad, AD_SKILL) : NULL;
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
    g_arm_sd = sd;   /* issue #64: each projectile carries the skill's summon / item (arm_shot) */
    int k = volley(sim, ch, pd, deg, n, sd_get(sd, SD_SPREAD), range, dmg_scaled(ch, sd_get(sd, SD_DAMAGE)));
    g_arm_sd = NULL;
    return k;
}
/* issue #64: a skill with UseWeaponAmmo (SkillData +0x238, the byte the loader stores at 0xb0bd2c) costs one weapon ammo
 * bar and needs one, as Byron's heal does (heal_ready). [?] the amount: the column is a flag, and no card text names the
 * cost. SHOT rows with the flag: Frank's HammerDude_Pull, Shelly's ShotgunGirl_Focus, Colt's Gunslinger_BigBullet, Emz's
 * Mummy_Acid, Meg's MechaDude_ReloadTower, the Percenter rows and FutureGirl_ProjectileGadget. */
#define SD_USE_AMMO 0x238
static int shot_ready(void *sim, Gad *g, uint8_t *ch) {
    (void)sim; void *sd = PTR(g->ad, AD_SKILL);
    if (!ch || I32(ch, 0x3c4) <= 0) return 0;
    if (sd && U8(sd, SD_USE_AMMO)) { uint8_t *sk = ammo_skill(ch); if (!sk || I32(sk, 0x18) < 1000 * (1 + env_pending_attacks(g->pid))) return 0; }
    return 1;
}
static int shot_fire(void *sim, Gad *g, uint8_t *ch, double deg, int tick) {
    if (I32(ch, 0x3c4) <= 0 || g->burst_left || !shot_ready(sim, g, ch)) return 0;
    if (shot_volley(sim, g, ch, deg) <= 0) return 0;
    if (U8(PTR(g->ad, AD_SKILL), SD_USE_AMMO)) I32(ammo_skill(ch), 0x18) -= 1000;
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

/* ---- REWIND: Max's Sneaky Sneakers (Speedy_Rewind, issue #64; published PROJECTILE). Text: "Max throws a lightning bolt. If
 * she reactivates the Gadget, or after 3 seconds, she blinks back to the lightning bolt and heals any damage taken since."
 * The skill (SpeedyRewindBonusSkill) throws SpeedyRewindProjectile (Indirect, ForceValidTile) to the aim, pulled back to a
 * walkable tile (superfix_valid_spot); at its end libg's projectile end (0xb75afc -> 0xb76c0c, iteration 0: the getter
 * 0xafa7f4, ProjectileData +0x128) spawns the skin's SpawnAreaEffectObject, SpeedyRewindArea (TimeMs 3000, type Effect, a
 * marker that deals nothing), as it spawns Griff's bomb explosion. The host finds that area with libg's finder
 * 0xb2b1b0(data, Max) (the first area of that data and player); if none shows up within REWIND_FIND ticks it spawns one
 * itself at the landing point (0xb35c40, as AREA). The rewind, at the throw + TimeMs or at a fire while it is pending (the
 * reactivation: the swapped-in SpeedyRewindBonusSkillBlink, BehaviorType DestroyArea; GadImpl.again, no use spent): Max is
 * teleported to the area (superfix_teleport, superfix_moves.c), healed the HP lost since the throw (0xb41554) and the area
 * ends (end tick +0xd8 = now; libg's area tick then expires it). A reactivation before the area is found waits for it
 * (at most REWIND_FIND ticks). Max dead or another character: no rewind, the area ends.
 * Not used: the card's character component Brawler_SpeedyRewind (type 32, vtable 0x120a880), whose skill-used 0xb9bb84
 * listens to the area's expire and does the same rewind in the client. It keeps raw pointers to Max and the area, and
 * nothing in this libg lets go of it when Max dies (0xb9bc8c's only caller is 0xb9bb84 itself), so a death with a pending
 * rewind could run its expire handler 0xb9be00 on a freed character.
 * Cooldown: none while the rewind is pending (the gadget publishes ready, so the policy can reactivate; the throw skill has
 * NoBonusSkillCooldown); the full BonusSkillCooldown (300 ticks) starts at the rewind, or when Max dies or changes before it
 * (the blink skill's FullBonusSkillCooldownOnDeath). */
#define CARD_REWIND 23000311       /* cards.csv Speedy_Rewind (a data id, as g_masked) */
#define PD_SPAWN_AREA 0x128        /* ProjectileData +0x128: the skin's SpawnAreaEffectObject (createReferences 0xaf9074) */
#define AREA_END 0xd8              /* area end tick (shouldExpire 0xb28d4c) */
#define AREA_TIME_MS 0x124         /* AreaEffectData TimeMs */
#define REWIND_FIND 4              /* ticks the host waits for the bolt's area (29000 u/s: it lands the tick after the throw) */
void superfix_valid_spot(void *sim, int x0, int y0, int *tx, int *ty) __attribute__((weak));   /* superfix_moves.c */
int superfix_teleport(uint8_t *ch, int tx, int ty) __attribute__((weak));
static long g_rewinds, g_rewind_again, g_rewind_done, g_rewind_drop, g_rewind_own;
static int g_cls_card;             /* the card being classified (gadget_reset_player) */
static int is_area(uint8_t *o) {   /* a live area: item vtable, data of type 17 (as gadget_root_post), not expired (+0xf4) */
    int vt = VTOF(o); uint8_t *d = vt == VT_ITEM || vt == VT_ITEM2 ? PTR(o, 0x10) : NULL;
    return d && I32(d, 0x20) / 1000000 == 17 && !U8(o, 0xf4);
}
static int rewind_classify(void *ad, int type) {
    void *sd = type == ACC_PLAIN ? PTR(ad, AD_SKILL) : NULL, *pd = sd ? skill_proj(sd) : NULL;
    return g_cls_card == CARD_REWIND && !PTR(ad, AD_AREA) && pd && PTR(pd, PD_SPAWN_AREA);
}
static int rewind_fire(void *sim, Gad *g, uint8_t *ch, double deg, int tick) {
    if (I32(ch, 0x3c4) <= 0 || g->rw_ch || !PTR(ch, 0x20)) return 0;
    void *sd = PTR(g->ad, AD_SKILL), *pd = skill_proj(sd), *ad_ = PTR(pd, PD_SPAWN_AREA);
    int cr = sd_get(sd, SD_RANGE), range = aimed_range(cr > 0 ? cr * 100 : 800, g->dist), X = I32(ch, 0x38), Y = I32(ch, 0x3c);
    double r = deg * M_PI / 180; int tx = (int)floor(X + range * cos(r) + 0.5), ty = (int)floor(Y + range * sin(r) + 0.5);
    if (superfix_valid_spot) superfix_valid_spot(sim, X, Y, &tx, &ty);   /* ForceValidTile */
    int d = (int)floor(hypot(tx - X, ty - Y) + 0.5);
    if (!shoot(sim, ch, pd, deg, d > 0 ? d : 1, 0)) return 0;   /* the bolt (29000 u/s: it lands in a tick) */
    g->rw_ch = I32(ch, 8); g->rw_area = 0; g->rw_at = tick; g->rw_x = tx; g->rw_y = ty; g->rw_hp = I32(ch, 0x3c4);
    g->rw_until = tick + (I32(ad_, AREA_TIME_MS) > 0 ? I32(ad_, AREA_TIME_MS) / 50 : 60);
    if (g_rewinds++ < 6) LOG("[gadget] rewind: bolt to %d,%d at tick %d, rewind at tick %d, hp %d\n", tx, ty, tick, g->rw_until, g->rw_hp);
    return 1;
}
static uint8_t *rewind_area(void *sim, Gad *g, uint8_t *ch, int tick) {   /* the bolt's marker area, NULL = none (yet / any more) */
    if (g->rw_area) { uint8_t *a = env_obj_by_id(sim, g->rw_area); return a && is_area(a) ? a : NULL; }
    void *ad_ = PTR(skill_proj(PTR(g->ad, AD_SKILL)), PD_SPAWN_AREA);
    uint8_t *a = ((void *(*)(void *, void *))B(0xb2b1b0))(ad_, ch);
    if (a && !is_area(a)) a = NULL;
    if (!a && tick >= g->rw_at + REWIND_FIND) {   /* the bolt spawned no area: the host's own at the landing point */
        a = ((void *(*)(void *, void *, int, int, int, int, void *))B(0xb35c40))(ch, ad_, g->rw_x, g->rw_y, 0, 2, NULL);
        if (a) g_rewind_own++;
    }
    if (a) g->rw_area = I32(a, 8);
    return a;
}
static void rewind_tick(void *sim, Gad *g, int tick) {
    uint8_t *ch = env_obj_by_id(sim, g->rw_ch);
    if (!ch || I32(ch, 0x3c4) <= 0 || VTOF(ch) != VT_CHAR) {   /* dead or another character: no rewind, full cooldown */
        uint8_t *a = g->rw_area ? env_obj_by_id(sim, g->rw_area) : NULL;
        if (a && is_area(a)) I32(a, AREA_END) = tick;
        g->rw_ch = 0; g->cd_until = tick + g->cd; g_rewind_drop++; return;
    }
    uint8_t *a = rewind_area(sim, g, ch, tick);
    if (!g->rw_area && tick < g->rw_at + REWIND_FIND) return;   /* the bolt is still flying */
    if (a && tick < g->rw_until) return;
    int x = a ? I32(a, 0x38) : g->rw_x, y = a ? I32(a, 0x3c) : g->rw_y, lost = g->rw_hp - I32(ch, 0x3c4);
    if (superfix_teleport) superfix_teleport(ch, x, y);
    if (lost > 0) ((void (*)(void *, int, int, int, void *, int, int, int, long, long))B(0xb41554))(ch, g->pid, lost, 1, NULL, 0, 0, 0, 0, 0);
    if (a) I32(a, AREA_END) = tick;
    if (g_rewind_done++ < 6) LOG("[gadget] rewind done at tick %d (thrown at %d): char at %d,%d, hp %d (%d at the throw)\n", tick, g->rw_at,
                                 I32(ch, 0x38), I32(ch, 0x3c), I32(ch, 0x3c4), g->rw_hp);
    g->rw_ch = 0; g->cd_until = tick + g->cd;
}
static int rewind_again(void *sim, Gad *g, uint8_t *ch, int tick) {   /* the reactivation: the rewind now */
    if (!g->rw_ch || !ch || I32(ch, 8) != g->rw_ch || I32(ch, 0x3c4) <= 0) return 0;
    g->rw_until = tick; g_rewind_again++;
    rewind_tick(sim, g, tick);   /* now, unless the bolt's area is still awaited (then within REWIND_FIND ticks) */
    return 1;
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
 *     Darryl's text (code 10: CustomValue6 / 40 %) recharges his super by CustomValue6 / 4000 of it per enemy hit
 *     (gadget_root_post; RE-IMPLEMENTED: a kind-4 shot gets no charge from libg). Fang's kernels burst in the air at their
 *     TriggerWithDelayMs (900 ms: ~675 u out, the game's own rule in the projectile update 0xb70408), and the 3 mines of each
 *     burst (spawnfix.c's BulletExplosion items) arm for the item's Value ms; an enemy within TriggerRangeSubTiles (200)
 *     then starts the Value2 ms fuse, and at its end the mine pops (superfix_items.c). An untriggered mine does not pop.
 *     With the audit's target in range: ~75 ticks after the shot.
 *   REPEAT by SubType, damage Damage x CustomValue2 % (codes 51 / 68; Mico's text: scaleaccessoryvalue2):
 *     1 (Gene; Barley with TargetFriends): one shot at each target within Range tiles (enemies, or allies and the brawler
 *       himself), nearest first; Gene's RequireEnemyInRange refuses with none. Barley's potion carries Hitpoints x
 *       |CustomValue2| % (code 59, "heals <VALUE1> health per second") for the BarkeepHealingArea its skin spawns.
 *     2 (Bea): the bees leave along the aim, turned 360 / n degrees each. They circle (TravelType 8, no ring radius): rep_one
 *       sets their angle and hyper.c circle_travel spirals them out from Bea (a guess of the compiled-out server path, see
 *       there); libg ends each at SteerLifeTime and ramps its damage from DamagePercentStart to End ("more damage the
 *       further they go").
 *     4 (Amber): |CustomValue3| flames at once, evenly around her (code 3, "creates <VALUE3> orbiting flames"): circling
 *       projectiles (TravelTypeVariable 800 the ring), spaced by rep_one's angles, moved by hyper.c circle_travel, for
 *       SteerLifeTime (code 41, "for <VALUE2> seconds": 100 ticks; CustomValue2 is the damage percent, code 51).
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
        int k;   /* list full: only a nearer one takes the last place (the old test also read d2s[k] before any write) */
        if (n < max) k = n++; else { k = max - 1; if (d2 >= d2s[k]) continue; }
        while (k > 0 && d2s[k - 1] > d2) { d2s[k] = d2s[k - 1]; ids[k] = ids[k - 1]; k--; }
        d2s[k] = d2; ids[k] = I32(c, 8);
    }
    return n;
}
/* the REPEAT / SPIN shots fired one at a time by rep_one (not Mico's volley, which goes through volley()): a ring per
 * player, cleared with the table: projectile id, player, super charge it gives on an enemy hit (Darryl's CustomValue6, else
 * 0), spawn tick. 32 slots: one use fires at most 20 (Gene; Darryl 15) and the cooldown is far longer than any flight, so a
 * player's own shots never push out one still flying. NB_REP_DBG=1 logs each one's position per tick and its hits. */
#define RSHOT_MAX 32
typedef struct { int id, pid, charge, tick; } RShot;
static RShot g_rshot[NBE_MAXP][RSHOT_MAX]; static int g_rshot_k[NBE_MAXP]; static long g_rep_charged;
static int rep_dbg(void) { static int d = -1; if (d < 0) { const char *e = getenv("NB_REP_DBG"); d = e && atoi(e) > 0; } return d; }
#define PD_TRAVEL 0xafab60   /* ProjectileData TravelType getter (data +0x210; 8 = circling) */
/* one REPEAT shot. A circling projectile (TravelType 8: Bea's bees, Amber's flames) gets what libg's own circling spawn
 * 0xb78c58 writes after its 0xb78190 call (0xb790e0 / 0xb790e4): +0x454 its angle on the circle (degrees, the direction it
 * was aimed: hyper.c circle_travel places it there) and +0x415 = 1 (the hit code at 0xb740f0 then calls 0xb5a86c on the
 * target, which only sets the target's +0x4a0 to 6 [?] a hit-reaction state). 0xb78c58 itself is not called: it spaces all
 * of the owner's circling projectiles of the kind from its own clock and removes the extras, which does not fit the bees
 * that leave one by one. */
static int rep_one(void *sim, Gad *g, uint8_t *ch, void *pd, double deg, int range) {
    int k = shoot(sim, ch, pd, deg, range, g->rep_dmg); uint8_t *p = g_last_shot;
    if (!p) return k;
    if (((int (*)(void *))B(PD_TRAVEL))(pd) == 8) { I32(p, 0x454) = (((int)lround(deg)) % 360 + 360) % 360; U8(p, 0x415) = 1; }
    int t = I32(sim, 0x10);
    if (g->pid >= 0 && g->pid < NBE_MAXP) {
        RShot *r = &g_rshot[g->pid][g_rshot_k[g->pid]++ % RSHOT_MAX];
        *r = (RShot){I32(p, 8), g->pid, g->type == ACC_SPIN ? g->rep_charge : 0, t};
    }
    if (rep_dbg()) LOG("[gadget] rep shot %d (card %d) at tick %d: from %d,%d angle %d to range %d, ticks %d..%d, dmg %d\n", I32(p, 8),
                       g->card, t, I32(ch, 0x38), I32(ch, 0x3c), (int)lround(deg), range, I32(p, 0x28), I32(p, 0x2c), g->rep_dmg);
    return k;
}
static RShot *rshot_of(int pid, int id) {   /* player pid's listed shot with that projectile id, or NULL */
    if (pid < 0 || pid >= NBE_MAXP || !id) return NULL;
    for (int k = 0; k < RSHOT_MAX; k++) if (g_rshot[pid][k].id == id) return &g_rshot[pid][k];
    return NULL;
}
/* hyper.c circle_travel: is this circling projectile a REPEAT gadget shot (Bea's bees)? Only those get its no-radius spiral;
 * libg's own radius-less circling projectiles (R-T's hypercharged lasers) keep their old path. */
int gadget_rep_shot(uint8_t *pr) {
    uint8_t *o = pr ? PTR(pr, 0xe0) : NULL;
    return o && rshot_of(I32(o, 0x80), I32(pr, 8)) != NULL;
}
static void rshot_trace(void *sim, int tick) {   /* NB_REP_DBG: where each recent shot is now (env_obj_by_id: only live ones) */
    static long nlog;
    for (int k = 0; k < NBE_MAXP * RSHOT_MAX && nlog < 4000; k++) {
        RShot *r = &g_rshot[k / RSHOT_MAX][k % RSHOT_MAX]; if (!r->id || tick - r->tick > 120) continue;
        uint8_t *p = env_obj_by_id(sim, r->id);
        if (!p || VTOF(p) != VT_PROJ) continue;
        LOG("[gadget] rep shot %d tick %d: at %d,%d\n", r->id, tick, I32(p, 0x38), I32(p, 0x3c)); nlog++;
    }
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
    if (g->rep_cnt > 1 && g->rep_spread >= 360) for (int k = 0; k < g->rep_cnt; k++) rep_one(sim, g, ch, pd, deg + 360.0 * k / g->rep_cnt, range);
    else if (g->rep_cnt <= 1) rep_one(sim, g, ch, pd, deg, range);
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
        g->rep_charge = ad_get(ad, AD_CV6);   /* Darryl: super charge per enemy hit (gadget_root_post) */
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
            uint8_t *t = env_obj_by_id(sim, id); if (!t) return 0;
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

/* ---- SUMMON: spawn rows whose CustomObject is a characters.csv row (issue #46 batch 3b; published SPAWN). The placement by
 * SubType is server code (the activation 0xb27c58 is `ret`, and no client reader of SubType handles spawn 9), so it is
 * RE-IMPLEMENTED here; the summon itself comes from libg's summon factory 0xb56e00, called with the arguments the
 * projectile-end summon 0xb77344 passes (the path that places Nita's bear or Bo's totem), the projectile's own words 0:
 *   SubType 1 (Penny's barrel, Bea's pot, Grom's tower, Janet's speaker, Stu's booster) and 2 (Leon's clone): one at the brawler.
 *   SubType 5: CustomValue1 summons CustomValue2 units out, each spot pulled back along the line from the brawler onto a
 *     walkable one (superfix_valid_spot): around the brawler from the aim (Tara's shadows, Charlie's spiders) [?] the start
 *     angle; a row with CustomValue4 (Ruffs) in an arc towards the aim, SUM_ARC degrees apart, each with CustomValue4 % of
 *     the brawler's max HP (the card's "<VALUE2>% of Ruffs' max health", value code 4 = CustomValue4); a row with
 *     CustomValue3 (Tara: "disappear after <VALUE1> seconds", code 30 = CustomValue3 / 20) retires its summons after
 *     CustomValue3 ticks, the way superfix_moves.c retires R-T's legs (HP 0, the retired flag).
 * The factory's w3 0 lets libg move a summon off a blocked spot by itself (0xc6be08). MaxSpawns is the use's count with the
 * "kill the oldest" byte of 0xb77344 (owner CharacterData ExtraMinions < 1): a new use replaces the last one's summons that
 * still live [?] (no data column says so). A summon keeps its power-1 table HP (as superfix.c's summons; Ruffs' sandbags
 * take theirs from the brawler) [?]: against power-11 brawlers it lasts about half as long. What a summon then does is libg's and the earlier rounds': its area
 * (superfix_summon_area: Bea's slow, Stu's speed, Janet's damage), its HP loss (HealthPromilleLostPerSecond), its AI (the
 * character tick's minion branches). Grom's Vision area (type 27) has no client reader: gadget_summon_vision answers
 * env.c's bush hiding (through gadget_self.c's gadget_vision) for a living tower of the team, within its area's Radius. */
#define SUM_ARC 35            /* Ruffs: degrees between two sandbags, 2 asin(CollisionRadius 120 / CustomValue2 400): they touch [?] */
#define AREA_VISION 27        /* AreaEffectData +0x118 Vision (the parser 0xa96980) */
typedef void *(*summon_t)(void *, int, int, int, int, int, int, int, void *, uint64_t, uint64_t, uint64_t, uint64_t,
                          uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t,
                          uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t);
static long g_summons, g_summons_lost, g_sum_retired, g_vis_hits;
static void *custom_char(void *ad) { return lookup_by_name(0xad2b60, ((void *(*)(void *))B(AD_CUSTOM_OBJ))(ad)); }
static uint64_t geti_ch(uint64_t fn, void *o) { return (uint64_t)(uint32_t)((int (*)(void *))B(fn))(o); }
/* one summon of data cd for brawler ch at (x, y): 0xb77344's call (0xb775a0..0xb77624) with the projectile's words 0 / NULL:
 * stack +8 player, +16 team, +24 the third id word, +32 owner id (the brawler's getters 0xb6a754 / 0xb6a818 / 0xb6a884 /
 * 0xb6a5d4), +40 kill the oldest over maxn, +48 0xab3268(cd) > 0, +64 the brawler's byte +0xaf1, +128 / +136 CharacterData
 * +634 == 0, +144 -1, +160 / +168 NULL (the factory then takes the player's modifier container, 0xbb1d18) */
static void *summon_at(void *sim, uint8_t *ch, uint8_t *cd, int x, int y, int maxn) {
    uint8_t *ocd = ((void *(*)(void *))B(0xb6a384))(ch); uint64_t z = 0, nf = !U8(cd, 634);
    uint64_t kill = !ocd || I32(ocd, 636) < 1, big = ((int (*)(void *))B(0xab3268))(cd) > 0;
    uint8_t *s = ((summon_t)B(0xb56e00))(cd, x, y, 0, 1, maxn, 0, 0, sim, geti_ch(0xb6a754, ch), geti_ch(0xb6a818, ch),
                                         geti_ch(0xb6a884, ch), geti_ch(0xb6a5d4, ch), kill, big, z, (uint64_t)U8(ch, 0xaf1), z, z, z, z,
                                         z, z, z, nf, nf, (uint64_t)-1, z, z, z, z);
    if (s) g_summons++; else g_summons_lost++;
    if (g_summons + g_summons_lost <= 12)
        LOG("[gadget] summon data %d at %d,%d (brawler at %d,%d) -> %d at %d,%d, owner %d, hp %d / %d\n", I32(cd, 0x20), x, y, I32(ch, 0x38),
            I32(ch, 0x3c), s ? I32(s, 8) : -1, s ? I32(s, 0x38) : 0, s ? I32(s, 0x3c) : 0, s ? I32(s, 0x80) : -1, s ? I32(s, 0x3c4) : 0, s ? I32(s, 0x3c8) : 0);
    return s;
}
static int summon_classify(void *ad, int type) {
    if (type != ACC_SPAWN || !custom_char(ad)) return 0;
    int sub = ad_get(ad, AD_SUBTYPE);
    return sub == 1 || sub == 2 || (sub == 5 && ad_get(ad, AD_CV1) > 0 && ad_get(ad, AD_CV2) > 0);
}
static int summon_fire(void *sim, Gad *g, uint8_t *ch, double deg, int tick) {
    if (I32(ch, 0x3c4) <= 0 || !PTR(ch, 0x20)) return 0;
    uint8_t *cd = custom_char(g->ad); if (!cd) return 0;
    int sub = ad_get(g->ad, AD_SUBTYPE), n = sub == 5 ? ad_get(g->ad, AD_CV1) : 1, R = sub == 5 ? ad_get(g->ad, AD_CV2) : 0;
    int cv3 = ad_get(g->ad, AD_CV3), cv4 = ad_get(g->ad, AD_CV4), X = I32(ch, 0x38), Y = I32(ch, 0x3c);
    n = n < 1 ? 1 : n > SUM_MAX ? SUM_MAX : n; g->sum_n = 0; g->sum_until = 0;
    for (int k = 0; k < n; k++) {
        double a = (cv4 > 0 ? deg + (k - (n - 1) / 2.0) * SUM_ARC : deg + 360.0 * k / n) * M_PI / 180;
        int x = (int)floor(X + R * cos(a) + 0.5), y = (int)floor(Y + R * sin(a) + 0.5);
        if (R > 0 && superfix_valid_spot) superfix_valid_spot(sim, X, Y, &x, &y);   /* not across a wall */
        uint8_t *s = summon_at(sim, ch, cd, x, y, n);
        if (!s) continue;
        if (cv4 > 0 && sub == 5) { int hp = (int)((int64_t)I32(ch, 0x3c8) * cv4 / 100); if (hp > 0) { I32(s, 0x3c8) = hp; I32(s, 0x3c4) = hp; } }
        g->sum_id[g->sum_n++] = I32(s, 8);
        uint8_t *ar = PTR(cd, 0xb8);   /* CharacterData +0xb8 AreaEffect (superfix_summon_area) */
        if (ar && I32(ar, 0x118) == AREA_VISION) {
            uint8_t *p = player_of(sim, g->pid); g->vis_id = I32(s, 8); g->vis_r = I32(ar, 0x12c); g->vis_team = p ? I32(p, 12) : I32(ch, 0x84);
        }
    }
    if (g->sum_n && sub == 5 && cv3 > 0) g->sum_until = tick + cv3;
    return g->sum_n > 0;
}
static void retire_char(uint8_t *c) { I32(c, 0x3c4) = 0; U8(c, 3273) = 1; }   /* 0xb4ffec's end, as superfix_moves.c retire() */
static void summon_tick(void *sim, Gad *g, int tick) {   /* CustomValue3 lifetime (Tara's shadows) */
    if (tick < g->sum_until) return;
    for (int k = 0; k < g->sum_n; k++) {
        uint8_t *c = env_obj_by_id(sim, g->sum_id[k]);
        if (c && VTOF(c) == VT_CHAR && I32(c, 0x3c4) > 0) { retire_char(c); g_sum_retired++; }
    }
    g->sum_until = 0;
}
/* gadget_self.c's gadget_vision (env.c's bush hiding): does a living Vision summon of team `team` see (x, y) */
int gadget_summon_vision(void *sim, int team, int x, int y) {
    for (int i = 0; sim && i < NBE_MAXP; i++) {
        Gad *g = &g_gad[i]; if (!g->vis_id || g->vis_team != team) continue;
        uint8_t *c = env_obj_by_id(sim, g->vis_id);
        if (!c || VTOF(c) != VT_CHAR || I32(c, 0x3c4) <= 0) { g->vis_id = 0; continue; }
        long dx = x - I32(c, 0x38), dy = y - I32(c, 0x3c);
        if (dx * dx + dy * dy <= (long)g->vis_r * g->vis_r) { g_vis_hits++; return 1; }
    }
    return 0;
}

/* ---- CHARGE (issue #46 batch 4; published DASH): an empty Type with a Skill whose BehaviorType is Charge (Brock, Max, Shelly,
 * Glowy, Bolt, Wendy) or activate_skill (52) with the Charge skill named by CustomObject (Angelo's InsectMan_Fly): the skill's
 * charge through env.c env_charge_start (the native charge mover with the real ChargeType, no super slot, no contact damage).
 * Distance: a jump (ChargeType 11) without AlwaysCastAtMaxRange (Bolt, Brock: "jumps to a target location") lands where aimed
 * (aimed_range of CastingRange); every other one goes the full CastingRange [?] (Glowy's and Max's dashes, Angelo's flight:
 * 1800 u at 2000 u/s is the card's "for 1 second"). The airborne types (11, 20: libg's 0xb5033c airborne set) go straight
 * over walls and water, landing on walkable ground [?]. Areas: AreaEffectObject once at take-off (Brock's blast, Angelo's
 * drain), AreaEffectObject2 at the landing with AreaEffect2AtEndOfCharge (Brock, Bolt, Glowy's heal). Extras at the fire:
 * each ActivationSelfStatusEffects entry on the brawler (Max's SpeedyGadgetDashShield, ShieldPercent 100, CancelOnChargeEnd:
 * libg's charge tick calls the stub 0xba3274 where a charge ends (0xb3e16c), superfix_status.c's my_charge_end ends it there,
 * and env.c's charge_end ends it for a gadget's charge too: superfix_status_charge_end),
 * and the skill's Reload flag (Shelly) refills the weapon ammo to full [?] (at the start). Bolt's landing area
 * (DestroysEnvironment) breaks walls through libg's area apply. Not modelled: Bolt's "loses all speed when landing",
 * Angelo's drain heal-back (the area's DamageDrain damages, nothing heals him; server code) and its PushbackStrengthSelf,
 * the ChargePushback contact (0 for all these skills). Cooldown: the Batch 0 rule (BonusSkillCooldown; Angelo's row Cooldown 360). */
enum { ACC_ACTIVATE_SKILL = 52 };   /* `mov w8, #0x34` at 0xb27928 after the "activate_skill" compare */
#define SD_CHARGE_SPEED 0xb0d848   /* ChargeSpeed (u/s; column word 0x1241000+888) */
#define SD_CHARGE_TYPE 0xb0dc34    /* ChargeType (+892) */
#define SD_CHARGE_PUSH 0xb0dd3c    /* ChargePushback (+880) */
#define SD_AREA2_AT_END 0xb0de50   /* AreaEffect2AtEndOfCharge (bool, +936) */
#define SD_MAX_RANGE 0xb0df98      /* AlwaysCastAtMaxRange (bool, +1056) */
#define SD_AREA2 0xa8              /* SkillData +0xa8 AreaEffectObject2 (AreaEffectData*) */
#define SD_SELF_ST 0x1d0           /* ActivationSelfStatusEffects: StatusEffectData* array, count at +0x1dc (0xb8072c reads them) */
#define SD_RELOAD 0x23b            /* BooleanAttributes "Reload" (the loader's strb at 0xb0bd80) */
#define BT_CHARGE 2
#define CT_JUMP 11                 /* ChargeType of the jumps (Bolt, Brock, Wendy) */
#define CT_FLY 20                  /* Angelo's flight */
static long g_charges, g_charge_sts, g_charge_reloads;
static void *charge_skill(void *ad, int type) {
    void *sd = type == ACC_PLAIN ? PTR(ad, AD_SKILL)
             : type == ACC_ACTIVATE_SKILL ? lookup_by_name(0xad2b7c, ((void *(*)(void *))B(AD_CUSTOM_OBJ))(ad)) : NULL;
    return sd && I32(sd, SD_BEHAVIOR) == BT_CHARGE && sd_get(sd, SD_CHARGE_SPEED) > 0 ? sd : NULL;
}
static int charge_classify(void *ad, int type) { return charge_skill(ad, type) != NULL; }
static int charge_fire(void *sim, Gad *g, uint8_t *ch, double deg, int tick) {
    (void)tick;
    void *sd = charge_skill(g->ad, g->type); if (!sd || !dash_ready(sim, g, ch)) return 0;
    int ty = sd_get(sd, SD_CHARGE_TYPE), cr = sd_get(sd, SD_RANGE) * 100, maxr = sd_get(sd, SD_MAX_RANGE) & 1;
    int R = ty == CT_JUMP && !maxr ? aimed_range(cr, g->dist) : cr, X = I32(ch, 0x38), Y = I32(ch, 0x3c);
    double r = deg * M_PI / 180;
    void *a1 = PTR(sd, SD_AREA), *a2 = PTR(sd, SD_AREA2), *aend = (sd_get(sd, SD_AREA2_AT_END) & 1) ? a2 : NULL;
    int len = env_charge_start(ch, (int)floor(X + R * cos(r) + 0.5), (int)floor(Y + R * sin(r) + 0.5), sd_get(sd, SD_CHARGE_SPEED), ty,
                               sd_get(sd, SD_CHARGE_PUSH), a1, aend, ty == CT_JUMP || ty == CT_FLY);
    if (len <= 0) return 0;
    void **st = PTR(sd, SD_SELF_ST); int nst = I32(sd, SD_SELF_ST + 0xc);
    int pid = ((int (*)(void *))B(0xb6a754))(ch), team = ((int (*)(void *))B(0xb6a820))(ch);
    for (int k = 0; st && k < nst && k < 8; k++) if (st[k]) {   /* as the skill start's loop 0xb8072c..0xb807ac, through the add wrapper */
        ((void (*)(void *, void *, int, int, void *, void *, int, int, int, int, int))B(0xb35dd0))(ch, st[k], pid, team, ch, ch, 0, 0, -1, -1, 0);
        g_charge_sts++; }
    if (U8(sd, SD_RELOAD)) { uint8_t *sk0; int mx = max_ammo(ch, &sk0); if (sk0) { I32(sk0, 0x18) = mx; g_charge_reloads++; } }
    if (g_charges++ < 10) LOG("[gadget] charge type %d: %d u of %d along %.0f deg at %d u/s, areas %p / %p, self statuses %d, reload %d\n", ty, len, R,
                              deg, sd_get(sd, SD_CHARGE_SPEED), a1, aend, nst, U8(sd, SD_RELOAD));
    return 1;
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
    RShot *rs = VTOF(src) == VT_PROJ ? rshot_of(I32(attacker, 0x80), I32(src, 8)) : NULL;
    if (rs) {   /* a REPEAT / SPIN shot hit a brawler */
        int enemy = I32(victim, 0x84) != I32(attacker, 0x84);
        if (rep_dbg()) LOG("[gadget] rep shot %d hit ch %d (%s) at %d,%d: -%d hp, tick %d\n", rs->id, I32(victim, 8),
                           enemy ? "enemy" : "ally", I32(src, 0x38), I32(src, 0x3c), removed, t);
        /* Darryl: "recharges his Super by <VALUE2>% if it hits enemies", VALUE2 = CustomValue6 / 40 (code 10): CustomValue6 / 4000
         * of the full super (player +0x58) per hit; a kind-4 shot gets no charge from libg. RE-IMPLEMENTED (server code). */
        void *sim_ = rs->charge > 0 && enemy && removed > 0 ? ((void *(*)(void *))B(0xb6a378))(attacker) : NULL;
        uint8_t *pl = sim_ && char_of(sim_, rs->pid) == attacker ? player_of(sim_, rs->pid) : NULL;
        if (pl) {
            int mx = I32(pl, 0x58), sc = I32(pl, 0x54) + (int)((int64_t)mx * rs->charge / 4000);
            I32(pl, 0x54) = sc < mx ? sc : mx; g_rep_charged++;
            if (rep_dbg()) LOG("[gadget] rep shot %d: player %d super charge -> %d / %d\n", rs->id, rs->pid, I32(pl, 0x54), mx);
        }
    }
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
    {NBE_GAD_DASH, dash_classify, dash_fire, dash_ready},
    {NBE_GAD_DASH, charge_classify, charge_fire, dash_ready},
    {NBE_GAD_HEAL, heal_classify, heal_fire, heal_ready},
    {NBE_GAD_SPAWN, area_classify, area_fire},
    {NBE_GAD_PROJECTILE, rewind_classify, rewind_fire, NULL, rewind_again},
    {NBE_GAD_PROJECTILE, shot_classify, shot_fire, shot_ready},
    {NBE_GAD_SPAWN, skill_area_classify, skill_area_fire},
    {NBE_GAD_PROJECTILE, auto_aim_classify, auto_aim_fire},
    {NBE_GAD_PROJECTILE, rep_classify, rep_fire},
    {NBE_GAD_SPAWN, item_classify, item_fire},
    {NBE_GAD_SPAWN, summon_classify, summon_fire},
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
    if (g_rep_charged) LOG("[gadget] repeat: %ld enemy hits gave super charge\n", g_rep_charged);
    if (g_rewinds) LOG("[gadget] rewind: %ld bolts, %ld reactivations, %ld rewinds, %ld dropped (death / changed), %ld areas spawned by the host\n", g_rewinds, g_rewind_again, g_rewind_done, g_rewind_drop, g_rewind_own);
    if (g_armed_summon + g_armed_item) LOG("[gadget] shots carrying a summon %ld / an item %ld\n", g_armed_summon, g_armed_item);
    g_rewinds = g_rewind_again = g_rewind_done = g_rewind_drop = g_rewind_own = g_armed_summon = g_armed_item = 0;
    if (g_summons + g_summons_lost) LOG("[gadget] summons: %ld spawned, %ld refused by the factory, %ld retired at their lifetime; vision answers %ld\n",
                                        g_summons, g_summons_lost, g_sum_retired, g_vis_hits);
    g_summons = g_summons_lost = g_sum_retired = g_vis_hits = 0;
    if (g_charges + g_dash_areas + g_dash_reloads) LOG("[gadget] charges %ld (self statuses %ld, reloads %ld); dash areas %ld, dash reloads %ld\n",
                                                       g_charges, g_charge_sts, g_charge_reloads, g_dash_areas, g_dash_reloads);
    g_charges = g_charge_sts = g_charge_reloads = g_dash_areas = g_dash_reloads = 0;
    g_rep_charged = 0; memset(g_rshot, 0, sizeof g_rshot); memset(g_rshot_k, 0, sizeof g_rshot_k);
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
    if (g->im->again && g->im->again(sim, g, ch, tick)) return 1;   /* Max's reactivation: no use, no cooldown test */
    if (g->uses <= 0 || tick < g->cd_until || !ch) return 1;
    if (g->im->ready && (g->not_ready || !g->im->ready(sim, g, ch))) return 1;   /* published as not ready: refused, nothing spent */
    if (g->im->fire(sim, g, ch, deg, tick)) {
        g->uses--; g->used++; g->cd_until = g->rw_ch ? tick : tick + g->cd;   /* REWIND: no cooldown while the rewind is pending */
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
        if (g_gad[i].rw_ch) rewind_tick(sim, &g_gad[i], tick);
        if (g_gad[i].sum_until) summon_tick(sim, &g_gad[i], tick);
        if (g_gad[i].im && g_gad[i].type == ACC_HEAL_TAKEN) taken_tick(sim, &g_gad[i], tick);
        if (g_gad[i].im && g_gad[i].type == ACC_NEXT) next_tick(sim, &g_gad[i], tick);
        if (g_gad[i].im && g_gad[i].im->ready) g_gad[i].not_ready = !g_gad[i].im->ready(sim, &g_gad[i], char_of(sim, i));
    }
    if (rep_dbg()) rshot_trace(sim, tick);
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
