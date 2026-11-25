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
 * and a hypercharged brawler's Heal area heals here (oc_heal_areas). Seven brawlers (Jester, Beamer, Twins, Skater, Domain, Dancer,
 * MechaDudeBig) have a separate super instead (characters.csv OverchargedUltimateSkill): the game builds it as the brawler's
 * third skill instance (char+0x458[2], 0xb34560) but what picks it for a super cast is compiled out; here instances 1
 * (the super) and 2 are swapped while hypercharged, so the game's own super code casts it, and swapped back once the
 * hypercharge ended and that super is idle (hyper_unswap). Meg's mech (MechaDudeBig, what MechaDude's super turns into)
 * takes Meg's card. A character change hands a running hypercharge to the new form (hyper_char_changed). NbeResp hyp_supers / hyp_super_id count the supers cast while hypercharged and name the SkillData of
 * the last one (hyper_super_data, from env.c fire_input_now).
 * The visual effects (client side) are whatever the client draws from +0xa0 and the overcharged skill data.
 * Also here: the steering of homing projectiles (on_travel), which Belle's and Hank's hypercharged supers need; it applies
 * to every TravelType 4 projectile, hypercharged or not. NBHOST_HYPER_TRACE=1 logs each libg call site of isOvercharged. */
#include "nbhost.h"
#include "nbenv_proto.h"
#include <string.h>
#include <stdlib.h>

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
    if (n < 128) { cache[n].d = chardata; cache[n].card = found; n++; }
    return found;
}

typedef struct { int card, used, dmg_pct, speed_pct, shield_pct, supers, super_id; } Hyp;
static Hyp g_hyp[NBE_MAXP];
static uint8_t *g_oc[NBE_MAXP];   /* player i's brawler while its hypercharge is active (what isOvercharged answers for) */
static uint8_t *g_sw[NBE_MAXP];   /* player i's brawler whose skill instances 1 / 2 are swapped (OverchargedUltimateSkill) */

