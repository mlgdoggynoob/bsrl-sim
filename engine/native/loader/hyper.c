/* hypercharge round (bsrl-sim issue #4): the host's own hypercharge ("Overcharge" in libg) for the battle.
 *
 * What the shipped libg v68.279 (a client build) still has: the activation 0xc42584(player, char) (reached in the game by
 * input kind 17 and by the bot AI; the input path is gated off offline) and the charging inside the super charge 0xc420d8
 * (player+0x98 += damage-based charge x CharacterData OverchargeChargeMul, 0 while active: OverchargeChargeActiveMul).
 * The activation needs the brawler's hypercharge card (cards.csv MetaType 6) in the player config (+0x28, the slot 0xc33e84
 * fills for MetaType 6), a full charge (+0x98 >= +0x9c) and not already active (+0xa0); it sets +0xa0 = 1, char+0x68 = 1
 * (overcharged) and the drain per tick +0xa4 = 40 (divided by 1 + x/100 for an "extend" card modifier), and spends nothing.
 * What is compiled out (server code): the drain and the expiry, and the three buffs. Measured (2026-11-24, Shelly, host
 * without this file): speed, shot damage and damage taken identical active and inactive; active never ended (400+ ticks),
 * the charge stayed full.
 *
 * Here: equip (offline.c my_player_ctor puts hyper_card_for(character) in cfg+0x28 for the RESET's div.hyper_mask), activate
 * (NbeAction.fire 4 -> hyper_use -> libg's own 0xc42584), drain +0xa4 per tick from the charge and end at 0 (hyper_tick:
 * 4000 / 40 = 100 ticks = 5 s at 20 ticks/s, as in the real game), and the buffs from the brawler's characters.csv row while
 * active: OverchargeSpeedPercent on the move speed (env.c rec_move), OverchargeDamagePercent on damage dealt and
 * OverchargeShieldPercent off damage taken (env.c my_root). The state goes to Python in NbeResp hyp_* (every response).
 *
 * The hypercharged super (and the other "overcharged" variants). The game's skill code asks Character::isOvercharged 0xb35bf0
 * (~170 call sites in the skill / projectile code, e.g. 0xb82d34 latches it into the skill instance +0x31 when a skill
 * starts, and 0xb7adfc then returns the SkillData's OverchargedVersion, skills.csv) — in this build that function is a bare
 * `return false`. Here it returns true for a brawler while its hypercharge is active (hyper_install), so the game's own
 * code runs every Overcharged* column of skills.csv: OverchargedVersion (3 supers and ~25 main attacks in this table),
 * OverchargedProjectiles, OverchargedChainProjectile, OverchargedSummonedCharacters, OverchargedAreaEffectObject/2,
 * OverchargedSpawnedItem and the Overcharged*Effect visuals; two reads of a normal list that ignore it (AttackPattern 11's
 * per-attack projectile, the Attack handler's summon) take the overcharged list here (hyper_proj_site, hyper_summon_bl),
 * a hypercharged brawler's Heal area heals here (oc_heal_areas), and the card-value stub 0xb5281c answers the hypercharge
 * card's values for the types in CARD_TYPES (Frank's and Glowy's full circle, Gene's 3 hands, Gale's 2 wider waves, Barley's
 * 3 brews, Brock's cluster volleys, Max's drinks, ...: my_card_value); the card-object stub 0xb39704 answers Melodie's card at
 * its one overcharge_axe_juggler call site (hyper_axe_card: her hypercharge notes). Hypercharges whose card Type
 * no libg call site asks for (code compiled out) are re-implemented: Lumi's side blasts (my_spawn), Griff's extra notes
 * (hyper_chain_extra, from spawnfix.c), Colette's spirit (hyper_spirit_damage, from env.c's charge contact) and Gus's
 * spirits (hyper_proj_end / hyper_spirits_tick); Carl's flame trail is libg's card component, whose tick hyper_trail_tick
 * runs (from env.c's hyper_tick); Damian's burning ground is libg's own component code, reached through env.c's charge_end_event; Fang's wall pass and
 * popcorn are env.c's (fang_oc_super); Alli's boost, whose one libg reader is unreachable here, is
 * hyper_stalk (from env.c's damage root); Tick's dead
 * head gets its summoner for its mine chain (hyper_dead_pet_owner, from superfix_items.c). Also here: Ruffs' +25 % (an area's
 * overcharged byte, hyper_area_mark), Poco's overheal shield (my_heal, hyper_shield_absorb), Pam's (hyper_overheal, from
 * superfix.c's turret heal) and Gray's portal shield (hyper_portal_shield, from superfix_moves.c's portals), Shade's dead
 * centre (hyper_dead_centre), Cordelius's slow of his realm target (hyper_realm_enter, hyper_slow_pct), the repeat of a Dot
 * area only the hypercharged super makes (Kaze's centre, hyper_area_tick) and
 * which areas those are (hyper_area_oc_only; superfix_status.c refreshes their Self / Ally statuses: Sandy's speed);
 * Stu's super recharge is env.c's charge_end. Seven brawlers (Jester, Beamer, Twins, Skater, Domain, Dancer,
 * MechaDudeBig) have a separate super instead (characters.csv OverchargedUltimateSkill): the game builds it as the brawler's
 * third skill instance (char+0x458[2], 0xb34560) but what picks it for a super cast is compiled out; here instances 1
 * (the super) and 2 are swapped while hypercharged, so the game's own super code casts it, and swapped back once the
 * hypercharge ended and that super is idle (hyper_unswap). Meg's mech (MechaDudeBig, what MechaDude's super turns into)
 * takes Meg's card, Kaze's other form (GeishaTransformed, Geisha's Pet) Kaze's. A character change hands a running hypercharge to the new form (hyper_char_changed). NbeResp hyp_supers / hyp_super_id count the supers cast while hypercharged and name the SkillData of
 * the last one (hyper_super_data, from env.c fire_input_now).
 * The visual effects (client side) are whatever the client draws from +0xa0 and the overcharged skill data.
 * Also here: the steering of homing projectiles (on_travel), which Belle's and Hank's hypercharged supers need, and the
 * circling of TravelType 8 ones (circle_travel: R-T's hypercharged lasers, Melodie's notes); both apply to every
 * projectile of that TravelType, hypercharged or not. NBHOST_HYPER_TRACE=1 logs each libg call site of isOvercharged. */
#include "nbhost.h"
#include "nbenv_proto.h"
#include <string.h>
#include <stdlib.h>
#include <unistd.h>

#define I32(p, o) (*(int32_t *)((uint8_t *)(p) + (o)))
#define U8(p, o) (*(uint8_t *)((uint8_t *)(p) + (o)))
#define PTR(p, o) (*(void **)((uint8_t *)(p) + (o)))
extern Module *g_libg;
#define B(off) ((uint8_t *)g_libg->base + (off))
void *div_data(int id);   /* env.c: data row by global id, NULL unless the table has it */
void *hook_replace(Module *m, uint64_t off, void *repl);
void hook_enter(Module *m, uint64_t off, void (*fn)(uint64_t *ctx));
void hook_bl(Module *m, uint64_t off, void *fn);

#define DRAIN_DEFAULT 40   /* +0xa4 that 0xc42584 sets without a duration modifier (4000 max / 40 = 100 ticks = 5 s) */

static void *player_cfg(void *p) {   /* the active loadout's config (player+0x30[player+0x40] -> +0x08); +0x28 hypercharge card */
    void **lo = PTR(p, 0x30); int li = I32(p, 0x40); void **ld = lo && li >= 0 && li < 8 ? lo[li] : NULL;
    return ld ? ld[1] : NULL;
}
static void *player_chardata(void *p) {
    void **lo = PTR(p, 0x30); int li = I32(p, 0x40); void **ld = lo && li >= 0 && li < 8 ? lo[li] : NULL;
    return ld ? ld[0] : NULL;
}
static int cd_pct(void *cd, unsigned off) { return cd ? ((int (*)(void *))B(off))(cd) : 0; }
/* CharacterData getters (characters.csv Overcharge* columns) */
#define CD_DAMAGE_PCT 0xab32a4
#define CD_SPEED_PCT 0xab32b0
#define CD_SHIELD_PCT 0xab32bc

/* the character's hypercharge card (cards.csv MetaType 6 whose target, card+0xd8, is this CharacterData), NULL if it has
 * none; cached per character (the cards table does not change while the host runs) */
void *hyper_card_for(void *chardata) {
    static struct { void *d, *card; } cache[128]; static int n;
    if (!chardata) return NULL;
    for (int k = 0; k < n; k++) if (cache[k].d == chardata) return cache[k].card;
    void *found = NULL;
    for (int idx = 0, miss = 0; idx < 20000 && miss < 64; idx++) {   /* table 23 = cards; stop after a run of missing rows */
        uint8_t *card = div_data(23000000 + idx);
        if (!card) { miss++; continue; }
        miss = 0;
        if (*(void **)(card + 0xd8) == chardata && I32(card, 0x108) == 6) { found = card; break; }
    }
    /* a brawler another one turns into (Meg's mech, MechaDudeBig, the SummonedCharacters of MechaDude's ChangeCharacter
     * super): the card of the brawler whose super it is (CharacterData +0x268 UltimateSkill, SkillData +0x80 / +0x8c) */
    for (int idx = 0, miss = 0; !found && idx < 20000 && miss < 64; idx++) {
        uint8_t *card = div_data(23000000 + idx);
        if (!card) { miss++; continue; }
        miss = 0;
        uint8_t *t = I32(card, 0x108) == 6 ? *(uint8_t **)(card + 0xd8) : NULL, *u = t ? PTR(t, 0x268) : NULL;
        void **sc = u ? PTR(u, 0x80) : NULL; int nsc = u ? I32(u, 0x8c) : 0;
        for (int k = 0; sc && k < nsc && k < 8; k++) if (sc[k] == chardata) { found = card; break; }
    }
    /* a form the brawler switches to (Kaze, GeishaTransformed: Geisha's Pet, reached by her change_character trait gadget;
     * Geisha_overcharge's text covers both forms' supers): the card of the brawler whose Pet (CharacterData +0x250, getter
     * 0xab3da4) it is. Only player brawlers ask (offline.c), so the other Pets (Tick's head, ...) never get here. */
    for (int idx = 0, miss = 0; !found && idx < 20000 && miss < 64; idx++) {
        uint8_t *card = div_data(23000000 + idx);
        if (!card) { miss++; continue; }
        miss = 0;
        uint8_t *t = I32(card, 0x108) == 6 ? *(uint8_t **)(card + 0xd8) : NULL;
        if (t && PTR(t, 0x250) == chardata) found = card;
    }
    if (n < 128) { cache[n].d = chardata; cache[n].card = found; n++; }
    return found;
}

typedef struct { int card, used, dmg_pct, speed_pct, shield_pct, supers, super_id, super_tick; } Hyp;
static Hyp g_hyp[NBE_MAXP];
static uint8_t *g_oc[NBE_MAXP];   /* player i's brawler while its hypercharge is active (what isOvercharged answers for) */
static uint8_t *g_sw[NBE_MAXP];   /* player i's brawler whose skill instances 1 / 2 are swapped (OverchargedUltimateSkill) */

static int g_heal_seen[32], g_nheal_seen; static long g_oc_heals;   /* oc_heal_areas: area ids already applied */
static void hyper_heal_clear(void) { memset(g_heal_seen, 0xff, sizeof g_heal_seen); g_nheal_seen = 0; }
static void hyper_pets_clear(void);
static void osh_clear(void);
void hyper_clear(void) { osh_clear(); memset(g_hyp, 0, sizeof g_hyp); memset(g_oc, 0, sizeof g_oc); memset(g_sw, 0, sizeof g_sw); hyper_heal_clear(); hyper_pets_clear(); }

/* Character::isOvercharged 0xb35bf0 (a bare `mov w0, wzr; ret` in this build): true for a brawler whose hypercharge is on.
 * Only the brawlers hyper_use activated answer true (not a read of char+0x68: some call sites may pass other objects). */
static int pet_slot(void *ch);   /* below: a pet a hypercharged super spawned (hyper_proj_spawn), -1 if none */
static int is_oc_char(void *ch) {
    if (!ch) return 0;
    for (int i = 0; i < NBE_MAXP; i++) if (g_oc[i] == ch && U8(ch, 0x68)) return 1;
    return pet_slot(ch) >= 0;
}
static int my_is_oc(void *ch) {
    int r = is_oc_char(ch);
    static int tr = -1; if (tr < 0) tr = getenv("NBHOST_HYPER_TRACE") != NULL;
    if (tr) {   /* debug: each call site once per (site, answer), and the object's first words */
        int any = 0; for (int i = 0; i < NBE_MAXP; i++) any |= g_oc[i] != NULL;
        static uint64_t seen[256]; static int ns; uint64_t lr = (uint64_t)__builtin_return_address(0) - (uint64_t)g_libg->base;
        uint64_t key = lr << 1 | r; int k = 0; while (k < ns && seen[k] != key) k++;
        if (any && k == ns && ns < 256) { seen[ns++] = key;
            LOG("[hyper-trace] site 0x%llx obj %p -> %d (vt 0x%llx, +8 %d)\n", (unsigned long long)lr, ch, r,
                ch ? (unsigned long long)((uint64_t)PTR(ch, 0) - (uint64_t)g_libg->base) : 0ULL, ch ? I32(ch, 8) : 0); }
    }
    return r;
}

/* Homing projectiles (projectiles_logic TravelType 4 with SteerStrength: Belle's and Hank's hypercharged supers, Gus's super,
 * Piper's homing shots, ...). The projectile update 0xb70408 calls the travel step 0xb709e4, which for a steering projectile
 * (0xb7634c, the SteerStrength with status modifiers, >= 1; TravelType 0xb7625c != 8) skips the straight-line position
 * 0xb76488 and moves the projectile to proj +0x94 / +0x98, a position only the compiled-out steer code writes: it stayed 0,
 * so the projectile was swept towards world (0, 0) on its first tick and ended there without a hit. Here an enter hook on
 * 0xb709e4 writes that position: Speed (proj +0x14c, units/s) / 20 per tick along a heading that starts at the aim
 * (+0xb0 start -> +0xb8 target) and, from SteerIgnoreTicks (data +0x224) on, turns by at most SteerStrength degrees per tick
 * towards the nearest live enemy character within HomeDistance (data +0x228) x 100 units of the projectile. The game's own
 * code then sweeps to that position (walls, hits, damage) and ends the flight at SteerLifeTime (its end tick +0x2c). */
#define STEER_MAX 64
static struct { uint8_t *pr; int start, last, heading; } g_steer[STEER_MAX];
static long g_nsteer, g_nsteer_turn;
static int sin1024(int deg) { return ((int (*)(int))B(0xd005e0))(deg); }   /* sin x 1024, degrees */
static int angle_to(int dx, int dy) { return (dx | dy) ? ((int (*)(int, int))B(0xd00960))(dx, dy) : 0; }   /* degrees */
/* nearest live enemy character of projectile pr within r of (x, y) (the object list and tests of spawnfix.c nearest_enemy) */
static uint8_t *steer_target(uint8_t *pr, int x, int y, int r) {
    uint8_t *mgr = PTR(pr, 0x20); void **arr = mgr ? PTR(mgr, 0x28) : NULL; int cnt = mgr ? I32(mgr, 0x34) : 0;
    if (!arr || cnt < 1 || cnt > 512) return NULL;
    uint8_t *best = NULL; long bd = (long)r * r;
    for (int i = 0; i < cnt; i++) {
        uint8_t *o = arr[i]; void **vt = o && o != pr ? *(void ***)o : NULL;
        if (!vt || o == PTR(pr, 0xe0) || I32(o, 0x88) != I32(pr, 0x88) || I32(o, 0x84) == I32(pr, 0x84)) continue;
        if (!(((uint64_t (*)(void *))vt[0x68 / 8])(o) & 1) || !(((uint64_t (*)(void *))B(0xc70134))(o) & 1)) continue;
        long dx = I32(o, 0x38) - x, dy = I32(o, 0x3c) - y, d2 = dx * dx + dy * dy;
        if (d2 < bd) { bd = d2; best = o; }
    }
    return best;
}
/* Circling projectiles (TravelType 8: R-T's hypercharged security lasers SplitterCirclingProjectile, Melodie's notes
 * AxeJugglerProjectile2, ...). Their spawn 0xb78c58 sets the angle on the circle (proj +0x454, degrees: 360 / n apart; a new
 * one re-spaces the owner's others from the first one's +0x454, 0xb79004..0xb79068) and the ring radius +0x498 when the
 * spawner gives one (libg's own Brawler_Splitter tick: 1000). The travel step 0xb709e4 ends the flight once the owner
 * (+0xe0) is gone or the end tick passed, then moves the projectile to +0x94 / +0x98 (0xb70bfc), the position the
 * compiled-out circling code writes: it stayed 0, so the lasers jumped to the map origin. Here (same enter hook as the homing
 * steer): that position = the owner's + radius along the angle, radius = +0x498 or else TravelTypeVariable (data +0x214, the
 * one 0xb70c44 reads: Melodie 650), angle = +0x454 + the turn since tick 0, one clock for all, so the spacing the spawner
 * sets holds. The turn: Speed (proj +0x14c) units/s along the circle ([?] guess: no client code turns it; Speed read as for
 * every other projectile; R-T's Speed 29 makes his lasers almost still, Melodie's 860 at 650 is a turn in 4.7 s). The
 * game's own code then places it there and its hits run as for any projectile. */
static long g_ncircle;
static void circle_travel(uint8_t *pr, uint8_t *d) {
    uint8_t *o = PTR(pr, 0xe0);
    int r = I32(pr, 0x498) > 0 ? I32(pr, 0x498) : I32(d, 0x214);
    if (!o || r < 1 || r > 5000) return;
    int now = I32(pr, 0x410) + ((int (*)(void *))B(0xc26bd8))(((void *(*)(void *))B(0xb6a378))(pr));
    /* degrees turned: Speed / 20 units per tick on a circle of radius r = Speed x 180 / (20 pi r) degrees per tick */
    long turn = now > 0 ? (long)now * I32(pr, 0x14c) * 9000 / (31416L * r / 10000) / 1000 : 0;
    int a = (int)(((I32(pr, 0x454) + turn) % 360 + 360) % 360);
    I32(pr, 0x94) = I32(o, 0x38) + ((sin1024(a + 90) * r) >> 10); I32(pr, 0x98) = I32(o, 0x3c) + ((sin1024(a) * r) >> 10);
    if (g_ncircle++ < 6) LOG("[hyper] circling projectile %d (data %d): owner %d, radius %d, angle %d at tick %d\n", I32(pr, 8), I32(d, 0x20),
                             I32(o, 8), r, a, now);
}
static void on_travel(uint64_t *c) {
    uint8_t *pr = (uint8_t *)c[0], *d = pr ? PTR(pr, 0x10) : NULL;
    if (!d) return;
    if (((int (*)(void *))B(0xb7625c))(pr) == 8) { circle_travel(pr, d); return; }
    int str = ((int (*)(void *))B(0xb7634c))(pr); if (str < 1) return;
    int now = I32(pr, 0x410) + ((int (*)(void *))B(0xc26bd8))(((void *(*)(void *))B(0xb6a378))(pr)), start = I32(pr, 0x28);
    int k = 0, fr = -1;
    for (; k < STEER_MAX && !(g_steer[k].pr == pr && g_steer[k].start == start); k++)
        if (fr < 0 && (!g_steer[k].pr || now - g_steer[k].last > 200)) fr = k;   /* free, or stale (the object is long gone) */
    if (k == STEER_MAX) {
        if (fr < 0) return;
        k = fr; g_steer[k].pr = pr; g_steer[k].start = g_steer[k].last = start; g_nsteer++;
        g_steer[k].heading = angle_to(I32(pr, 0xb8) - I32(pr, 0xb0), I32(pr, 0xbc) - I32(pr, 0xb4));
        if (g_nsteer <= 10) LOG("[hyper] homing projectile %d (data %d): heading %d, steer %d, ignore %d, home %d, end tick %d\n", I32(pr, 8),
                                I32(d, 0x20), g_steer[k].heading, str, I32(d, 0x224), I32(d, 0x228), I32(pr, 0x2c));
    }
    int x = I32(pr, 0x38), y = I32(pr, 0x3c), step = I32(pr, 0x14c) / 20, h = g_steer[k].heading;
    for (int t = g_steer[k].last + 1; t <= now && t <= g_steer[k].last + 8; t++) {   /* one step per tick (the first call: none) */
        uint8_t *tg = t - start >= I32(d, 0x224) ? steer_target(pr, x, y, I32(d, 0x228) * 100) : NULL;
        if (tg) {
            int want = angle_to(I32(tg, 0x38) - x, I32(tg, 0x3c) - y), diff = ((want - h) % 360 + 540) % 360 - 180;
            h += diff > str ? str : diff < -str ? -str : diff; h = (h % 360 + 360) % 360; g_nsteer_turn++;
        }
        x += (sin1024(h + 90) * step) >> 10; y += (sin1024(h) * step) >> 10;
    }
    if (now > g_steer[k].last) g_steer[k].last = now;
    g_steer[k].heading = h; I32(pr, 0x94) = x; I32(pr, 0x98) = y;
}
/* Two places that read the normal list where the overcharged one applies (both only for a skill instance whose +0x31
 * overcharged latch is set, sk = the skill instance, sd = its SkillData):
 * - AttackPattern 11 (Lumi: a different projectile per attack): the character's attack tick picks SkillData Projectiles
 *   (+0x58, count +0x64)[attack % count] at 0xb4b978 (`ldr x9, [x25, #88]`; x19 char, x20 skill instance or 0, x25 data).
 *   hyper_proj_site replaces that load: the OverchargedProjectiles list (+0x68, count +0x74) when it is as long.
 * - SummonedCharacters (Pam's station): the Attack handler of the skill execute 0xb7b268 (x19 skill instance, x21 its data)
 *   reads getSummonedCharacter 0xb0ddf8(data, 0) at 8 `bl`s (HP / level / the setSummon 0xb5a6b4 at 0xb7ef1c);
 *   hyper_summon_bl answers the first OverchargedSummonedCharacters (+0x90, count +0x9c) instead. */
static int sk_oc(uint8_t *sk, uint8_t *sd) {
    uint8_t *d = sk ? PTR(sk, 0) : NULL;
    return d && U8(sk, 0x31) && (d == sd || ((void *(*)(void *))B(0xb0def8))(d) == sd);   /* data or its OverchargedVersion */
}
uint64_t g_hyper_proj_next;   /* libg 0xb4b97c */
__attribute__((target("general-regs-only"))) void *hyper_proj_list(uint8_t *ch, uint8_t *sk, uint8_t *sd) {
    (void)ch;
    return sk_oc(sk, sd) && I32(sd, 0x74) == I32(sd, 0x64) && PTR(sd, 0x68) ? PTR(sd, 0x68) : PTR(sd, 0x58);
}
__attribute__((target("general-regs-only"))) void *hyper_summon_data(uint8_t *sd, int i, uint8_t *sk) {
    if (sd && sk_oc(sk, sd) && I32(sd, 0x9c) > 0 && ((void **)PTR(sd, 0x90))[0]) return ((void **)PTR(sd, 0x90))[0];
    return ((void *(*)(void *, int))B(0xb0ddf8))(sd, i);
}
/* (global symbols: each gets its own GOT slot) entered from hook_replace's stub at 0xb4b978 (every register as at the site but x16): x9 = the list, back at 0xb4b97c;
 * x0-x18 (but x9) and x30 kept; the flags are not live there */
__asm__(".pushsection .text\n.p2align 2\n.globl hyper_proj_site\n.type hyper_proj_site, %function\nhyper_proj_site:\n"
        " sub sp, sp, #160\n stp x0, x1, [sp]\n stp x2, x3, [sp, #16]\n stp x4, x5, [sp, #32]\n stp x6, x7, [sp, #48]\n"
        " stp x8, x10, [sp, #64]\n stp x11, x12, [sp, #80]\n stp x13, x14, [sp, #96]\n stp x15, x17, [sp, #112]\n"
        " stp x18, x30, [sp, #128]\n mov x0, x19\n mov x1, x20\n mov x2, x25\n bl hyper_proj_list\n mov x9, x0\n"
        " ldp x0, x1, [sp]\n ldp x2, x3, [sp, #16]\n ldp x4, x5, [sp, #32]\n ldp x6, x7, [sp, #48]\n ldp x8, x10, [sp, #64]\n"
        " ldp x11, x12, [sp, #80]\n ldp x13, x14, [sp, #96]\n ldp x15, x17, [sp, #112]\n ldp x18, x30, [sp, #128]\n"
        " add sp, sp, #160\n adrp x16, g_hyper_proj_next\n ldr x16, [x16, :lo12:g_hyper_proj_next]\n br x16\n"
        ".globl hyper_summon_bl\n.type hyper_summon_bl, %function\nhyper_summon_bl:\n mov x2, x19\n b hyper_summon_data\n.popsection\n");
void hyper_proj_site(void); void hyper_summon_bl(void);

/* A Heal area (area_effects_logic Type Heal, enum 3) of a hypercharged brawler, e.g. Pam's MinigunOverchargedInstantHeal
 * ("Pam's turret heals on deploy", TID_MINIGUN_DUDE_OVERCHARGE_DESC): the area apply 0xb29494 acts on a Heal area only
 * for a positive amount (0xb29628..0xb29670) and no client code heals with it. Here, after each tick (hyper_tick_player),
 * each new Heal area the hypercharged brawler owns (area +0x108) heals every living character of its team (+0x84) within
 * Radius (+0x12c) once, up to max HP (the turret's later heals overheal: hyper_overheal), by the area's damage word +0xe8
 * negated, or where that is not negative by the DamageScaleType 2 amount of the area create 0xb2b124: the owner's max HP
 * +0x3c8 x Damage (+0x134) / 100. */