static int g_heal_seen[32], g_nheal_seen; static long g_oc_heals;   /* oc_heal_areas: area ids already applied */
static void hyper_heal_clear(void) { memset(g_heal_seen, 0xff, sizeof g_heal_seen); g_nheal_seen = 0; }
static void hyper_pets_clear(void);
void hyper_clear(void) { memset(g_hyp, 0, sizeof g_hyp); memset(g_oc, 0, sizeof g_oc); memset(g_sw, 0, sizeof g_sw); hyper_heal_clear(); hyper_pets_clear(); }

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
static void on_travel(uint64_t *c) {
    uint8_t *pr = (uint8_t *)c[0], *d = pr ? PTR(pr, 0x10) : NULL;
    if (!d || ((int (*)(void *))B(0xb7625c))(pr) == 8) return;
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
 * Radius (+0x12c) once, up to max HP (the hypercharge's overheal shield is not modelled), by the area's damage word +0xe8
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
 * a brawler whose hypercharge is on (Type enum card +0x100, Value<i> 0xaa9568), for the types in CARD_TYPES only: the other
 * types' call sites (overcharge_brock, _barkeep, _sniper, ...) are not checked here and keep the -1 they had. */
#define CT_PROJ_SPAWN 177    /* overcharge_projectile_spawn (the `mov w8, #N` per Type string in the card loader 0xaa3000..) */
#define CT_PET_BUFF 179      /* overcharge_pet_buff_stats */
#define CT_MORE_PETS 274     /* overcharge_more_pets */
static const int CARD_TYPES[] = {CT_MORE_PETS};
static void *g_card[NBE_MAXP];   /* player i's hypercharge card (cfg +0x28), set at hyper_use */
static int card_value(void *card, int idx) { return ((int (*)(void *, int))B(0xaa9568))(card, idx); }
static int my_card_value(uint8_t *ch, int type, int idx) {
    unsigned k = 0; while (k < sizeof CARD_TYPES / sizeof *CARD_TYPES && CARD_TYPES[k] != type) k++;
    if (!ch || k == sizeof CARD_TYPES / sizeof *CARD_TYPES) return -1;
    for (int i = 0; i < NBE_MAXP; i++)
        if (g_oc[i] == ch && U8(ch, 0x68) && g_card[i] && I32(g_card[i], 0x100) == type) {
            int v = card_value(g_card[i], idx);
            static int nlog; if (nlog++ < 20) LOG("[hyper] card value: player %d type %d value%d = %d\n", i, type, idx, v);
            return v;
        }
    return -1;
}

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
 *   / 100 (hyper_pet_speed, env.c rec_move), and isOvercharged answers true for it (char +0x68 = 1), so the game's own
 *   code takes its OverchargedAutoAttackProjectile (Juju's "bigger needles", VoodooOverchargedPetSlowProjectile). */
#define PET_MAX 32
static struct { uint8_t *ch; int id, dmg_pct, speed_pct; } g_pet[PET_MAX];
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
static void hyper_pets_clear(void) { memset(g_pet, 0, sizeof g_pet); memset(g_card, 0, sizeof g_card); }
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
        g_pet[s].ch = c; g_pet[s].id = I32(c, 8); g_pet[s].dmg_pct = dm > 0 ? dm : 0; g_pet[s].speed_pct = sp > 0 ? sp : 0;
        U8(c, 0x68) = 1; g_npet_buff++;
    }
    static int nlog; if (nlog++ < 20) LOG("[hyper] hypercharged spawn: projectile data %d, card type %d: %d new characters%s\n",
                                          I32(d, 0x20), type, nnew, type == CT_PET_BUFF ? " (pet buff)" : " (+ owner's pet)");
}

void hyper_install(void) {
    hook_enter(g_libg, 0xb709e4, on_travel);   /* homing projectiles (above) */
    uint32_t *f = (uint32_t *)B(0xb35bf0);
    if (f[0] != 0x2a1f03e0 || f[1] != 0xd65f03c0) {   /* mov w0, wzr ; ret */
        LOG("[hyper] isOvercharged 0xb35bf0: unexpected bytes %08x %08x, hypercharged skills off\n", f[0], f[1]); return;
    }
    hook_replace(g_libg, 0xb35bf0, (void *)my_is_oc);
    uint32_t *cv = (uint32_t *)B(0xb5281c);
    if (cv[0] == 0x12800000 && cv[1] == 0xd65f03c0) hook_replace(g_libg, 0xb5281c, (void *)my_card_value);   /* mov w0, #-1 ; ret */
    else LOG("[hyper] 0xb5281c: unexpected bytes %08x %08x, hypercharge card values off\n", cv[0], cv[1]);
    uint32_t *ps = (uint32_t *)B(0xb75b24);   /* bl 0xb77344 */
    if ((*ps & 0xfc000000) == 0x94000000 && (uint8_t *)ps + (((int32_t)(*ps << 6)) >> 4) == B(0xb77344)) hook_bl(g_libg, 0xb75b24, (void *)hyper_proj_spawn);
    else LOG("[hyper] 0xb75b24: unexpected bytes, hypercharged pets off\n");
    if (*(uint32_t *)B(0xb4b978) == 0xf9402f29) {   /* ldr x9, [x25, #88] */
        g_hyper_proj_next = (uint64_t)B(0xb4b97c); hook_replace(g_libg, 0xb4b978, (void *)hyper_proj_site);
    } else LOG("[hyper] 0xb4b978: unexpected bytes, AttackPattern 11 keeps the normal projectiles\n");
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
        if (!old || g_oc[i] != old) continue;
        g_oc[i] = nc; U8(nc, 0x68) = U8(old, 0x68);
        if (has_oc_ulti(nc)) { swap_ulti(nc); g_sw[i] = nc; }
    }
}
/* the super player i casts now (sd = its SkillData, SKILL_SUPER): counted in hyp_supers / hyp_super_id while hypercharged */
void *hyper_super_data(int i, uint8_t *ch, void *sd) {
    if (i < 0 || i >= NBE_MAXP || !sd || !is_oc_char(ch)) return sd;
    g_hyp[i].supers++; g_hyp[i].super_id = I32(sd, 0x20);
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
    g_hyp[i].used++; g_oc[i] = ch; { void *cfg = player_cfg(p); g_card[i] = cfg ? PTR(cfg, 0x28) : NULL; }
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