static void oc_heal_areas(uint8_t *ch) {
    void *sim = ((void *(*)(void *))B(0xb6a378))(ch), *h = sim ? PTR(sim, 0) : NULL;
    int n = h ? I32(h, 0xc) : 0; void **v = h ? PTR(h, 0) : NULL;
    for (int i = 0; v && i < n && i < 4096; i++) {
        uint8_t *a = v[i], *d = a ? PTR(a, 0x10) : NULL;
        if (!d || I32(d, 0x20) / 1000000 != 17 || I32(d, 0x118) != 3 || PTR(a, 0x108) != ch) continue;
        int id = I32(a, 8), k = 0; while (k < 32 && g_heal_seen[k] != id) k++;
        if (k < 32) continue;
        g_heal_seen[g_nheal_seen++ & 31] = id;
        int heal = I32(a, 0xe8) < 0 ? -I32(a, 0xe8) : (I32(d, 0x138) == 2 ? -I32(ch, 0x3c8) * I32(d, 0x134) / 100 : 0);
        int r = I32(d, 0x12c), team = I32(ch, 0x84), healed = 0;
        for (int q = 0; heal > 0 && q < n && q < 4096; q++) {
            uint8_t *c = v[q];
            if (!c || PTR(c, 0) != B(0x1209020) || I32(c, 0x3c4) <= 0 || I32(c, 0x84) != team) continue;   /* a living ally */
            long dx = I32(c, 0x38) - I32(a, 0x38), dy = I32(c, 0x3c) - I32(a, 0x3c);
            int hp = I32(c, 0x3c4), mx = I32(c, 0x3c8);
            if (dx * dx + dy * dy > (long)r * r || hp >= mx) continue;
            I32(c, 0x3c4) = hp + heal < mx ? hp + heal : mx; healed++; g_oc_heals++;
        }
        static int nlog; if (nlog++ < 20) LOG("[hyper] heal area %d (word %d) at %d,%d r %d: %d hp to %d characters\n", I32(d, 0x20),
                                              I32(a, 0xe8), I32(a, 0x38), I32(a, 0x3c), r, heal, healed);
    }
}

/* The hypercharge card's own values (cards.csv MetaType 6: Type, Value..Value6). The skill code asks the character's card
 * through 0xb5281c(character, card type enum, value index 1..6) -> Value<index>, or -1 without such a card; in this build that
 * function is a bare `mov w0, #-1; ret` (~55 call sites, ~20 card types). The Attack handler's summon reads it for
 * overcharge_more_pets (Ash, 0xb7eeac..0xb7eee8, only for a skill instance whose +0x31 latch is set): NumSpawns + Value,
 * MaxSpawns + Value2 (Knight_overcharge 5 / 10: "Little Helper spawns 5 more rats"). my_card_value answers it from the card of
 * the brawler that holds it (Type enum card +0x100, Value<i> 0xaa9568), for the types in CARD_TYPES only, also after its
 * hypercharge ended: every call site of these types checks isOvercharged (or the skill's +0x31 / +0x49 latch) itself, except
 * Rosa's, which ends her hypercharged area when her super ends, also when that is after the hypercharge (as the game's card
 * holder would answer). The other types' call sites are not checked here and keep the -1 they had.
 * overcharge_attack_pattern_override (202): the super's Attack handler (0xb7e1a8..0xb7f2ec) takes the AttackPattern from Value
 * and NumBulletsInOneAttack from Value2 in place of the skill's. HammerDude_overcharge 19 / 10 (Frank: "hits an entire circle
 * around him"; pattern 19 is the full circle of MegaBossFrankAttackHyper) and Mender_overcharge 19 / 14 (Glowy).
 * Checked and left at -1 (types above 210): _door_man 272 (portal count, Value 2 = the default
 * 2; the shield Value2 / Value3 has no reader: hyper_portal_shield), _mecha_dude 281 (Value 0 / 0, which the reader 0xb7d030 skips), _geisha 296 (Value2 %
 * on the skill's ChargeSpeed, 0 for GeishaUlti). overcharge_stalker 319 (Alli 25 / 20): libg reads it at 0xb2a340 only
 * while the character's stalk aggregate +0x96c is set, which only the network decode writes; env.c's damage root asks it
 * through hyper_stalk instead (Value1 % of the target's max HP in place of the super's % of its current HP, Value2 % of the
 * damage dealt healed). */
#define CT_PROJ_SPAWN 177    /* overcharge_projectile_spawn (the `mov w8, #N` per Type string in the card loader 0xaa3000..) */
#define CT_PET_BUFF 179      /* overcharge_pet_buff_stats */
#define CT_PATTERN_OVERRIDE 202   /* overcharge_attack_pattern_override (the parse at 0xaa66e4) */
#define CT_MORE_PETS 274     /* overcharge_more_pets */
#define CT_RUFFS 263         /* overcharge_ruffs (Ruffs_overcharge 25, "Ruffs' Super deals 25% more damage"): the area apply
                              * 0xb29494 adds Value % to the damage of an area of the owner's super (+0xf8 == 2) whose
                              * overcharged byte +0x2e4 is set (0xb29bac..0xb29bf4, applied at 0xb2a108); hyper_area_mark sets
                              * that byte */
#define CT_DRAGON_RIDER 304  /* overcharge_dragon_rider (Draco 10 / 4, "breathes more flames in a wider area and with longer
                              * range"): while hypercharged and mounted (CharacterData UniqueProperty 28), the dragon's attack
                              * fires NumBulletsInOneAttack + Value2 flames (Attack handler 0xb7e3dc: 4 -> 8 at Spread 90) and
                              * reaches Value more tiles (the range bonus 0xc6e4d4 -> 0xc6e958) */
#define CT_STALKER 319      /* overcharge_stalker */
#define CT_AXE_JUGGLER 266   /* overcharge_axe_juggler (hyper_axe_card) */
#define CT_DIGGER 307        /* overcharge_digger (Moe 10 / 300 / 100 / 5, "Driller has longer range and lasts for longer"):
                              * the dive's ChargeSpeed + Value3 % (skill fire 0xb7bc14: 2500 -> 5000), its range bonus + Value
                              * tiles (0xc6e754), and the Driller's (UniqueProperty 32) attack Value4 more tiles (0xc6e998:
                              * DiggerDrillWeapon 5 -> 10). Value2 (the longer Driller form) has no reader in this build. */
/* The other types whose call sites apply the value themselves (the Type enum from the card loader's string table; Value<n>
 * from cards.csv; the "Attack handler" is the super's attack setup 0xb7d108..0xb7f2ec, where the overrides chain 192 -> 201
 * -> 194 -> 200 -> 202 for the super, w27 == 2): */
static const int CARD_TYPES[] = {
    CT_PATTERN_OVERRIDE, CT_MORE_PETS, CT_RUFFS,
    166,   /* overcharge_weapon_spread, Shelly (ShotgunGirl_overcharge 33): Spread + Value (100 -> 133, 0xb7deec): "Super
            * Shell is 33% larger" */
    178,   /* overcharge_slowing_area, Rosa (3): when Rosa's super ends (0xb7cc78, Value >= 0 only), the RosaOverchargedUltiArea
            * (TimeMs 600000) ends with it: "slows down all nearby enemies while her Super is active" */
    192,   /* overcharge_brock, Brock (750 / 18 / 7 / 400 / 500 / 420): MsBetweenAttacks Value (ActiveTime 1850 / 750 = 2
            * volleys), Spread 0, AttackPattern Value2, NumBulletsInOneAttack Value3, damage Value4 (0xb7d8fc, 0xb7e1c4..);
            * Value5 / Value6 only with Brock's star power type 48 (0xb7dd78..): "Rockets fired during the Super are cluster bombs" */
    193,   /* overcharge_speedy, Max (6, only >= 0 asked): Max's AreaBuff super (+0x31 latch) throws SpeedyOverchargedProjectile
            * at each teammate, homing on it (0xb7d590): "throws an energy drink to each team member" */
    194,   /* overcharge_hookdude, Gene (150 / 3): Spread Value, NumBulletsInOneAttack Value2 (0xb7d944, 0xb7ecc8): "splits into
            * 3 different hands ... the other 2 go diagonally" */
    197,   /* overcharge_transport_shadowrealm, Lily (100): her hypercharged super's hit sends the target and Lily to the Shadow
            * Realm for Value (0xb7472c, 0xb58214's duration): "transports the enemy and Lily to the Shadow Realm" */
    200,   /* overcharge_blower, Gale (7 / 400 / 200): NumBulletsInOneAttack Value (4 -> 7), ActiveTime Value2 (also the skill
            * instance's +8 at its start, 0xb81f3c), MsBetweenAttacks Value3: 400 / 200 = 2 waves (0xb7d9cc.., 0xb7f29c):
            * "slightly wider and fires twice" */
    201,   /* overcharge_barkeep, Barley (450 / 21 / 100): MsBetweenAttacks Value (ActiveTime 1050), AttackPattern Value2,
            * Spread Value3 (0xb7d9a8, 0xb7ec2c): "hurls 3 big brews" */
    203,   /* overcharge_insectMan, Angelo (1, only >= 1 asked): the super's area follows Angelo (0xb29350 at 0xb7f078 /
            * 0xb7fefc): "the Super will follow Angelo" */
    209,   /* overcharge_sniper, Piper (1 / 2500): ChargeSpeed Value2 (1500 -> 2500, 0xb7bbfc): "departs at an increased speed";
            * Value is not asked (no call site): the terrain breaking is not here */
    CT_DRAGON_RIDER, CT_DIGGER,
    CT_STALKER,   /* overcharge_stalker, Alli (25 / 20): hyper_stalk (env.c's damage root) */
};
static void *g_card[NBE_MAXP];   /* player i's hypercharge card (cfg +0x28), set at hyper_use */
static uint8_t *g_card_ch[NBE_MAXP]; static int g_card_id[NBE_MAXP];   /* the brawler holding it (object, id), kept after the end */
static int card_value(void *card, int idx) { return ((int (*)(void *, int))B(0xaa9568))(card, idx); }
static int my_card_value(uint8_t *ch, int type, int idx) {
    unsigned k = 0; while (k < sizeof CARD_TYPES / sizeof *CARD_TYPES && CARD_TYPES[k] != type) k++;
    if (!ch || k == sizeof CARD_TYPES / sizeof *CARD_TYPES) return -1;
    for (int i = 0; i < NBE_MAXP; i++)
        if (g_card_ch[i] == ch && I32(ch, 8) == g_card_id[i] && g_card[i] && I32(g_card[i], 0x100) == type) {
            int v = card_value(g_card[i], idx);
            static int nlog; if (nlog++ < 20) LOG("[hyper] card value: player %d type %d value%d = %d\n", i, type, idx, v);
            return v;
        }
    return -1;
}
/* An area's overcharged byte +0x2e4 (read only by overcharge_ruffs' bonus above). libg copies it from the projectile's
 * +0x5a4 at the projectile's area spawn (0xb76f48), a byte only server code writes, and a chained area gets none: Ruffs'
 * damage comes from RuffsOverchargedSupplyExplosion, the ChainAreaEffect of the RuffsOverchargedSupplySpawn his
 * hypercharged super's projectile drops. hyper_area_mark (spawnfix.c's enter hook on the area apply 0xb29494) sets it on an
 * area of a CT_RUFFS card holder's super whose data is reached from the super's OverchargedProjectiles (the area rows a
 * projectile row names, and their chains) and not from its Projectiles. Not through the projectile byte: 0xb77104 would add
 * OverchargeDamagePercent a second time (env.c my_root adds it). */
static void **g_arows; static int g_narows;   /* every area row (table 17), sorted */
static int cmp_ptr(const void *a, const void *b) { uintptr_t x = *(const uintptr_t *)a, y = *(const uintptr_t *)b; return x < y ? -1 : x > y; }
static int is_area_row(void *p) { return p && g_narows && bsearch(&p, g_arows, g_narows, sizeof *g_arows, cmp_ptr); }
static int readable(const void *p, size_t len) {   /* p .. p+len can be read (write(2) to a pipe fails with EFAULT if not) */
    static int fd[2] = {-1, -1}; char buf[64];
    if (fd[0] < 0 && pipe(fd)) return 0;
    if (len > sizeof buf || write(fd[1], p, len) != (ssize_t)len) return 0;
    return read(fd[0], buf, len) == (ssize_t)len;
}
static void area_add(void *a, void **s, int *n, int cap, int depth);
static void area_reach(uint8_t *d, int lim, void **s, int *n, int cap, int depth) {   /* area rows row d names, and their chains */
    for (int o = 0x28; o < lim && *n < cap; o += 8) {
        void *a = PTR(d, o);
        if (is_area_row(a)) { area_add(a, s, n, cap, depth); continue; }
        /* a list column (pointer, count at +0xc, as the skill lists +0x58 / +0x64): SpawnAreaEffectObjectsAdditional (Kaze's
         * GeishaStormOverchargedCenterDamage) */
        int cnt = o + 0x10 <= lim ? I32(d, o + 0xc) : 0;
        if (cnt < 1 || cnt > 8 || !a || ((uintptr_t)a & 7) || !readable(a, cnt * 8)) continue;
        for (int k = 0; k < cnt; k++) if (is_area_row(((void **)a)[k])) area_add(((void **)a)[k], s, n, cap, depth);
    }
}
static void area_add(void *a, void **s, int *n, int cap, int depth) {
    { int k = 0;
        while (k < *n && s[k] != a) k++;
        if (k < *n || *n >= cap) return;
        s[(*n)++] = a;
        if (depth > 0) area_reach(a, 0x200, s, n, cap, depth - 1);   /* area rows end before +0x200 (InnerRadius +0x1b8) */
    }
}
/* 1 if area a's data is reached from its owner's super's OverchargedProjectiles and not from its Projectiles (an area only
 * the hypercharged super makes); the owner is a brawler hyper_use activated (g_card_ch) */
static int oc_only_area(uint8_t *a) {
    uint8_t *d = a ? PTR(a, 0x10) : NULL, *ow = d ? PTR(a, 0x108) : NULL; int i = 0;
    while (ow && i < NBE_MAXP && !(g_card_ch[i] == ow && I32(ow, 8) == g_card_id[i])) i++;
    if (!ow || i == NBE_MAXP) return 0;
    static struct { void *cd; void *oc[16]; int n; } cache[16]; static int nc;
    void *cd = ((void *(*)(void *))B(0xb6a384))(ow); int c = 0;
    while (c < nc && cache[c].cd != cd) c++;
    if (c == nc) {
        if (!g_arows) {
            g_arows = malloc(4000 * sizeof *g_arows);
            for (int idx = 0, miss = 0; g_arows && idx < 4000 && miss < 64; idx++) {
                void *r = div_data(17000000 + idx);
                if (!r) { miss++; continue; }
                miss = 0; g_arows[g_narows++] = r;
            }
            if (g_narows) qsort(g_arows, g_narows, sizeof *g_arows, cmp_ptr);
        }
        uint8_t *sd = cd ? PTR(cd, 0x268) : NULL;   /* UltimateSkill: Projectiles +0x58 (count +0x64), OverchargedProjectiles +0x68 (+0x74) */
        void *nrm[32]; int nn = 0, no = 0; void *oc[16];
        for (int k = 0; sd && k < I32(sd, 0x64) && k < 8; k++) area_reach(((uint8_t **)PTR(sd, 0x58))[k], 0x400, nrm, &nn, 32, 3);
        for (int k = 0; sd && k < I32(sd, 0x74) && k < 8; k++) area_reach(((uint8_t **)PTR(sd, 0x68))[k], 0x400, oc, &no, 16, 3);
        if (nc == 16) nc = 0;
        c = nc++; cache[c].cd = cd; cache[c].n = 0;
        for (int k = 0; k < no; k++) { int j = 0; while (j < nn && nrm[j] != oc[k]) j++; if (j == nn) cache[c].oc[cache[c].n++] = oc[k]; }
        LOG("[hyper] areas only the hypercharged super of character data %d makes: %d (normal super: %d)\n", I32(cd, 0x20), cache[c].n, nn);
    }
    for (int k = 0; k < cache[c].n; k++) if (cache[c].oc[k] == d) return 1;
    return 0;
}
int hyper_area_oc_only(uint8_t *a) { return oc_only_area(a); }
void hyper_area_mark(uint8_t *a) {
    uint8_t *ow = a && PTR(a, 0x10) ? PTR(a, 0x108) : NULL;
    if (!ow || I32(a, 0xf8) != 2 || U8(a, 0x2e4) || my_card_value(ow, CT_RUFFS, 1) < 0 || !oc_only_area(a)) return;
    U8(a, 0x2e4) = 1;
    static int nlog; if (nlog++ < 20) LOG("[hyper] area %d (data %d) marked overcharged\n", I32(a, 8), I32((uint8_t *)PTR(a, 0x10), 0x20));
}
/* Dot areas (type 2) only the hypercharged super makes (Kaze's GeishaStormOverchargedCenterDamage, TimeMs 5000: "The center
 * of the Fan Storm damages enemies over time"): the area apply 0xb29494 runs once, at the spawn (no area code calls it again;
 * the per-tick damage is server code), so the area hit once. From the area tick (superfix.c's enter hook on 0xb28c0c) the
 * apply runs again every DOT_EVERY ticks while the area lives (+0xd0 start .. +0xd8 end), its +0xd0 / +0xd4 / +0xd8 saved
 * and restored as superfix.c's slippery re-apply does. The normal super's Dot areas are left as they are. */
#define DOT_EVERY 20   /* [?] the row has no interval: 1 s, as the SameAreaEffectCanNotDamageMs 1000 of other lingering areas */
static long g_oc_dot;
void hyper_area_tick(uint8_t *a) {
    uint8_t *d = a ? PTR(a, 0x10) : NULL, *sim = d ? ((void *(*)(void *))B(0xb6a378))(a) : NULL;
    if (!sim || I32(d, 0x118) != 2) return;
    int now = I32(sim, 0x10), d0 = I32(a, 0xd0), d4 = I32(a, 0xd4), d8 = I32(a, 0xd8), el = now - d0;
    if (el <= 0 || el % DOT_EVERY || now > d8 || !oc_only_area(a)) return;
    ((void (*)(void *))B(0xb29494))(a);
    I32(a, 0xd0) = d0; I32(a, 0xd4) = d4; I32(a, 0xd8) = d8; g_oc_dot++;
    static int nlog; if (nlog++ < 10) LOG("[hyper] overcharged Dot area %d (data %d) hit again after %d ticks, dmg %d\n", I32(a, 8), I32(d, 0x20), el, I32(a, 0xe8));
}

/* Alli's hypercharge (Stalker_overcharge 25 / 20, TID_STALKER_OVERCHARGE_DESC "Alli's Super damages for <VALUE1>% of enemies
 * max health. Damaging enemies heals Alli for <VALUE2>% of damage dealt."): Value<idx> of the card while ch's hypercharge is
 * active, else -1. Her super's boost (StalkerUltiDamageTargetCurrentHpBoost, 25 % of the target's current HP on the next
 * hit) is env.c's; there the hypercharged boost takes Value1 % of the target's max HP, as libg's own reader does (0xb2a340:
 * the card value replaces the status percent and 0xc70898's w2 = isOvercharged picks max HP +0x3c8 over HP +0x3c4), and
 * heals her Value2 % of the HP that hit removed. [?] that the heal is for the boosted hit only: Value2 has no reader. */
int hyper_stalk(uint8_t *ch, int idx) { return is_oc_char(ch) ? my_card_value(ch, CT_STALKER, idx) : -1; }

/* Pets of a hypercharged super. The projectile end 0xb75b24 calls 0xb77344(projectile), which spawns the projectile's
 * character (+0x1c0: its SpawnCharacter or the skill's summon, Charlie's cocoon, Jessie's turret, Juju's Gris-Gris, Ash's
 * rats) +0x3e8 times around it. Two hypercharge card types act on these summons in server code this build lacks (no reader
 * of either type is left): overcharge_projectile_spawn (Charlie, Cocooner_overcharge 3: "Cocoon spawns 3 spiders that seek
 * and attack the nearest enemies") and overcharge_pet_buff_stats (Jessie 50 / 20, Juju 20 / 20 / 250, Nita 20 / 0 / 150:
 * "+Value% health, +Value2% damage, +Value3% speed", TID_*_OVERCHARGE_DESC). hyper_proj_spawn takes that call: for a
 * projectile of the owner's ulti OverchargedProjectiles (the hypercharged super's) whose player holds such a card,
 * - overcharge_projectile_spawn: after the normal spawn, the same spawn again with the owner's Pet (CharacterData +0x250,
 *   CocoonerPet) x Value;
 * - overcharge_pet_buff_stats: each character the spawn added gets max HP and HP x (100 + Value) / 100, and is kept here
 *   (pet_slot): its damage dealt x (100 + Value2) / 100 (hyper_pet_damage, env.c my_root), its move speed x (100 + Value3)
 *   / 100 (hyper_pet_speed, env.c rec_move), isOvercharged answers true for it (char +0x68 = 1), and its overcharged-pet
 *   byte +0xaac (what the spawn 0xb56e00 stores from a stack argument at 0xb5771c) is set, so the game's own code takes its
 *   OverchargedAutoAttackProjectile (CharacterData +0x68, read at 0xb3e848 / 0xb3f4ac only when +0xaac is set: Juju's
 *   "bigger needles", Jessie's and Penny's turrets) and its DeathOverchargedAreaEffect (Tick's head). A pet with a
 *   DeathOverchargedAreaEffect (CharacterData +0xd0, count +0xdc) takes no damage buff: Tick's Value2 5 is the minimines
 *   his text names ("leaving behind 5 of his minimines"), not a damage percent. Value4 (Penny 5, "a bigger cannon that shoots
 *   <VALUE1> cannonballs at a time instead of 1"): each OverchargedAutoAttackProjectile the pet fires comes Value4 times
 *   (my_spawn). */
#define PET_MAX 32
static struct { uint8_t *ch; int id, dmg_pct, speed_pct, death_oc, owner_id, x, y, shots; } g_pet[PET_MAX];
void *env_obj_by_id(void *sim, int id);   /* env.c */
/* A dead hypercharged pet's DeathOverchargedAreaEffect (Tick's ClusterBombPetOverchargedExplosion) has no owner (+0x108 NULL
 * when it expires), so superfix_items.c's ChainAreaEffect (ClusterBombOverchargedExplosion, 6 ClusterOverchargedMine) had
 * none to spawn with. hyper_pets_tick keeps each such pet's last position; hyper_dead_pet_owner gives the area expiring at
 * (x, y) the summoner of the dead pet that stood nearest (within DEAD_PET_R), once per pet, and *wdmg = the summoner's main
 * attack Damage (CharacterData +0x260, getter 0xb0dc14), the damage of "his minimines" (power 1: my_root scales it). */
#define DEAD_PET_R 700   /* the pet can move a little in its last tick; the area spawns where it died */
void hyper_pets_tick(void *sim) {
    for (int k = 0; k < PET_MAX; k++) if (g_pet[k].death_oc) {
        uint8_t *c = env_obj_by_id(sim, g_pet[k].id);
        if (c && I32(c, 0x3c4) > 0) { g_pet[k].x = I32(c, 0x38); g_pet[k].y = I32(c, 0x3c); }
    }
}
void *hyper_dead_pet_owner(void *sim, int x, int y, int *wdmg) {
    int best = -1; long bd = (long)DEAD_PET_R * DEAD_PET_R;
    for (int k = 0; k < PET_MAX; k++) if (g_pet[k].death_oc && g_pet[k].owner_id) {
        uint8_t *c = env_obj_by_id(sim, g_pet[k].id); if (c && I32(c, 0x3c4) > 0) continue;   /* still alive */
        long dx = g_pet[k].x - x, dy = g_pet[k].y - y; if (dx * dx + dy * dy <= bd) { bd = dx * dx + dy * dy; best = k; }
    }
    if (best < 0) return NULL;
    g_pet[best].death_oc = 0;
    uint8_t *o = env_obj_by_id(sim, g_pet[best].owner_id); if (!o) return NULL;
    void *cd = ((void *(*)(void *))B(0xb6a384))(o), *wd = cd ? PTR(cd, 0x260) : NULL;
    *wdmg = wd ? ((int (*)(void *))B(0xb0dc14))(wd) : 0;
    return o;
}
static long g_npet_buff, g_npet_spawn;
static int pet_slot(void *ch) {
    for (int k = 0; ch && k < PET_MAX; k++) if (g_pet[k].ch == ch && I32(ch, 8) == g_pet[k].id) return k;
    return -1;
}
int hyper_pet_damage(void *attacker, int d) {
    int k = d > 0 ? pet_slot(attacker) : -1;
    return k >= 0 && g_pet[k].dmg_pct ? d * (100 + g_pet[k].dmg_pct) / 100 : d;
}
int hyper_pet_speed(uint8_t *ch) {   /* 0 = unchanged */
    int k = pet_slot(ch); if (k < 0 || !g_pet[k].speed_pct) return 0;
    void *cd = ((void *(*)(void *))B(0xb6a384))(ch); int base = cd ? ((int (*)(void *))B(0xab31e0))(cd) : 0;
    return base > 0 ? base * (100 + g_pet[k].speed_pct) / 100 : 0;
}
/* overcharge_pet_charge (Colette, Percenter_overcharge 66: "Colette's spirit follows her during her dash, damaging enemies on
 * the way"): no card-value reader in this build asks for type 180 (no 0xb5281c / 0xc427d8 call with w1 #0xb4), the
 * spirit is server code. Here each enemy her dash hits while hypercharged (env.c charge_contact_tick: a charge of the super
 * instance, char +0x6d8 2) takes the spirit's hit of Value % of the dash's hit d right after it. [?] that Value is that
 * percent; the spirit (PercenterPet, Minion_Percenter) is not drawn and hits in the same tick as Colette. */
#define CT_PET_CHARGE 180
int hyper_spirit_damage(uint8_t *ch, int d) {
    if (!ch || d <= 0 || I32(ch, 0x6d8) != 2 || !U8(ch, 0x68)) return 0;   /* +0x68: hypercharged now */
    for (int i = 0; i < NBE_MAXP; i++)
        if (g_card_ch[i] == ch && I32(ch, 8) == g_card_id[i] && g_card[i] && I32(g_card[i], 0x100) == CT_PET_CHARGE) {
            int v = card_value(g_card[i], 1), sp = v > 0 ? d * v / 100 : 0;
            static int nlog; if (sp > 0 && nlog++ < 20) LOG("[hyper] spirit hit: player %d, dash hit %d -> spirit %d (%d%%)\n", i, d, sp, v);
            return sp;
        }
    return 0;
}
/* overcharge_whirlwind (Carl, Whirlwind_overcharge: "Carl gains a flame trail while using his Super. The trail burns on
 * contact, causing damage over time"): libg's own trail code. The character init 0xb59de0 gives the holder of a card of type
 * 285 (0xb5a12c) a component (ctor 0xba0fe0: +8 the character, +0x38 the card, +0x40 the last spawn's tick, -1 = none,
 * +0x44 / +0x48 its spot; vtable 0x120b1e8) whose tick (vtable +0x40 = 0xba1028) libg never calls, as the other
 * components' (superfix_moves.c's R-T, superfix_status.c's Draco). That tick, while the super that started hypercharged
 * runs (skill instance 1: +8 its ActiveTime left > 0 and +0x31 its overcharged latch), spawns the card's AreaEffect (the
 * list card +0x78, WhirlwindOverchargedAreaEffect: a StatusEffect area, WhirlwindUltiTrailFire on enemies, TimeMs 4000,
 * Radius 270; superfix_status.c applies it) at Carl through the shipped helper 0xb35c40 (kind 10) when it has spawned none
 * yet, when the last one's TimeMs has passed, or when Carl is more than Radius x 150 % from the last one (405 u). Here it
 * runs once per tick for a hypercharge holder of that card (from env.c's hyper_tick); without the component (a character
 * made before the card was in the config) the same rule runs here. */
#define CT_WHIRLWIND 285
#define AREA_STATUS 36        /* AreaEffectData +0x118: StatusEffect */
#define TRAIL_TICK 0xba1028   /* the component's tick (vtable 0x120b1e8 +0x40) */
static struct { int id, x, y, tick; } g_trail[NBE_MAXP]; static long g_ntrail, g_ntrail_comp;
void hyper_trail_tick(int i, uint8_t *ch) {
    if (i < 0 || i >= NBE_MAXP || !ch || I32(ch, 0x3c4) <= 0 || !PTR(ch, 0x20)) return;
    uint8_t *card = g_card_ch[i] == ch && I32(ch, 8) == g_card_id[i] ? g_card[i] : NULL;
    if (!card || I32(card, 0x100) != CT_WHIRLWIND) return;
    int nc = I32(ch, 0xa6c); void **c = PTR(ch, 0xa60);
    for (int k = 0; c && k < nc && k < 64; k++)
        if (c[k] && PTR(c[k], 8) == ch && (*(void ***)c[k])[0x40 / 8] == (void *)B(TRAIL_TICK)) {
            ((void (*)(void *))B(TRAIL_TICK))(c[k]);
            if (g_ntrail_comp++ == 0) LOG("[hyper] flame trail: player %d runs libg's trail component\n", i);
            return;
        }
    uint8_t **sk = PTR(ch, 0x458); int n = I32(ch, 0x464);
    if (!sk || n < 2 || !sk[1] || I32(sk[1], 8) < 1 || !(U8(sk[1], 0x31) & 1)) return;
    void **al = PTR(card, 0x78); uint8_t *ad = al && I32(card, 0x84) > 0 ? al[0] : NULL;
    uint8_t *sim = ((void *(*)(void *))B(0xb6a378))(ch);
    if (!ad || !sim || I32(ad, 0x118) != AREA_STATUS) return;
    int x = I32(ch, 0x38), y = I32(ch, 0x3c), now = I32(sim, 0x10);
    long r = I32(ad, 0x12c) * 150 / 100, dx = x - g_trail[i].x, dy = y - g_trail[i].y;   /* 0xba10e4: Radius x 150 % */
    if (g_trail[i].id == I32(ch, 8) && (long)(now - g_trail[i].tick) * 50 < I32(ad, 0x124) && dx * dx + dy * dy <= r * r) return;   /* +0x124 TimeMs */
    void *a = ((void *(*)(void *, void *, int, int, int, int, void *))B(0xb35c40))(ch, ad, x, y, 0, 10, NULL);
    g_trail[i].id = I32(ch, 8); g_trail[i].x = x; g_trail[i].y = y; g_trail[i].tick = now;
    if (a && g_ntrail++ < 10) LOG("[hyper] flame trail: player %d area %d at %d,%d (no component)\n", i, I32(ad, 0x20), x, y);
}
static void hyper_pets_clear(void) { memset(g_pet, 0, sizeof g_pet); memset(g_card, 0, sizeof g_card); memset(g_card_ch, 0, sizeof g_card_ch); memset(g_trail, 0, sizeof g_trail); }
#define SNAP_MAX 1024
static int snap_chars(uint8_t *pr, void **out) {   /* the sim's character objects now */
    void *sim = ((void *(*)(void *))B(0xb6a378))(pr), *h = sim ? PTR(sim, 0) : NULL;
    int n = h ? I32(h, 0xc) : 0, m = 0; void **v = h ? PTR(h, 0) : NULL;
    for (int i = 0; v && i < n && i < 4096 && m < SNAP_MAX; i++) if (v[i] && PTR(v[i], 0) == B(0x1209020)) out[m++] = v[i];
    return m;
}
static void hyper_proj_spawn(uint8_t *pr) {
    void (*spawn)(void *) = (void (*)(void *))B(0xb77344);
    void *p = ((void *(*)(void *))B(0xb6a718))(pr), *cfg = p ? player_cfg(p) : NULL, *card = cfg ? PTR(cfg, 0x28) : NULL;
    uint8_t *cd = p ? player_chardata(p) : NULL, *u = cd ? PTR(cd, 0x268) : NULL, *d = PTR(pr, 0x10);
    int type = card ? I32(card, 0x100) : 0, oc = 0;
    void **ol = u ? PTR(u, 0x68) : NULL; int nol = u ? I32(u, 0x74) : 0;
    for (int k = 0; d && ol && k < nol && k < 8; k++) oc |= ol[k] == d;
    if (!oc || (type != CT_PROJ_SPAWN && type != CT_PET_BUFF)) { spawn(pr); return; }
    static void *before[SNAP_MAX], *after[SNAP_MAX];
    int nb = snap_chars(pr, before);
    spawn(pr);
    uint8_t *pet = type == CT_PROJ_SPAWN ? PTR(cd, 0x250) : NULL; int npet = type == CT_PROJ_SPAWN ? card_value(card, 1) : 0;
    if (pet && npet > 0 && npet <= 10) {
        void *s0 = PTR(pr, 0x1c0); int s1 = I32(pr, 0x3e8);
        PTR(pr, 0x1c0) = pet; I32(pr, 0x3e8) = npet; spawn(pr); PTR(pr, 0x1c0) = s0; I32(pr, 0x3e8) = s1;
        g_npet_spawn += npet;
    }
    int na = snap_chars(pr, after), nnew = 0;
    for (int j = 0; j < na; j++) {
        int k = 0; while (k < nb && before[k] != after[j]) k++;
        if (k < nb) continue;
        uint8_t *c = after[j]; nnew++;
        if (type != CT_PET_BUFF) continue;
        int hp = card_value(card, 1), dm = card_value(card, 2), sp = card_value(card, 3);
        if (hp > 0) { I32(c, 0x3c8) = I32(c, 0x3c8) * (100 + hp) / 100; I32(c, 0x3c4) = I32(c, 0x3c4) * (100 + hp) / 100; }
        int s = (int)(g_npet_buff % PET_MAX);   /* round robin: a battle has far fewer living hypercharged pets than PET_MAX */
        uint8_t *pd = ((void *(*)(void *))B(0xb6a384))(c);
        int death_oc = pd && I32(pd, 0xdc) > 0;   /* DeathOverchargedAreaEffect (Tick's head): Value2 is its minimines, no damage */
        g_pet[s].ch = c; g_pet[s].id = I32(c, 8); g_pet[s].dmg_pct = dm > 0 && !death_oc ? dm : 0; g_pet[s].speed_pct = sp > 0 ? sp : 0;
        { int pi = I32(c, 0x80); g_pet[s].death_oc = death_oc; g_pet[s].x = I32(c, 0x38); g_pet[s].y = I32(c, 0x3c);   /* summoner: the hypercharged brawler of its player */
          g_pet[s].owner_id = pi >= 0 && pi < NBE_MAXP && g_card_ch[pi] ? g_card_id[pi] : 0; }
        int shots = card_value(card, 4); g_pet[s].shots = shots > 1 && shots <= 8 ? shots : 0;   /* Value4: Penny's cannonballs (my_spawn) */
        U8(c, 0x68) = 1; U8(c, 0xaac) = 1; g_npet_buff++;
        static int nlog2; if (nlog2++ < 20) LOG("[hyper] pet %d (data %d): hp %d/%d, damage +%d%%, speed +%d%%%s\n", I32(c, 8), I32(pd, 0x20),
                                                I32(c, 0x3c4), I32(c, 0x3c8), g_pet[s].dmg_pct, g_pet[s].speed_pct, death_oc ? ", overcharged death area" : "");
    }
    static int nlog; if (nlog++ < 20) LOG("[hyper] hypercharged spawn: projectile data %d, card type %d: %d new characters%s\n",
                                          I32(d, 0x20), type, nnew, type == CT_PET_BUFF ? " (pet buff)" : " (+ owner's pet)");
}

/* The hypercharge card's own code. Some hypercharges are a card Type with code of its own (cards.csv MetaType 6 Type, e.g.
 * overcharge_hookdude, and the card's Value..Value6) rather than Overcharged* columns. Neither card-value reader of this
 * build (0xc427d8(player, type, idx), 0xb5281c(character, type, idx)) is asked for overcharge_morningstar (303) or
 * overcharge_griff (295) (no bl / b to them with that w1): their code is compiled out with the server. Re-implemented here at the projectile spawn 0xb78190 (hook_replace; the attack code spawns
 * every projectile of a super through it): when a hypercharged brawler's super spawns its OverchargedProjectiles entry,
 * the extra projectiles of its card are spawned with the same arguments (damage, owner, kind), only the target moved:
 * - overcharge_morningstar (Lumi, "The final explosion ... has an extra blast on both sides"): with the OverchargedProjectiles
 *   entry number Value1 (3, the final blast) two more land beside its target, perpendicular to the throw, Value2 % (100) of
 *   the blast's radius (the projectile's SpawnAreaEffectObject Radius, area data +0x12c) away. [?] the side and the unit. */
#define CT_MORNINGSTAR 303    /* overcharge_morningstar (the card Type enum, the string table 0xaa3000..0xaa8860) */
typedef uint64_t (*spawn16_t)(uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t,
                              uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t);
static spawn16_t o_spawn;
static int g_spawn_rec; static long g_oc_extra;
static int card_val(uint8_t *card, int k) { return ((int (*)(void *, int))B(0xaa9568))(card, k); }
static uint8_t *oc_card(uint8_t *ch) {   /* the card of the hypercharged brawler ch, NULL if ch is not hypercharged */
    for (int i = 0; ch && i < NBE_MAXP; i++) if (g_oc[i] == ch && U8(ch, 0x68) && g_hyp[i].card) return div_data(g_hyp[i].card);
    return NULL;
}
/* The value Value<idx> of the hypercharge card of type `type` while ch is hypercharged, else -1: for the card types whose
 * code no libg call site has and env.c re-implements (overcharge_painter 273: Berry's double scoops, charge_contact_tick) */
int hyper_card_live(void *ch, int type, int idx) {
    uint8_t *card = oc_card(ch);
    return card && ((int (*)(void *))B(0xaa9500))(card) == type ? card_val(card, idx) : -1;
}
static int oc_proj_index(uint8_t *ch, void *d) {   /* d's place in the brawler's super's OverchargedProjectiles, -1 if none */
    uint8_t *cd = ((void *(*)(void *))B(0xb6a384))(ch), *sd = cd ? PTR(cd, 0x268) : NULL;   /* UltimateSkill */
    void **l = sd ? PTR(sd, 0x68) : NULL; int n = sd ? I32(sd, 0x74) : 0;
    for (int k = 0; l && k < n && k < 8; k++) if (l[k] == d) return k;
    return -1;
}
static int proj_area_radius(uint8_t *d) {   /* the Radius of the projectile data's area (a word of d that is an area row) */
    static uint8_t *last_d; static int last_r;
    if (d == last_d) return last_r;
    int r = 0;
    for (int idx = 0, miss = 0; !r && idx < 4000 && miss < 64; idx++) {   /* table 17 = area effects */
        uint8_t *a = div_data(17000000 + idx);
        if (!a) { miss++; continue; }
        miss = 0;
        for (int o = 0x28; o < 0x400; o += 8) if (PTR(d, o) == a) { r = I32(a, 0x12c); break; }
    }
    last_d = d; last_r = r; return r;
}
/* A pet's volley (overcharge_pet_buff_stats Value4, Penny's turret): its OverchargedAutoAttackProjectile (CharacterData +0x68)
 * spawned shots - 1 more times, aimed on a ring around the target at the shot's explosion radius (SpawnAreaEffectObject,
 * 450 u for ArtilleryDudeOverchargedTurretExplosion) so the cannonballs land side by side. [?] the real spread. */
static int pet_volley(uint64_t *a, uint8_t *ch) {
    int k = pet_slot(ch); uint8_t *pd = k >= 0 && g_pet[k].shots > 1 ? ((void *(*)(void *))B(0xb6a384))(ch) : NULL;
    if (!pd || !PTR(pd, 0x68) || (void *)a[4] != PTR(pd, 0x68)) return 0;
    int tx = (int)a[5], ty = (int)a[6], r = proj_area_radius((uint8_t *)a[4]), n = 0;
    if (r <= 0) r = 300;   /* one tile */
    g_spawn_rec = 1;
    for (int j = 1; j < g_pet[k].shots; j++) {
        int deg = 360 * j / (g_pet[k].shots - 1), ox = tx + r * sin1024((deg + 90) % 360) / 1024, oy = ty + r * sin1024(deg) / 1024;
        n += o_spawn(a[0], a[1], a[2], a[3], a[4], (uint64_t)(uint32_t)ox, (uint64_t)(uint32_t)oy, a[7], a[8], a[9], a[10], a[11], a[12],
                     a[13], a[14], a[15]) != 0;
    }
    g_spawn_rec = 0; g_oc_extra += n;
    static int nlog; if (nlog++ < 10) LOG("[hyper] pet %d volley: %d more of projectile %d around %d,%d (r %d)\n", I32(ch, 8), n,
                                          I32((uint8_t *)a[4], 0x20), tx, ty, r);
    return n;
}
static uint64_t my_spawn(uint64_t a0, uint64_t a1, uint64_t a2, uint64_t a3, uint64_t a4, uint64_t a5, uint64_t a6, uint64_t a7,
                         uint64_t a8, uint64_t a9, uint64_t a10, uint64_t a11, uint64_t a12, uint64_t a13, uint64_t a14, uint64_t a15) {
    uint64_t p = o_spawn(a0, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, a11, a12, a13, a14, a15);
    uint8_t *ch = (uint8_t *)a2, *card;
    if (!g_spawn_rec && p) { uint64_t a[16] = {a0, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, a11, a12, a13, a14, a15}; if (pet_volley(a, ch)) return p; }
    if (g_spawn_rec || !p || !(card = oc_card(ch))) return p;
    int type = ((int (*)(void *))B(0xaa9500))(card);
    if (type != CT_MORNINGSTAR) return p;
    int k = oc_proj_index(ch, (void *)a4); if (k < 0) return p;
    int x = (int)a0, y = (int)a1, tx = (int)a5, ty = (int)a6, n = 0, ox[4], oy[4];
    if (x == -1 && y == -1) { x = I32(ch, 0x38); y = I32(ch, 0x3c); }   /* the attack code's "from the owner" (+0x330 = -1) */
    int dx = tx - x, dy = ty - y;
    if (k == card_val(card, 1) - 1) {
        int len = (int)__builtin_sqrt((double)dx * dx + (double)dy * dy), off = proj_area_radius((uint8_t *)a4) * card_val(card, 2) / 100;
        if (len > 0 && off > 0)
            for (int sd = -1; sd <= 1; sd += 2, n++) { ox[n] = tx - sd * dy * off / len; oy[n] = ty + sd * dx * off / len; }
    }
    g_spawn_rec = 1;
    for (int j = 0; j < n; j++)
        if (o_spawn(a0, a1, a2, a3, a4, (uint64_t)(uint32_t)ox[j], (uint64_t)(uint32_t)oy[j], a7, a8, a9, a10, a11, a12, a13, a14, a15)) g_oc_extra++;
    g_spawn_rec = 0;
    static int nlog; if (n && nlog++ < 20) LOG("[hyper] card type %d: %d more of projectile %d (aim %d,%d -> %d,%d)\n", type, n,
                                               I32((uint8_t *)a4, 0x20), dx, dy, n ? ox[0] - x : 0, n ? oy[0] - y : 0);
    return p;
}

/* overcharge_griff (Griff, "banknotes multiply at max range before returning, with the newly created banknotes returning
 * after a delay"): when spawnfix.c sends a hypercharged Griff's note back at max range (reason 1; its ChainBullet
 * AssaultShotgunOverchargedUltiProjectile2, TravelType 11, TravelTypeVariable 20), Value1 (1) more go back with it of the
 * row after that child (AssaultShotgunOverchargedUltiProjectile3: the same with TravelTypeVariable 30; no column names it)
 * -> that data and *n, NULL if none */
#define CT_GRIFF 295          /* overcharge_griff */
void *hyper_chain_extra(void *owner, uint8_t *child, int reason, int *n) {
    uint8_t *card = oc_card(owner), *nx;
    *n = 0;
    if (!card || reason != 1 || !child || ((int (*)(void *))B(0xaa9500))(card) != CT_GRIFF) return NULL;
    uint8_t *lc = PTR(child, 0x58), *ln;   /* +0x58: the skin row's logic row (projectiles_logic, table 125) */
    if (!(nx = div_data(I32(child, 0x20) + 1)) || !lc || !(ln = PTR(nx, 0x58)) || I32(ln, 0x20) != I32(lc, 0x20) + 1 || PTR(nx, 0x180))
        return NULL;   /* the next skin row on the next logic row, with no ChainBullet of its own */
    *n = card_val(card, 1); g_oc_extra += *n;
    static int nlog; if (nlog++ < 10) LOG("[hyper] card type %d: %d more of projectile %d at max range\n", CT_GRIFF, *n, I32(nx, 0x20));
    return nx;
}

/* overcharge_soul_collector (Gus, SoulCollector_overcharge 120 / 200, TID_SOUL_COLLECTOR_OVERCHARGE_DESC "On impact, Gus' Super
 * will drop spirits in all directions that deal damage to enemies and heal teammates!"): no card-value reader asks for type
 * 286 and no logic column names the spirits; the data has them only in rows nothing reads here: the hypercharged ulti
 * projectile's skin CustomObject2 SoulCollectorOverchargedAreaEffect (BulletExplosion, CustomValue 10 of
 * GusOverchargedAreaEffectProjectile, offset 500) and the statuses GusOverchargedDmgProjectile (Damage 900, UltiChargePercent
 * 20) / GusOverchargedHealingProjectile (Healing 340). RE-IMPLEMENTED: when the OverchargedProjectiles entry of a brawler holding
 * this card ends (spawnfix.c on_explode -> hyper_proj_end), that area is spawned at its end point (the sequence of env.c's
 * charge_area; spawnfix.c's area hook fires the 10 spirits), and each spirit, once per character it passes within
 * SPIRIT_HIT_R, gives an enemy the damage status and a teammate (not Gus) the healing one through the status store
 * (superfix_status.c; arguments of env.c's charge-hit status). [?] the server's spirit hit rule; the card's 120 / 200 have no
 * reader and are not used. */
#define CT_SOUL 286
#define SPIRIT_HIT_R 270   /* GusOverchargedAreaEffectProjectile Radius 150 + 120, the CollisionRadius of most brawlers */
static void *data_named(int table, const char *name) {   /* row by name: column 0 (0xcf6a28(row, 0)) == name (String 0xe9779c) */
    for (int idx = 0, miss = 0; idx < 4000 && miss < 64; idx++) {
        uint8_t *d = div_data(table * 1000000 + idx);
        if (!d) { miss++; continue; }
        miss = 0;
        void *s = PTR(d, 8) ? ((void *(*)(void *, int))B(0xcf6a28))(PTR(d, 8), 0) : NULL;
        if (s && (((int (*)(void *, const char *))B(0xe9779c))(s, name) & 1)) return d;
    }
    return NULL;
}
static void *g_soul_area, *g_soul_dmg, *g_soul_heal; static int g_soul_init;
static struct { uint8_t *pr; int start, n; int hit[12]; } g_spirit[32];
static long g_nsoul_area, g_nsoul_hit[2];
static void soul_init(void) {
    if (g_soul_init) return;
    g_soul_init = 1; g_soul_area = data_named(17, "SoulCollectorOverchargedAreaEffect");
    g_soul_dmg = data_named(117, "GusOverchargedDmgProjectile"); g_soul_heal = data_named(117, "GusOverchargedHealingProjectile");
    LOG("[hyper] Gus's spirits: area %p (bullet %p), statuses %p / %p\n", g_soul_area, g_soul_area ? PTR(g_soul_area, 0x78) : NULL,
        g_soul_dmg, g_soul_heal);
}
void hyper_proj_end(uint8_t *pr, int reason) {
    if (!pr || reason == 0 || reason == 5 || I32(pr, 0x90) != 0) return;   /* the ends spawnfix.c also skips; the first end only */
    uint8_t *owner = PTR(pr, 0xe0), *d = PTR(pr, 0x10);
    void *p = owner ? ((void *(*)(void *))B(0xb6a718))(pr) : NULL, *cfg = p ? player_cfg(p) : NULL, *card = cfg ? PTR(cfg, 0x28) : NULL;
    if (!card || I32(card, 0x100) != CT_SOUL || !d || oc_proj_index(owner, d) < 0 || I32(owner, 0x3c4) <= 0) return;
    static uint8_t *last; static int last_start;
    if (pr == last && I32(pr, 0x28) == last_start) return;
    last = pr; last_start = I32(pr, 0x28);
    soul_init(); if (!g_soul_area) return;
    uint8_t *a = ((void *(*)(void *, void *, int, int, int, int, int))B(0xb2aefc))(g_soul_area, owner, I32(pr, 0x38), I32(pr, 0x3c), 0, 2, 0);
    void *w = PTR(owner, 0x20); if (!a || !w) return;
    ((void (*)(void *, void *))B(0xb63198))(w, a); ((void (*)(void *))B(0xb29494))(a); g_nsoul_area++;
    if (g_nsoul_area <= 5) LOG("[hyper] Gus's hypercharged super ended (reason %d) at %d,%d: spirits area %p\n", reason, I32(pr, 0x38), I32(pr, 0x3c), a);
}
void hyper_spirits_tick(void *sim) {   /* after every tick: the spirits' hits */
    if (!g_soul_init || !g_soul_area || !sim || !PTR(sim, 0)) return;
    uint8_t *bullet = PTR(g_soul_area, 0x78), *mgr = PTR(sim, 0); void **arr = PTR(mgr, 0x28); int cnt = I32(mgr, 0x34);
    if (!bullet || !arr || cnt < 1 || cnt > 512) return;
    for (int i = 0; i < cnt; i++) {
        uint8_t *pr = arr[i];
        if (!pr || (uint64_t)((uint8_t *)PTR(pr, 0) - g_libg->base) != 0x1209318 || PTR(pr, 0x10) != bullet) continue;   /* VT_PROJ */
        uint8_t *owner = PTR(pr, 0xe0); if (!owner) continue;
        int k = 0, fr = -1, start = I32(pr, 0x28);
        for (; k < 32 && !(g_spirit[k].pr == pr && g_spirit[k].start == start); k++) if (fr < 0 && !g_spirit[k].pr) fr = k;
        if (k == 32 && I32(pr, 0x90)) continue;   /* finished before it was seen */
        if (k == 32) { if (fr < 0) { memset(g_spirit, 0, sizeof g_spirit); fr = 0; } k = fr; g_spirit[k].pr = pr; g_spirit[k].start = start; g_spirit[k].n = 0; }
        int x = I32(pr, 0x38), y = I32(pr, 0x3c);
        for (int j = 0; j < cnt && g_spirit[k].n < 12; j++) {
            uint8_t *c = arr[j];
            if (!c || c == owner || (uint64_t)((uint8_t *)PTR(c, 0) - g_libg->base) != 0x1209020 || I32(c, 0x3c4) <= 0) continue;   /* VT_CHAR */
            long dx = I32(c, 0x38) - x, dy = I32(c, 0x3c) - y; if (dx * dx + dy * dy > (long)SPIRIT_HIT_R * SPIRIT_HIT_R) continue;
            int id = I32(c, 8), seen = 0; for (int h = 0; h < g_spirit[k].n; h++) seen |= g_spirit[k].hit[h] == id;
            if (seen) continue;
            g_spirit[k].hit[g_spirit[k].n++] = id;
            int ally = I32(c, 0x84) == I32(owner, 0x84); void *st = ally ? g_soul_heal : g_soul_dmg;
            if (!st) continue;
            ((void (*)(void *, void *, int, int, void *, void *, int, int, int, int, int))B(0xb35dd0))(c, st, I32(owner, 0x80),
                I32(owner, 0x84), owner, owner, 2, 0, -1, -1, 0);
            if (g_nsoul_hit[0] + g_nsoul_hit[1] < 10) LOG("[hyper] Gus's spirit hits ch %d (%s)\n", id, ally ? "teammate: heal" : "enemy: damage");
            g_nsoul_hit[ally]++;
        }
        g_spirit[k].pr = I32(pr, 0x90) ? NULL : g_spirit[k].pr;   /* finished: its slot is free again */
    }
}
/* overcharge_axe_juggler (Melodie, AxeJuggler_overcharge 3 / 120: "Melodie adds up to <VALUE1> Hypercharge notes using Catchy
 * Chorus. Hypercharge notes do <VALUE2> damage"): the skill fire's charge start (0xb7c378..0xb7c4a4) asks, for a hypercharged
 * character, the card object of that type through 0xb39704(character, 266) — in this build a bare `mov x0, xzr; ret` (17 call
 * sites, each for one card type; only 0xb7c388 asks 266). With a card it spawns the skill's OverchargedChainProjectile
 * (AxeJugglerOverchargedProjectile2, the orbiting note) through 0xb78c58(character, Value1 notes, data, character, damage
 * from Value2 (0xb565a8 level scale + 0xb4b660 percent), Value2, 10, ...). hyper_axe_card answers that one call site
 * (hook_bl) with the card of the hypercharged brawler that holds it, NULL otherwise. */
static void *hyper_axe_card(uint8_t *ch, int type) {
    if (!ch || type != CT_AXE_JUGGLER || !my_is_oc(ch)) return NULL;
    for (int i = 0; i < NBE_MAXP; i++)
        if (g_card_ch[i] == ch && I32(ch, 8) == g_card_id[i] && g_card[i] && I32(g_card[i], 0x100) == type) {
            static int nlog; if (nlog++ < 10) LOG("[hyper] card object: player %d type %d (%d notes, %d)\n", i, type, card_value(g_card[i], 1), card_value(g_card[i], 2));
            return g_card[i];
        }
    return NULL;
}

/* overcharge_deadMariachi (Poco, DeadMariachi_overcharge 100: "Encore now overheals, adding a decaying shield for the amount
 * overhealed. Shield lasts for <VALUE1> seconds"; RE-IMPLEMENTED: no card-value reader asks for type 238, the code is the
 * server's). Each heal of a projectile of the card holder's super's OverchargedProjectiles (the hit's ally heal 0xb754f4 and
 * superfix.c's own heal both call 0xb41554(ch, source player, amount, 1, projectile data, ...), wrapped here) that goes past
 * max HP gives the healed character a shield of the excess; it shrinks linearly to 0 over Value ticks after the last
 * overheal (a new overheal adds to what is left) and takes damage before HP (hyper_shield_absorb, env.c my_root).
 * Value 100 is ticks: the card text's <VALUE1> for type 238 is Value through the ticks-to-seconds formatter 0xa18e8c
 * (card description 0x90c024: Value / 20) -> "5 seconds". */
#define CT_DEAD_MARIACHI 238
#define OSH_MAX 16
static struct { uint8_t *ch; int id, hp, start, end, flat; } g_osh[OSH_MAX];   /* flat: no decay (Gray's portals) */
static long g_osh_given, g_osh_absorbed;
typedef uint64_t (*heal16_t)(uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t,
                             uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t);
static heal16_t o_heal;
static void osh_clear(void) { memset(g_osh, 0, sizeof g_osh); }
static int sim_now(uint8_t *ch) { uint8_t *sim = ((void *(*)(void *))B(0xb6a378))(ch); return sim ? I32(sim, 0x10) : 0; }
static int osh_left(int k, int now) {
    if (!g_osh[k].ch || now >= g_osh[k].end) return 0;
    if (g_osh[k].flat) return g_osh[k].hp;
    return (int)((long)g_osh[k].hp * (g_osh[k].end - now) / (g_osh[k].end - g_osh[k].start));
}
static uint64_t my_heal(uint64_t a0, uint64_t a1, uint64_t a2, uint64_t a3, uint64_t a4, uint64_t a5, uint64_t a6, uint64_t a7,
                        uint64_t a8, uint64_t a9, uint64_t a10, uint64_t a11, uint64_t a12, uint64_t a13, uint64_t a14, uint64_t a15) {
    uint8_t *ch = (uint8_t *)a0; int before = ch ? I32(ch, 0x3c4) : 0, mx = ch ? I32(ch, 0x3c8) : 0, amt = (int)a2;
    uint64_t r = o_heal(a0, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, a11, a12, a13, a14, a15);
    if (!ch || !a4 || amt <= 0 || before <= 0 || before + amt <= mx) return r;
    for (int i = 0; i < NBE_MAXP; i++) {
        uint8_t *pc = g_card_ch[i];
        if (!pc || !g_card[i] || I32(g_card[i], 0x100) != CT_DEAD_MARIACHI || I32(pc, 8) != g_card_id[i] || oc_proj_index(pc, (void *)a4) < 0) continue;
        int ticks = card_value(g_card[i], 1), now = sim_now(ch), k = 0, fr = -1;
        if (ticks <= 0) break;
        for (; k < OSH_MAX && !(g_osh[k].ch == ch && g_osh[k].id == I32(ch, 8)); k++) if (fr < 0 && osh_left(k, now) <= 0) fr = k;
        if (k == OSH_MAX) { if (fr < 0) break; k = fr; g_osh[k].ch = ch; g_osh[k].id = I32(ch, 8); g_osh[k].hp = 0; g_osh[k].end = now; }
        int left = osh_left(k, now), over = before + amt - mx;
        g_osh[k].hp = left + over; g_osh[k].start = now; g_osh[k].end = now + ticks; g_osh[k].flat = 0; g_osh_given += over;
        static int nlog; if (nlog++ < 10) LOG("[hyper] overheal: ch %d hp %d + %d (max %d) -> shield %d for %d ticks\n", I32(ch, 8), before, amt, mx, g_osh[k].hp, ticks);
        break;
    }
    return r;
}
int hyper_shield_absorb(void *victim, int dmg) {   /* env.c my_root: damage left after the overheal shield */
    uint8_t *ch = victim; if (!ch || dmg <= 0) return dmg;
    for (int k = 0; k < OSH_MAX; k++) if (g_osh[k].ch == ch && g_osh[k].id == I32(ch, 8)) {
        int now = sim_now(ch), left = osh_left(k, now), a = dmg < left ? dmg : left;
        if (a <= 0) return dmg;
        /* what is left shrinks on from here: keep the rate, take a off the amount */
        if (g_osh[k].flat) g_osh[k].hp = left - a; else g_osh[k].hp = (int)((long)(left - a) * (g_osh[k].end - g_osh[k].start) / (g_osh[k].end - now)); g_osh_absorbed += a;
        static int nlog; if (nlog++ < 10) LOG("[hyper] overheal shield of ch %d takes %d of %d (left %d)\n", I32(ch, 8), a, dmg, left - a);
        return dmg - a;
    }
    return dmg;
}
/* overcharge_door_man (Gray, DoorMan_overcharge 2 / 1000 / 300: "Gray opens a new pair of portals that shields him and
 * allies for <VALUE2> when they pass through"; RE-IMPLEMENTED: libg reads only Value (the portal count, 0xb7d1a4), the
 * teleport and the shield are the server's): superfix_moves.c's portals give a character that passes through a hypercharged
 * pair a shield of Value2 that takes damage before HP (hyper_shield_absorb) for Value3 / 5 ticks ([?] Value3 300 read as
 * hundredths of a second: 3 s; the description names no time). A new pass sets it to Value2 again (no stacking). */
#define CT_DOOR_MAN 272
int hyper_portal_shield(void *chp, int player) {   /* -> the shield given (0: none: no such card for that player) */
    uint8_t *ch = chp; if (!ch || player < 0 || player >= NBE_MAXP || !g_card[player] || I32(g_card[player], 0x100) != CT_DOOR_MAN) return 0;
    int hp = card_value(g_card[player], 2), ticks = card_value(g_card[player], 3) / 5, now = sim_now(ch), k = 0, fr = -1;
    if (hp <= 0 || ticks <= 0) return 0;
    for (; k < OSH_MAX && !(g_osh[k].ch == ch && g_osh[k].id == I32(ch, 8)); k++) if (fr < 0 && osh_left(k, now) <= 0) fr = k;
    if (k == OSH_MAX) { if (fr < 0) return 0; k = fr; }
    g_osh[k].ch = ch; g_osh[k].id = I32(ch, 8); g_osh[k].hp = hp; g_osh[k].start = now; g_osh[k].end = now + ticks; g_osh[k].flat = 1;
    g_osh_given += hp;
    static int nlog; if (nlog++ < 10) LOG("[hyper] portal shield: ch %d gets %d for %d ticks (player %d's card)\n", I32(ch, 8), hp, ticks, player);
    return hp;
}
/* Pam (MinigunDude_overcharge, overcharge_pet_change: "It continues to heal Brawlers over their max health by providing them
 * with a decaying shield"; RE-IMPLEMENTED: the area type HotAndOverheals 45 and its OverHeal* columns, AreaEffectData +0x1a4
 * OverHealTicks / +0x1a8 StackOverHeal / +0x1ac MaxOverHeal / +0x1b0 OverHealMultiplier (stores at 0xa96420..0xa964a8), have
 * no reader in the client). superfix.c's summon heal of the hypercharged turret's MinigunOverchargedHealingStationHeal
 * (OverHealTicks 150, StackOverHeal, MaxOverHeal 6000, OverHealMultiplier 80) calls this with what went past max HP: a shield
 * of amount x mult / 100, added to what is left when the data stacks (else the larger), at most max, which shrinks linearly
 * to 0 over OverHealTicks ticks after the last overheal (the same store as Poco's above, taken by hyper_shield_absorb).
 * [?] OverHealTicks read as the decay time in ticks (7.5 s) and MaxOverHeal as an absolute cap (power-11 HP). */
void hyper_overheal(uint8_t *ch, int over, uint8_t *ad) {
    int ticks = ad ? I32(ad, 0x1a4) : 0, mx = ad ? I32(ad, 0x1ac) : 0, amt = ad ? (int)((long)over * I32(ad, 0x1b0) / 100) : 0;
    if (!ch || over <= 0 || ticks <= 0 || amt <= 0) return;
    int now = sim_now(ch), k = 0, fr = -1;
    for (; k < OSH_MAX && !(g_osh[k].ch == ch && g_osh[k].id == I32(ch, 8)); k++) if (fr < 0 && osh_left(k, now) <= 0) fr = k;
    if (k == OSH_MAX) { if (fr < 0) return; k = fr; g_osh[k].ch = ch; g_osh[k].id = I32(ch, 8); g_osh[k].hp = 0; g_osh[k].end = now; }
    int left = osh_left(k, now), hp = U8(ad, 0x1a8) ? left + amt : (amt > left ? amt : left);
    if (mx > 0 && hp > mx) hp = mx;
    g_osh[k].hp = hp; g_osh[k].start = now; g_osh[k].end = now + ticks; g_osh[k].flat = 0; g_osh_given += hp - left;
    static int nlog; if (nlog++ < 10) LOG("[hyper] turret overheal: ch %d +%d over max (x %d %%) -> shield %d for %d ticks\n", I32(ch, 8), over,
                                          I32(ad, 0x1b0), hp, ticks);
}
/* Shade (Ghost_overcharge, overcharge_default: "Shade's attacks during its Hypercharged Super all deal maximum damage, even if
 * the enemy is not hugged in the center"; RE-IMPLEMENTED: libg asks nothing hypercharge-specific there). The melee hit
 * 0xb5ad54..0xb5ae98 (x22 the attacker) gives MeleeDeadCenterBoost (trait 267, GhostDeadCenterBoost 100: damage + 100 %, and
 * trait 133's status) only when 0xd00b6c, the squared distance of the target (x29-32) to the attack's centre line
 * (x29-16 .. x29-24), is below (the trait's radius + w21)^2 (0xb5adcc..0xb5ade0). hook_bl on that call (0xb5adc8, through
 * hyper_dc_thunk, which passes x22): 0 (dead centre) for an attacker hypercharged now that cast its hypercharged super within
 * the last DC_TICKS ticks. */
#define DC_TICKS 120   /* GhostUlti's ActivationSelfStatusEffects GhostIncorporeal DurationTicks: how long his super lasts */
static long g_dc_forced;
int hyper_dead_centre(void *a, void *b, void *c, uint8_t *att) {
    int r = ((int (*)(void *, void *, void *))B(0xd00b6c))(a, b, c);
    if (!att || !is_oc_char(att)) return r;
    for (int i = 0; i < NBE_MAXP; i++) if (g_oc[i] == att && g_hyp[i].super_tick > 0 && sim_now(att) - g_hyp[i].super_tick <= DC_TICKS) {
        if (r > 0) { g_dc_forced++; static int nlog; if (nlog++ < 10) LOG("[hyper] dead centre forced for ch %d (distance^2 %d)\n", I32(att, 8), r); }
        return 0;
    }
    return r;
}
void hyper_dc_thunk(void);
__asm__(".text\n.global hyper_dc_thunk\nhyper_dc_thunk:\n\tmov x3, x22\n\tb hyper_dead_centre\n");
/* Cordelius (Duelist_overcharge, overcharge_default: "Cordelius slows down his targets when sending them to the Shadow Realm";
 * RE-IMPLEMENTED: no slow in the data, the card's Value 6 is the batch value of ten overcharge_default cards). His super's
 * hit (UniqueProperty 13, 0xb750cc..0xb75208) sends him and the target x27 to the Shadow Realm with 0xb58214 (ch, enter,
 * ticks, ...); its last call (0xb751fc) sets the target's realm ticks (w2, from 0xb77e3c). hook_bl on that call
 * (hyper_realm_thunk, which passes the projectile x25): a hypercharged Cordelius's target is slowed REALM_SLOW % for the
 * realm's ticks (hyper_slow_pct, read by superfix_status.c's speed for env.c's mover). */
#define REALM_SLOW 30   /* [?] guess: no number in the data or texts; 30 % is the most common SpeedReducePercent of the slows */
static struct { uint8_t *ch; int id, until, pct; } g_slow[16];
int hyper_slow_pct(uint8_t *ch) {   /* superfix_status.c superfix_status_speed: an extra SpeedReducePercent, 0 = none */
    int t = -1, pct = 0;
    for (int k = 0; ch && k < 16; k++) if (g_slow[k].ch == ch && g_slow[k].id == I32(ch, 8)) {
        if (t < 0) t = sim_now(ch);
        if (t < g_slow[k].until && g_slow[k].pct > pct) pct = g_slow[k].pct;
    }
    return pct;
}
void hyper_realm_enter(uint8_t *target, int enter, int ticks, int a3, int a4, uint8_t *proj) {
    ((void (*)(void *, int, int, int, int))B(0xb58214))(target, enter, ticks, a3, a4);
    uint8_t *owner = proj ? PTR(proj, 0xe0) : NULL;
    if (!owner || !target || PTR(target, 0) != B(0x1209020) || ticks <= 0 || !(my_is_oc(owner) & 1)) return;
    int now = sim_now(target), k = 0, fr = 0;
    for (; k < 16 && !(g_slow[k].ch == target && g_slow[k].id == I32(target, 8)); k++) if (g_slow[k].until < g_slow[fr].until) fr = k;
    if (k == 16) k = fr;   /* a new record over the one that ends first */
    g_slow[k].ch = target; g_slow[k].id = I32(target, 8); g_slow[k].until = now + ticks; g_slow[k].pct = REALM_SLOW;
    static int nlog; if (nlog++ < 10) LOG("[hyper] shadow realm: ch %d slowed %d %% for %d ticks (Cordelius ch %d)\n", I32(target, 8),
                                          REALM_SLOW, ticks, I32(owner, 8));
}
void hyper_realm_thunk(void);
__asm__(".text\n.global hyper_realm_thunk\nhyper_realm_thunk:\n\tmov x5, x25\n\tb hyper_realm_enter\n");
void hyper_install(void) {
    hook_enter(g_libg, 0xb709e4, on_travel);   /* homing projectiles (above) */
    { uint32_t *pc = (uint32_t *)B(0xb5adc8);   /* bl 0xd00b6c (Shade's dead centre, above) */
      if ((*pc & 0xfc000000) == 0x94000000 && (uint8_t *)pc + (((int32_t)(*pc << 6)) >> 4) == B(0xd00b6c)) hook_bl(g_libg, 0xb5adc8, (void *)hyper_dc_thunk);
      else LOG("[hyper] 0xb5adc8: unexpected bytes, Shade's hypercharged dead centre is off\n"); }
    if (*(uint32_t *)B(0xb41554) == 0xd10303ff) o_heal = (heal16_t)hook_replace(g_libg, 0xb41554, (void *)my_heal);   /* sub sp, sp, #0xc0 */
    else LOG("[hyper] heal 0xb41554: unexpected bytes, Poco's overheal shield is off\n");
    if (*(uint32_t *)B(0xb78190) == 0xa9ba7bfd) o_spawn = (spawn16_t)hook_replace(g_libg, 0xb78190, (void *)my_spawn);   /* stp x29, x30, [sp, #-96]! */
    else LOG("[hyper] 0xb78190: unexpected bytes, the hypercharge cards' extra projectiles are off\n");
    uint32_t *f = (uint32_t *)B(0xb35bf0);
    if (f[0] != 0x2a1f03e0 || f[1] != 0xd65f03c0) {   /* mov w0, wzr ; ret */
        LOG("[hyper] isOvercharged 0xb35bf0: unexpected bytes %08x %08x, hypercharged skills off\n", f[0], f[1]); return;
    }
    hook_replace(g_libg, 0xb35bf0, (void *)my_is_oc);
    { uint32_t *pc = (uint32_t *)B(0xb751fc);   /* bl 0xb58214: the target's realm ticks (Cordelius's slow, above) */
      if ((*pc & 0xfc000000) == 0x94000000 && (uint8_t *)pc + (((int32_t)(*pc << 6)) >> 4) == B(0xb58214)) hook_bl(g_libg, 0xb751fc, (void *)hyper_realm_thunk);
      else LOG("[hyper] 0xb751fc: unexpected bytes, Cordelius's hypercharged slow is off\n"); }
    uint32_t *cv = (uint32_t *)B(0xb5281c);
    if (cv[0] == 0x12800000 && cv[1] == 0xd65f03c0) hook_replace(g_libg, 0xb5281c, (void *)my_card_value);   /* mov w0, #-1 ; ret */
    else LOG("[hyper] 0xb5281c: unexpected bytes %08x %08x, hypercharge card values off\n", cv[0], cv[1]);
    uint32_t *ps = (uint32_t *)B(0xb75b24);   /* bl 0xb77344 */
    if ((*ps & 0xfc000000) == 0x94000000 && (uint8_t *)ps + (((int32_t)(*ps << 6)) >> 4) == B(0xb77344)) hook_bl(g_libg, 0xb75b24, (void *)hyper_proj_spawn);
    else LOG("[hyper] 0xb75b24: unexpected bytes, hypercharged pets off\n");
    if (*(uint32_t *)B(0xb4b978) == 0xf9402f29) {   /* ldr x9, [x25, #88] */
        g_hyper_proj_next = (uint64_t)B(0xb4b97c); hook_replace(g_libg, 0xb4b978, (void *)hyper_proj_site);
    } else LOG("[hyper] 0xb4b978: unexpected bytes, AttackPattern 11 keeps the normal projectiles\n");
    uint32_t *ax = (uint32_t *)B(0xb7c388);   /* bl 0xb39704 (Melodie's card, above) */
    if ((*ax & 0xfc000000) == 0x94000000 && (uint8_t *)ax + (((int32_t)(*ax << 6)) >> 4) == B(0xb39704)) hook_bl(g_libg, 0xb7c388, (void *)hyper_axe_card);
    else LOG("[hyper] 0xb7c388: unexpected bytes, Melodie's hypercharge notes off\n");
    static const uint32_t sbl[] = {0xb7eac0, 0xb7eadc, 0xb7eaf0, 0xb7eb04, 0xb7eb1c, 0xb7ec54, 0xb7eda8, 0xb7eef4};
    for (unsigned k = 0; k < sizeof sbl / sizeof *sbl; k++) {
        uint32_t *c = (uint32_t *)B(sbl[k]);   /* mov x0, x21 ; mov w1, wzr ; bl 0xb0ddf8 */
        if (c[-2] != 0xaa1503e0 || c[-1] != 0x2a1f03e1 || (uint8_t *)c + (((int32_t)(c[0] << 6)) >> 4) != B(0xb0ddf8)) {
            LOG("[hyper] 0x%x: unexpected bytes, the normal summon stays\n", sbl[k]); continue;
        }
        hook_bl(g_libg, sbl[k], (void *)hyper_summon_bl);
    }
}

/* The OverchargedUltimateSkill is the brawler's third skill instance (char+0x458[2]); the game's super code uses instance 1.
 * While hypercharged the two are swapped, so every super path (input, charge, the skill's own timers) runs the hypercharged
 * one with the game's own code; swapped back once the hypercharge ended and the hypercharged super is not running. */
static void swap_ulti(uint8_t *ch) {
    uint8_t **sk = PTR(ch, 0x458); uint8_t *t = sk[1]; sk[1] = sk[2]; sk[2] = t;
}
static int has_oc_ulti(uint8_t *ch) {
    uint8_t **sk = ch ? PTR(ch, 0x458) : NULL; int n = ch ? I32(ch, 0x464) : 0;
    return sk && n >= 3 && n <= 16 && sk[1] && sk[2];
}
/* a character change (env_char_changed: Meg's eject and her mech, Bonnie, Moe) builds a new object: a running hypercharge
 * follows the player's new brawler (isOvercharged, char+0x68, the swapped OverchargedUltimateSkill when the new form has
 * one); the old object's swap ends with it */
void hyper_char_changed(uint8_t *old, uint8_t *nc) {
    for (int i = 0; i < NBE_MAXP; i++) {
        if (g_sw[i] == old) g_sw[i] = NULL;
        if (old && g_card_ch[i] == old) { g_card_ch[i] = nc; g_card_id[i] = nc ? I32(nc, 8) : 0; }
        if (!old || g_oc[i] != old) continue;
        g_oc[i] = nc; U8(nc, 0x68) = U8(old, 0x68);
        if (has_oc_ulti(nc)) { swap_ulti(nc); g_sw[i] = nc; }
    }
}
/* the super player i casts now (sd = its SkillData, SKILL_SUPER): counted in hyp_supers / hyp_super_id while hypercharged */
void *hyper_super_data(int i, uint8_t *ch, void *sd) {
    if (i < 0 || i >= NBE_MAXP || !sd || !is_oc_char(ch)) return sd;
    g_hyp[i].supers++; g_hyp[i].super_id = I32(sd, 0x20); g_hyp[i].super_tick = sim_now(ch);
    static int nlog; if (nlog++ < 40) LOG("[hyper] player %d hypercharged super: data %d%s\n", i, I32(sd, 0x20), g_sw[i] == ch ? " (OverchargedUltimateSkill)" : "");
    return sd;
}
/* after every tick: a swapped brawler whose hypercharge is over gets its normal super back once the swapped one is idle
 * (skill instance +0x30 = running; char+0x6d8 2 = a charge of instance 1 in progress) */
void hyper_unswap(int i, uint8_t *ch) {
    if (i < 0 || i >= NBE_MAXP || !g_sw[i] || g_oc[i]) return;
    if (ch != g_sw[i]) { g_sw[i] = NULL; return; }   /* the brawler is gone (a new object): nothing to undo */
    uint8_t **sk = PTR(ch, 0x458);
    if (!has_oc_ulti(ch) || U8(sk[1], 0x30) || I32(ch, 0x6d8) == 2) return;
    swap_ulti(ch); g_sw[i] = NULL;
}

/* RESET response (env.c div_publish), per player: the card the game's config holds and the brawler's buff percents */
void hyper_reset_player(int i, void *p) {
    if (i < 0 || i >= NBE_MAXP) return;
    Hyp *h = &g_hyp[i]; memset(h, 0, sizeof *h);
    void *cfg = p ? player_cfg(p) : NULL, *card = cfg ? PTR(cfg, 0x28) : NULL, *cd = p ? player_chardata(p) : NULL;
    if (!card) return;
    h->card = I32(card, 0x20);
    h->dmg_pct = cd_pct(cd, CD_DAMAGE_PCT); h->speed_pct = cd_pct(cd, CD_SPEED_PCT); h->shield_pct = cd_pct(cd, CD_SHIELD_PCT);
    static int nlog; if (nlog++ < 20) LOG("[hyper] player %d card %d: damage +%d%%, speed +%d%%, shield %d%%\n", i, h->card,
                                          h->dmg_pct, h->speed_pct, h->shield_pct);
}

int hyper_active(void *p) { return p && U8(p, 0xa0); }

/* NbeAction.fire 4 for player i (its brawler ch, alive): libg's activation; -> 1 if the hypercharge is now active and was not */
int hyper_use(int i, void *p, uint8_t *ch) {
    if (i < 0 || i >= NBE_MAXP || !p || !ch || !g_hyp[i].card || U8(p, 0xa0) || I32(p, 0x98) < I32(p, 0x9c)) return 0;
    ((void (*)(void *, void *))B(0xc42584))(p, ch);
    if (!U8(p, 0xa0)) return 0;   /* refused by the game's own checks (e.g. a state that forbids it) */
    g_hyp[i].used++; g_oc[i] = ch; { void *cfg = player_cfg(p); g_card[i] = cfg ? PTR(cfg, 0x28) : NULL; g_card_ch[i] = ch; g_card_id[i] = I32(ch, 8); }
    if (has_oc_ulti(ch) && g_sw[i] != ch) { swap_ulti(ch); g_sw[i] = ch; }
    static int nlog; if (nlog++ < 40) LOG("[hyper] player %d activated (charge %d, drain %d/tick)\n", i, I32(p, 0x98), I32(p, 0xa4));
    return 1;
}

/* after every tick, per player i (ch = its brawler or NULL): drain the charge; -> 1 if the hypercharge ended at this tick */
int hyper_tick_player(int i, void *p, uint8_t *ch, int alive) {
    if (!p || !U8(p, 0xa0)) return 0;
    if (ch && alive) oc_heal_areas(ch);
    int drain = I32(p, 0xa4) > 0 ? I32(p, 0xa4) : DRAIN_DEFAULT, c = I32(p, 0x98) - drain;
    if (c > 0 && alive) { I32(p, 0x98) = c; return 0; }
    I32(p, 0x98) = alive ? 0 : (c > 0 ? c : 0); U8(p, 0xa0) = 0;   /* ended (charge used up, or the brawler died) */
    if (ch) U8(ch, 0x68) = 0;
    if (i >= 0 && i < NBE_MAXP) g_oc[i] = NULL;
    return 1;
}

/* damage through the root 0xb422d0: d > 0 dealt by player ai's brawler to player vi's brawler (-1 = not a player's brawler) */
int hyper_damage(void *pa, int ai, void *pv, int vi, int d) {
    if (d <= 0) return d;
    if (ai >= 0 && ai < NBE_MAXP && hyper_active(pa) && g_hyp[ai].dmg_pct) d = d * (100 + g_hyp[ai].dmg_pct) / 100;
    if (vi >= 0 && vi < NBE_MAXP && hyper_active(pv) && g_hyp[vi].shield_pct) d = d * (100 - g_hyp[vi].shield_pct) / 100;
    return d;
}

/* the move speed (units/s) player i's brawler moves with now, 0 = unchanged (not hypercharged) */
int hyper_speed(int i, void *p, uint8_t *ch) {
    if (i < 0 || i >= NBE_MAXP || !hyper_active(p) || !g_hyp[i].speed_pct || !ch) return 0;
    void *cd = ((void *(*)(void *))B(0xb6a384))(ch);   /* the brawler's CharacterData (what the mover reads its speed from) */
    int base = cd ? ((int (*)(void *))B(0xab31e0))(cd) : 0;
    return base > 0 ? base * (100 + g_hyp[i].speed_pct) / 100 : 0;
}

void hyper_publish(NbeResp *r, void **ps, int np) {   /* every response */
    r->hyp_valid = 1;
    for (int i = 0; i < NBE_MAXP; i++) {
        const Hyp *h = &g_hyp[i]; void *p = i < np ? ps[i] : NULL;
        int on = hyper_active(p), drain = p && I32(p, 0xa4) > 0 ? I32(p, 0xa4) : DRAIN_DEFAULT;
        r->hyp_card[i] = h->card; r->hyp_used[i] = h->used;
        r->hyp_left[i] = on ? (I32(p, 0x98) + drain - 1) / drain : 0;
        r->hyp_damage_pct[i] = h->card ? h->dmg_pct : 0; r->hyp_speed_pct[i] = h->card ? h->speed_pct : 0;
        r->hyp_shield_pct[i] = h->card ? h->shield_pct : 0;
        r->hyp_supers[i] = h->supers; r->hyp_super_id[i] = h->super_id;
    }
}
